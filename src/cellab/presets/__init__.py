"""Ready-made definitions of known automata (the "pick a preset" option in the GUI).

Each preset is a JSON file in this package; its id is the file name without `.json`.
"""

from __future__ import annotations

from pathlib import Path

from cellab.model.validate import ValidationResult, load_definition

PRESET_DIR = Path(__file__).parent


def preset_ids() -> list[str]:
    return sorted(p.stem for p in PRESET_DIR.glob("*.json"))


def preset_path(preset_id: str) -> Path:
    path = PRESET_DIR / f"{preset_id}.json"
    if path.parent != PRESET_DIR or not path.is_file():
        raise KeyError(f"Unknown preset '{preset_id}'. Available: {', '.join(preset_ids())}.")
    return path


def load_preset(preset_id: str) -> ValidationResult:
    return load_definition(preset_path(preset_id))
