"""Steps 2 and 3 (initial world, run) and the World / Saved runs tabs of the right column."""

from __future__ import annotations

import html
import os

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from cellab.engine import (
    RunSettings,
    SimulationError,
    WorldError,
    needs_rng,
    simulate,
)
from cellab.model import Automaton
from cellab.storage import DEFAULT_ROOT, StorageError, list_runs, load_run, save_run
from cellab.ui.components import swatch
from cellab.ui.run_logic import (
    DEFAULT_PLAY_DELAY,
    PLAY_DELAYS,
    build_world,
    chart_colors,
    default_world,
    generations_label,
    neighbour_view,
    next_view,
    png_data_uri,
    render,
    run_label,
    space_time,
)

WORLD_KINDS = {"random": "Random", "centre": "Centre cell", "text": "Text"}
HISTORY = {"all": "Every generation", "every": "Every k-th", "final": "Only the last"}
MAX_GUI_GENERATIONS = 10_000


# --- keeping widget values while the widget is hidden ----------------------------------------


def _save(key: str) -> None:
    st.session_state[f"_saved_{key}"] = st.session_state[key]


def keep(key: str, default) -> dict:
    """Widget kwargs that keep the value across reruns where the widget is not drawn."""
    ss = st.session_state
    saved = f"_saved_{key}"
    ss.setdefault(saved, default)
    if ss.get(key) != ss[saved]:
        ss[key] = ss[saved]
    return {"key": key, "on_change": _save, "args": (key,)}


def _reset_world_settings(automaton: Automaton) -> None:
    """A different automaton gets its own default world (e.g. a centre cell for Rule 30)."""
    ss = st.session_state
    for key in [k for k in ss if str(k).startswith("_saved_w_")]:
        del ss[key]
    ss._world_for = automaton.name


def runs_root() -> str:
    return os.environ.get("CELLAB_RUNS_DIR") or str(DEFAULT_ROOT)


# --- step 2: initial world ------------------------------------------------------------------


def world_section(automaton: Automaton) -> tuple[np.ndarray | None, dict]:
    """Draw the initial-world settings; return generation 0 (None if invalid) and the setting."""
    ss = st.session_state
    if ss.get("_world_for") != automaton.name:
        _reset_world_settings(automaton)
    default = default_world(automaton)
    kind = st.segmented_control(
        "How the world starts",
        list(WORLD_KINDS),
        format_func=WORLD_KINDS.get,
        required=True,
        label_visibility="collapsed",
        **keep("w_kind", default["kind"]),
    )
    others = [s for s in automaton.state_names if s != automaton.default_state]
    setting: dict = {"kind": kind}
    if kind == "random":
        shares = default.get("probabilities") or dict.fromkeys(
            others, round(0.3 / max(len(others), 1), 3)
        )
        with st.container(horizontal=True):
            probabilities = {}
            for name in others:
                probabilities[name] = st.number_input(
                    f"Share of {name}",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    format="%.2f",
                    **keep(f"w_p_{name}", float(shares.get(name, 0.0))),
                )
            seed = st.number_input(
                "Seed", min_value=0, step=1, help="Same seed, same world.", **keep("w_seed", 1)
            )
        st.caption(f"The rest of the cells are {automaton.default_state}.")
        setting |= {"probabilities": probabilities, "seed": int(seed)}
    elif kind == "centre":
        names = others or [automaton.default_state]
        if ss.get("_saved_w_centre") not in names:
            ss["_saved_w_centre"] = names[-1]
        state = st.selectbox("State of the centre cell", names, **keep("w_centre", names[-1]))
        setting["state"] = state
    else:
        symbols = ", ".join(f"{s.symbol} {s.name}" for s in automaton.states)
        text = st.text_area(
            "World as text",
            height=150,
            placeholder=". # .\n. . #\n# # #",
            help="One row per line, one symbol per cell; spaces are optional. Smaller than the "
            "grid is fine: it is placed in the centre.",
            **keep("w_text", ""),
        )
        st.caption(f"Symbols: {symbols}.")
        setting["text"] = text
    try:
        return build_world(automaton, setting), setting
    except WorldError as exc:
        st.error(str(exc))
        return None, setting


# --- step 3: run ----------------------------------------------------------------------------


def showing_run(automaton: Automaton | None, setting: dict | None) -> bool:
    """The run is shown only for the automaton and world settings it was made with; after a
    change, the World tab previews the new initial world instead."""
    ss = st.session_state
    return ss.get("run") is not None and ss.get("run_context") == (automaton, setting)


def run_section(automaton: Automaton, world: np.ndarray | None, setting: dict) -> None:
    ss = st.session_state
    ss.current_context = (automaton, setting)
    with st.container(horizontal=True, vertical_alignment="bottom"):
        # no max_value: a browser field over its maximum keeps showing the typed number while
        # Streamlit silently keeps the old one; the limit is explained below instead
        generations = st.number_input(
            "Generations",
            min_value=1,
            step=10,
            **keep("r_generations", 50),
        )
        history = st.segmented_control(
            "Keep",
            list(HISTORY),
            format_func=HISTORY.get,
            required=True,
            help="Which generations are stored. Counts per state are recorded for every "
            "generation either way.",
            **keep("r_history", "all"),
        )
        every = 1
        if history == "every":
            every = st.number_input("k", min_value=1, step=1, **keep("r_every", 10))
    seed = None
    if needs_rng(automaton):
        seed = int(
            st.number_input(
                "Seed for random rules",
                min_value=0,
                step=1,
                help="Same seed, same run.",
                **keep("r_seed", 1),
            )
        )
    settings = RunSettings(history, int(every), seed)
    too_many = int(generations) > MAX_GUI_GENERATIONS
    if too_many:
        st.error(
            f"The GUI computes at most {MAX_GUI_GENERATIONS:,} generations at a time. Use a "
            "smaller number; Continue extends a run as often as you like."
        )
    run = ss.get("run")
    with st.container(horizontal=True):
        if st.button(
            f"Run {generations_label(int(generations))}",
            type="primary",
            disabled=world is None or too_many,
        ):
            try:
                with st.spinner("Running..."):
                    ss.run = simulate(automaton, world, int(generations), settings, setting)
                ss.run_context = (automaton, setting)
                stop_playback()
                show_world_tab()
                ss.view_gen = None  # show the last generation
                ss.run_notice = None
            except SimulationError as exc:
                st.error(str(exc))
        run = ss.get("run")  # may have been replaced by the Run button just above
        can_continue = showing_run(automaton, setting) and run.automaton == automaton
        if can_continue and st.button(
            f"Continue for {generations_label(int(generations))}", disabled=too_many
        ):
            try:
                with st.spinner("Running..."):
                    run.advance(int(generations))
                ss.view_gen = None
                show_world_tab()
            except SimulationError as exc:
                st.error(str(exc))
        if showing_run(automaton, setting) and st.button("Save run"):
            try:
                save_run(ss.run, ss.run.meta.get("folder"), root=runs_root())
                run = ss.run
                label = run_label(run.automaton.name, run.last_generation, run.meta["created"])
                ss.run_notice = f"Saved: {label}. Find it under Saved runs."
            except OSError as exc:
                st.error(f"The run could not be saved: {exc}")
    if ss.get("run_notice"):
        st.success(ss.run_notice)


# --- World tab ------------------------------------------------------------------------------


def _stage_head(name: str, status: str) -> None:
    st.html(
        f'<div class="cl-stage-head"><span class="cl-name">{html.escape(name)}</span>'
        f'<span class="cl-gen">{html.escape(status)}</span></div>'
    )


def _counts_line(automaton: Automaton, counts) -> None:
    """Legend and counts in one line: swatch (the real cell colour), state, number of cells."""
    parts = "".join(
        f"{swatch(s.color)}{html.escape(s.name)}<b>{int(n)}</b>"
        for s, n in zip(automaton.states, counts, strict=True)
    )
    st.html(f'<div class="cl-counts">Cells: {parts}</div>')


def _population_chart(run) -> None:
    """Cells per generation for the non-default states (the default is the large remainder)."""
    a = run.automaton
    table = run.population_table()
    shown = [i for i, s in enumerate(a.states) if s.name != a.default_state] or [0]
    names = [a.states[i].name for i in shown]
    colors = [chart_colors(a)[i] for i in shown]
    data = pd.DataFrame(table[:, shown], columns=names)
    data["Generation"] = range(len(data))
    long = data.melt("Generation", var_name="State", value_name="Cells")
    font = "Atkinson Hyperlegible Next, sans-serif"
    chart = (
        alt.Chart(long)
        .mark_line(strokeWidth=1.75)
        .encode(
            x=alt.X("Generation:Q", axis=alt.Axis(tickMinStep=1, tickCount=10, grid=False)),
            y=alt.Y("Cells:Q", axis=alt.Axis(gridColor="#E6E9F0", tickCount=4)),
            color=alt.Color("State:N", scale=alt.Scale(domain=names, range=colors), legend=None),
            tooltip=["Generation:Q", "State:N", "Cells:Q"],
        )
        .properties(height=170)
        .configure_axis(
            labelFont=font,
            titleFont=font,
            labelColor="#5C6178",
            titleColor="#5C6178",
            domainColor="#D5DAE3",
            tickColor="#D5DAE3",
            titleFontWeight="normal",
        )
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(
        chart,
        width="stretch",
        theme=None,
        alt=f"Number of cells in each state over {run.last_generation} generations",
    )


def _show_grid(automaton: Automaton, grid: np.ndarray, alt: str) -> None:
    image = render(automaton, grid)
    height, width = image.shape[:2]
    st.html(
        f'<img class="cl-grid" src="{png_data_uri(image)}" width="{width}" height="{height}" '
        f'alt="{html.escape(alt)}">'
    )


def show_world_tab() -> None:
    """Switch the right column to the World tab (runs before the tab bar is drawn)."""
    st.session_state.result_tab = "World"


def stop_playback() -> None:
    st.session_state.play_state = "stopped"


def _view_options(run) -> list[int]:
    # random runs: generations that were not stored cannot be recomputed
    if run.is_deterministic:
        return list(range(run.last_generation + 1))
    return run.stored_generations


# Play / Pause / Skip change whether the player's timer runs, which needs a full rerun. They are
# handled from the button's return value with st.rerun() in the script body, not from on_click
# callbacks: calling st.rerun() inside a callback sometimes lost the click in the browser (after
# the delay had been changed).


def _toggle_play() -> None:
    ss = st.session_state
    if ss.play_state == "playing":
        ss.play_state = "paused"
    else:
        options = _view_options(ss.run)
        if ss.view_gen == options[-1]:  # at the end: play again from the start
            ss.view_gen = options[0]
        ss.play_state = "playing"


def _skip_to_end() -> None:
    ss = st.session_state
    ss.view_gen = _view_options(ss.run)[-1]
    ss.play_state = "stopped"


def _step(step: int) -> None:
    ss = st.session_state
    ss.view_gen = neighbour_view(_view_options(ss.run), ss.view_gen, step)


def _on_slider() -> None:
    st.session_state.view_gen = st.session_state.run_view


def _player() -> None:
    """Grid, playback controls and slider; reruns on its own timer while playing."""
    ss = st.session_state
    run = ss.run
    a = run.automaton
    options = _view_options(run)
    if ss.get("view_gen") not in options:
        ss.view_gen = options[-1]
    playing = ss.play_state == "playing"
    if playing:
        ss.view_gen, at_end = next_view(options, ss.view_gen)
        if at_end:
            ss.play_state = "stopped"
            st.rerun()  # stop the timer
    g = ss.view_gen
    last = run.last_generation

    _stage_head(a.name, f"Generation {g} of {last}")
    if a.is_elementary:
        _show_grid(a, space_time(run, g), alt=f"{a.name}, generations 0 to {g}, time downwards")
        st.caption("Each row is one generation; time runs downwards.")
    else:
        _show_grid(a, run.generation(g), alt=f"{a.name} at generation {g}")

    if len(options) > 1:
        with st.container(horizontal=True, vertical_alignment="center"):
            st.button(
                "Previous",
                icon=":material/chevron_left:",
                help="Previous generation",
                key="view_prev",
                on_click=_step,
                args=(-1,),
                disabled=playing or g == options[0],
            )
            if playing:
                # No slider widget while playing: the browser would send back its own, older
                # position with the next click (e.g. Skip) and undo the server's change.
                st.progress(options.index(g) / (len(options) - 1), width="stretch")
            else:
                # always set: a slider that was hidden during playback is drawn anew and would
                # otherwise start at its default position (generation 0) in the browser
                ss.run_view = g
                st.select_slider(
                    "Generation",
                    options,
                    key="run_view",
                    on_change=_on_slider,
                    label_visibility="collapsed",
                )
            st.button(
                "Next",
                icon=":material/chevron_right:",
                icon_position="right",
                help="Next generation",
                key="view_next",
                on_click=_step,
                args=(1,),
                disabled=playing or g == options[-1],
            )
        with st.container(horizontal=True, vertical_alignment="bottom"):
            label = {"playing": "Pause", "paused": "Resume"}.get(ss.play_state, "Play")
            icon = ":material/pause:" if playing else ":material/play_arrow:"
            if st.button(label, icon=icon, key="play_pause"):
                _toggle_play()
                st.rerun()  # full rerun, so the player's timer starts or stops
            if st.button(
                "Skip to the end",
                icon=":material/skip_next:",
                key="skip_end",
                disabled=g == options[-1],
            ):
                _skip_to_end()
                st.rerun()
            st.space("stretch")
            st.segmented_control(
                "Delay",
                PLAY_DELAYS,
                format_func=lambda d: f"{d:g} s",
                required=True,
                disabled=playing,
                help="Time between generations while playing. Change it before playing or "
                "while paused.",
                **keep("play_delay", DEFAULT_PLAY_DELAY),
            )

    _counts_line(a, run.population_table()[g])


def world_tab(
    automaton: Automaton | None, preview: np.ndarray | None, setting: dict | None
) -> None:
    ss = st.session_state
    ss.setdefault("play_state", "stopped")
    if not showing_run(automaton, setting):
        stop_playback()
        if automaton is None or preview is None:
            st.markdown("The world appears here once the automaton and initial world are valid.")
            return
        with st.container(key="stage"):
            if ss.get("run") is None:
                _stage_head(automaton.name, "Initial world, not run yet")
            else:
                _stage_head(automaton.name, "Initial world for the current settings")
            _show_grid(automaton, preview, alt=f"Initial world of {automaton.name}")
            _counts_line(automaton, np.bincount(preview.ravel(), minlength=len(automaton.states)))
        if ss.get("run") is not None:
            st.caption(
                "Run to simulate this world. The previous run comes back if you return to its "
                "settings."
            )
        return

    run = ss.run
    a = run.automaton
    if automaton is not None and a != automaton:
        st.info(
            "This run used a different automaton than the one on the left. Run again to "
            "simulate the current one."
        )
    delay = ss.get("_saved_play_delay", DEFAULT_PLAY_DELAY)
    with st.container(key="stage"):
        st.fragment(_player, run_every=delay if ss.play_state == "playing" else None)()
    _population_chart(run)
    if not run.is_deterministic and run.settings.history != "all":
        st.caption("This automaton has random rules, so only the stored generations can be shown.")


# --- Saved runs tab -------------------------------------------------------------------------


def _open_run(folder: str) -> None:
    ss = st.session_state
    try:
        ss.run = load_run(folder)
        # show it until the automaton or world settings on the left are changed
        ss.run_context = ss.get("current_context")
        stop_playback()
        show_world_tab()
        ss.view_gen = None
        run = ss.run
        label = run_label(run.automaton.name, run.last_generation, run.meta.get("created", ""))
        ss.run_notice = f"Opened: {label}."
    except StorageError as exc:
        ss.run_notice = None
        ss.open_error = str(exc)


def saved_runs_tab() -> None:
    ss = st.session_state
    runs = list_runs(runs_root())
    if not runs:
        st.markdown(f"No saved runs yet. Saved runs are stored in {runs_root()}.")
        return
    labels = {str(r.folder): run_label(r.automaton, r.last_generation, r.created) for r in runs}
    choice = st.selectbox("Saved run", list(labels), format_func=labels.get, key="open_choice")
    st.button("Open run", on_click=_open_run, args=(choice,))
    if ss.get("open_error"):
        st.error(ss.pop("open_error"))
    st.caption("Opening a run shows it in the World tab; you can continue it and save it again.")
