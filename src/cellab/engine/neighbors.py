"""Neighbour counting with NumPy (docs/DESIGN.md, section 6).

The grid is padded once according to the boundary ("wrap" copies the opposite edge, "fixed" adds
cells of the fixed state); every neighbour offset is then a slice of the padded array, so counting
is vectorised and never reads a cell that was already updated.
"""

from __future__ import annotations

import numpy as np

from cellab.model import Automaton, Neighborhood


def offsets(nb: Neighborhood) -> list[tuple[int, int]]:
    """(dy, dx) of every neighbour, row-major order, without the cell itself."""
    if nb.type == "elementary":
        return [(0, -1), (0, 1)]
    r = nb.radius
    result = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if (dy, dx) == (0, 0):
                continue
            if nb.type == "von_neumann" and abs(dy) + abs(dx) > r:
                continue
            result.append((dy, dx))
    return result


def pad(automaton: Automaton, grid: np.ndarray, r: int) -> np.ndarray:
    if automaton.grid.boundary == "wrap":
        return np.pad(grid, r, mode="wrap")
    fill = automaton.state_index(automaton.grid.fixed_state)
    return np.pad(grid, r, mode="constant", constant_values=fill)


class NeighbourCounts:
    """Lazily computed per-state neighbour counts for one generation.

    `counts[i]` is an int16 array of shape (height, width): how many neighbours of each cell are
    in state index i. Only the states that rules actually ask about are computed.
    """

    def __init__(self, automaton: Automaton, grid: np.ndarray) -> None:
        nb = automaton.neighborhood
        self._r = 1 if nb.type == "elementary" else nb.radius
        self._offsets = offsets(nb)
        self._padded = pad(automaton, grid, self._r)
        self._shape = grid.shape
        self._cache: dict[int, np.ndarray] = {}

    def neighbour(self, dy: int, dx: int) -> np.ndarray:
        """State of the neighbour at offset (dy, dx) for every cell."""
        h, w = self._shape
        r = self._r
        return self._padded[r + dy : r + dy + h, r + dx : r + dx + w]

    def __getitem__(self, state: int) -> np.ndarray:
        if state not in self._cache:
            total = np.zeros(self._shape, dtype=np.int16)
            for dy, dx in self._offsets:
                total += self.neighbour(dy, dx) == state
            self._cache[state] = total
        return self._cache[state]
