"""The "Build" source: a form that produces the same definition JSON as the other sources.

State handling (see the developing-with-streamlit skill, session state and data editor notes):
- `form` holds the current form values; it is rewritten from the widgets on every run.
- `load_form()` is the only way in: it is called from callbacks (before widgets are drawn) when
  the user opens the builder, and copies the form into the widget keys. The two tables are
  `st.data_editor`s whose input (`form_base`) stays fixed while the user edits; their key changes
  (`form_version`) each time a form is loaded, so they start fresh from the loaded values.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from cellab.model import ValidationResult, validate
from cellab.ui.builder import (
    COMPARISONS,
    RULE_COLUMNS,
    STATE_COLUMNS,
    apply_renames,
    blank_form,
    copy_form,
    definition_from_form,
    renamed_states,
)

# widget key -> form field
FIELDS = {
    "f_name": "name",
    "f_description": "description",
    "f_width": "width",
    "f_height": "height",
    "f_default": "default_state",
    "f_boundary": "boundary",
    "f_fixed": "fixed_state",
    "f_neighborhood": "neighborhood",
    "f_radius": "radius",
    "f_code": "elementary_code",
}
BOUNDARIES = {"wrap": "Wrap around", "fixed": "Fixed state outside"}
NEIGHBOURHOODS = {
    "moore": "8 around (Moore)",
    "von_neumann": "4 around (von Neumann)",
    "elementary": "Left and right (1D)",
}


def init_form_state() -> None:
    ss = st.session_state
    if "form" not in ss:
        ss.form = blank_form()
        ss.form_base = blank_form()
        ss.form_version = 0


def load_form(form: dict) -> None:
    """Show `form` in the builder. Call from a callback, before the widgets are drawn."""
    ss = st.session_state
    ss.form = copy_form(form)
    ss.form_base = copy_form(form)
    ss.form_version = ss.get("form_version", 0) + 1
    for widget, field in FIELDS.items():
        ss[widget] = form[field]


def _clear_form() -> None:
    load_form(blank_form())


def clear_form_control() -> None:
    """ "Clear the form" with a confirmation; resets only the builder."""
    with st.popover("Clear the form", help="Start a new automaton from an empty form."):
        st.markdown(
            "This removes everything in the form. Known automata and the JSON draft are not "
            "affected."
        )
        st.button("Clear the form", type="primary", key="clear_form", on_click=_clear_form)


def _keep_choice(widget: str, options: list[str]) -> None:
    """A select's saved value may disappear (state renamed); fall back to the first option."""
    if options and st.session_state.get(widget) not in options:
        st.session_state[widget] = options[0]


def _states_editor() -> dict[int, dict]:
    """The states table; returns the edited rows by row label (labels of new rows are new)."""
    base = pd.DataFrame(st.session_state.form_base["states"], columns=list(STATE_COLUMNS))
    edited = st.data_editor(
        base.astype("string"),
        key=f"states_{st.session_state.form_version}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        placeholder="",
        column_config={
            "name": st.column_config.TextColumn("Name", required=True),
            "symbol": st.column_config.TextColumn(
                "Symbol", max_chars=1, help="One character, used when typing a world as text."
            ),
            "color": st.column_config.TextColumn(
                "Colour",
                validate=r"^#[0-9a-fA-F]{6}$",
                help="Hex colour like #2E2A5C. Left empty, one is chosen for you.",
            ),
        },
    )
    return edited.to_dict("index")


def _rules_editor(names: list[str]) -> list[dict]:
    base = pd.DataFrame(st.session_state.form_base["rules"], columns=list(RULE_COLUMNS))
    base = base.astype({c: "string" for c in RULE_COLUMNS if c != "probability"})
    base["probability"] = pd.to_numeric(base["probability"], errors="coerce")
    edited = st.data_editor(
        base,
        key=f"rules_{st.session_state.form_version}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        placeholder="",
        column_config={
            "from": st.column_config.SelectboxColumn(
                "Cell in state", options=["any", *names], default="any", width=115
            ),
            # not required: Streamlit would hold a new row back until it is filled in, so the
            # rule would silently not count; the form explains a missing value instead
            "to": st.column_config.SelectboxColumn("Becomes", options=names, width=105),
            "comparison": st.column_config.SelectboxColumn(
                "When it has", options=list(COMPARISONS), default="always", required=True, width=110
            ),
            "value": st.column_config.TextColumn(
                "Number(s)", help="For example 3, or 2, 3 (one of), or 2-4 (between).", width=90
            ),
            "count": st.column_config.SelectboxColumn(
                "Neighbours in state", options=names, width=150
            ),
            "probability": st.column_config.NumberColumn(
                "Probability",
                width=95,
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                help="Leave empty when the rule always applies.",
            ),
        },
    )
    return edited.to_dict("records")


def builder_section() -> tuple[ValidationResult, dict]:
    """Draw the form; return the validation result and the definition data it produced."""
    ss = st.session_state
    if "pending_form" in ss:  # set by a rename on the previous run, loaded before any widget
        load_form(ss.pop("pending_form"))
    elementary = ss.get("f_neighborhood") == "elementary"

    st.text_input("Name", key="f_name")
    st.text_area("Description (optional)", key="f_description", height=68)

    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.number_input("Grid width", min_value=1, max_value=1000, step=1, key="f_width")
        st.number_input(
            "Grid height",
            min_value=1,
            max_value=1000,
            step=1,
            key="f_height",
            disabled=elementary,
            help="One-dimensional automata always use a single row." if elementary else None,
        )

    st.markdown("**States**: one row per cell type. Renaming a state also renames it in the rules.")
    edited_states = _states_editor()
    renames = renamed_states(ss.form_base["states"], edited_states)
    if renames:
        # reload the whole form with the new names (widgets cannot change once drawn)
        ss.pending_form = apply_renames(ss.form, renames) | {"states": list(edited_states.values())}
        st.rerun()
    states = list(edited_states.values())
    names = [
        str(s["name"]).strip() for s in states if not pd.isna(s["name"]) and str(s["name"]).strip()
    ]

    _keep_choice("f_default", names)
    _keep_choice("f_fixed", names)
    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.selectbox(
            "Empty cells are", names, key="f_default", help="The default state of the grid."
        )
        st.segmented_control(
            "Edges", list(BOUNDARIES), format_func=BOUNDARIES.get, required=True, key="f_boundary"
        )
        if ss.f_boundary == "fixed":
            st.selectbox("State outside the grid", names, key="f_fixed")

    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.segmented_control(
            "Neighbours",
            list(NEIGHBOURHOODS),
            format_func=NEIGHBOURHOODS.get,
            required=True,
            key="f_neighborhood",
        )
        if not elementary:
            st.number_input("Radius", min_value=1, max_value=5, step=1, key="f_radius")

    if elementary:
        st.number_input(
            "Rule number",
            min_value=0,
            max_value=255,
            step=1,
            key="f_code",
            help="Wolfram code 0-255: the new state for each left/self/right combination.",
        )
        rules = ss.form["rules"]
    else:
        st.markdown(
            "**Rules**, checked from top to bottom: the first rule that applies decides. "
            "A cell no rule applies to keeps its state."
        )
        rules = _rules_editor(names)

    ss.form = {field: ss[widget] for widget, field in FIELDS.items() if widget in ss}
    ss.form |= {"states": states, "rules": rules}
    for field, value in blank_form().items():
        ss.form.setdefault(field, value)

    data, form_issues = definition_from_form(ss.form)
    result = validate(data)
    # the form already explains these fields in its own words; drop the JSON-worded twin
    explained = {i.path.removeprefix("form.") for i in form_issues}
    rest = [i for i in result.issues if i.path not in explained]
    if any(i.level == "error" for i in form_issues):
        return ValidationResult(None, form_issues + rest), data
    return ValidationResult(result.automaton, form_issues + rest), data  # warnings never block
    return result, data
