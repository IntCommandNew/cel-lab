import json
from dataclasses import replace

import numpy as np
import pytest

from cellab.engine import RunSettings, centre_cell, random_world, simulate
from cellab.model import validate
from cellab.presets import load_preset
from cellab.storage import StorageError, list_runs, load_run, new_run_folder, save_run


def small(preset_id, width=14, height=11):
    a = load_preset(preset_id).automaton
    return replace(a, grid=replace(a.grid, width=width, height=height))


NOISY = {
    "name": "Noisy fire",
    "grid": {"width": 14, "height": 11, "boundary": {"fixed": "empty"}},
    "states": [
        {"name": "empty", "symbol": ".", "color": "#F3F5F8"},
        {"name": "tree", "symbol": "T", "color": "#4F9D69"},
        {"name": "fire", "symbol": "F", "color": "#E8A33A"},
    ],
    "default_state": "empty",
    "rules": [
        {"from": "fire", "to": "empty"},
        {"from": "tree", "to": "fire", "when": {"count": "fire", "ge": 1}},
        {"from": "tree", "to": "fire", "probability": 0.01},
        {"from": "empty", "to": "tree", "probability": 0.05},
    ],
}


def noisy():
    return validate(NOISY).automaton


def assert_same_run(a, b):
    assert a.automaton == b.automaton
    assert a.settings == b.settings
    assert a.world_source == b.world_source
    assert a.hashes == b.hashes
    assert a.stored_generations == b.stored_generations
    for g in a.stored_generations:
        np.testing.assert_array_equal(a.stored[g], b.stored[g])
    np.testing.assert_array_equal(a.current, b.current)
    np.testing.assert_array_equal(a.population_table(), b.population_table())


@pytest.mark.parametrize(
    "history", [RunSettings("all"), RunSettings("every", 4), RunSettings("final")]
)
def test_save_and_load_give_the_same_run(tmp_path, history):
    life = small("game-of-life")
    source = {"kind": "random", "probabilities": {"alive": 0.3}, "seed": 1}
    run = simulate(life, random_world(life, {"alive": 0.3}, seed=1), 13, history, source)
    folder = save_run(run, root=tmp_path)
    assert sorted(p.name for p in folder.iterdir()) == [
        "definition.json",
        "experiment.json",
        "history.npz",
    ]
    assert_same_run(load_run(folder), run)


@pytest.mark.parametrize(
    "make,history",
    [
        (lambda: small("game-of-life"), RunSettings("all")),
        (lambda: small("brians-brain"), RunSettings("every", 3)),
        (noisy, RunSettings("all", seed=5)),
        (noisy, RunSettings("final", seed=5)),
    ],
    ids=["life all", "brain every 3", "random all", "random final"],
)
def test_save_load_resume_equals_an_uninterrupted_run(tmp_path, make, history):
    automaton = make()
    world = random_world(automaton, {automaton.state_names[1]: 0.4}, seed=2)
    whole = simulate(automaton, world, 30, history)

    first = simulate(automaton, world, 12, history)
    resumed = load_run(save_run(first, root=tmp_path)).advance(18)

    assert_same_run(resumed, whole)


def test_resaving_a_resumed_run_updates_its_folder(tmp_path):
    life = small("game-of-life")
    run = simulate(life, random_world(life, {"alive": 0.3}, seed=1), 5)
    folder = save_run(run, root=tmp_path)
    resumed = load_run(folder).advance(5)
    save_run(resumed, folder)
    assert load_run(folder).last_generation == 10
    assert len(list_runs(tmp_path)) == 1


def test_rule_30_run(tmp_path):
    rule30 = load_preset("rule-30").automaton
    run = simulate(rule30, centre_cell(rule30, "alive"), 40)
    loaded = load_run(save_run(run, root=tmp_path))
    assert loaded.generation(40).shape == (1, 81)
    assert_same_run(loaded, run)


def test_experiment_file_is_readable(tmp_path):
    life = small("game-of-life")
    run = simulate(life, random_world(life, {"alive": 0.3}, seed=1), 6, RunSettings("every", 2))
    experiment = json.loads((save_run(run, root=tmp_path) / "experiment.json").read_text())
    assert experiment["settings"] == {"history": "every", "every": 2, "seed": None}
    assert experiment["last_generation"] == 6
    assert experiment["stored_generations"] == 4
    assert experiment["rng_state"] is None


def test_new_run_folder_names_are_unique(tmp_path):
    first = new_run_folder("Game of Life!", tmp_path)
    first.mkdir()
    second = new_run_folder("Game of Life!", tmp_path)
    assert first.name.endswith("_game-of-life")
    assert second != first


def test_list_runs_skips_incomplete_folders(tmp_path):
    life = small("game-of-life")
    save_run(simulate(life, random_world(life, {"alive": 0.3}, seed=1), 3), root=tmp_path)
    (tmp_path / "not-a-run").mkdir()
    runs = list_runs(tmp_path)
    assert [(r.automaton, r.last_generation, r.stored_generations) for r in runs] == [
        ("Game of Life", 3, 4)
    ]
    assert list_runs(tmp_path / "missing") == []


@pytest.fixture
def saved(tmp_path):
    life = small("game-of-life")
    return save_run(simulate(life, random_world(life, {"alive": 0.3}, seed=1), 4), root=tmp_path)


@pytest.mark.parametrize(
    "damage,message",
    [
        (lambda f: (f / "history.npz").unlink(), "history.npz is missing"),
        (lambda f: (f / "experiment.json").unlink(), "experiment.json is missing"),
        (lambda f: (f / "definition.json").write_text("{"), "damaged"),
        (lambda f: (f / "history.npz").write_bytes(b"nonsense"), "damaged"),
        (
            lambda f: (f / "definition.json").write_text(
                (f / "definition.json").read_text().replace('"dead",', '"ghost",', 1)
            ),
            "not valid",
        ),
        (
            lambda f: (f / "experiment.json").write_text(
                (f / "experiment.json")
                .read_text()
                .replace('"last_generation": 4', '"last_generation": 9')
            ),
            "inconsistent",
        ),
    ],
    ids=["no history", "no experiment", "bad json", "bad npz", "bad definition", "inconsistent"],
)
def test_damaged_runs_give_clear_errors(saved, damage, message):
    damage(saved)
    with pytest.raises(StorageError, match=message):
        load_run(saved)


def test_missing_folder(tmp_path):
    with pytest.raises(StorageError, match="no run folder"):
        load_run(tmp_path / "nothing")
