"""Formal automaton definition, shared by the validator, engine, storage and GUI.

The JSON form (see docs/DESIGN.md) is what the GUI builder and, later, the natural-language parser
produce. `automaton_from_dict` expects data that already passed `cellab.model.validate`; use
`validate()` / `load_definition()` to turn untrusted JSON into an `Automaton`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BOUNDARIES = ("wrap", "fixed")
NEIGHBORHOODS = ("moore", "von_neumann", "elementary")
# Comparisons a neighbour-count condition can use, with the type of value each one takes.
SCALAR_OPS = ("eq", "ne", "lt", "le", "gt", "ge")
LIST_OPS = ("in", "not_in")
RANGE_OPS = ("between",)
COUNT_OPS = SCALAR_OPS + LIST_OPS + RANGE_OPS
ANY_STATE = "any"


@dataclass(frozen=True)
class State:
    name: str
    symbol: str  # one keyboard character, used in text grids
    color: str  # "#RRGGBB"


@dataclass(frozen=True)
class Grid:
    width: int
    height: int
    boundary: str = "wrap"  # "wrap" (torus) or "fixed"
    fixed_state: str | None = None  # state assumed outside the grid when boundary == "fixed"


@dataclass(frozen=True)
class Neighborhood:
    type: str = "moore"
    radius: int = 1

    @property
    def size(self) -> int:
        """Number of neighbours each cell has."""
        r = self.radius
        if self.type == "moore":
            return (2 * r + 1) ** 2 - 1
        if self.type == "von_neumann":
            return 2 * r * (r + 1)
        return 2  # elementary: left and right


@dataclass(frozen=True)
class Always:
    pass


@dataclass(frozen=True)
class Count:
    """Number of neighbours whose state is one of `states`, compared using `op`."""

    states: tuple[str, ...]
    op: str
    value: int | tuple[int, ...]  # int for SCALAR_OPS, tuple for LIST_OPS, (low, high) for between


@dataclass(frozen=True)
class AllOf:
    items: tuple[Condition, ...]


@dataclass(frozen=True)
class AnyOf:
    items: tuple[Condition, ...]


@dataclass(frozen=True)
class Not:
    item: Condition


Condition = Always | Count | AllOf | AnyOf | Not


@dataclass(frozen=True)
class Rule:
    """A cell in one of `from_states` (None = any state) becomes `to` when `when` holds."""

    to: str
    from_states: tuple[str, ...] | None = None
    when: Condition = Always()
    probability: float | None = None  # None = always applies when the condition holds


@dataclass(frozen=True)
class ElementaryRule:
    """Wolfram elementary rule (0-255) for 1D automata with two states."""

    code: int


@dataclass(frozen=True)
class Automaton:
    name: str
    grid: Grid
    states: tuple[State, ...]
    default_state: str
    neighborhood: Neighborhood
    rules: tuple[Rule | ElementaryRule, ...]
    description: str = ""

    @property
    def state_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.states)

    def state_index(self, name: str) -> int:
        return self.state_names.index(name)

    @property
    def is_elementary(self) -> bool:
        return any(isinstance(r, ElementaryRule) for r in self.rules)


# --- JSON conversion ------------------------------------------------------------------------


def _states_value(states: tuple[str, ...]) -> str | list[str]:
    return states[0] if len(states) == 1 else list(states)


def condition_to_dict(cond: Condition) -> dict | str:
    if isinstance(cond, Always):
        return "always"
    if isinstance(cond, Count):
        value = list(cond.value) if isinstance(cond.value, tuple) else cond.value
        return {"count": _states_value(cond.states), cond.op: value}
    if isinstance(cond, AllOf):
        return {"all": [condition_to_dict(c) for c in cond.items]}
    if isinstance(cond, AnyOf):
        return {"any": [condition_to_dict(c) for c in cond.items]}
    return {"not": condition_to_dict(cond.item)}


def condition_from_dict(data: dict | str) -> Condition:
    if data == "always":
        return Always()
    if "all" in data:
        return AllOf(tuple(condition_from_dict(c) for c in data["all"]))
    if "any" in data:
        return AnyOf(tuple(condition_from_dict(c) for c in data["any"]))
    if "not" in data:
        return Not(condition_from_dict(data["not"]))
    states = data["count"]
    states = (states,) if isinstance(states, str) else tuple(states)
    op = next(k for k in data if k in COUNT_OPS)
    value = data[op]
    return Count(states, op, tuple(value) if isinstance(value, list) else value)


def rule_to_dict(rule: Rule | ElementaryRule) -> dict:
    if isinstance(rule, ElementaryRule):
        return {"kind": "elementary", "code": rule.code}
    out: dict = {
        "from": ANY_STATE if rule.from_states is None else _states_value(rule.from_states),
        "to": rule.to,
    }
    if not isinstance(rule.when, Always):
        out["when"] = condition_to_dict(rule.when)
    if rule.probability is not None:
        out["probability"] = rule.probability
    return out


def rule_from_dict(data: dict) -> Rule | ElementaryRule:
    if data.get("kind") == "elementary":
        return ElementaryRule(data["code"])
    source = data.get("from", ANY_STATE)
    if source == ANY_STATE:
        from_states = None
    else:
        from_states = (source,) if isinstance(source, str) else tuple(source)
    return Rule(
        to=data["to"],
        from_states=from_states,
        when=condition_from_dict(data.get("when", "always")),
        probability=data.get("probability"),
    )


def automaton_to_dict(a: Automaton) -> dict:
    boundary = "wrap" if a.grid.boundary == "wrap" else {"fixed": a.grid.fixed_state}
    out: dict = {"name": a.name}
    if a.description:
        out["description"] = a.description
    out |= {
        "grid": {"width": a.grid.width, "height": a.grid.height, "boundary": boundary},
        "states": [{"name": s.name, "symbol": s.symbol, "color": s.color} for s in a.states],
        "default_state": a.default_state,
        "neighborhood": {"type": a.neighborhood.type, "radius": a.neighborhood.radius},
        "rules": [rule_to_dict(r) for r in a.rules],
    }
    return out


def automaton_from_dict(data: dict) -> Automaton:
    """Build an Automaton from a definition that already passed validation."""
    g = data["grid"]
    boundary = g.get("boundary", "wrap")
    nb = data.get("neighborhood", {})
    return Automaton(
        name=data["name"],
        description=data.get("description", ""),
        grid=Grid(
            width=g["width"],
            height=g["height"],
            boundary="wrap" if boundary == "wrap" else "fixed",
            fixed_state=None if boundary == "wrap" else boundary["fixed"],
        ),
        states=tuple(State(s["name"], s["symbol"], s["color"]) for s in data["states"]),
        default_state=data["default_state"],
        neighborhood=Neighborhood(nb.get("type", "moore"), nb.get("radius", 1)),
        rules=tuple(rule_from_dict(r) for r in data["rules"]),
    )


def to_json(a: Automaton) -> str:
    return json.dumps(automaton_to_dict(a), indent=2) + "\n"


def save_definition(a: Automaton, path: str | Path) -> None:
    Path(path).write_text(to_json(a), encoding="utf-8")
