import pytest

from cellab.model import (
    AllOf,
    AnyOf,
    Count,
    Not,
    Rule,
    describe,
    describe_rule,
)
from cellab.presets import load_preset


def test_game_of_life_summary():
    text = describe(load_preset("game-of-life").automaton)
    assert text.splitlines()[2:] == [
        "Grid: 40 x 30, edges wrap around",
        "States: dead (.), alive (#); empty cells are dead",
        "Neighbours: the 8 surrounding cells",
        "Rules, checked in order (a cell no rule applies to keeps its state):",
        "  1. An alive cell becomes dead if it has fewer than 2 or more than 3 alive neighbours.",
        "  2. A dead cell becomes alive if it has exactly 3 alive neighbours.",
    ]


def test_fixed_boundary_and_unconditional_rules():
    text = describe(load_preset("forest-fire").automaton)
    assert "cells outside the grid count as empty" in text
    assert "1. A fire cell always becomes empty." in text
    assert "2. A tree cell becomes fire if it has at least 1 fire neighbour." in text


def test_elementary_rule():
    text = describe(load_preset("rule-30").automaton)
    assert "Neighbours: the left and right cell" in text
    assert "Elementary rule 30:" in text


@pytest.mark.parametrize(
    "rule,expected",
    [
        (Rule("alive", ("dead",), Count(("alive",), "eq", 1)), "exactly 1 alive neighbour."),
        (Rule("alive", ("dead",), Count(("alive",), "lt", 2)), "fewer than 2 alive neighbours."),
        (Rule("alive", ("dead",), Count(("alive",), "le", 1)), "at most 1 alive neighbour."),
        (Rule("alive", ("dead",), Count(("alive",), "gt", 3)), "more than 3 alive neighbours."),
        (
            Rule("alive", ("dead",), Count(("alive",), "between", (2, 4))),
            "between 2 and 4 alive neighbours.",
        ),
        (
            Rule("alive", ("dead",), Count(("alive",), "in", (3, 6))),
            "exactly 3 or 6 alive neighbours.",
        ),
        (
            Rule("alive", ("dead",), Count(("alive", "dying"), "ge", 2)),
            "at least 2 alive or dying neighbours.",
        ),
        (
            Rule("dead", ("alive",), Count(("alive",), "not_in", (3, 2))),
            "fewer than 2 or more than 3 alive neighbours.",
        ),
        (
            Rule("dead", ("alive",), Count(("alive",), "not_in", (0, 1, 2))),
            "more than 2 alive neighbours.",
        ),
        (
            Rule("dead", ("alive",), Count(("alive",), "not_in", (2, 4))),
            "a number of alive neighbours other than 2 or 4.",
        ),
        (
            Rule("dead", ("alive",), Count(("alive",), "not_in", (1,))),
            "a number of alive neighbours other than 1.",
        ),
        (Rule("dead", None), "Any cell always becomes dead."),
        (Rule("alive", ("dead", "dying")), "A dead or dying cell always becomes alive."),
        (
            Rule("alive", ("dead",), probability=0.05),
            "always becomes alive, with probability 0.05.",
        ),
        (
            Rule("alive", ("dead",), Not(Count(("alive",), "eq", 3))),
            "if it is not true that it has exactly 3 alive neighbours.",
        ),
        (
            Rule(
                "alive",
                ("dead",),
                AnyOf(
                    (
                        Count(("alive",), "eq", 3),
                        AllOf((Count(("alive",), "ge", 1), Count(("dying",), "eq", 0))),
                    )
                ),
            ),
            "if it has exactly 3 alive neighbours or (it has at least 1 alive neighbour and "
            "it has exactly 0 dying neighbours).",
        ),
    ],
)
def test_rule_phrases(rule, expected):
    assert describe_rule(rule).endswith(expected)
