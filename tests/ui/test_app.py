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
    app.button[0].click().run()
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


def test_build_option_says_what_to_do_meanwhile(app):
    source(app).set_value("build").run()
    assert "form builder" in app.info[0].value
    assert not app.exception


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
    app.button[0].click().run()  # Edit as JSON
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
