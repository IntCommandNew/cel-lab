"""Saving, loading and listing runs (docs/DESIGN.md, section 8).

A run is a folder:

    data/runs/2026-11-06_093012_game-of-life/
    |-- definition.json   the validated automaton definition
    |-- experiment.json   settings, initial-world source, generations, random state, timings
    `-- history.npz       stored generations, their indices, hashes and populations

Everything needed to browse the run, recompute missing generations (deterministic automata) or
continue it exactly where it stopped is in the folder.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cellab.engine.simulate import Run, RunSettings
from cellab.engine.world import WorldError, check_world
from cellab.model import automaton_to_dict, validate

FORMAT_VERSION = 1
DEFAULT_ROOT = Path("data") / "runs"
DEFINITION = "definition.json"
EXPERIMENT = "experiment.json"
HISTORY = "history.npz"


class StorageError(Exception):
    pass


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "run"


def new_run_folder(name: str, root: str | Path = DEFAULT_ROOT) -> Path:
    """A folder path that does not exist yet: <root>/<date>_<time>_<slug>."""
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base = Path(root) / f"{stamp}_{_slug(name)}"
    path, n = base, 2
    while path.exists():
        path = base.with_name(f"{base.name}-{n}")
        n += 1
    return path


def save_run(run: Run, folder: str | Path | None = None, root: str | Path = DEFAULT_ROOT) -> Path:
    """Write the run to `folder` (created or overwritten) or to a new folder under `root`."""
    folder = Path(folder) if folder else new_run_folder(run.automaton.name, root)
    folder.mkdir(parents=True, exist_ok=True)
    generations = run.stored_generations
    experiment = {
        "format_version": FORMAT_VERSION,
        "created": run.meta.get("created") or dt.datetime.now().isoformat(timespec="seconds"),
        "saved": dt.datetime.now().isoformat(timespec="seconds"),
        "settings": {
            "history": run.settings.history,
            "every": run.settings.every,
            "seed": run.settings.seed,
        },
        "world_source": run.world_source,
        "last_generation": run.last_generation,
        "stored_generations": len(generations),
        "elapsed_seconds": round(run.elapsed, 4),
        "rng_state": None if run.rng is None else run.rng.bit_generator.state,
    }
    (folder / DEFINITION).write_text(
        json.dumps(automaton_to_dict(run.automaton), indent=2) + "\n", encoding="utf-8"
    )
    (folder / EXPERIMENT).write_text(json.dumps(experiment, indent=2) + "\n", encoding="utf-8")
    np.savez_compressed(
        folder / HISTORY,
        generations=np.array(generations, dtype=np.int64),
        grids=np.stack([run.stored[g] for g in generations]),
        current=run.current,
        hashes=np.array(run.hashes),
        populations=run.population_table(),
    )
    run.meta["folder"] = str(folder)
    run.meta.setdefault("created", experiment["created"])
    return folder


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StorageError(
            f"{path.parent.name} is not a complete run: {path.name} is missing."
        ) from exc
    except json.JSONDecodeError as exc:
        raise StorageError(f"{path} is damaged: {exc.msg} (line {exc.lineno}).") from exc


def load_run(folder: str | Path) -> Run:
    folder = Path(folder)
    if not folder.is_dir():
        raise StorageError(f"There is no run folder at {folder}.")
    result = validate(_read_json(folder / DEFINITION))
    if not result.ok:
        problems = "; ".join(str(i) for i in result.errors)
        raise StorageError(f"The saved definition is not valid: {problems}")
    automaton = result.automaton
    experiment = _read_json(folder / EXPERIMENT)
    if experiment.get("format_version") != FORMAT_VERSION:
        raise StorageError(
            f"This run was saved in format {experiment.get('format_version')}; this version of "
            f"CelLab reads format {FORMAT_VERSION}."
        )
    try:
        with np.load(folder / HISTORY) as data:
            generations = [int(g) for g in data["generations"]]
            grids = data["grids"]
            current = data["current"]
            hashes = [str(h) for h in data["hashes"]]
            populations = list(data["populations"])
    except FileNotFoundError as exc:
        raise StorageError(f"{folder.name} is not a complete run: {HISTORY} is missing.") from exc
    except (OSError, KeyError, ValueError) as exc:
        raise StorageError(f"{folder / HISTORY} is damaged: {exc}") from exc

    last = experiment["last_generation"]
    if len(hashes) != last + 1 or len(populations) != last + 1 or generations[-1] != last:
        raise StorageError(f"{folder.name} is inconsistent: its files disagree on the generations.")
    try:
        check_world(automaton, current)
        for grid in grids:
            check_world(automaton, grid)
    except WorldError as exc:
        raise StorageError(f"{folder.name} does not match its definition: {exc}") from exc

    s = experiment["settings"]
    rng = None
    if experiment.get("rng_state") is not None:
        rng = np.random.default_rng()
        rng.bit_generator.state = experiment["rng_state"]
    return Run(
        automaton=automaton,
        settings=RunSettings(s["history"], s["every"], s["seed"]),
        world_source=experiment.get("world_source", {}),
        stored={g: grids[i] for i, g in enumerate(generations)},
        hashes=hashes,
        populations=populations,
        current=current,
        rng=rng,
        elapsed=experiment.get("elapsed_seconds", 0.0),
        meta={"folder": str(folder), "created": experiment.get("created")},
    )


@dataclass(frozen=True)
class RunInfo:
    folder: Path
    automaton: str
    last_generation: int
    stored_generations: int
    created: str


def list_runs(root: str | Path = DEFAULT_ROOT) -> list[RunInfo]:
    """Saved runs under `root`, newest first. Incomplete or damaged folders are skipped."""
    root = Path(root)
    if not root.is_dir():
        return []
    runs = []
    for folder in root.iterdir():
        try:
            definition = json.loads((folder / DEFINITION).read_text(encoding="utf-8"))
            experiment = json.loads((folder / EXPERIMENT).read_text(encoding="utf-8"))
            runs.append(
                RunInfo(
                    folder=folder,
                    automaton=str(definition.get("name", "?")),
                    last_generation=int(experiment["last_generation"]),
                    stored_generations=int(experiment["stored_generations"]),
                    created=str(experiment.get("created", "")),
                )
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(runs, key=lambda r: (r.created, r.folder.name), reverse=True)
