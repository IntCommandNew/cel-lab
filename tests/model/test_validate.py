import pytest

from cellab.model import validate, validate_json
from cellab.presets import load_preset, preset_ids


def issues_at(result, path, level="error"):
    return [i for i in result.issues if i.path == path and i.level == level]


@pytest.mark.parametrize("preset_id", preset_ids())
def test_presets_are_valid_without_warnings(preset_id):
    result = load_preset(preset_id)
    assert result.ok
    assert result.issues == []


def test_valid_definition_builds_an_automaton(base_definition):
    result = validate(base_definition)
    assert result.ok and result.errors == [] and result.automaton.name == "Test automaton"


def test_invalid_json_reports_line_and_column():
    result = validate_json('{"name": "x",\n  "grid": }')
    assert not result.ok
    assert "line 2" in result.errors[0].message


def test_definition_must_be_an_object():
    assert not validate([1, 2]).ok


# --- structural and reference errors: (mutation, path that must be reported) ----------------

ERROR_CASES = {
    "missing name": (lambda d: d.pop("name"), "name"),
    "blank name": (lambda d: d.update(name="  "), "name"),
    "zero width": (lambda d: d["grid"].update(width=0), "grid.width"),
    "huge height": (lambda d: d["grid"].update(height=5000), "grid.height"),
    "width as text": (lambda d: d["grid"].update(width="40"), "grid.width"),
    "width as bool": (lambda d: d["grid"].update(width=True), "grid.width"),
    "bad boundary": (lambda d: d["grid"].update(boundary="bounce"), "grid.boundary"),
    "unknown fixed state": (
        lambda d: d["grid"].update(boundary={"fixed": "wall"}),
        "grid.boundary.fixed",
    ),
    "no states": (lambda d: d.update(states=[]), "states"),
    "duplicate state name": (lambda d: d["states"][1].update(name="Dead"), "states[1].name"),
    "state named any": (lambda d: d["states"][1].update(name="any"), "states[1].name"),
    "two-character symbol": (lambda d: d["states"][0].update(symbol=".."), "states[0].symbol"),
    "space symbol": (lambda d: d["states"][0].update(symbol=" "), "states[0].symbol"),
    "duplicate symbol": (lambda d: d["states"][1].update(symbol="."), "states[1].symbol"),
    "bad color": (lambda d: d["states"][0].update(color="red"), "states[0].color"),
    "missing default state": (lambda d: d.pop("default_state"), "default_state"),
    "unknown default state": (lambda d: d.update(default_state="empty"), "default_state"),
    "unknown neighbourhood": (
        lambda d: d["neighborhood"].update(type="hexagonal"),
        "neighborhood.type",
    ),
    "radius too large": (lambda d: d["neighborhood"].update(radius=9), "neighborhood.radius"),
    "rules not a list": (lambda d: d.update(rules={}), "rules"),
    "unknown target state": (lambda d: d["rules"][0].update(to="burning"), "rules[0].to"),
    "unknown source state": (lambda d: d["rules"][0].update(**{"from": "x"}), "rules[0].from"),
    "missing target": (lambda d: d["rules"][0].pop("to"), "rules[0].to"),
    "unknown counted state": (
        lambda d: d["rules"][0]["when"].update(count="fire"),
        "rules[0].when.count",
    ),
    "two comparisons": (lambda d: d["rules"][0]["when"].update(lt=4), "rules[0].when"),
    "unknown comparison": (
        lambda d: d["rules"][0].update(when={"count": "alive", "approx": 3}),
        "rules[0].when",
    ),
    "probability above 1": (
        lambda d: d["rules"][0].update(probability=1.5),
        "rules[0].probability",
    ),
    "probability zero": (lambda d: d["rules"][0].update(probability=0), "rules[0].probability"),
    "between reversed": (
        lambda d: d["rules"][0].update(when={"count": "alive", "between": [4, 2]}),
        "rules[0].when.between",
    ),
    "empty all": (lambda d: d["rules"][0].update(when={"all": []}), "rules[0].when.all"),
}


@pytest.mark.parametrize("mutate,path", ERROR_CASES.values(), ids=ERROR_CASES.keys())
def test_errors_are_reported_at_the_right_field(base_definition, mutate, path):
    mutate(base_definition)
    result = validate(base_definition)
    assert not result.ok
    assert issues_at(result, path), [str(i) for i in result.issues]


# --- semantic checks ------------------------------------------------------------------------

IMPOSSIBLE_COUNTS = [
    {"count": "alive", "eq": 9},
    {"count": "alive", "gt": 8},
    {"count": "alive", "ge": 9},
    {"count": "alive", "lt": 0},
    {"count": "alive", "in": [9, 10]},
    {"count": "alive", "between": [9, 12]},
]


@pytest.mark.parametrize("when", IMPOSSIBLE_COUNTS)
def test_counts_impossible_for_the_neighbourhood_are_errors(base_definition, when):
    base_definition["rules"][0]["when"] = when
    result = validate(base_definition)
    assert not result.ok
    assert "can never apply" in result.errors[0].message
    assert "0 to 8 neighbours" in result.errors[0].message


def test_impossible_count_depends_on_neighbourhood(base_definition):
    base_definition["rules"][0]["when"] = {"count": "alive", "eq": 5}
    assert validate(base_definition).ok  # Moore: up to 8
    base_definition["neighborhood"] = {"type": "von_neumann", "radius": 1}
    assert not validate(base_definition).ok  # von Neumann: up to 4


def test_partly_impossible_list_is_a_warning(base_definition):
    base_definition["rules"][0]["when"] = {"count": "alive", "in": [3, 9]}
    result = validate(base_definition)
    assert result.ok
    assert issues_at(result, "rules[0].when.in", "warning")


def test_rule_shadowed_by_unconditional_rule_is_a_warning(base_definition):
    base_definition["rules"] = [
        {"from": "dead", "to": "alive"},
        {"from": "dead", "to": "alive", "when": {"count": "alive", "eq": 3}},
    ]
    result = validate(base_definition)
    assert result.ok
    assert "never applies" in issues_at(result, "rules[1]", "warning")[0].message


def test_rule_after_any_rule_is_shadowed(base_definition):
    base_definition["rules"] = [{"to": "dead"}, {"from": "alive", "to": "dead"}]
    assert issues_at(validate(base_definition), "rules[1]", "warning")


def test_probabilistic_rule_does_not_shadow(base_definition):
    base_definition["rules"] = [
        {"from": "dead", "to": "alive", "probability": 0.1},
        {"from": "dead", "to": "alive", "when": {"count": "alive", "eq": 3}},
    ]
    assert validate(base_definition).warnings == []


def test_rule_without_effect_is_a_warning(base_definition):
    base_definition["rules"][0]["to"] = "dead"
    result = validate(base_definition)
    assert result.ok
    assert "no effect" in issues_at(result, "rules[0]", "warning")[0].message


def test_unknown_fields_are_warnings(base_definition):
    base_definition["colour_scheme"] = "dark"
    base_definition["rules"][0]["priority"] = 1
    result = validate(base_definition)
    assert result.ok
    assert issues_at(result, "colour_scheme", "warning")
    assert issues_at(result, "rules[0].priority", "warning")


def test_empty_rules_is_a_warning(base_definition):
    base_definition["rules"] = []
    result = validate(base_definition)
    assert result.ok and issues_at(result, "rules", "warning")


def test_unknown_state_message_lists_declared_states(base_definition):
    base_definition["rules"][0]["to"] = "burning"
    message = validate(base_definition).errors[0].message
    assert message == (
        "Rule 1 uses the state 'burning', which is not declared. Declared states: dead, alive."
    )


# --- elementary rules -----------------------------------------------------------------------


def elementary(base_definition, **grid):
    base_definition["grid"].update(height=1, **grid)
    base_definition["neighborhood"] = {"type": "elementary", "radius": 1}
    base_definition["rules"] = [{"kind": "elementary", "code": 30}]
    return base_definition


def test_elementary_definition_is_valid(base_definition):
    assert validate(elementary(base_definition)).ok


@pytest.mark.parametrize(
    "mutate,path",
    [
        (lambda d: d["rules"][0].update(code=256), "rules[0].code"),
        (lambda d: d["grid"].update(height=3), "grid.height"),
        (lambda d: d.update(neighborhood={"type": "moore"}), "neighborhood.type"),
        (lambda d: d["rules"].append({"from": "dead", "to": "alive"}), "rules[0]"),
        (
            lambda d: d["states"].append({"name": "x", "symbol": "x", "color": "#000000"}),
            "states",
        ),
        (lambda d: d["rules"][0].update(kind="totalistic"), "rules[0].kind"),
    ],
    ids=["code", "height", "neighbourhood", "not alone", "three states", "kind"],
)
def test_elementary_constraints(base_definition, mutate, path):
    data = elementary(base_definition)
    mutate(data)
    result = validate(data)
    assert not result.ok
    assert issues_at(result, path), [str(i) for i in result.issues]
