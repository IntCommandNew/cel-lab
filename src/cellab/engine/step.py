"""One generation step (docs/DESIGN.md, sections 3 and 6).

Semantics:
1. Rules are checked in order; the first rule whose `from` matches the cell and whose condition
   holds decides the new state.
2. A probabilistic rule decides the cell only when its random draw succeeds; otherwise the next
   rules are still considered.
3. A cell no rule applies to keeps its state.
4. Everything is computed from the unchanged previous generation (synchronous update).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from cellab.engine.neighbors import NeighbourCounts
from cellab.model import AllOf, Always, Automaton, Condition, Count, Not, Rule

DTYPE = np.uint8


@dataclass(frozen=True)
class _CompiledRule:
    sources: tuple[int, ...] | None  # state indices, None = any
    target: int
    when: Condition
    probability: float | None


@lru_cache(maxsize=64)
def _compile(automaton: Automaton) -> tuple[_CompiledRule, ...]:
    index = {name: i for i, name in enumerate(automaton.state_names)}
    compiled = []
    for rule in automaton.rules:
        assert isinstance(rule, Rule)
        sources = None if rule.from_states is None else tuple(index[s] for s in rule.from_states)
        compiled.append(_CompiledRule(sources, index[rule.to], rule.when, rule.probability))
    return tuple(compiled)


def _condition(
    cond: Condition, counts: NeighbourCounts, index: dict[str, int]
) -> np.ndarray | bool:
    if isinstance(cond, Always):
        return True
    if isinstance(cond, Count):
        total = sum(counts[index[s]] for s in cond.states)
        v = cond.value
        match cond.op:
            case "eq":
                return total == v
            case "ne":
                return total != v
            case "lt":
                return total < v
            case "le":
                return total <= v
            case "gt":
                return total > v
            case "ge":
                return total >= v
            case "in":
                return np.isin(total, v)
            case "not_in":
                return ~np.isin(total, v)
            case _:  # between
                return (total >= v[0]) & (total <= v[1])
    if isinstance(cond, Not):
        return np.logical_not(_condition(cond.item, counts, index))
    parts = [_condition(c, counts, index) for c in cond.items]
    combine = np.logical_and if isinstance(cond, AllOf) else np.logical_or
    result = parts[0]
    for part in parts[1:]:
        result = combine(result, part)
    return result


def _elementary_step(automaton: Automaton, grid: np.ndarray) -> np.ndarray:
    code = automaton.rules[0].code
    table = np.array([(code >> i) & 1 for i in range(8)], dtype=DTYPE)
    counts = NeighbourCounts(automaton, grid)
    left, right = counts.neighbour(0, -1), counts.neighbour(0, 1)
    return table[4 * left.astype(np.intp) + 2 * grid + right]


def needs_rng(automaton: Automaton) -> bool:
    return any(isinstance(r, Rule) and r.probability is not None for r in automaton.rules)


def step(
    automaton: Automaton, grid: np.ndarray, rng: np.random.Generator | None = None
) -> np.ndarray:
    """Return the next generation; `grid` is not modified.

    `rng` is required when a rule has a probability (pass a seeded generator for reproducibility).
    """
    if automaton.is_elementary:
        return _elementary_step(automaton, grid)
    if rng is None and needs_rng(automaton):
        raise ValueError("This automaton has probabilistic rules: pass a seeded random generator.")
    index = {name: i for i, name in enumerate(automaton.state_names)}
    counts = NeighbourCounts(automaton, grid)
    new = grid.copy()
    decided = np.zeros(grid.shape, dtype=bool)
    for rule in _compile(automaton):
        candidates = ~decided
        if rule.sources is not None:
            candidates &= np.isin(grid, rule.sources)
        if not candidates.any():
            continue
        hit = candidates & _condition(rule.when, counts, index)
        if rule.probability is not None:
            hit &= rng.random(grid.shape) < rule.probability
        new[hit] = rule.target
        decided |= hit
    return new
