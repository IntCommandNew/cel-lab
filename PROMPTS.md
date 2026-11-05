# AI Interaction Log

The course requires that **all interactions with conversational AI agents are saved**. This file
records every prompt given to an AI assistant while building CelLab: when, by whom, to which
assistant, the exact prompt, and a short summary of the result.

- **Claude Code** and **GitHub Copilot (agent mode)** prompts are appended automatically by
  `tools/prompt_log.py`; the assistant fills in the *Result* line at the end of its turn.
- Prompts to **any other assistant** (ChatGPT, Gemini, ...) or Copilot modes without hooks (ask/edit
  mode, inline chat) must be added manually with the template below.
- Entries are in chronological order. Don't rewrite old entries. `PROMPTS.md` uses git's `union`
  merge strategy (see `.gitattributes`) so concurrent appends from different branches merge without
  conflicts.
- Character rules (see `AGENTS.md`): headings and results use keyboard characters only; a name with
  diacritics is written with character codes (e.g. `D&#259;nu&#539;`). The prompts and pasted texts
  inside fenced blocks are the only exception: they are verbatim records and are never altered.
- Pasted items keep their placeholder in the prompt (e.g. `[Image #1]`) and get a *Pasted* line each.
  **Pasted text is never summarised**: if it is not already in full in the prompt, it is saved
  verbatim in a fenced block right after its *Pasted* line. Images, files and other pasted items are
  not stored; their *Pasted* line says what the item is and what it contains.

## Template

`````markdown
### YYYY-MM-DD HH:MM (UTC+0200) - Full Name

- **Assistant:** Claude Code / ChatGPT (model) / ...
- **Prompt:**

````text
the exact prompt, unchanged (pasted items may appear as placeholders, e.g. [Image #1])
````

- **Pasted:** [Pasted text #1 +3 lines] - saved verbatim below:

````text
the pasted text, unchanged
````

- **Pasted:** [Image #2] screenshot of ... showing ... (one line per image/file; omit if none)
- **Result:** 1-4 lines: what was produced or decided (files, features, answers).
`````

## Log

### 2026-11-05 15:20 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code (Claude Opus 5.5)
- **Prompt:**

````text
this project is about cellular automata. the specifications of the project are found in @proiect.pdf . you can delete this file from the project after you read it. also, an example README.md file content can be found in @copy.md . you will read it, then delete it, and use it to write our own @README.md file. the AI (or IA) part you will see in @copy.md refers to the course for wich we will build this project, not that this is an AI powered project (as you will see, we are forbiden from including any AI or LLM, be that localy or online, in our project, but we are allowed to use them to create our project). the team (this is a team project) consists of Georgică Dănuț-Liviu, Ghica Alexandra-Mihaela, Iacob David-Gabriel (me), Zavincu Sergiu-Constantin. as the section 12 in @copy.md specifies, we are required to state and record any usage of AI, LLM, or agentic generated code. for this, we will have a section in @README.md that speeks generally about how we used AI to create this project and point it to a PROMPTS.md file that will record exactly every prompt given, when it was given, and what result (on short) did it produce.
first things first, you will write the @README.md file, make the initialisation setup and create the general structure for this GitHub project (we will work in VS Code), but don't wite any code yet, create the PROMPTS.md file and log in the first prompt (this one) and every other prompt I give you without having to specify this to you. also, create yor general claude code setup so that my teamates can have the same working context and settings for claude code. in @proiect.pdf you will find, in the laboratory schedule section, 4 deliverable entries. we will interpret them as sprint planing. for time distribution of sprints and their duration take into consideration that every laboratory takes place on a friday, and that L6 is on 6 november 2026. consider the first sprint as already done (it was presented in another form on its required day), so now we will start working from sprint 2.
regarding @copy.md , it already presents a planning about many things and how we will/should make/implement them. if you consider them good, keep them. if you have a better aproach/solution, go with it. regarding the technology stack, we will use python as our main programing language. regarding the other tehnologies, if you have sugestions for other technologies (like replacing the sugested ones with others) go for it. our focus is to create the final product as easy and as fast as possible. there is no need for overly complex arhtectures or tehnologies if we can use a more simpler alternative.
````

- **Result:** Read the course PDF and the draft README, then deleted both. Wrote README.md,
  CLAUDE.md, PROMPTS.md, docs/SPECIFICATION.md, docs/DESIGN.md and docs/PLANNING.md (Sprint 2 due L6
  on 6 Nov 2026, Sprint 3 due 11 Dec, Sprint 4 due 8 Jan 2027 assuming a winter break, final on 15
  Jan 2027). Simplified the stack to Python + NumPy + Streamlit + JSON/.npz files (dropped
  FastAPI/React/SQLite). Created the package skeleton (no code yet), pyproject.toml, VS Code config,
  .gitignore/.gitattributes, and the shared Claude Code setup (settings, plus hooks that log each
  prompt here automatically).

### 2026-11-05 15:57 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code
- **Prompt:**

````text
some of my teammates use GitHub Copilot to write code. can you create the setup for it too like we have for claude code?
````

- **Result:** Added a GitHub Copilot setup equivalent to the Claude Code one. Moved the shared
  project context into AGENTS.md (CLAUDE.md now imports it) and added
  .github/copilot-instructions.md, .github/hooks/prompt-log.json, Copilot settings in
  .vscode/settings.json and the Copilot extensions. The prompt logger moved to tools/prompt_log.py
  and is shared by both tools. It now records which assistant was used, takes the author from
  `git config cellab.author`, skips duplicates and tool-generated messages (a sub-agent report had been
  logged as a prompt; that entry was removed). Updated README and this file's header.

### 2026-11-05 16:14 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code
- **Prompt:**

````text
another thing I wanted to flag is regarding the use of non-keyboard characters and emojis. non-keyboard characters can be used, but for code and md files they must be inserted via their code or similar value, not directly inserted as characters. for other files they can be used, but sparingly and when they are needed. for emojis the rules are similar, but they should be used even more sparingly. this must be recorded rules.
````

- **Result:** Recorded the character/emoji rules in AGENTS.md (section "Characters and emojis") and
  .github/copilot-instructions.md, with verbatim prompts in PROMPTS.md exempt. Added
  tools/check_chars.py to list violations, plus VS Code highlighting of non-ASCII characters.
  Converted the existing files: keyboard equivalents where possible, HTML entities or escapes for
  diacritics in names and Greek letters, and emojis replaced with words. The prompt logger now
  writes author names with character codes.

### 2026-11-05 16:27 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code
- **Prompt:**

````text
[Image #1]
````

- **Pasted:** [Image #1] screenshot of VS Code with `.vscode/settings.json` open, showing the
  warning on `"editor.defaultFormatter": "charliermarsh.ruff"`: "Value is not accepted. Valid
  values: ..." followed by the list of installed formatter extensions (Ruff is not among them).
- **Result:** Explained the cause: the Ruff VS Code extension isn't installed yet, so VS Code
  doesn't recognise it as a formatter. The config is correct; installing the recommended extension
  (`code --install-extension charliermarsh.ruff`) clears the warning. Also confirmed from the
  diagnostics that VS Code recognises the Copilot hook settings. (The screenshot was first saved in
  docs/prompt-images/; superseded by the next entry: pasted items are described, not stored.)

### 2026-11-05 18:01 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code
- **Prompt:**

````text
I made some changes in some md files. keep them. you can make the diagrams in @docs/DESIGN.md and @README.md with mermaid so that they are more easily unrestandable. I also get some warnings from markdownlint about the formating of some md files. can you check and resolve these warnings? also, regarding the pasted inputs for prompts, it is a waste of space to keep every pasted image, text or something else and separately and point the log at it. we don't need to keep these pasted items. for the prompts log, just specify that something was pasted, what it is and what it contains (a description of the pasted picture, a summary of the pasted text etc.).
````

- **Result:** Kept the user's Markdown edits. Replaced the pipeline/architecture diagrams in
  docs/DESIGN.md and README.md with Mermaid flowcharts. Added a shared .markdownlint.jsonc (100-char
  lines like the code, asterisk emphasis) and fixed every warning: rewrapped long lines, table
  delimiter spacing, code-fence languages, list spacing, bare URLs. Pasted items are now described in
  a `**Pasted:**` line instead of stored (rule in AGENTS.md/Copilot instructions/PROMPTS.md header;
  the hook adds a pending Pasted line per placeholder); deleted docs/prompt-images/ and described
  the earlier screenshot instead.

### 2026-11-05 18:15 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code
- **Prompt:**

````text
ok. then change the rule only for pasted text so that it is never summarised and is saved alongside the prompt if it isn't already placed inline in the prompt.
````

- **Result:** Changed the rule for pasted text only: it is never summarised; if it isn't already
  in full in the prompt, it is saved verbatim in a fenced text block after its `**Pasted:**` line.
  Images/files are still only described. Updated AGENTS.md, Copilot instructions, the PROMPTS.md
  header and template, and the hook (pasted-text placeholders get a "copy verbatim" pending line).

### 2026-11-05 18:24 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code
- **Prompt:**

````text
all looks good. you can push all the changes to GitHub.
````

- **Result:** Committed the whole project setup on a new branch `feature/project-setup` (team
  convention: no direct commits to `main`) and pushed it to GitHub, ready to be merged into `main`
  through a pull request.

### 2026-11-05 18:29 (UTC+0200) - Iacob David-Gabriel

- **Assistant:** Claude Code
- **Prompt:**

````text
open the pull request
````

- **Result:** Opened pull request #1 (`feature/project-setup` -> `main`):
  <https://github.com/IntCommandNew/cel-lab/pull/1>, with a summary of the setup, the steps each
  team member does after merging, and the checks that pass.
