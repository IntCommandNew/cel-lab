"""Validation of automaton definitions (docs/DESIGN.md, section 4).

Turns untrusted JSON (pasted, uploaded, built in the GUI or produced by the parser) into an
`Automaton`, or explains what is wrong. Every issue has a level ("error" blocks simulation,
"warning" is shown but allowed), a path to the field (e.g. "rules[1].when") and a message written
for the person fixing the definition. Rules are numbered from 1 in messages.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from cellab.model.definition import (
    ANY_STATE,
    COUNT_OPS,
    LIST_OPS,
    NEIGHBORHOODS,
    RANGE_OPS,
    Automaton,
    automaton_from_dict,
)

MAX_GRID_SIDE = 1000
MAX_STATES = 256  # grids store state indices as uint8
MAX_RADIUS = 5
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
TOP_LEVEL_KEYS = {"name", "description", "grid", "states", "default_state", "neighborhood", "rules"}
RULE_KEYS = {"from", "to", "when", "probability"}
NEIGHBORHOOD_NAMES = {
    "moore": "Moore (8 surrounding cells at radius 1)",
    "von_neumann": "von Neumann (4 orthogonal cells at radius 1)",
    "elementary": "elementary (left and right cell, for 1D automata)",
}


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning"
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


@dataclass
class ValidationResult:
    automaton: Automaton | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return self.automaton is not None


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _quote_list(names: list[str]) -> str:
    return ", ".join(names) if names else "(none)"


class _Checker:
    def __init__(self) -> None:
        self.issues: list[Issue] = []
        self.states: list[str] = []
        self.neighbours: int | None = None  # neighbourhood size, once known to be valid

    def error(self, path: str, message: str) -> None:
        self.issues.append(Issue("error", path, message))

    def warn(self, path: str, message: str) -> None:
        self.issues.append(Issue("warning", path, message))

    def unknown_keys(self, data: dict, allowed: set[str], path: str, what: str) -> None:
        for key in sorted(set(data) - allowed):
            where = f"{path}.{key}" if path else key
            self.warn(where, f"'{key}' is not a known {what} field and is ignored.")

    def state_ref(self, value: object, path: str, what: str) -> bool:
        if not isinstance(value, str) or not value:
            self.error(path, f"{what} must be the name of a state.")
            return False
        if value not in self.states:
            self.error(
                path,
                f"{what} uses the state '{value}', which is not declared. "
                f"Declared states: {_quote_list(self.states)}.",
            )
            return False
        return True

    # --- sections ---------------------------------------------------------------------------

    def check(self, data: object) -> None:
        if not isinstance(data, dict):
            self.error("", "The definition must be a JSON object: { ... }.")
            return
        self.unknown_keys(data, TOP_LEVEL_KEYS, "", "definition")
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            self.error("name", 'Give the automaton a name, e.g. "Game of Life".')
        if "description" in data and not isinstance(data["description"], str):
            self.error("description", "The description must be text.")
        self.check_states(data.get("states"))
        if "default_state" not in data:
            self.error("default_state", "Choose the default state (used for empty cells).")
        elif self.states:
            self.state_ref(data["default_state"], "default_state", "The default state")
        self.check_grid(data.get("grid"))
        nb_type = self.check_neighborhood(data.get("neighborhood", {}))
        self.check_rules(data.get("rules"), nb_type, data.get("grid"))

    def check_states(self, states: object) -> None:
        if not isinstance(states, list) or not states:
            self.error("states", "Declare at least one state, e.g. dead and alive.")
            return
        if len(states) > MAX_STATES:
            self.error("states", f"At most {MAX_STATES} states are supported.")
        seen_names: set[str] = set()
        seen_symbols: set[str] = set()
        for i, state in enumerate(states):
            path = f"states[{i}]"
            if not isinstance(state, dict):
                self.error(path, "Each state must be an object with a name, symbol and color.")
                continue
            self.unknown_keys(state, {"name", "symbol", "color"}, path, "state")
            name = state.get("name")
            if not isinstance(name, str) or not name.strip():
                self.error(f"{path}.name", f"State {i + 1} needs a name.")
            elif name != name.strip() or name == ANY_STATE:
                self.error(
                    f"{path}.name",
                    f"'{name}' cannot be a state name"
                    + (" ('any' means every state in rules)." if name == ANY_STATE else "")
                    + (" Remove the spaces around it." if name != name.strip() else ""),
                )
            elif name.lower() in seen_names:
                self.error(f"{path}.name", f"The state name '{name}' is used twice.")
            else:
                seen_names.add(name.lower())
                self.states.append(name)
            symbol = state.get("symbol")
            if not (isinstance(symbol, str) and len(symbol) == 1 and "!" <= symbol <= "~"):
                self.error(
                    f"{path}.symbol",
                    f"The symbol of state {i + 1} must be one visible keyboard character, "
                    "e.g. '.' or '#'.",
                )
            elif symbol in seen_symbols:
                self.error(f"{path}.symbol", f"The symbol '{symbol}' is used by two states.")
            else:
                seen_symbols.add(symbol)
            color = state.get("color")
            if not (isinstance(color, str) and COLOR.match(color)):
                self.error(
                    f"{path}.color",
                    f'The color of state {i + 1} must be a hex color like "#2E2A5C".',
                )
        if len(states) == 1:
            self.warn("states", "With a single state nothing can ever change.")

    def check_grid(self, grid: object) -> None:
        if not isinstance(grid, dict):
            self.error("grid", 'Describe the grid: {"width": 40, "height": 30}.')
            return
        self.unknown_keys(grid, {"width", "height", "boundary"}, "grid", "grid")
        for side in ("width", "height"):
            value = grid.get(side)
            if not _is_int(value) or not 1 <= value <= MAX_GRID_SIDE:
                self.error(
                    f"grid.{side}",
                    f"The grid {side} must be a whole number from 1 to {MAX_GRID_SIDE}.",
                )
        boundary = grid.get("boundary", "wrap")
        if boundary == "wrap":
            return
        if isinstance(boundary, dict) and set(boundary) == {"fixed"}:
            if self.states:
                self.state_ref(boundary["fixed"], "grid.boundary.fixed", "The fixed boundary")
            return
        self.error(
            "grid.boundary",
            'The boundary must be "wrap" (edges join up) or {"fixed": "<state>"} '
            "(cells outside the grid count as that state).",
        )

    def check_neighborhood(self, nb: object) -> str | None:
        if not isinstance(nb, dict):
            self.error(
                "neighborhood", 'The neighborhood must be an object, e.g. {"type": "moore"}.'
            )
            return None
        self.unknown_keys(nb, {"type", "radius"}, "neighborhood", "neighborhood")
        nb_type = nb.get("type", "moore")
        radius = nb.get("radius", 1)
        ok = True
        if nb_type not in NEIGHBORHOODS:
            self.error(
                "neighborhood.type",
                f"Unknown neighborhood '{nb_type}'. Use one of: "
                + "; ".join(f'"{k}" - {v}' for k, v in NEIGHBORHOOD_NAMES.items())
                + ".",
            )
            ok = False
        if not _is_int(radius) or not 1 <= radius <= MAX_RADIUS:
            self.error(
                "neighborhood.radius",
                f"The radius must be a whole number from 1 to {MAX_RADIUS}.",
            )
            ok = False
        elif nb_type == "elementary" and radius != 1:
            self.error("neighborhood.radius", "The elementary neighborhood always has radius 1.")
            ok = False
        if not ok:
            return None
        if nb_type == "moore":
            self.neighbours = (2 * radius + 1) ** 2 - 1
        elif nb_type == "von_neumann":
            self.neighbours = 2 * radius * (radius + 1)
        else:
            self.neighbours = 2
        return nb_type

    def check_rules(self, rules: object, nb_type: str | None, grid: object) -> None:
        if not isinstance(rules, list):
            self.error("rules", 'List the rules: [ {"from": ..., "to": ..., "when": ...} ].')
            return
        if not rules:
            self.warn("rules", "There are no rules, so nothing will ever change.")
            return
        elementary = [i for i, r in enumerate(rules) if isinstance(r, dict) and "kind" in r]
        for i, rule in enumerate(rules):
            path = f"rules[{i}]"
            if not isinstance(rule, dict):
                self.error(path, f"Rule {i + 1} must be an object.")
            elif "kind" in rule:
                self.check_elementary(rule, path, i, len(rules), nb_type, grid)
            else:
                self.check_rule(rule, path, i)
        if not elementary:
            self.check_shadowing(rules)

    def check_elementary(
        self, rule: dict, path: str, i: int, n_rules: int, nb_type: str | None, grid: object
    ) -> None:
        if rule.get("kind") != "elementary":
            self.error(f"{path}.kind", 'The only special rule kind is "elementary".')
            return
        self.unknown_keys(rule, {"kind", "code"}, path, "elementary rule")
        code = rule.get("code")
        if not _is_int(code) or not 0 <= code <= 255:
            self.error(f"{path}.code", "An elementary rule code is a whole number from 0 to 255.")
        if n_rules > 1:
            self.error(path, "An elementary rule must be the only rule of the automaton.")
        if nb_type is not None and nb_type != "elementary":
            self.error(
                "neighborhood.type",
                'Elementary rules need the "elementary" neighborhood (left and right cell).',
            )
        if len(self.states) != 2:
            self.error("states", "Elementary rules need exactly two states (0 and 1, in order).")
        if isinstance(grid, dict) and grid.get("height") != 1:
            self.error("grid.height", "Elementary automata are one-dimensional: use height 1.")

    def check_rule(self, rule: dict, path: str, i: int) -> None:
        label = f"Rule {i + 1}"
        self.unknown_keys(rule, RULE_KEYS, path, "rule")
        source = rule.get("from", ANY_STATE)
        if isinstance(source, list):
            if not source:
                self.error(f"{path}.from", f"{label}: list at least one state in 'from'.")
            for j, name in enumerate(source):
                self.state_ref(name, f"{path}.from[{j}]", label)
        elif source != ANY_STATE:
            self.state_ref(source, f"{path}.from", label)
        if "to" not in rule:
            self.error(f"{path}.to", f"{label} needs a target state ('to').")
        else:
            self.state_ref(rule["to"], f"{path}.to", label)
        if "when" in rule:
            self.check_condition(rule["when"], f"{path}.when", label)
        if "probability" in rule:
            p = rule["probability"]
            if not _is_number(p) or not 0 < p <= 1:
                self.error(
                    f"{path}.probability",
                    f"{label}: the probability must be a number greater than 0 and at most 1.",
                )
        if isinstance(source, str) and source == rule.get("to"):
            self.warn(path, f"{label} changes '{source}' into itself, so it has no effect.")

    def check_condition(self, cond: object, path: str, label: str) -> None:
        if cond == "always":
            return
        if not isinstance(cond, dict):
            self.error(
                path,
                f'{label}: a condition is "always" or an object like '
                '{"count": "alive", "eq": 3}.',
            )
            return
        combinators = [k for k in ("all", "any", "not") if k in cond]
        if combinators:
            key = combinators[0]
            if len(cond) != 1:
                self.error(path, f"{label}: '{key}' must be the only key of its condition.")
                return
            if key == "not":
                self.check_condition(cond["not"], f"{path}.not", label)
                return
            items = cond[key]
            if not isinstance(items, list) or not items:
                self.error(f"{path}.{key}", f"{label}: '{key}' needs a list of conditions.")
                return
            for j, item in enumerate(items):
                self.check_condition(item, f"{path}.{key}[{j}]", label)
            return
        if "count" not in cond:
            self.error(path, f"{label}: a condition needs 'count', 'all', 'any' or 'not'.")
            return
        states = cond["count"]
        names = [states] if isinstance(states, str) else states
        if not isinstance(names, list) or not names:
            self.error(f"{path}.count", f"{label}: 'count' takes a state or a list of states.")
        else:
            for j, name in enumerate(names):
                where = f"{path}.count" if isinstance(states, str) else f"{path}.count[{j}]"
                self.state_ref(name, where, label)
        ops = [k for k in cond if k != "count"]
        if len(ops) != 1 or ops[0] not in COUNT_OPS:
            self.error(
                path,
                f"{label}: compare the count with exactly one of: {', '.join(COUNT_OPS)} "
                '(e.g. {"count": "alive", "eq": 3}).',
            )
            return
        self.check_count_value(ops[0], cond[ops[0]], f"{path}.{ops[0]}", label)

    def check_count_value(self, op: str, value: object, path: str, label: str) -> None:
        n = self.neighbours
        if op in LIST_OPS:
            if not isinstance(value, list) or not value or not all(_is_int(v) for v in value):
                self.error(path, f"{label}: '{op}' takes a list of whole numbers, e.g. [2, 3].")
                return
            if n is not None and op == "in":
                outside = [v for v in value if not 0 <= v <= n]
                if len(outside) == len(value):
                    self.error(path, f"{label} can never apply: a cell has 0 to {n} neighbours.")
                elif outside:
                    self.warn(path, f"{label}: {outside} can never occur (0 to {n} neighbours).")
            return
        if op in RANGE_OPS:
            if not (isinstance(value, list) and len(value) == 2 and all(_is_int(v) for v in value)):
                self.error(path, f"{label}: 'between' takes two whole numbers, e.g. [2, 4].")
                return
            low, high = value
            if low > high:
                self.error(path, f"{label}: 'between' needs the smaller number first.")
            elif n is not None and (low > n or high < 0):
                self.error(path, f"{label} can never apply: a cell has 0 to {n} neighbours.")
            return
        if not _is_int(value):
            self.error(path, f"{label}: '{op}' takes a whole number.")
            return
        if n is None:
            return
        never = {
            "eq": not 0 <= value <= n,
            "lt": value <= 0,
            "le": value < 0,
            "gt": value >= n,
            "ge": value > n,
            "ne": False,
        }[op]
        if never:
            self.error(path, f"{label} can never apply: a cell has 0 to {n} neighbours.")

    def check_shadowing(self, rules: list) -> None:
        """Warn about rules that can never be reached because an earlier rule always wins."""
        covered: set[str] = set()  # states already fully decided by an unconditional rule
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                continue
            source = rule.get("from", ANY_STATE)
            sources = (
                set(self.states)
                if source == ANY_STATE
                else (
                    {source}
                    if isinstance(source, str)
                    else set(source)
                    if isinstance(source, list) and all(isinstance(s, str) for s in source)
                    else set()
                )
            )
            if sources and sources <= covered:
                self.warn(
                    f"rules[{i}]",
                    f"Rule {i + 1} never applies: earlier rules always decide "
                    f"{_quote_list(sorted(sources))} cells first.",
                )
            if rule.get("when", "always") == "always" and "probability" not in rule:
                covered |= sources


def validate(data: object) -> ValidationResult:
    """Check a parsed JSON definition; build the Automaton when there are no errors."""
    checker = _Checker()
    checker.check(data)
    errors = [i for i in checker.issues if i.level == "error"]
    automaton = None if errors else automaton_from_dict(data)  # type: ignore[arg-type]
    return ValidationResult(automaton, checker.issues)


def validate_json(text: str) -> ValidationResult:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return ValidationResult(
            None,
            [
                Issue(
                    "error",
                    "",
                    f"This is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}.",
                )
            ],
        )
    return validate(data)


def load_definition(path: str | Path) -> ValidationResult:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationResult(None, [Issue("error", "", f"Cannot read {path}: {exc.strerror}.")])
    return validate_json(text)
