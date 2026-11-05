import numpy as np
import pytest

from cellab.engine import (
    WorldError,
    centre_cell,
    check_world,
    empty_world,
    parse_pattern,
    random_world,
    world_from_text,
    world_to_text,
)
from cellab.presets import load_preset


@pytest.fixture
def life():
    return load_preset("game-of-life").automaton  # 40 x 30


@pytest.fixture
def forest():
    return load_preset("forest-fire").automaton


def test_empty_world_uses_the_default_state(life):
    world = empty_world(life)
    assert world.shape == (30, 40) and world.dtype == np.uint8 and not world.any()


def test_pattern_with_or_without_spaces(forest):
    with_spaces = parse_pattern(forest, "T . F\nT T T")
    without = parse_pattern(forest, "T.F\nTTT\n\n")
    np.testing.assert_array_equal(with_spaces, without)
    assert with_spaces.tolist() == [[1, 0, 2], [1, 1, 1]]


def test_text_world_is_centred_by_default(life):
    world = world_from_text(life, "#")
    assert np.argwhere(world).tolist() == [[15, 20]]


def test_text_world_at_a_position(life):
    world = world_from_text(life, "##", top=0, left=38)
    assert np.argwhere(world).tolist() == [[0, 38], [0, 39]]


def test_world_to_text_round_trips(forest):
    world = random_world(forest, {"tree": 0.6, "fire": 0.05}, seed=3)
    np.testing.assert_array_equal(parse_pattern(forest, world_to_text(forest, world)), world)


@pytest.mark.parametrize(
    "text,message",
    [
        ("", "empty"),
        ("   \n  ", "empty"),
        ("###\n##", "Row 2 has 2 cells, but row 1 has 3"),
        ("#x#\n#?#", "Row 1 uses unknown symbols x. Use: . (dead), # (alive)"),
        ("#" * 41, "41 x 1 cells but the grid is only 40 x 30"),
    ],
)
def test_text_world_errors(life, text, message):
    with pytest.raises(WorldError, match=message.replace("(", r"\(").replace(")", r"\)")):
        world_from_text(life, text)


def test_pattern_outside_the_grid_is_an_error(life):
    with pytest.raises(WorldError, match="does not fit"):
        world_from_text(life, "##", top=0, left=39)


def test_random_world_is_reproducible(forest):
    a = random_world(forest, {"tree": 0.6}, seed=11)
    b = random_world(forest, {"tree": 0.6}, seed=11)
    c = random_world(forest, {"tree": 0.6}, seed=12)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_random_world_proportions(forest):
    world = random_world(forest, {"tree": 0.6, "fire": 0.1}, seed=1)
    assert abs((world == 1).mean() - 0.6) < 0.05
    assert abs((world == 2).mean() - 0.1) < 0.03


@pytest.mark.parametrize(
    "probabilities,message",
    [
        ({"rock": 0.1}, "Unknown state 'rock'"),
        ({"tree": 1.2}, "between 0 and 1"),
        ({"tree": 0.7, "fire": 0.5}, "more than 1"),
    ],
)
def test_random_world_errors(forest, probabilities, message):
    with pytest.raises(WorldError, match=message):
        random_world(forest, probabilities, seed=0)


def test_centre_cell():
    rule30 = load_preset("rule-30").automaton
    world = centre_cell(rule30, "alive")
    assert world.shape == (1, 81)
    assert np.argwhere(world).tolist() == [[0, 40]]


def test_check_world(life):
    check_world(life, empty_world(life))
    with pytest.raises(WorldError, match="needs 40 x 30"):
        check_world(life, np.zeros((3, 3), np.uint8))
    bad = empty_world(life)
    bad[0, 0] = 7
    with pytest.raises(WorldError, match="does not declare"):
        check_world(life, bad)
