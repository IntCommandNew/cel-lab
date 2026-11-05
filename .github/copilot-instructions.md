# Copilot instructions - CelLab

Full project context, layout and conventions are in [`AGENTS.md`](../AGENTS.md) at the repository
root - read and follow it. The essentials, repeated here for tools that only read this file:

- **CelLab** is a cellular automata simulator (Python, NumPy, Streamlit, JSON + `.npz` storage,
  pytest, ruff). Users describe automata in English; a deterministic parser turns the text into a
  validated definition that is simulated and analysed. Design: `docs/DESIGN.md`. Plan:
  `docs/PLANNING.md`.
- **Never add AI/LLM/agent calls to the product.** Nothing under `src/` may import or call OpenAI,
  Anthropic, Hugging Face `transformers`, Ollama, LangChain, spaCy models or any language model.
  Natural-language parsing uses regexes, templates, synonym tables and explicit rules only.
  `src/cellab` must never import `torch` (the NN experiment lives in `experiments/`).
- Keep code simple: plain functions and `dataclasses`, type hints on public functions, pytest tests
  for every engine / analysis / parser feature, English everywhere.
- **Characters and emojis:** in code, config and Markdown files use keyboard (printable ASCII)
  characters only. Prefer equivalents (`-`, `->`, `>=`, `...`); if a special character is really
  needed, write its code (`"\u2192"` in code, `&rarr;` / `&#x21B;` in Markdown). Other files may use
  such characters directly but sparingly; emojis even more sparingly. Verbatim prompts in
  `PROMPTS.md` are exempt. Details in `AGENTS.md`; check with `python tools/check_chars.py`.

## Prompt log (course requirement)

Every prompt given to an AI assistant must be recorded in `PROMPTS.md`.

- In **agent mode**, a hook (`.github/hooks/prompt-log.json` -> `tools/prompt_log.py`) appends the
  prompt automatically. Before ending your turn, replace the latest entry's
  `**Result:** *pending ...*` line with a 1-4 line summary of what the turn produced (wrapped at 100
  characters). If a stop hook asks you to do this, do it and stop.
- Pasted items keep their placeholder in the prompt and get a `- **Pasted:**` line each. Pasted
  text is never summarised: if it isn't already in full in the prompt, copy it verbatim into a
  fenced `text` block after its `Pasted` line. Images and files are not stored; their line says
  what the item is and what it contains. Details and template: `AGENTS.md`, `PROMPTS.md`.
- If the latest entry in `PROMPTS.md` is not the current prompt (hook didn't run) and you can edit
  files, add the entry yourself using the template at the top of `PROMPTS.md`, with `GitHub Copilot`
  (and the model name, if known) as the assistant.
- Never edit or delete older entries except to fix their own pending lines.
