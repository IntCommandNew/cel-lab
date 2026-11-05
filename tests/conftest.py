import copy

import pytest

BASE_DEFINITION = {
    "name": "Test automaton",
    "grid": {"width": 10, "height": 8, "boundary": "wrap"},
    "states": [
        {"name": "dead", "symbol": ".", "color": "#F3F5F8"},
        {"name": "alive", "symbol": "#", "color": "#2E2A5C"},
    ],
    "default_state": "dead",
    "neighborhood": {"type": "moore", "radius": 1},
    "rules": [{"from": "dead", "to": "alive", "when": {"count": "alive", "eq": 3}}],
}


@pytest.fixture
def base_definition():
    """A small valid definition; tests modify their own deep copy."""
    return copy.deepcopy(BASE_DEFINITION)
