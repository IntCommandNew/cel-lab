"""Reusable pieces of the Streamlit GUI: page styling, definition summary, validation messages."""

from __future__ import annotations

import html

import streamlit as st

from cellab.model import Automaton, ValidationResult, describe_rule
from cellab.model.describe import describe_grid, describe_neighborhood

# Only what the theme in .streamlit/config.toml cannot do.
CSS = """
<style>
[data-testid="stMainBlockContainer"] { padding-top: 2rem; }
.cl-header { display: flex; align-items: center; gap: 0.9rem; padding-bottom: 1.1rem;
  border-bottom: 1px solid #D5DAE3; margin-bottom: 0.5rem; }
.cl-header h1 { font-size: 1.75rem; font-weight: 700; margin: 0; padding: 0;
  letter-spacing: -0.01em; line-height: 1; }
.cl-header p { margin: 0 0 0 0.4rem; color: #5C6178; font-size: 0.95rem; }
.cl-mark { display: grid; grid-template-columns: repeat(3, 7px); gap: 2px; }
.cl-mark i { width: 7px; height: 7px; background: #E1E5EC; }
.cl-mark i.on { background: #2E2A5C; }
.cl-step { display: flex; align-items: baseline; gap: 0.6rem; margin: 1.25rem 0 0.25rem;
  padding-top: 1.25rem; border-top: 1px solid #D5DAE3;
  font-size: 1.35rem; font-weight: 700; line-height: 1.2; }
.cl-step.cl-first { border-top: none; padding-top: 0; }
.st-key-stage { background: #FFFFFF; border: 1px solid #D5DAE3; border-radius: 6px;
  padding: 1.1rem 1.25rem 1rem; }
.cl-stage-head { display: flex; justify-content: space-between; align-items: baseline;
  gap: 1rem; margin-bottom: 0.25rem; }
.cl-stage-head .cl-name { font-weight: 700; font-size: 1.15rem; }
.cl-stage-head .cl-gen { color: #5C6178; font-variant-numeric: tabular-nums; }
.cl-counts { color: #5C6178; font-size: 0.9rem; font-variant-numeric: tabular-nums; }
.cl-counts .cl-swatch { margin-left: 0.9em; }
.cl-counts .cl-swatch:first-of-type { margin-left: 0.35em; }
.cl-counts b { color: #2E2A5C; font-weight: 700; margin-left: 0.25em; }
.cl-step-n { font-weight: 400; color: #7A8094; min-width: 1ch; }
.cl-swatch {
  display: inline-block; width: 0.95em; height: 0.95em; margin-right: 0.45em;
  border: 1px solid #7A8094; border-radius: 2px; vertical-align: -0.12em;
}
.cl-facts { display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 1.25rem;
  margin: 0.5rem 0 1rem; padding: 0; }
.cl-facts dt, .cl-facts dd { margin: 0 !important; padding: 0 !important; }
.cl-facts dt { color: #5C6178; }
.cl-facts { margin-left: 0 !important; padding-left: 0 !important; }
textarea[aria-label="Definition (JSON)"] {
  font-family: "Atkinson Hyperlegible Mono", monospace; font-size: 0.85rem; }
img.cl-grid { display: block; margin: 0.4rem auto; max-width: 100%; height: auto;
  image-rendering: pixelated; }
.cl-legend { color: #5C6178; font-size: 0.875rem; }
.cl-legend .cl-swatch { margin-left: 0.6em; }
.cl-symbol { font-family: "Atkinson Hyperlegible Mono", monospace; color: #5C6178;
  margin-left: 0.35em; }
</style>
"""


def inject_css() -> None:
    st.html(CSS)


GLIDER = (0, 1, 0, 0, 0, 1, 1, 1, 1)  # the mark: a glider, the best-known pattern of Life


def page_header() -> None:
    cells = "".join('<i class="on"></i>' if on else "<i></i>" for on in GLIDER)
    st.html(
        f'<header class="cl-header"><span class="cl-mark" aria-hidden="true">{cells}</span>'
        "<h1>CelLab</h1><p>Choose or write a cellular automaton, check it, then run it.</p>"
        "</header>"
    )


def step_heading(number: int, title: str) -> None:
    """Heading of one step of the left column; the steps are a real sequence, so numbered."""
    first = " cl-first" if number == 1 else ""
    st.html(
        f'<h3 class="cl-step{first}"><span class="cl-step-n">{number}</span>'
        f"{html.escape(title)}</h3>"
    )


def swatch(color: str) -> str:
    return f'<span class="cl-swatch" style="background:{html.escape(color)}"></span>'


def state_lines(a: Automaton) -> str:
    lines = []
    for s in a.states:
        default = " (default)" if s.name == a.default_state else ""
        lines.append(
            f"{swatch(s.color)}{html.escape(s.name)}"
            f'<span class="cl-symbol">{html.escape(s.symbol)}</span>{default}'
        )
    return "<br>".join(lines)


def render_summary(a: Automaton) -> None:
    st.subheader(a.name, anchor=False)
    if a.description:
        st.write(a.description)
    st.html(
        '<dl class="cl-facts">'
        f"<dt>Grid</dt><dd>{html.escape(describe_grid(a))}</dd>"
        f"<dt>Neighbours</dt><dd>{html.escape(describe_neighborhood(a))}</dd>"
        f"<dt>States</dt><dd>{state_lines(a)}</dd>"
        "</dl>"
    )
    st.markdown("**Rules**, checked in order. A cell no rule applies to keeps its state.")
    st.markdown("\n".join(f"{i}. {describe_rule(r)}" for i, r in enumerate(a.rules, 1)))


def _issue_lines(issues) -> str:
    return "\n".join(f"- `{i.path}` {i.message}" if i.path else f"- {i.message}" for i in issues)


def render_issues(result: ValidationResult) -> None:
    if result.errors:
        st.error(_issue_lines(result.errors), title="This definition can't be used yet")
    if result.warnings:
        st.warning(_issue_lines(result.warnings), title="Worth checking")
