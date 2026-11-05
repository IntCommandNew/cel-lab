"""Plain-English rendering of a definition, so people can check what will be simulated.

Also the "canonical English" the Sprint 4 parser must read back into the same definition.
"""

from __future__ import annotations

from cellab.model.definition import (
    AllOf,
    Always,
    Automaton,
    Condition,
    Count,
    ElementaryRule,
    Not,
    Rule,
)


def _join(words: list[str], last: str = "or") -> str:
    if len(words) <= 1:
        return "".join(words)
    return f"{', '.join(words[:-1])} {last} {words[-1]}"


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def _numbers(values: tuple[int, ...] | list[int]) -> str:
    return _join([str(v) for v in values])


def _outside_phrase(values: list[int], noun) -> str:
    """Phrase for counts NOT in `values`; a consecutive run reads as a range."""
    low, high = values[0], values[-1]
    if len(values) == 1 or high - low + 1 != len(values):  # single value or gaps
        return f"a number of {noun()} other than {_numbers(values)}"
    if low <= 0:
        return f"more than {high} {noun(high)}"
    return f"fewer than {low} or more than {high} {noun()}"


def _count_phrase(cond: Count) -> str:
    """'exactly 3 alive neighbours' etc."""
    states = _join(list(cond.states))
    value = cond.value

    def noun(n: int | None = None) -> str:
        return f"{states} neighbour" + ("" if n == 1 else "s")

    match cond.op:
        case "eq":
            return f"exactly {value} {noun(value)}"
        case "ne":
            return f"a number of {noun()} other than {value}"
        case "lt":
            return f"fewer than {value} {noun()}"
        case "le":
            return f"at most {value} {noun(value)}"
        case "gt":
            return f"more than {value} {noun(value)}"
        case "ge":
            return f"at least {value} {noun(value)}"
        case "in":
            return f"exactly {_numbers(value)} {noun()}"
        case "not_in":
            return _outside_phrase(sorted(set(value)), noun)
        case _:  # between
            low, high = value
            return f"between {low} and {high} {noun()}"


def describe_condition(cond: Condition) -> str:
    """Phrase that completes 'if ...'."""
    if isinstance(cond, Always):
        return "always"
    if isinstance(cond, Count):
        return f"it has {_count_phrase(cond)}"
    if isinstance(cond, Not):
        return f"it is not true that {describe_condition(cond.item)}"
    joiner = "and" if isinstance(cond, AllOf) else "or"
    parts = [describe_condition(c) for c in cond.items]
    return f" {joiner} ".join(f"({p})" if " and " in p or " or " in p else p for p in parts)


def describe_rule(rule: Rule | ElementaryRule) -> str:
    if isinstance(rule, ElementaryRule):
        return (
            f"Elementary rule {rule.code}: each cell's next state depends on its own state and "
            "the states of its left and right neighbours."
        )
    if rule.from_states is None:
        subject = "Any cell"
    else:
        names = _join(list(rule.from_states))
        subject = f"{_article(names).capitalize()} {names} cell"
    if isinstance(rule.when, Always):
        text = f"{subject} always becomes {rule.to}"
    else:
        text = f"{subject} becomes {rule.to} if {describe_condition(rule.when)}"
    if rule.probability is not None:
        text += f", with probability {rule.probability:g}"
    return text + "."


def describe_grid(a: Automaton) -> str:
    size = f"{a.grid.width} x {a.grid.height}"
    if a.grid.boundary == "wrap":
        return f"{size}, edges wrap around"
    return f"{size}, cells outside the grid count as {a.grid.fixed_state}"


def describe_neighborhood(a: Automaton) -> str:
    nb = a.neighborhood
    if nb.type == "elementary":
        return "the left and right cell"
    reach = "" if nb.radius == 1 else f" within distance {nb.radius}"
    if nb.type == "moore":
        return f"the {nb.size} surrounding cells{reach}"
    return f"the {nb.size} cells above, below, left and right{reach}"


def describe(a: Automaton) -> str:
    lines = [a.name]
    if a.description:
        lines.append(a.description)
    states = ", ".join(f"{s.name} ({s.symbol})" for s in a.states)
    lines += [
        f"Grid: {describe_grid(a)}",
        f"States: {states}; empty cells are {a.default_state}",
        f"Neighbours: {describe_neighborhood(a)}",
        "Rules, checked in order (a cell no rule applies to keeps its state):",
    ]
    lines += [f"  {i}. {describe_rule(r)}" for i, r in enumerate(a.rules, 1)]
    return "\n".join(lines)
