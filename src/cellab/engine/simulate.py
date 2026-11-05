"""Simulation runs with configurable history (docs/DESIGN.md, section 6).

The number of generations computed is independent of the number stored:

- history "all" keeps every generation, "every" keeps every k-th, "final" only the last one;
  generation 0 (the initial world) and the latest generation are always kept;
- for every generation the run records a hash of the grid and the number of cells in each state,
  whatever the history mode, so stability / cycle questions and population charts work even when
  intermediate grids are not stored.

A run can be extended later (`advance`), also after being saved and loaded: the latest grid and
the random generator state are part of the run, so resuming gives exactly the same result as an
uninterrupted run.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

import numpy as np

from cellab.engine.step import needs_rng, step
from cellab.engine.world import check_world
from cellab.model import Automaton

HISTORY_MODES = ("all", "every", "final")
MAX_GENERATIONS = 100_000  # per call to simulate/advance
MAX_STORED_BYTES = 512 * 1024 * 1024  # stored grids kept in memory


class SimulationError(ValueError):
    pass


def grid_hash(grid: np.ndarray) -> str:
    return hashlib.blake2b(grid.tobytes(), digest_size=16).hexdigest()


@dataclass(frozen=True)
class RunSettings:
    history: str = "all"  # "all" | "every" | "final"
    every: int = 1  # used when history == "every"
    seed: int | None = None  # random generator seed for probabilistic rules

    def keeps(self, generation: int) -> bool:
        """Whether this generation is stored (besides 0 and the latest, which always are)."""
        if self.history == "all":
            return True
        if self.history == "every":
            return generation % self.every == 0
        return False


@dataclass
class Run:
    automaton: Automaton
    settings: RunSettings
    world_source: dict  # how the initial world was made, e.g. {"kind": "random", ...}
    stored: dict[int, np.ndarray]  # generation -> grid
    hashes: list[str]  # one per generation 0..last
    populations: list[np.ndarray]  # one per generation: cells per state index
    current: np.ndarray  # latest generation
    rng: np.random.Generator | None = None
    elapsed: float = 0.0  # seconds spent computing
    meta: dict = field(default_factory=dict)  # free-form (e.g. created, saved folder)

    @property
    def last_generation(self) -> int:
        return len(self.hashes) - 1

    @property
    def stored_generations(self) -> list[int]:
        return sorted(self.stored)

    @property
    def is_deterministic(self) -> bool:
        return not needs_rng(self.automaton)

    def population_table(self) -> np.ndarray:
        """Array (generations + 1, states): cells in each state per generation."""
        return np.stack(self.populations)

    def advance(self, generations: int) -> Run:
        """Compute `generations` more generations (in place); returns the run itself."""
        check_generations(generations)
        start = time.perf_counter()
        a = self.automaton
        grid = self.current
        last = self.last_generation
        n_states = len(a.states)
        for g in range(last + 1, last + generations + 1):
            grid = step(a, grid, self.rng)
            self.hashes.append(grid_hash(grid))
            self.populations.append(np.bincount(grid.ravel(), minlength=n_states))
            if self.settings.keeps(g):
                self.stored[g] = grid
        # the previous latest generation stays only if the history mode keeps it
        if last != 0 and not self.settings.keeps(last) and generations:
            self.stored.pop(last, None)
        self.stored[self.last_generation] = grid
        self.current = grid
        self.elapsed += time.perf_counter() - start
        return self

    def generation(self, g: int) -> np.ndarray:
        """Grid of generation g: stored, or recomputed from the nearest earlier stored one.

        Recomputing is only possible for deterministic automata; for probabilistic ones a
        generation that was not stored cannot be recovered.
        """
        if not 0 <= g <= self.last_generation:
            raise SimulationError(
                f"Generation {g} does not exist: this run has generations 0 to "
                f"{self.last_generation}."
            )
        if g in self.stored:
            return self.stored[g]
        if not self.is_deterministic:
            raise SimulationError(
                f"Generation {g} was not stored, and this automaton has random rules, so it "
                "cannot be recomputed. Run again with history 'all' to keep every generation."
            )
        base = max(s for s in self.stored if s < g)
        grid = self.stored[base]
        for _ in range(g - base):
            grid = step(self.automaton, grid)
        return grid


def check_generations(generations: int) -> None:
    if not isinstance(generations, int) or isinstance(generations, bool) or generations < 0:
        raise SimulationError("The number of generations must be a whole number, 0 or more.")
    if generations > MAX_GENERATIONS:
        raise SimulationError(
            f"At most {MAX_GENERATIONS:,} generations can be computed at once; continue the run "
            "for more."
        )


def check_settings(settings: RunSettings, automaton: Automaton, generations: int) -> None:
    if settings.history not in HISTORY_MODES:
        raise SimulationError(f"History must be one of: {', '.join(HISTORY_MODES)}.")
    if settings.history == "every" and (not isinstance(settings.every, int) or settings.every < 1):
        raise SimulationError("Keep every k-th generation: k must be a whole number, 1 or more.")
    check_generations(generations)
    if settings.history == "final":
        kept = 2
    elif settings.history == "every":
        kept = generations // settings.every + 2
    else:
        kept = generations + 1
    cells = automaton.grid.width * automaton.grid.height
    if kept * cells > MAX_STORED_BYTES:
        raise SimulationError(
            f"Storing {kept:,} generations of {cells:,} cells needs about "
            f"{kept * cells / 2**20:,.0f} MB. Keep every k-th generation or only the final one."
        )


def simulate(
    automaton: Automaton,
    world: np.ndarray,
    generations: int,
    settings: RunSettings | None = None,
    world_source: dict | None = None,
) -> Run:
    """Run `generations` steps from `world` (generation 0)."""
    settings = settings or RunSettings()
    check_settings(settings, automaton, generations)
    check_world(automaton, world)
    rng = np.random.default_rng(settings.seed) if needs_rng(automaton) else None
    initial = world.copy()
    run = Run(
        automaton=automaton,
        settings=settings,
        world_source=world_source or {"kind": "custom"},
        stored={0: initial},
        hashes=[grid_hash(initial)],
        populations=[np.bincount(initial.ravel(), minlength=len(automaton.states))],
        current=initial,
        rng=rng,
    )
    return run.advance(generations)
