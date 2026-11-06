import json
import math

import pytest

from cellab.model import validate
from cellab.model.definition import COUNT_OPS
from cellab.presets import preset_ids, preset_path
from cellab.ui.builder import (
    COMPARISONS,
    OP_TO_COMPARISON,
    blank_form,
    definition_from_form,
    form_from_definition,
)


def preset_data(preset_id):
    return json.loads(preset_path(preset_id).read_text(encoding="utf-8"))


def build(form):
    data, issues = definition_from_form(form)
    return validate(data), issues


def rule_row(**values):
    row = dict.fromkeys(("from", "to", "comparison", "value", "count", "probability"))
    return row | values


@pytest.mark.parametrize("preset_id", preset_ids())
def test_every_preset_survives_form_round_trip(preset_id):
    original = validate(preset_data(preset_id)).automaton
    form, reason = form_from_definition(preset_data(preset_id))
    assert reason is None
    result, issues = build(form)
    assert issues == []
    assert result.ok, result.issues
    assert result.automaton == original


def test_every_comparison_has_a_label():
    assert set(OP_TO_COMPARISON) == set(COUNT_OPS)
    assert list(COMPARISONS)[0] == "always"


def test_blank_form_is_valid_but_warns_about_missing_rules():
    result, issues = build(blank_form())
    assert issues == [] and result.ok
    assert "no rules" in result.warnings[0].message


def test_game_of_life_typed_into_the_form():
    form = blank_form() | {"name": "Life by hand"}
    form["rules"] = [
        rule_row(**{"from": "alive"}, to="dead", comparison="none of", value="2, 3", count="alive"),
        rule_row(**{"from": "dead"}, to="alive", comparison="exactly", value="3", count="alive"),
    ]
    result, issues = build(form)
    assert issues == [] and result.ok
    life = validate(preset_data("game-of-life")).automaton
    assert result.automaton.rules == life.rules


@pytest.mark.parametrize(
    "comparison,value,expected",
    [
        ("exactly", "3", {"count": "alive", "eq": 3}),
        ("at least", " 2 ", {"count": "alive", "ge": 2}),
        ("one of", "2,3", {"count": "alive", "in": [2, 3]}),
        ("none of", "2 and 3", {"count": "alive", "not_in": [2, 3]}),
        ("between", "2-4", {"count": "alive", "between": [2, 4]}),
        ("between", "2 to 4", {"count": "alive", "between": [2, 4]}),
    ],
)
def test_numbers_are_read_from_free_text(comparison, value, expected):
    form = blank_form()
    form["rules"] = [
        rule_row(**{"from": "dead"}, to="alive", comparison=comparison, value=value, count="alive")
    ]
    data, issues = definition_from_form(form)
    assert issues == []
    assert data["rules"][0]["when"] == expected


@pytest.mark.parametrize(
    "row,path,message",
    [
        (
            rule_row(
                **{"from": "dead"}, to="alive", comparison="at least", value="", count="alive"
            ),
            "form.rules[0].value",
            "Rule 1: 'at least' needs one whole number, e.g. 3.",
        ),
        (
            rule_row(
                **{"from": "dead"}, to="alive", comparison="exactly", value="2 3", count="alive"
            ),
            "form.rules[0].value",
            "needs one whole number",
        ),
        (
            rule_row(
                **{"from": "dead"}, to="alive", comparison="between", value="4", count="alive"
            ),
            "form.rules[0].value",
            "needs two numbers, e.g. 2-4",
        ),
        (
            rule_row(**{"from": "dead"}, to="alive", comparison="exactly", value="3"),
            "form.rules[0].count",
            "choose which neighbours to count",
        ),
    ],
    ids=["no number", "two numbers", "one number for between", "no counted state"],
)
def test_form_problems_point_to_the_row(row, path, message):
    form = blank_form()
    form["rules"] = [row]
    _, issues = definition_from_form(form)
    assert [i.path for i in issues] == [path]
    assert message in issues[0].message


def test_missing_target_is_explained_by_the_form():
    form = blank_form()
    form["rules"] = [rule_row(**{"from": "dead"})]
    _, issues = definition_from_form(form)
    assert [(i.path, i.message) for i in issues] == [
        ("form.rules[0].to", "Rule 1: choose what the cell becomes.")
    ]


def test_empty_rows_are_ignored_including_pandas_nan():
    form = blank_form()
    form["states"].append({"name": None, "symbol": float("nan"), "color": ""})
    form["rules"] = [
        rule_row(),
        rule_row(comparison="always", probability=math.nan),
        rule_row(**{"from": "dead"}, to="alive", comparison="exactly", value="3", count="alive"),
    ]
    data, issues = definition_from_form(form)
    assert issues == []
    assert len(data["states"]) == 2
    assert len(data["rules"]) == 1 and "probability" not in data["rules"][0]


def test_any_source_and_probability():
    form = blank_form()
    form["rules"] = [rule_row(to="dead", probability=0.25)]
    data, _ = definition_from_form(form)
    assert data["rules"] == [{"from": "any", "to": "dead", "probability": 0.25}]


def test_new_states_get_a_symbol_and_colour():
    form = blank_form()
    form["states"].append({"name": "fire", "symbol": "", "color": None})
    form["states"].append({"name": "fog", "symbol": None, "color": None})
    data, _ = definition_from_form(form)
    fire, fog = data["states"][2:]
    assert fire["symbol"] == "f" and fog["symbol"] == "*"  # "f" taken, next free symbol
    assert fire["color"].startswith("#") and fog["color"].startswith("#")
    assert validate(data).ok


def test_elementary_forces_one_row_and_uses_the_rule_number():
    form = blank_form() | {"neighborhood": "elementary", "elementary_code": 90, "height": 30}
    form["rules"] = [rule_row(**{"from": "dead"}, to="alive")]  # ignored in elementary mode
    result, issues = build(form)
    assert issues == [] and result.ok
    assert result.automaton.grid.height == 1
    assert result.automaton.rules[0].code == 90


def test_fixed_boundary():
    form = blank_form() | {"boundary": "fixed", "fixed_state": "alive"}
    data, _ = definition_from_form(form)
    assert data["grid"]["boundary"] == {"fixed": "alive"}


def test_unknown_default_state_falls_back_to_the_first_state():
    form = blank_form() | {"default_state": "removed"}
    data, _ = definition_from_form(form)
    assert data["default_state"] == "dead"


@pytest.mark.parametrize(
    "rule,reason",
    [
        (
            {"from": "dead", "to": "alive", "when": {"all": [{"count": "alive", "eq": 3}]}},
            "combines several conditions",
        ),
        ({"from": ["dead", "alive"], "to": "alive"}, "several states"),
        (
            {"from": "dead", "to": "alive", "when": {"count": ["dead", "alive"], "ge": 1}},
            "counts several states",
        ),
    ],
)
def test_definitions_the_form_cannot_show(rule, reason):
    data = preset_data("game-of-life")
    data["rules"].append(rule)
    form, why = form_from_definition(data)
    assert form is None and reason in why


# --- renaming states ------------------------------------------------------------------------


def test_renamed_states_are_detected_by_row():
    from cellab.ui.builder import renamed_states

    before = [{"name": "off"}, {"name": "firing"}, {"name": "dying"}]
    after = {0: {"name": "off"}, 2: {"name": "decay"}, 5: {"name": "new"}}  # row 1 deleted
    assert renamed_states(before, after) == {"dying": "decay"}
    assert renamed_states(before, {1: {"name": ""}}) == {}  # cleared, not renamed


def test_renames_reach_rules_default_and_boundary():
    from cellab.ui.builder import apply_renames

    form, _ = form_from_definition(preset_data("brians-brain"))
    form |= {"boundary": "fixed", "fixed_state": "off"}
    renamed = apply_renames(form, {"dying": "decay", "off": "rest"})
    assert renamed["default_state"] == "rest" and renamed["fixed_state"] == "rest"
    assert [(r["from"], r["to"], r["count"]) for r in renamed["rules"]] == [
        ("firing", "decay", None),
        ("decay", "rest", None),
        ("rest", "firing", "firing"),
    ]
    assert form["rules"][1]["from"] == "dying"  # original untouched


def test_values_ignored_by_always_are_pointed_out_without_blocking():
    form = blank_form()
    form["rules"] = [rule_row(to="alive", comparison="always", value="2", count="alive")]
    data, issues = definition_from_form(form)
    assert [(i.level, i.path) for i in issues] == [("warning", "form.rules[0].comparison")]
    assert "Number(s) and Neighbours in state are ignored" in issues[0].message
    assert validate(data).ok
    form["rules"] = [rule_row(to="alive", comparison="always", count="alive")]
    assert "Neighbours in state is ignored" in definition_from_form(form)[1][0].message
