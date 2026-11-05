import json

import pytest

from cellab.model import (
    AllOf,
    Count,
    ElementaryRule,
    Not,
    Rule,
    automaton_to_dict,
    load_definition,
    save_definition,
)
from cellab.presets import preset_ids, preset_path


@pytest.mark.parametrize("preset_id", preset_ids())
def test_preset_round_trips_to_identical_json(preset_id):
    original = json.loads(preset_path(preset_id).read_text(encoding="utf-8"))
    result = load_definition(preset_path(preset_id))
    assert result.ok, result.issues
    assert automaton_to_dict(result.automaton) == original


def test_save_and_load_give_the_same_automaton(tmp_path):
    automaton = load_definition(preset_path("brians-brain")).automaton
    path = tmp_path / "brain.json"
    save_definition(automaton, path)
    assert load_definition(path).automaton == automaton


def test_game_of_life_is_parsed_into_typed_rules():
    life = load_definition(preset_path("game-of-life")).automaton
    assert life.state_names == ("dead", "alive")
    assert life.state_index("alive") == 1
    assert life.neighborhood.size == 8
    assert life.rules[0] == Rule(
        to="dead", from_states=("alive",), when=Count(("alive",), "not_in", (2, 3))
    )
    assert life.rules[1].when == Count(("alive",), "eq", 3)
    assert not life.is_elementary


def test_rule_30_is_elementary():
    rule30 = load_definition(preset_path("rule-30")).automaton
    assert rule30.is_elementary
    assert rule30.rules == (ElementaryRule(30),)
    assert rule30.grid.boundary == "fixed"
    assert rule30.grid.fixed_state == "dead"


def test_nested_conditions_and_defaults_round_trip(base_definition):
    base_definition["rules"] = [
        {
            "from": ["dead", "alive"],
            "to": "alive",
            "when": {"all": [{"count": "alive", "ge": 2}, {"not": {"count": "alive", "eq": 5}}]},
            "probability": 0.5,
        },
        {"to": "dead"},
    ]
    automaton = load_definition_from(base_definition)
    first, second = automaton.rules
    assert first.from_states == ("dead", "alive")
    assert first.when == AllOf((Count(("alive",), "ge", 2), Not(Count(("alive",), "eq", 5))))
    assert first.probability == 0.5
    assert second.from_states is None  # "from" omitted = any state
    out = automaton_to_dict(automaton)
    assert out["rules"][1] == {"from": "any", "to": "dead"}
    assert out["rules"][0]["when"] == base_definition["rules"][0]["when"]


def test_neighbourhood_sizes():
    from cellab.model import Neighborhood

    assert Neighborhood("moore", 1).size == 8
    assert Neighborhood("moore", 2).size == 24
    assert Neighborhood("von_neumann", 1).size == 4
    assert Neighborhood("von_neumann", 2).size == 12
    assert Neighborhood("elementary", 1).size == 2


def load_definition_from(data):
    from cellab.model import validate

    result = validate(data)
    assert result.ok, result.issues
    return result.automaton
