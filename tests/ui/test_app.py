"""GUI tests with Streamlit's AppTest: the app runs headless, widgets are driven from code."""

import json
import logging
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
    """All visible text: markdown, html, subheaders, alerts."""
    parts = [m.value for m in at.markdown] + [h.value for h in at.get("html")]
    parts += [s.value for s in at.subheader] + [e.value for e in at.error]
    parts += [w.value for w in at.warning] + [i.value for i in at.info]
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
    headings = [h.value for h in app.get("html") if h.value.startswith('<h3 class="cl-step"')]
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
