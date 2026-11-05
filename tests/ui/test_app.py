"""GUI tests with Streamlit's AppTest: the app runs headless, widgets are driven from code."""

import json
import logging
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from cellab.presets import preset_ids, preset_path

APP = Path(__file__).resolve().parents[2] / "src" / "cellab" / "ui" / "app.py"


@pytest.fixture
def app():
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    assert not at.exception
    return at


def source(at):
    return at.get("button_group")[0]


def texts(at):
    """All visible text: markdown, html, subheaders, alerts, captions."""
    parts = [m.value for m in at.markdown] + [h.value for h in at.get("html")]
    parts += [s.value for s in at.subheader] + [e.value for e in at.error]
    parts += [w.value for w in at.warning] + [i.value for i in at.info]
    parts += [c.value for c in at.caption]
    return "\n".join(parts)


def button(at, label):
    return next(b for b in at.button if b.label == label)


def use_json(at, text):
    source(at).set_value("json").run()
    at.text_area(key="json_text").input(text).run()
    assert not at.exception
    return at


def test_starts_with_game_of_life(app):
    assert source(app).value == "preset"
    assert app.selectbox(key="preset_id").value == "game-of-life"
    shown = texts(app)
    assert "Game of Life" in shown
    assert "fewer than 2 or more than 3 alive neighbours" in shown
    assert "40 x 30, edges wrap around" in shown
    assert not app.error


def test_steps_are_shown_in_order(app):
    headings = [h.value for h in app.get("html") if h.value.startswith('<h3 class="cl-step')]
    for number, title, heading in zip(
        (1, 2, 3), ("Automaton", "Initial world", "Run"), headings, strict=True
    ):
        assert f">{number}</span>{title}</h3>" in heading


@pytest.mark.parametrize("preset_id", preset_ids())
def test_every_known_automaton_is_shown_without_errors(app, preset_id):
    app.selectbox(key="preset_id").set_value(preset_id).run()
    name = json.loads(preset_path(preset_id).read_text(encoding="utf-8"))["name"]
    assert name in [s.value for s in app.subheader]
    assert not app.error and not app.exception


def test_edit_as_json_copies_the_preset(app):
    app.selectbox(key="preset_id").set_value("rule-30").run()
    button(app, "Edit as JSON").click().run()
    assert source(app).value == "json"
    assert json.loads(app.text_area(key="json_text").value)["name"] == "Rule 30"
    assert "Elementary rule 30" in texts(app)


def test_switching_to_json_prefills_the_current_preset(app):
    app.selectbox(key="preset_id").set_value("forest-fire").run()
    source(app).set_value("json").run()
    assert json.loads(app.text_area(key="json_text").value)["name"] == "Forest Fire"


def test_invalid_json_is_explained(app):
    use_json(app, '{"name": "x", ')
    assert "This is not valid JSON (line 1" in app.error[0].value
    assert "appears here once it has no errors" in texts(app)


def test_errors_point_to_the_field(app):
    data = json.loads(preset_path("forest-fire").read_text(encoding="utf-8"))
    data["rules"][0]["to"] = "burning"
    data["grid"]["height"] = 0
    use_json(app, json.dumps(data))
    error = app.error[0].value
    assert "`rules[0].to` Rule 1 uses the state 'burning'" in error
    assert "`grid.height`" in error
    assert not app.get("download_button")


def test_warnings_do_not_block(app):
    data = json.loads(preset_path("game-of-life").read_text(encoding="utf-8"))
    data["rules"].append({"from": "dead", "to": "dead"})
    use_json(app, json.dumps(data))
    assert not app.error
    assert "Rule 3 changes 'dead' into itself" in app.warning[0].value
    assert "Game of Life" in [s.value for s in app.subheader]


def test_valid_json_can_be_downloaded(app):
    data = json.loads(preset_path("brians-brain").read_text(encoding="utf-8"))
    data["name"] = "My Brain"
    use_json(app, json.dumps(data))
    assert "My Brain" in [s.value for s in app.subheader]
    assert len(app.get("download_button")) == 1
    code = app.code[0].value
    assert json.loads(code)["name"] == "My Brain"


def test_empty_json_gives_directions(app):
    use_json(app, "   ")
    assert "No definition yet" in texts(app)
    assert not app.error


def test_build_starts_from_a_blank_form(app):
    source(app).set_value("build").run()
    assert not app.exception
    assert app.text_input(key="f_name").value == "My automaton"
    assert "There are no rules" in app.warning[0].value


# --- state handling (regressions found when running the app) --------------------------------


@pytest.fixture
def streamlit_warnings():
    """Warnings Streamlit logs about widget state (e.g. value set twice)."""
    records = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("streamlit.elements.lib.policies")
    handler = Collect(level=logging.WARNING)
    logger.addHandler(handler)
    yield records
    logger.removeHandler(handler)


def test_interactions_do_not_trigger_state_warnings(app, streamlit_warnings):
    app.selectbox(key="preset_id").set_value("rule-30").run()
    button(app, "Edit as JSON").click().run()
    source(app).set_value("preset").run()
    source(app).set_value("build").run()
    source(app).set_value("json").run()
    assert not app.exception
    assert streamlit_warnings == []


def test_json_edits_survive_looking_at_a_known_automaton(app):
    use_json(app, '{"name": "draft in progress"')
    source(app).set_value("preset").run()
    source(app).set_value("json").run()
    assert app.text_area(key="json_text").value == '{"name": "draft in progress"'


def test_chosen_known_automaton_survives_switching_away(app):
    app.selectbox(key="preset_id").set_value("forest-fire").run()
    source(app).set_value("build").run()
    source(app).set_value("preset").run()
    assert app.selectbox(key="preset_id").value == "forest-fire"
    assert "Forest Fire" in [s.value for s in app.subheader]


# --- form builder ---------------------------------------------------------------------------


def group(at, key):
    return next(b for b in at.get("button_group") if b.key == key)


def open_in_form(at, preset_id):
    at.selectbox(key="preset_id").set_value(preset_id).run()
    button(at, "Edit in the form").click().run()
    assert source(at).value == "build"
    return at


def test_known_automaton_opens_in_the_form(app):
    open_in_form(app, "forest-fire")
    assert app.text_input(key="f_name").value == "Forest Fire"
    assert group(app, "f_boundary").value == "fixed"
    assert app.selectbox(key="f_fixed").value == "empty"
    assert "Forest Fire" in [s.value for s in app.subheader]
    assert not app.error


def test_form_changes_show_in_the_summary(app):
    open_in_form(app, "game-of-life")
    app.text_input(key="f_name").input("Small Life").run()
    app.number_input(key="f_width").set_value(12).run()
    group(app, "f_neighborhood").set_value("von_neumann").run()
    shown = texts(app)
    assert "Small Life" in [s.value for s in app.subheader]
    assert "12 x 30, edges wrap around" in shown
    assert "the 4 cells above, below, left and right" in shown


def test_elementary_neighbourhood_asks_for_a_rule_number(app):
    source(app).set_value("build").run()
    group(app, "f_neighborhood").set_value("elementary").run()
    app.number_input(key="f_code").set_value(90).run()
    assert app.number_input(key="f_height").disabled
    shown = texts(app)
    assert "Elementary rule 90" in shown and "81" not in shown
    assert not app.error


def test_form_edits_survive_switching_away(app):
    source(app).set_value("build").run()
    app.text_input(key="f_name").input("Kept").run()
    source(app).set_value("preset").run()
    source(app).set_value("build").run()
    assert app.text_input(key="f_name").value == "Kept"


def test_form_to_json_and_back(app):
    open_in_form(app, "brians-brain")
    app.text_input(key="f_name").input("Brain v2").run()
    button(app, "Edit as JSON").click().run()
    assert source(app).value == "json"
    assert json.loads(app.text_area(key="json_text").value)["name"] == "Brain v2"
    button(app, "Edit in the form").click().run()
    assert source(app).value == "build"
    assert app.text_input(key="f_name").value == "Brain v2"


def test_json_the_form_cannot_show_keeps_the_button_disabled(app):
    data = json.loads(preset_path("game-of-life").read_text(encoding="utf-8"))
    data["rules"][1]["when"] = {"all": [{"count": "alive", "eq": 3}, {"count": "dead", "ge": 1}]}
    use_json(app, json.dumps(data))
    edit = button(app, "Edit in the form")
    assert edit.disabled
    assert "combines several conditions" in edit.help


def test_builder_flows_do_not_trigger_state_warnings(app, streamlit_warnings):
    open_in_form(app, "rule-30")
    group(app, "f_neighborhood").set_value("moore").run()
    group(app, "f_boundary").set_value("wrap").run()
    source(app).set_value("json").run()
    source(app).set_value("build").run()
    assert not app.exception
    assert streamlit_warnings == []


def test_clear_the_form_resets_only_the_form(app):
    use_json(app, '{"name": "json draft"')
    source(app).set_value("preset").run()
    open_in_form(app, "forest-fire")
    app.text_input(key="f_name").input("To be cleared").run()
    next(b for b in app.button if b.key == "clear_form").click().run()
    assert app.text_input(key="f_name").value == "My automaton"
    assert group(app, "f_boundary").value == "wrap"
    assert "My automaton" in [s.value for s in app.subheader]
    assert "There are no rules" in app.warning[0].value
    # the other sources keep their own state
    source(app).set_value("preset").run()
    assert app.selectbox(key="preset_id").value == "forest-fire"
    source(app).set_value("json").run()
    assert app.text_area(key="json_text").value == '{"name": "json draft"'


# --- initial world, run, viewer, saved runs -------------------------------------------------


def run_button(at):
    return next(b for b in at.button if b.label.startswith("Run "))


def headline(at):
    """The stage header, as "**Name**: generation g of n." (the format the tests compare with)."""
    head = next(h.value for h in at.get("html") if "cl-stage-head" in h.value)
    name = re.search(r'cl-name">([^<]*)<', head).group(1).replace("&#x27;", "'")
    status = re.search(r'cl-gen">([^<]*)<', head).group(1)
    return f"**{name}**: {status[0].lower()}{status[1:]}."


NOISY = {
    "name": "Noisy",
    "grid": {"width": 12, "height": 10},
    "states": [
        {"name": "off", "symbol": ".", "color": "#F3F5F8"},
        {"name": "on", "symbol": "#", "color": "#2E2A5C"},
    ],
    "default_state": "off",
    "rules": [{"from": "off", "to": "on", "probability": 0.1}, {"from": "on", "to": "off"}],
}


def test_world_tab_previews_the_initial_world(app):
    assert app.tabs[0].label == "World"
    assert headline(app) == "**Game of Life**: initial world, not run yet."
    assert app.session_state["run"] is None if "run" in app.session_state else True


def test_run_and_browse_generations(app):
    assert run_button(app).label == "Run 50 generations"
    run_button(app).click().run()
    assert not app.exception
    assert app.session_state["run"].last_generation == 50
    assert headline(app) == "**Game of Life**: generation 50 of 50."
    app.select_slider(key="run_view").set_value(10).run()
    assert headline(app) == "**Game of Life**: generation 10 of 50."
    assert "Cells: " in texts(app) and "dead<b>" in texts(app)


def test_continue_extends_the_run(app):
    run_button(app).click().run()
    button(app, "Continue for 50 generations").click().run()
    assert app.session_state["run"].last_generation == 100
    assert headline(app) == "**Game of Life**: generation 100 of 100."


def test_save_and_open_a_run(app, tmp_path, monkeypatch):
    monkeypatch.setenv("CELLAB_RUNS_DIR", str(tmp_path))
    app.number_input(key="r_generations").set_value(12).run()
    run_button(app).click().run()
    button(app, "Save run").click().run()
    assert "Saved as" in app.success[0].value
    assert len(list(tmp_path.iterdir())) == 1
    run_button(app).click().run()  # a new run replaces the shown one
    button(app, "Open run").click().run()
    assert not app.exception
    assert app.session_state["run"].last_generation == 12
    assert "Opened" in app.success[0].value


def test_one_dimensional_automata_start_from_a_centre_cell(app):
    app.selectbox(key="preset_id").set_value("rule-30").run()
    assert group(app, "w_kind").value == "centre"
    run_button(app).click().run()
    assert headline(app) == "**Rule 30**: generation 50 of 50."
    assert "time runs downwards" in texts(app)


def test_text_world_errors_disable_running(app):
    group(app, "w_kind").set_value("text").run()
    app.text_area(key="w_text").input("#x#").run()
    assert "unknown symbols x" in app.error[0].value
    assert run_button(app).disabled


def test_random_rules_ask_for_a_seed_and_show_only_stored_generations(app):
    use_json(app, json.dumps(NOISY))
    assert app.number_input(key="r_seed").value == 1
    group(app, "r_history").set_value("final").run()
    run_button(app).click().run()
    assert not app.exception
    assert app.select_slider(key="run_view").options == ["0", "50"]
    assert "only the stored generations can be shown" in texts(app)


def test_changing_the_automaton_previews_its_world_and_keeps_the_run(app):
    run_button(app).click().run()
    app.selectbox(key="preset_id").set_value("brians-brain").run()
    assert headline(app) == "**Brian's Brain**: initial world for the current settings."
    assert not [b for b in app.button if b.label in ("Save run", "Continue for 50 generations")]
    app.selectbox(key="preset_id").set_value("game-of-life").run()
    assert headline(app) == "**Game of Life**: generation 50 of 50."


def test_changing_the_world_settings_shows_the_new_initial_world(app):
    run_button(app).click().run()
    app.number_input(key="w_seed").set_value(7).run()
    assert "initial world for the current settings" in headline(app)
    app.number_input(key="w_seed").set_value(1).run()  # back to the settings of the run
    assert headline(app) == "**Game of Life**: generation 50 of 50."


def by_key(at, key):
    return next(b for b in at.button if b.key == key)


def test_arrow_buttons_step_through_generations(app):
    run_button(app).click().run()
    assert by_key(app, "view_next").disabled  # already at the last generation
    by_key(app, "view_prev").click().run()
    by_key(app, "view_prev").click().run()
    assert headline(app) == "**Game of Life**: generation 48 of 50."
    by_key(app, "view_next").click().run()
    assert headline(app) == "**Game of Life**: generation 49 of 50."


def test_play_pause_resume_and_skip(app):
    run_button(app).click().run()
    app.select_slider(key="run_view").set_value(10).run()
    by_key(app, "play_pause").click().run()
    assert app.session_state["play_state"] == "playing"
    assert by_key(app, "play_pause").label == "Pause"
    assert group(app, "play_delay").disabled  # speed fixed while playing
    # while playing the slider is replaced by a progress bar (see _player)
    assert not [s for s in app.select_slider if s.key == "run_view"]
    by_key(app, "play_pause").click().run()
    assert app.session_state["play_state"] == "paused"
    assert by_key(app, "play_pause").label == "Resume"
    assert not group(app, "play_delay").disabled  # editable while paused
    group(app, "play_delay").set_value(0.5).run()
    by_key(app, "skip_end").click().run()
    assert headline(app) == "**Game of Life**: generation 50 of 50."
    assert app.session_state["play_state"] == "stopped"
    assert by_key(app, "play_pause").label == "Play"


def test_play_at_the_end_starts_again_from_the_beginning(app):
    run_button(app).click().run()
    by_key(app, "play_pause").click().run()
    # the first frame after pressing Play already shows generation 1
    assert headline(app) == "**Game of Life**: generation 1 of 50."


def test_run_flows_do_not_trigger_state_warnings(app, streamlit_warnings, tmp_path, monkeypatch):
    monkeypatch.setenv("CELLAB_RUNS_DIR", str(tmp_path))
    group(app, "w_kind").set_value("centre").run()
    group(app, "r_history").set_value("every").run()
    run_button(app).click().run()
    app.select_slider(key="run_view").set_value(20).run()
    source(app).set_value("json").run()
    source(app).set_value("preset").run()
    assert group(app, "w_kind").value == "centre"  # kept while the step was redrawn
    assert not app.exception
    assert streamlit_warnings == []


def test_opening_a_saved_run_shows_the_world_tab(app, tmp_path, monkeypatch, streamlit_warnings):
    monkeypatch.setenv("CELLAB_RUNS_DIR", str(tmp_path))
    run_button(app).click().run()
    button(app, "Save run").click().run()
    app.session_state["result_tab"] = "Saved runs"  # the user opens the Saved runs tab
    app.run()
    button(app, "Open run").click().run()
    assert app.session_state["result_tab"] == "World"
    assert not app.exception and streamlit_warnings == []


def test_running_from_another_tab_shows_the_world_tab(app):
    app.session_state["result_tab"] = "Definition"
    app.run()
    run_button(app).click().run()
    assert app.session_state["result_tab"] == "World"


def test_skip_while_playing_goes_to_the_end(app):
    """Regression: Skip during playback used to stop at the current generation (in the browser
    the old slider position was sent back with the click). While playing there is no slider."""
    run_button(app).click().run()
    app.select_slider(key="run_view").set_value(5).run()
    by_key(app, "play_pause").click().run()
    assert app.session_state["play_state"] == "playing"
    by_key(app, "skip_end").click().run()
    assert headline(app) == "**Game of Life**: generation 50 of 50."
    assert app.select_slider(key="run_view").value == 50
    assert by_key(app, "skip_end").disabled
