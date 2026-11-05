from dataclasses import replace

import numpy as np
import pytest

from cellab.engine import offsets, random_world, step, world_from_text, world_to_text
from cellab.model import AllOf, Always, AnyOf, ElementaryRule, Grid, Not, validate
from cellab.presets import load_preset


def preset(preset_id, width=None, height=None, boundary=None, fixed_state=None):
    a = load_preset(preset_id).automaton
    g = a.grid
    grid = Grid(
        width or g.width,
        height or g.height,
        boundary or g.boundary,
        fixed_state if boundary == "fixed" else (None if boundary == "wrap" else g.fixed_state),
    )
    return replace(a, grid=grid)


def run(automaton, world, n, rng=None):
    for _ in range(n):
        world = step(automaton, world, rng)
    return world


def text(automaton, world):
    return world_to_text(automaton, world)


# --- naive reference implementation: loops written directly from the semantics -------------


def naive_step(a, grid):
    h, w = grid.shape
    names = a.state_names

    def state_at(y, x):
        if a.grid.boundary == "wrap":
            return grid[y % h, x % w]
        if 0 <= y < h and 0 <= x < w:
            return grid[y, x]
        return names.index(a.grid.fixed_state)

    def holds(cond, y, x):
        if isinstance(cond, Always):
            return True
        if isinstance(cond, Not):
            return not holds(cond.item, y, x)
        if isinstance(cond, AllOf):
            return all(holds(c, y, x) for c in cond.items)
        if isinstance(cond, AnyOf):
            return any(holds(c, y, x) for c in cond.items)
        wanted = {names.index(s) for s in cond.states}
        n = sum(state_at(y + dy, x + dx) in wanted for dy, dx in offsets(a.neighborhood))
        v = cond.value
        return {
            "eq": lambda: n == v,
            "ne": lambda: n != v,
            "lt": lambda: n < v,
            "le": lambda: n <= v,
            "gt": lambda: n > v,
            "ge": lambda: n >= v,
            "in": lambda: n in v,
            "not_in": lambda: n not in v,
            "between": lambda: v[0] <= n <= v[1],
        }[cond.op]()

    new = grid.copy()
    for y in range(h):
        for x in range(w):
            for rule in a.rules:
                if rule.from_states is not None and names[grid[y, x]] not in rule.from_states:
                    continue
                if holds(rule.when, y, x):
                    new[y, x] = names.index(rule.to)
                    break
    return new


CUSTOM = {
    "name": "Mixed conditions",
    "grid": {"width": 13, "height": 11, "boundary": {"fixed": "b"}},
    "states": [
        {"name": "a", "symbol": "a", "color": "#F3F5F8"},
        {"name": "b", "symbol": "b", "color": "#2E2A5C"},
        {"name": "c", "symbol": "c", "color": "#D9467A"},
    ],
    "default_state": "a",
    "neighborhood": {"type": "von_neumann", "radius": 2},
    "rules": [
        {"from": "a", "to": "b", "when": {"count": ["b", "c"], "between": [3, 6]}},
        {
            "from": ["b", "c"],
            "to": "a",
            "when": {"any": [{"count": "c", "ge": 4}, {"not": {"count": "a", "in": [2, 3, 5]}}]},
        },
        {"to": "c", "when": {"all": [{"count": "b", "ne": 4}, {"count": "a", "lt": 7}]}},
    ],
}


def custom():
    result = validate(CUSTOM)
    assert result.ok, result.issues
    return result.automaton


@pytest.mark.parametrize(
    "make",
    [
        lambda: preset("game-of-life", 17, 13),
        lambda: preset("game-of-life", 17, 13, "fixed", "alive"),
        lambda: preset("brians-brain", 15, 12),
        lambda: preset("forest-fire", 16, 9),
        custom,
    ],
    ids=["life wrap", "life fixed alive", "brians brain", "forest fire", "custom"],
)
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_engine_matches_naive_reference(make, seed):
    a = make()
    world = random_world(a, {name: 0.3 for name in a.state_names[1:]}, seed)
    for _ in range(5):
        expected = naive_step(a, world)
        world = step(a, world)
        np.testing.assert_array_equal(world, expected)


# --- known patterns -------------------------------------------------------------------------


def test_blinker_oscillates_with_period_2():
    life = preset("game-of-life", 5, 5)
    blinker = world_from_text(life, "###")
    once = step(life, blinker)
    assert text(life, once) == text(life, world_from_text(life, "#\n#\n#"))
    np.testing.assert_array_equal(step(life, once), blinker)


def test_block_is_still():
    life = preset("game-of-life", 6, 6)
    block = world_from_text(life, "##\n##")
    np.testing.assert_array_equal(step(life, block), block)


def test_glider_moves_one_cell_diagonally_every_4_generations():
    life = preset("game-of-life", 10, 10)
    glider = ".#.\n..#\n###"
    start = world_from_text(life, glider, top=1, left=1)
    expected = world_from_text(life, glider, top=2, left=2)
    np.testing.assert_array_equal(run(life, start, 4), expected)


def test_glider_wraps_around_the_edges():
    life = preset("game-of-life", 8, 8)
    start = world_from_text(life, ".#.\n..#\n###", top=0, left=0)
    np.testing.assert_array_equal(run(life, start, 32), start)  # 8 cells x 4 generations


def test_fixed_boundary_changes_the_result_at_the_edge():
    wrap = preset("game-of-life", 5, 5)
    fixed = preset("game-of-life", 5, 5, "fixed", "dead")
    edge = world_from_text(wrap, "###", top=0, left=1)
    assert not np.array_equal(step(wrap, edge), step(fixed, edge))
    # with a dead border the blinker on the top edge loses its upper half
    assert text(fixed, step(fixed, edge)).splitlines()[:2] == [". . # . .", ". . # . ."]


def test_brians_brain_example_from_the_statement():
    brain = preset("brians-brain", 5, 3, "fixed", "off")
    start = world_from_text(brain, ". . F . .\n. F . F .\n. . . . .")
    assert text(brain, step(brain, start)) == ". F D F .\n. D . D .\n. . F . ."


def test_forest_fire_example_from_the_statement():
    forest = preset("forest-fire", 5, 4)
    start = world_from_text(forest, "T T T T .\nT T . T T\n. T F T T\nT T T T T")
    assert text(forest, step(forest, start)) == ("T T T T .\nT F . F T\n. F . F T\nT F F F T")
    # fires burn out; every remaining tree touches a fire (diagonals count in Moore)
    assert text(forest, run(forest, start, 2)) == ("F F F F .\nF . . . F\n. . . . F\nF . . . F")


def rule_30_reference(row):
    left, right = np.roll(row, 1), np.roll(row, -1)
    left[0] = right[-1] = 0  # fixed dead boundary
    return left ^ (row | right)


def test_rule_30_matches_its_formula():
    rule30 = preset("rule-30")
    world = world_from_text(rule30, "1")
    assert text(rule30, world).count("1") == 1
    row = world[0].copy()
    for _ in range(40):
        world = step(rule30, world)
        row = rule_30_reference(row)
        np.testing.assert_array_equal(world[0], row)


def test_rule_30_first_rows():
    rule30 = preset("rule-30", width=7)
    world = world_from_text(rule30, "1")
    rows = []
    for _ in range(4):
        rows.append(world_to_text(rule30, world, sep=""))
        world = step(rule30, world)
    assert rows == ["0001000", "0011100", "0110010", "1101111"]


@pytest.mark.parametrize("code", [0, 90, 110, 255])
def test_other_elementary_codes_follow_the_wolfram_table(code):
    a = replace(preset("rule-30", width=9), rules=(ElementaryRule(code),))
    world = random_world(a, {"alive": 0.5}, seed=code)
    new = step(a, world)
    padded = np.concatenate(([0], world[0], [0]))
    for x in range(9):
        neighbourhood = 4 * padded[x] + 2 * padded[x + 1] + padded[x + 2]
        assert new[0, x] == (code >> neighbourhood) & 1


# --- semantics ------------------------------------------------------------------------------


def two_state(rules, width=6, height=5):
    data = {
        "name": "t",
        "grid": {"width": width, "height": height},
        "states": [
            {"name": "dead", "symbol": ".", "color": "#F3F5F8"},
            {"name": "alive", "symbol": "#", "color": "#2E2A5C"},
            {"name": "other", "symbol": "o", "color": "#D9467A"},
        ],
        "default_state": "dead",
        "rules": rules,
    }
    result = validate(data)
    assert result.ok, result.issues
    return result.automaton


def test_first_matching_rule_wins():
    a = two_state([{"from": "dead", "to": "alive"}, {"from": "dead", "to": "other"}])
    world = random_world(a, {}, seed=0)
    assert set(np.unique(step(a, world))) == {1}


def test_cells_without_a_matching_rule_keep_their_state():
    a = two_state([{"from": "alive", "to": "other"}])
    world = random_world(a, {"alive": 0.4}, seed=4)
    new = step(a, world)
    np.testing.assert_array_equal(new[world == 0], world[world == 0])
    assert (new[world == 1] == 2).all()


def test_step_does_not_modify_its_input():
    life = preset("game-of-life", 10, 10)
    world = random_world(life, {"alive": 0.5}, seed=9)
    before = world.copy()
    step(life, world)
    np.testing.assert_array_equal(world, before)


def test_probabilistic_rules_need_a_generator():
    a = two_state([{"from": "dead", "to": "alive", "probability": 0.5}])
    with pytest.raises(ValueError, match="random generator"):
        step(a, random_world(a, {}, seed=0))


def test_probabilistic_rule_is_reproducible_and_roughly_right():
    a = two_state([{"from": "dead", "to": "alive", "probability": 0.5}], 100, 100)
    world = random_world(a, {}, seed=0)
    first = step(a, world, np.random.default_rng(42))
    second = step(a, world, np.random.default_rng(42))
    np.testing.assert_array_equal(first, second)
    assert 0.45 < (first == 1).mean() < 0.55


def test_failed_random_draw_falls_through_to_the_next_rule():
    a = two_state(
        [
            {"from": "dead", "to": "alive", "probability": 1e-12},
            {"from": "dead", "to": "other"},
        ]
    )
    new = step(a, random_world(a, {}, seed=0), np.random.default_rng(0))
    assert (new == 2).all()


def test_probability_one_equals_the_deterministic_rule():
    deterministic = two_state(
        [{"from": "dead", "to": "alive", "when": {"count": "alive", "ge": 2}}]
    )
    certain = two_state(
        [{"from": "dead", "to": "alive", "when": {"count": "alive", "ge": 2}, "probability": 1}]
    )
    world = random_world(deterministic, {"alive": 0.3}, seed=5)
    np.testing.assert_array_equal(
        step(deterministic, world), step(certain, world, np.random.default_rng(1))
    )


def test_rule_compilation_handles_any_source():
    a = two_state([{"to": "other", "when": {"count": "alive", "ge": 1}}])
    world = world_from_text(a, "#")
    new = step(a, world)
    assert (new == 2).sum() == 8  # the 8 neighbours of the single alive cell
