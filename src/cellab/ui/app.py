"""CelLab graphical interface. Run from the repository folder:

    streamlit run src/cellab/ui/app.py

Layout: a narrow column with the steps in order (automaton, initial world, run) and a wide
column showing the result. Every way of getting a definition (known automaton, form, JSON) ends in
the same JSON and the same validator.
"""

from __future__ import annotations

import json
import re

import streamlit as st

from cellab.model import ValidationResult, to_json, validate_json
from cellab.presets import preset_ids, preset_path
from cellab.ui.build_form import (
    builder_section,
    clear_form_control,
    init_form_state,
    load_form,
)
from cellab.ui.builder import definition_from_form, form_from_definition
from cellab.ui.components import inject_css, render_issues, render_summary, step_heading

SOURCES = {"preset": "Known automata", "build": "Build", "json": "JSON"}
DEFAULT_PRESET = "game-of-life"
JSON_PLACEHOLDER = """{
  "name": "My automaton",
  "grid": { "width": 40, "height": 30 },
  ...
}"""


@st.cache_data
def preset_text(preset_id: str) -> str:
    return preset_path(preset_id).read_text(encoding="utf-8")


@st.cache_data
def preset_name(preset_id: str) -> str:
    result = validate_json(preset_text(preset_id))
    return result.automaton.name if result.ok else preset_id


# --- state ----------------------------------------------------------------------------------
# Streamlit resets a widget's value while the widget is not shown (e.g. the JSON editor while a
# known automaton is selected). The user's choices therefore live in plain keys ("preset_choice",
# "json_draft"); `restore()` puts them back into the widget keys ("preset_id", "json_text") right
# before the widget is drawn.


def init_state() -> None:
    ss = st.session_state
    ss.setdefault("source", "preset")
    ss.setdefault("preset_choice", DEFAULT_PRESET)
    ss.setdefault("json_draft", "")
    init_form_state()


def restore(widget_key: str, saved_key: str) -> None:
    if st.session_state.get(widget_key) != st.session_state[saved_key]:
        st.session_state[widget_key] = st.session_state[saved_key]


def _set_json(text: str) -> None:
    st.session_state.json_text = st.session_state.json_draft = text


# --- callbacks (run before the script reruns, so they may set widget state) -----------------


def _edit_preset_as_json() -> None:
    _set_json(preset_text(st.session_state.preset_choice))
    st.session_state.source = "json"


def _edit_in_form(definition: dict) -> None:
    form, _ = form_from_definition(definition)
    load_form(form)
    st.session_state.source = "build"


def _edit_preset_in_form() -> None:
    _edit_in_form(json.loads(preset_text(st.session_state.preset_choice)))


def _edit_json_in_form() -> None:
    _edit_in_form(json.loads(st.session_state.json_draft))


def _edit_form_as_json() -> None:
    data, _ = definition_from_form(st.session_state.form)
    _set_json(json.dumps(data, indent=2) + "\n")
    st.session_state.source = "json"


def _on_source_change() -> None:
    source = st.session_state.source
    if source == "json" and not st.session_state.json_draft.strip():
        _set_json(preset_text(st.session_state.preset_choice))
    elif source == "build":
        load_form(st.session_state.form)


def _on_preset_change() -> None:
    st.session_state.preset_choice = st.session_state.preset_id


def _on_json_edit() -> None:
    st.session_state.json_draft = st.session_state.json_text


def _on_upload() -> None:
    uploaded = st.session_state.get("upload")
    if uploaded is not None:
        _set_json(uploaded.getvalue().decode("utf-8", errors="replace"))


# --- sections -------------------------------------------------------------------------------


def automaton_section() -> ValidationResult | None:
    step_heading(1, "Automaton")
    with st.container(horizontal=True, vertical_alignment="center"):
        source = st.segmented_control(
            "Where the automaton comes from",
            options=list(SOURCES),
            format_func=SOURCES.get,
            required=True,
            key="source",
            on_change=_on_source_change,
            label_visibility="collapsed",
        )
        if source == "build":
            st.space("stretch")
            clear_form_control()

    if source == "preset":
        restore("preset_id", "preset_choice")
        st.selectbox(
            "Known automaton",
            preset_ids(),
            format_func=preset_name,
            key="preset_id",
            on_change=_on_preset_change,
        )
        with st.container(horizontal=True):
            st.button(
                "Edit in the form",
                on_click=_edit_preset_in_form,
                help="Copy this definition to the form builder to change it.",
            )
            st.button(
                "Edit as JSON",
                on_click=_edit_preset_as_json,
                help="Copy this definition to the JSON editor to change it.",
            )
        return validate_json(preset_text(st.session_state.preset_choice))

    if source == "build":
        result, _ = builder_section()
        st.button(
            "Edit as JSON",
            on_click=_edit_form_as_json,
            help="Copy what the form produces to the JSON editor.",
        )
        return result

    st.file_uploader(
        "Upload a definition", type="json", key="upload", on_change=_on_upload, max_upload_size=1
    )
    restore("json_text", "json_draft")
    st.text_area(
        "Definition (JSON)",
        key="json_text",
        on_change=_on_json_edit,
        height=380,
        placeholder=JSON_PLACEHOLDER,
        help="Edit freely: the definition is checked every time you leave the field "
        "(or press Ctrl+Enter).",
    )
    text = st.session_state.json_draft
    if not text.strip():
        return None
    result = validate_json(text)
    if result.ok:
        _, reason = form_from_definition(json.loads(text))
        st.button(
            "Edit in the form",
            on_click=_edit_json_in_form,
            disabled=reason is not None,
            help=reason or "Copy this definition to the form builder.",
        )
    return result


def later_steps() -> None:
    step_heading(2, "Initial world")
    st.caption("Next: choose, generate or draw the starting world.")
    step_heading(3, "Run")
    st.caption("Next: number of generations, which generations to keep, and run.")


def definition_tab(result: ValidationResult | None) -> None:
    if result is None:
        st.markdown(
            "No definition yet. Pick a known automaton, build one with the form, or paste or "
            "upload a JSON definition on the left."
        )
        return
    render_issues(result)
    if result.ok:
        render_summary(result.automaton)


def json_tab(result: ValidationResult | None) -> None:
    if result is None or not result.ok:
        st.markdown("The checked definition appears here once it has no errors.")
        return
    text = to_json(result.automaton)
    slug = re.sub(r"[^a-z0-9]+", "-", result.automaton.name.lower()).strip("-") or "automaton"
    st.download_button("Download JSON", text, file_name=f"{slug}.json", mime="application/json")
    st.code(text, language="json")


def main() -> None:
    st.set_page_config(page_title="CelLab", layout="wide")
    inject_css()
    init_state()
    st.title("CelLab", anchor=False)
    st.caption("Choose or write a cellular automaton, check it, then run it.")

    # building needs room for the tables; otherwise the result gets the wider column
    ratio = [3, 2] if st.session_state.source == "build" else [2, 3]
    left, right = st.columns(ratio, gap="large")
    with left:
        result = automaton_section()
        later_steps()
    st.session_state.automaton = result.automaton if result is not None else None
    with right:
        definition, json_view = st.tabs(["Definition", "JSON"])
        with definition:
            definition_tab(result)
        with json_view:
            json_tab(result)


main()
