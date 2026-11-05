"""Initial-world settings, grid images and chart colours for the GUI. Pure Python + NumPy.

A world setting is a plain dict, also stored with saved runs as their `world_source`:

    {"kind": "random", "probabilities": {"alive": 0.3}, "seed": 1}
    {"kind": "centre", "state": "alive"}
    {"kind": "text", "text": ". # .\\n. # .\\n. # ."}
"""

from __future__ import annotations

import numpy as np

from cellab.engine import Run, centre_cell, empty_world, random_world, world_from_text
from cellab.model import Automaton

MAX_IMAGE_PX = 720  # widest grid image, in pixels
MAX_CELL_PX = 24
GRID_LINE = (0xC9, 0xCE, 0xD9)  # graticule hairline, as in the theme's borderColor
LINE_MIN_CELL_PX = 8  # draw cell borders only when cells are at least this big
CHART_FALLBACK = "#7A8094"  # graticule grey for state colours too pale to see on the page


def default_world(automaton: Automaton) -> dict:
    """A sensible first world: one centre cell for 1D automata, else 30% non-default cells."""
    others = [s for s in automaton.state_names if s != automaton.default_state]
    if automaton.is_elementary:
        return {"kind": "centre", "state": others[-1] if others else automaton.default_state}
    share = round(0.3 / len(others), 3) if others else 0.0
    return {"kind": "random", "probabilities": dict.fromkeys(others, share), "seed": 1}


def build_world(automaton: Automaton, setting: dict) -> np.ndarray:
    """Generation 0 for a world setting; raises WorldError with a readable message."""
    kind = setting["kind"]
    if kind == "random":
        return random_world(automaton, setting.get("probabilities", {}), setting.get("seed"))
    if kind == "centre":
        return centre_cell(automaton, setting["state"])
    if kind == "text":
        return world_from_text(automaton, setting.get("text", ""))
    return empty_world(automaton)


def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


def cell_size(width: int) -> int:
    return max(1, min(MAX_CELL_PX, MAX_IMAGE_PX // width))


def render(automaton: Automaton, grid: np.ndarray, cell: int | None = None) -> np.ndarray:
    """RGB image (uint8) of a grid of state indices: `cell` pixels per cell, exact colours,
    hairlines between cells when they are large enough to read individually."""
    cell = cell or cell_size(grid.shape[1])
    palette = np.array([_rgb(s.color) for s in automaton.states], dtype=np.uint8)
    image = palette[grid].repeat(cell, axis=0).repeat(cell, axis=1)
    if cell >= LINE_MIN_CELL_PX:
        image[::cell, :] = GRID_LINE
        image[:, ::cell] = GRID_LINE
        image[-1, :] = GRID_LINE
        image[:, -1] = GRID_LINE
    return image


def space_time(run: Run, upto: int) -> np.ndarray:
    """1D automata: generations 0..upto stacked as rows (time runs downwards)."""
    return np.concatenate([run.generation(g) for g in range(upto + 1)], axis=0)


def _luminance(color: str) -> float:
    r, g, b = (c / 255 for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def chart_colors(automaton: Automaton) -> list[str]:
    """Line colours per state; colours too pale for the slide-glass page become grey."""
    return [s.color if _luminance(s.color) < 0.85 else CHART_FALLBACK for s in automaton.states]


def generations_label(n: int) -> str:
    return f"{n} generation" if n == 1 else f"{n} generations"


# --- playback -------------------------------------------------------------------------------

PLAY_DELAYS = (0.1, 0.2, 0.5, 1.0, 2.0)  # seconds between generations


def next_view(options: list[int], current: int) -> tuple[int, bool]:
    """The generation shown after `current` during playback, and whether the end is reached."""
    later = [g for g in options if g > current]
    if not later:
        return options[-1], True
    return later[0], later[0] == options[-1]


def neighbour_view(options: list[int], current: int, step: int) -> int:
    """The generation one position before (step=-1) or after (step=+1) `current`."""
    i = options.index(current) if current in options else 0
    return options[max(0, min(len(options) - 1, i + step))]
