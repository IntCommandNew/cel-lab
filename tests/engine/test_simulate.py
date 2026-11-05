from dataclasses import replace

import numpy as np
import pytest

from cellab.engine import (
    RunSettings,
    SimulationError,
    grid_hash,
    random_world,
    simulate,
    step,
    world_from_text,
)
from cellab.model import validate
from cellab.presets import load_preset


@pytest.fixture
def life():
    a = load_preset("game-of-life").automaton
    return replace(a, grid=replace(a.grid, width=12, height=10))


@pytest.fixture
def noisy():
    """Probabilistic automaton: tests that random runs are reproducible."""
    result = validate(
        {
            "name": "Noisy",
            "grid": {"width": 12, "height": 10},
            "states": [
                {"name": "off", "symbol": ".", "color": "#F3F5F8"},
                {"name": "on", "symbol": "#", "color": "#2E2A5C"},
            ],
            "default_state": "off",
            "rules": [
                {"from": "off", "to": "on", "when": {"count": "on", "ge": 1}, "probability": 0.3},
                {"from": "on", "to": "off", "probability": 0.2},
            ],
        }
    )
    assert result.ok, result.issues
    return result.automaton


def manual_run(automaton, world, n, rng=None):
    grids = [world]
    for _ in range(n):
        grids.append(step(automaton, grids[-1], rng))
    return grids


def test_history_all_keeps_every_generation(life):
    world = random_world(life, {"alive": 0.35}, seed=2)
    run = simulate(life, world, 15)
    expected = manual_run(life, world, 15)
    assert run.last_generation == 15
    assert run.stored_generations == list(range(16))
    for g in range(16):
        np.testing.assert_array_equal(run.generation(g), expected[g])
    assert run.hashes == [grid_hash(g) for g in expected]


def test_history_every_k_keeps_multiples_plus_first_and_last(life):
    run = simulate(life, random_world(life, {"alive": 0.35}, seed=2), 17, RunSettings("every", 5))
    assert run.stored_generations == [0, 5, 10, 15, 17]


def test_history_final_keeps_first_and_last(life):
    run = simulate(life, random_world(life, {"alive": 0.35}, seed=2), 17, RunSettings("final"))
    assert run.stored_generations == [0, 17]
    assert len(run.hashes) == 18 and len(run.populations) == 18  # still recorded


def test_continuing_moves_the_kept_last_generation(life):
    run = simulate(life, random_world(life, {"alive": 0.35}, seed=2), 7, RunSettings("every", 5))
    run.advance(6)
    assert run.stored_generations == [0, 5, 10, 13]
    run = simulate(life, random_world(life, {"alive": 0.35}, seed=2), 7, RunSettings("final"))
    run.advance(3)
    assert run.stored_generations == [0, 10]


def test_missing_generations_are_recomputed_for_deterministic_automata(life):
    world = random_world(life, {"alive": 0.35}, seed=4)
    run = simulate(life, world, 20, RunSettings("every", 6))
    expected = manual_run(life, world, 20)
    for g in range(21):
        np.testing.assert_array_equal(run.generation(g), expected[g])


def test_missing_generations_cannot_be_recomputed_for_random_automata(noisy):
    run = simulate(noisy, world_from_text(noisy, "#"), 10, RunSettings("final", seed=1))
    with pytest.raises(SimulationError, match="cannot be recomputed"):
        run.generation(4)
    run.generation(10)  # stored


def test_generation_out_of_range(life):
    run = simulate(life, random_world(life, {}, seed=0), 3)
    with pytest.raises(SimulationError, match="0 to 3"):
        run.generation(4)


def test_populations_count_every_state(life):
    world = random_world(life, {"alive": 0.35}, seed=5)
    run = simulate(life, world, 8)
    table = run.population_table()
    assert table.shape == (9, 2)
    assert (table.sum(axis=1) == 120).all()
    assert table[0, 1] == world.sum()


def test_random_runs_are_reproducible_with_the_same_seed(noisy):
    world = world_from_text(noisy, "#")
    a = simulate(noisy, world, 30, RunSettings(seed=7))
    b = simulate(noisy, world, 30, RunSettings(seed=7))
    c = simulate(noisy, world, 30, RunSettings(seed=8))
    assert a.hashes == b.hashes
    assert a.hashes != c.hashes


def test_continuing_equals_one_uninterrupted_run(life, noisy):
    for automaton, world in [
        (life, random_world(life, {"alive": 0.35}, seed=3)),
        (noisy, world_from_text(noisy, "#")),
    ]:
        whole = simulate(automaton, world, 25, RunSettings(seed=11))
        parts = simulate(automaton, world, 10, RunSettings(seed=11)).advance(15)
        assert parts.hashes == whole.hashes


def test_initial_world_is_copied(life):
    world = random_world(life, {"alive": 0.35}, seed=3)
    run = simulate(life, world, 2)
    world[:] = 0
    assert run.generation(0).any()


@pytest.mark.parametrize(
    "generations,settings,message",
    [
        (-1, RunSettings(), "0 or more"),
        (2.5, RunSettings(), "whole number"),
        (200_000, RunSettings(), "At most"),
        (5, RunSettings("sometimes"), "History must be one of"),
        (5, RunSettings("every", 0), "k must be"),
    ],
)
def test_invalid_settings(life, generations, settings, message):
    with pytest.raises(SimulationError, match=message):
        simulate(life, random_world(life, {}, seed=0), generations, settings)


def test_storing_too_much_is_refused_with_advice():
    big = load_preset("game-of-life").automaton
    big = replace(big, grid=replace(big.grid, width=1000, height=1000))
    world = np.zeros((1000, 1000), np.uint8)
    with pytest.raises(SimulationError, match="every k-th generation or only the final one"):
        simulate(big, world, 1000)
    simulate(big, world, 3, RunSettings("final"))  # fine


def test_world_must_match_the_automaton(life):
    with pytest.raises(ValueError, match="needs 12 x 10"):
        simulate(life, np.zeros((3, 3), np.uint8), 1)
