"""Initial worlds (docs/DESIGN.md, section 5): text grids, random worlds, single centre cell.

All functions return a fresh uint8 grid of state indices with the automaton's grid shape.
Problems are raised as `WorldError` with a message meant for the person entering the world.
"""

from __future__ import annotations

import numpy as np

from cellab.engine.step import DTYPE
from cellab.model import Automaton


class WorldError(ValueError):
    pass


def empty_world(automaton: Automaton) -> np.ndarray:
    g = automaton.grid
    return np.full((g.height, g.width), automaton.state_index(automaton.default_state), DTYPE)


def parse_pattern(automaton: Automaton, text: str) -> np.ndarray:
    """Parse rows of state symbols, e.g. ". # ." or ".#.". Spaces between symbols are optional."""
    symbols = {s.symbol: i for i, s in enumerate(automaton.states)}
    rows = []
    for line in text.splitlines():
        cells = [c for c in line if not c.isspace()]
        if cells:
            rows.append(cells)
    if not rows:
        raise WorldError("The world is empty: enter at least one row of symbols.")
    width = len(rows[0])
    for n, row in enumerate(rows, 1):
        if len(row) != width:
            raise WorldError(
                f"Row {n} has {len(row)} cells, but row 1 has {width}. All rows need the same "
                "number of cells."
            )
        unknown = sorted({c for c in row if c not in symbols})
        if unknown:
            known = ", ".join(f"{s.symbol} ({s.name})" for s in automaton.states)
            raise WorldError(f"Row {n} uses unknown symbols {', '.join(unknown)}. Use: {known}.")
    return np.array([[symbols[c] for c in row] for row in rows], dtype=DTYPE)


def place(world: np.ndarray, pattern: np.ndarray, top: int | None = None, left: int | None = None):
    """Copy `pattern` into `world` (in place); centred when top/left are not given."""
    h, w = pattern.shape
    height, width = world.shape
    if h > height or w > width:
        raise WorldError(
            f"The pattern is {w} x {h} cells but the grid is only {width} x {height}. "
            "Make the grid larger or the pattern smaller."
        )
    # centre the pattern on the same cell centre_cell() uses: (height // 2, width // 2)
    top = height // 2 - h // 2 if top is None else top
    left = width // 2 - w // 2 if left is None else left
    if not (0 <= top <= height - h and 0 <= left <= width - w):
        raise WorldError(f"A {w} x {h} pattern at row {top}, column {left} does not fit the grid.")
    world[top : top + h, left : left + w] = pattern
    return world


def world_from_text(
    automaton: Automaton, text: str, top: int | None = None, left: int | None = None
) -> np.ndarray:
    """Text grid placed on an otherwise default world (centred unless top/left are given)."""
    return place(empty_world(automaton), parse_pattern(automaton, text), top, left)


def random_world(
    automaton: Automaton, probabilities: dict[str, float], seed: int | None
) -> np.ndarray:
    """Each cell independently gets a state with the given probability; the rest of the
    probability goes to the default state. Same seed, same world."""
    names = automaton.state_names
    p = np.zeros(len(names))
    for name, value in probabilities.items():
        if name not in names:
            raise WorldError(f"Unknown state '{name}'. Declared states: {', '.join(names)}.")
        if not 0 <= value <= 1:
            raise WorldError(f"The probability of '{name}' must be between 0 and 1.")
        p[names.index(name)] = value
    default = automaton.state_index(automaton.default_state)
    rest = 1 - (p.sum() - p[default])
    if rest < -1e-9:
        raise WorldError("The probabilities add up to more than 1.")
    p[default] = max(rest, 0.0)
    g = automaton.grid
    rng = np.random.default_rng(seed)
    return rng.choice(len(names), size=(g.height, g.width), p=p / p.sum()).astype(DTYPE)


def centre_cell(automaton: Automaton, state: str) -> np.ndarray:
    """Default world with one cell of `state` in the middle (e.g. Rule 30's starting row)."""
    if state not in automaton.state_names:
        raise WorldError(f"Unknown state '{state}'.")
    world = empty_world(automaton)
    h, w = world.shape
    world[h // 2, w // 2] = automaton.state_index(state)
    return world


def world_to_text(automaton: Automaton, world: np.ndarray, sep: str = " ") -> str:
    symbols = [s.symbol for s in automaton.states]
    return "\n".join(sep.join(symbols[v] for v in row) for row in world)


def check_world(automaton: Automaton, world: np.ndarray) -> None:
    """Raise WorldError if `world` does not fit the automaton (shape, state indices)."""
    g = automaton.grid
    if world.shape != (g.height, g.width):
        raise WorldError(
            f"The world is {world.shape[1]} x {world.shape[0]} cells; the automaton needs "
            f"{g.width} x {g.height}."
        )
    if world.size and int(world.max()) >= len(automaton.states):
        raise WorldError("The world contains a state the automaton does not declare.")
