# AGENTS.md - shared context for AI coding assistants

Single source of project context for every assistant the team uses. Claude Code reads it through
`CLAUDE.md`; GitHub Copilot reads it directly (plus `.github/copilot-instructions.md`).
Edit this file - not the assistant-specific ones - when project-wide rules change.

## Project

**CelLab** - a cellular automata simulator for the Artificial Intelligence course (FII, year 3,
group 3B4). A user describes a 2D automaton (world size, cell types, rules) in **English natural
language**; the system parses it deterministically, validates it, simulates N generations,
shows/stores them, and answers analysis questions (state after N, stability, pattern occurrence,
cell counts, cycles).

Team: Georgic&abreve; D&abreve;nu&#x21B;-Liviu, Ghica Alexandra-Mihaela, Iacob David-Gabriel,
Zavincu Sergiu-Constantin.

- Requirements summary: `docs/SPECIFICATION.md` (the original course PDF is not in the repo)
- Design decisions & formal model: `docs/DESIGN.md`
- Sprint plan & task checklists: `docs/PLANNING.md` - tick tasks off there when finished

## Hard constraints - never violate

1. **No AI/LLM/agent calls in the product.** Nothing under `src/` may import or call OpenAI,
   Anthropic, Hugging Face `transformers`, Ollama, LangChain, spaCy models, or any online/offline
   language model. Natural-language parsing is done with regexes, templates, synonym tables and
   explicit rules only.
2. The neural-network experiment (Deliverable 3) lives in `experiments/` and is **not** used by the
   app or the parser. `src/cellab` must never import `torch`.
3. **Every prompt to an AI assistant is logged in `PROMPTS.md`** (course requirement, see below).

## Prompt log (PROMPTS.md) - your responsibility at the end of every turn

- A hook (`tools/prompt_log.py`) appends each prompt verbatim with a timestamp, author and
  assistant. A stop hook reminds you if the result is still pending.
- Before finishing a turn, replace the latest entry's `**Result:** *pending ...*` line with a 1-4
  line summary of what the turn produced (files created/changed, decisions, open questions). Wrap it
  at 100 characters (markdownlint), indenting continuation lines by two spaces.
- **Pasted items** keep their placeholder in the prompt block (`[Image #1]`,
  `[Pasted text #1 +40 lines]`) and get one `- **Pasted:**` line each. The hook adds these lines
  as pending when it sees a placeholder.
  - **Pasted text is never summarised.** If it already appears in full in the prompt block, nothing
    more is needed. Otherwise copy it verbatim into a fenced `text` block right after its
    `Pasted` line (fence longer than any backtick run in the text), as in the template.
  - **Images, files and other pasted items are not stored.** Their `Pasted` line says what the item
    is and what it contains (e.g. a description of a screenshot).
- If the latest entry is *not* the current prompt (hook didn't run), add the entry yourself using
  the template at the top of `PROMPTS.md`.
- Never edit or delete older entries except to fix their own pending lines.

## Tech stack

Python >= 3.11, NumPy (grids & simulation), Streamlit (GUI), JSON + compressed `.npz` files
(persistence), pytest, ruff, PyTorch only in `experiments/` (optional `ml` extra).

## Commands

```bash
python -m venv .venv                     # once
.\.venv\Scripts\Activate.ps1             # Windows PowerShell (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"                  # app + test tools   (add ,ml for the NN experiment)
python -m pytest                         # run tests
ruff check . && ruff format .            # lint + format
python tools/check_chars.py              # character rules (see below)
npx markdownlint-cli2 "**/*.md" "#.venv"  # Markdown lint (needs Node.js; same rules as VS Code)
streamlit run src/cellab/ui/app.py       # GUI (once it exists)
```

## Layout

```text
src/cellab/model/     formal automaton definition + validator
src/cellab/engine/    simulator + initial-world generation
src/cellab/analysis/  the 5 analysis questions
src/cellab/storage/   save/load definitions, experiments, generation histories
src/cellab/nlp/       deterministic natural-language parser
src/cellab/ui/        Streamlit app
src/cellab/presets/   ready-made definitions of known automata (.json)
experiments/          Deliverable 3: dataset generation + NN experiment
examples/automata/    example definitions (.json) and NL descriptions (.txt)
tests/                pytest suite (mirrors src/cellab)
tools/                developer tooling (prompt-logging hook) - not part of the product
data/                 runtime output (runs, datasets) - git-ignored
```

## Characters and emojis (team rule)

"Keyboard characters" = printable ASCII (letters, digits, `` !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~ ``),
space, tab and newline. Everything else (diacritics, arrows, dashes, math symbols, box drawing,
emojis) is a non-keyboard character.

- **Code and Markdown files** (`.py`, `.md`, and config such as `.toml`, `.json`, `.yml`): never
  type non-keyboard characters directly. Prefer a keyboard equivalent (`-` not an em dash, `->`,
  `>=`, `...`, `x`). When the exact character is really needed, write its code:
  - Python / TOML / JSON strings: escapes, e.g. `"\u2192"`, `"D\u0103nu\u021b"`, `"\U0001F600"`.
  - Markdown: HTML entities outside code blocks, e.g. `&rarr;`, `&ge;`, `&abreve;`, `&#x21B;`.
    Entities do not render inside code blocks or inline code, so use keyboard equivalents there
    (e.g. `|--` for tree diagrams, `->` for arrows).
  - Comments and docstrings: keyboard characters only.
- **Other files** (e.g. `.txt` example descriptions, data files): non-keyboard characters may be
  typed directly, but sparingly and only when needed.
- **Emojis**: same rules, but even more sparingly; in practice almost never. Prefer words
  ("Yes", "done", "out of scope").
- **Exception:** the verbatim prompts and pasted texts inside the fenced blocks of `PROMPTS.md` are
  a record and are never altered. Third-party files copied verbatim are exempt too (see below).
- Check before committing: `python tools/check_chars.py` (lists violations with the code to use).

## Assistant skills

Shared skills live in `.claude/skills/<name>/SKILL.md`. Claude Code and VS Code Copilot both load
them from there; they are used automatically when relevant or invoked with `/<name>`.

| Skill | Use it for | Source |
| --- | --- | --- |
| `frontend-design` | Visual/UX design of the Streamlit GUI: palette, typography, layout, interface wording, grid colours | [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/frontend-design) at commit `41bbe19`, Apache-2.0 |

The skill targets HTML/CSS/React pages. In this project apply its guidance through Streamlit's
means: the theme in `.streamlit/config.toml`, layout primitives (columns, tabs, containers), and
custom CSS only where the theme is not enough.

**Use `frontend-design` implicitly**, without being asked, whenever work touches UI/UX: GUI
layout and styling, terminal output meant for people (CLI rendering, messages), visualisations
(grid colours, charts) and interface wording (labels, buttons, errors).

## Third-party files

Files copied verbatim from other projects (currently `.claude/skills/frontend-design/`) are kept
**unmodified**, with their license file next to them, so they can be updated cleanly. They are
exempt from the character rules and markdownlint (`THIRD_PARTY_DIRS` in `tools/check_chars.py`,
`ignores` in `.markdownlint-cli2.jsonc`). To update one, copy the new upstream version over it and
change the commit in the table above. Add new third-party files to both exemption lists.

## Conventions

- Keep it simple: plain functions + `dataclasses`; no frameworks/abstractions we don't need yet.
- Grids are `numpy.ndarray[uint8]` of state indices, shape `(height, width)`.
  1D automata are `(1, width)`.
- A new generation is always computed from an unchanged copy of the previous one
  (synchronous update).
- Anything random takes an explicit `seed` so runs are reproducible.
- Type hints on public functions; docstrings only where the *why* isn't obvious.
- Every engine/analysis/parser feature gets pytest tests
  (known automata: Life, Brian's Brain, Rule 30...).
- Code, comments, docs and commit messages in English.
- Branches: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>`; PRs into `main`.
  Don't commit/push unless asked.
- `main` is protected on GitHub (ruleset "Protect main"): changes only through pull requests,
  no force pushes, no deletion; review conversations must be resolved before merging. Merged
  branches are deleted automatically. Never try to push to `main` directly: create a branch first.
- `PROMPTS.md` updates are committed on the current working branch together with the work they
  describe; if there is no working branch yet, they wait uncommitted until there is one.
