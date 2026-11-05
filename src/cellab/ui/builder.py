"""Form builder logic: form values <-> definition JSON. Pure Python, no Streamlit.

The form covers the common case: one neighbour-count condition per rule (or none), an optional
probability, single or "any" source states, and elementary rules. Definitions with combined
conditions (all / any / not) or several source states are edited as JSON instead.

A form is a plain dict (it lives in Streamlit's session state):

    name, description, width, height, boundary ("wrap" | "fixed"), fixed_state,
    default_state, neighborhood ("moore" | "von_neumann" | "elementary"), radius,
    elementary_code, states: [{name, symbol, color}], rules: [{from, to, comparison, value,
    count, probability}]
"""

from __future__ import annotations

import copy
import math
import re

from cellab.model import Issue
from cellab.model.definition import ANY_STATE

# Wording used in the rules table, in the order offered to the user.
COMPARISONS = {
    "always": None,
    "exactly": "eq",
    "not": "ne",
    "fewer than": "lt",
    "at most": "le",
    "more than": "gt",
    "at least": "ge",
    "one of": "in",
    "none of": "not_in",
    "between": "between",
}
OP_TO_COMPARISON = {op: label for label, op in COMPARISONS.items() if op}
# Colours given to new states, in order (stain palette, see docs/DESIGN.md section 11).
STATE_COLORS = ["#F3F5F8", "#2E2A5C", "#D9467A", "#E8A33A", "#4F9D69", "#8E86C9", "#7A8094"]
SYMBOLS = ".#*o+x@%&=~^"

STATE_COLUMNS = ("name", "symbol", "color")
RULE_COLUMNS = ("from", "to", "comparison", "value", "count", "probability")


def blank_form() -> dict:
    return {
        "name": "My automaton",
        "description": "",
        "width": 40,
        "height": 30,
        "boundary": "wrap",
        "fixed_state": "dead",
        "default_state": "dead",
        "neighborhood": "moore",
        "radius": 1,
        "elementary_code": 30,
        "states": [
            {"name": "dead", "symbol": ".", "color": STATE_COLORS[0]},
            {"name": "alive", "symbol": "#", "color": STATE_COLORS[1]},
        ],
        "rules": [],
    }


def _blank(value: object) -> bool:
    """Empty table cell: None, "", or NaN (pandas uses NaN for empty number cells)."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def _text(value: object) -> str:
    return "" if _blank(value) else str(value).strip()


def _format_value(op: str, value) -> str:
    if op == "between":
        return f"{value[0]}-{value[1]}"
    if isinstance(value, list | tuple):
        return ", ".join(str(v) for v in value)
    return str(value)


# --- definition -> form ---------------------------------------------------------------------


def form_from_definition(data: dict) -> tuple[dict | None, str | None]:
    """Form values for a (valid) definition, or (None, reason) if the form cannot show it."""
    grid = data["grid"]
    boundary = grid.get("boundary", "wrap")
    nb = data.get("neighborhood", {})
    names = [s["name"] for s in data["states"]]
    form = blank_form() | {
        "name": data["name"],
        "description": data.get("description", ""),
        "width": grid["width"],
        "height": grid["height"],
        "boundary": "wrap" if boundary == "wrap" else "fixed",
        "fixed_state": names[0] if boundary == "wrap" else boundary["fixed"],
        "default_state": data["default_state"],
        "neighborhood": nb.get("type", "moore"),
        "radius": nb.get("radius", 1),
        "states": [{k: s[k] for k in STATE_COLUMNS} for s in data["states"]],
        "rules": [],
    }
    for i, rule in enumerate(data["rules"], 1):
        if rule.get("kind") == "elementary":
            form["elementary_code"] = rule["code"]
            continue
        source = rule.get("from", ANY_STATE)
        if isinstance(source, list):
            if len(source) != 1:
                return None, f"Rule {i} starts from several states, which the form cannot show."
            source = source[0]
        row = {
            "from": source,
            "to": rule["to"],
            "comparison": "always",
            "value": "",
            "count": None,
            "probability": rule.get("probability"),
        }
        when = rule.get("when", "always")
        if when != "always":
            if "count" not in when:
                return None, f"Rule {i} combines several conditions, which the form cannot show."
            counted = when["count"]
            if isinstance(counted, list):
                if len(counted) != 1:
                    return None, f"Rule {i} counts several states at once; edit it as JSON."
                counted = counted[0]
            op = next(k for k in when if k != "count")
            row |= {
                "comparison": OP_TO_COMPARISON[op],
                "value": _format_value(op, when[op]),
                "count": counted,
            }
        form["rules"].append(row)
    return form, None


# --- form -> definition ---------------------------------------------------------------------


def _numbers(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\d+", text)]


def _fill_states(rows: list[dict]) -> list[dict]:
    """Non-empty state rows, with a symbol and colour filled in when left empty."""
    states = []
    for row in rows:
        if all(_blank(row.get(k)) for k in STATE_COLUMNS):
            continue
        states.append({k: _text(row.get(k)) for k in STATE_COLUMNS})
    used = {s["symbol"] for s in states if s["symbol"]}
    for i, state in enumerate(states):
        if not state["symbol"]:
            candidates = [state["name"][:1]] + list(SYMBOLS)
            free = next((c for c in candidates if c and c not in used and "!" <= c <= "~"), "")
            state["symbol"] = free
            used.add(free)
        if not state["color"]:
            state["color"] = STATE_COLORS[i % len(STATE_COLORS)]
    return states


def _rule_from_row(row: dict, number: int) -> tuple[dict, list[Issue]]:
    path = f"form.rules[{number - 1}]"
    label = f"Rule {number}"
    rule: dict = {"from": _text(row.get("from")) or ANY_STATE}
    if not _blank(row.get("to")):
        rule["to"] = _text(row.get("to"))
    comparison = _text(row.get("comparison")) or "always"
    issues = []
    if comparison not in COMPARISONS:
        issues.append(Issue("error", f"{path}.comparison", f"{label}: unknown comparison."))
    elif COMPARISONS[comparison] is not None:
        op = COMPARISONS[comparison]
        counted = _text(row.get("count"))
        numbers = _numbers(_text(row.get("value")))
        if not counted:
            issues.append(
                Issue("error", f"{path}.count", f"{label}: choose which neighbours to count.")
            )
        if op in ("in", "not_in"):
            value = numbers
            ok = len(numbers) >= 1
            example = "one or more numbers, e.g. 2, 3"
        elif op == "between":
            value = numbers[:2]
            ok = len(numbers) == 2
            example = "two numbers, e.g. 2-4"
        else:
            value = numbers[0] if numbers else None
            ok = len(numbers) == 1
            example = "one whole number, e.g. 3"
        if not ok:
            issues.append(
                Issue("error", f"{path}.value", f"{label}: '{comparison}' needs {example}.")
            )
        rule["when"] = {"count": counted, op: value}
    probability = row.get("probability")
    if not _blank(probability):
        rule["probability"] = float(probability)
    return rule, issues


def _empty_rule_row(row: dict) -> bool:
    filled = [k for k in RULE_COLUMNS if not _blank(row.get(k))]
    return filled == [] or filled == ["comparison"] and row["comparison"] == "always"


def definition_from_form(form: dict) -> tuple[dict, list[Issue]]:
    """Definition JSON built from the form, plus problems only the form can detect.

    The result still has to pass `cellab.model.validate`, which checks everything else.
    """
    elementary = form["neighborhood"] == "elementary"
    states = _fill_states(form["states"])
    names = [s["name"] for s in states]
    data: dict = {"name": _text(form["name"])}
    if _text(form.get("description")):
        data["description"] = _text(form["description"])
    boundary = "wrap" if form["boundary"] == "wrap" else {"fixed": form["fixed_state"]}
    default = form["default_state"]
    if default not in names:
        default = names[0] if names else ""
    radius = 1 if elementary else int(form["radius"])
    data |= {
        "grid": {
            "width": int(form["width"]),
            "height": 1 if elementary else int(form["height"]),
            "boundary": boundary,
        },
        "states": states,
        "default_state": default,
        "neighborhood": {"type": form["neighborhood"], "radius": radius},
        "rules": [],
    }
    issues: list[Issue] = []
    if elementary:
        data["rules"] = [{"kind": "elementary", "code": int(form["elementary_code"])}]
        return data, issues
    number = 0
    for row in form["rules"]:
        if _empty_rule_row(row):
            continue  # a row the user added but did not fill in
        number += 1
        rule, rule_issues = _rule_from_row(row, number)
        data["rules"].append(rule)
        issues += rule_issues
    return data, issues


def copy_form(form: dict) -> dict:
    return copy.deepcopy(form)


# --- renaming states ------------------------------------------------------------------------


def renamed_states(before: list[dict], after: dict[int, dict]) -> dict[str, str]:
    """{old name: new name} for state rows whose name was changed in the table.

    `before` are the rows the table started from (row label = position); `after` maps the row
    labels still present to their edited values. Rows added or deleted are not renames.
    """
    renames = {}
    for label, row in after.items():
        if not isinstance(label, int) or not 0 <= label < len(before):
            continue
        old, new = _text(before[label].get("name")), _text(row.get("name"))
        if old and new and old != new:
            renames[old] = new
    return renames


def apply_renames(form: dict, renames: dict[str, str]) -> dict:
    """Copy of `form` where every reference to a renamed state uses the new name."""
    form = copy_form(form)
    for key in ("default_state", "fixed_state"):
        form[key] = renames.get(form[key], form[key])
    for row in form["rules"]:
        for key in ("from", "to", "count"):
            value = _text(row.get(key))
            if value in renames:
                row[key] = renames[value]
    return form
