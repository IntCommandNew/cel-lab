"""Prompt-logging hook shared by Claude Code and GitHub Copilot (course requirement).

Keeps PROMPTS.md up to date. Wired up in:
    .claude/settings.json         (Claude Code)          --assistant claude
    .github/hooks/prompt-log.json (GitHub Copilot)       --assistant copilot

Usage:
    python tools/prompt_log.py prompt --assistant claude|copilot   # user prompt: append entry
    python tools/prompt_log.py stop   --assistant claude|copilot   # agent stop: remind about Result

Author name: env CELLAB_AUTHOR, else `git config cellab.author`, else `git config user.name`.
Standard library only, so it works before any virtualenv exists. It must never break a session:
every error is swallowed and the exit code is always 0.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PENDING_MARK = "*pending - "
PENDING = PENDING_MARK + "the assistant fills this in at the end of the turn*"
PASTED_ITEM_PENDING = PENDING_MARK + "the assistant describes this item: what it is, what it shows*"
PASTED_TEXT_PENDING = (
    PENDING_MARK + "the assistant copies the pasted text verbatim into a text block below; "
    "never a summary*"
)
# Placeholders the assistants put in a prompt instead of pasted content. Pasted text is saved
# verbatim (AGENTS.md); images and files are only described.
PASTE_PLACEHOLDER = re.compile(r"\[(Image|Pasted text|Pasted image|File)\b[^\]]*\]", re.IGNORECASE)
ENTRY_HEADING = "### "
ASSISTANTS = {"claude": "Claude Code", "copilot": "GitHub Copilot"}
REMINDER = (
    "PROMPTS.md: replace the pending lines of the latest entry: '**Result:**' with a short summary "
    "of what this turn produced (files changed, decisions, open questions; 1-4 lines wrapped at "
    "100 characters) and each '**Pasted:**' line: pasted text is copied verbatim into a fenced "
    "text block after its line (never summarised); images/files get a description."
)
# Messages injected by the tools themselves (sub-agent reports, notifications, our own reminder)
# arrive through the same hook but are not prompts written by a person.
NOT_HUMAN = re.compile(
    r"^\s*(<(agent-message|system-reminder|task-notification|command-|local-command)"
    r"|\[Subagent hand-back\]|" + re.escape(REMINDER[:30]) + ")",
    re.IGNORECASE,
)
DUPLICATE_WINDOW = dt.timedelta(minutes=2)


def project_dir(data: dict, assistant: str) -> Path:
    if assistant == "claude" and os.environ.get("CLAUDE_PROJECT_DIR"):
        return Path(os.environ["CLAUDE_PROJECT_DIR"])
    return Path(__file__).resolve().parents[1]


def git_config(key: str, cwd: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "config", key], capture_output=True, text=True, timeout=5, cwd=cwd
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def author(root: Path) -> str:
    name = (
        os.environ.get("CELLAB_AUTHOR", "").strip()
        or git_config("cellab.author", root)
        or git_config("user.name", root)
        or "unknown"
    )
    # Character rules (AGENTS.md): non-keyboard characters in Markdown are written as codes.
    return name.encode("ascii", "xmlcharrefreplace").decode("ascii")


def fence_for(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(4, longest + 1)


def last_entry(text: str) -> str:
    return text.rsplit(f"\n{ENTRY_HEADING}", 1)[-1]


def is_duplicate(log: str, prompt: str, now: dt.datetime) -> bool:
    """Same prompt logged moments ago, e.g. when two hook sources fire for one prompt."""
    entry = last_entry(log)
    match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", entry)
    if not match or prompt not in entry:
        return False
    logged = dt.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=now.tzinfo)
    return now - logged <= DUPLICATE_WINDOW


def log_prompt(data: dict, assistant: str) -> None:
    prompt = (data.get("prompt") or "").rstrip()
    if not prompt or NOT_HUMAN.match(prompt):
        return
    root = project_dir(data, assistant)
    path = root / "PROMPTS.md"
    if not path.exists():
        return
    now = dt.datetime.now().astimezone()
    if is_duplicate(path.read_text(encoding="utf-8"), prompt, now):
        return
    fence = fence_for(prompt)
    pasted = "".join(
        f"- **Pasted:** {m.group(0)} "
        f"{PASTED_TEXT_PENDING if m.group(1).lower() == 'pasted text' else PASTED_ITEM_PENDING}\n"
        for m in PASTE_PLACEHOLDER.finditer(prompt)
    )
    entry = (
        f"\n{ENTRY_HEADING}{now:%Y-%m-%d %H:%M} (UTC{now:%z}) - {author(root)}\n\n"
        f"- **Assistant:** {ASSISTANTS[assistant]}\n"
        f"- **Prompt:**\n\n"
        f"{fence}text\n{prompt}\n{fence}\n\n"
        f"{pasted}"
        f"- **Result:** {PENDING}\n"
    )
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(entry)


def check_result(data: dict, assistant: str) -> None:
    if data.get("stop_hook_active") or data.get("stopHookActive"):
        return  # already reminded once in this stop cycle; never loop
    path = project_dir(data, assistant) / "PROMPTS.md"
    if not path.exists() or PENDING_MARK not in last_entry(path.read_text(encoding="utf-8")):
        return
    output: dict = {"decision": "block", "reason": REMINDER}
    if assistant == "copilot":
        # Copilot's CLI/cloud runtime reads the top-level keys; VS Code's local runtime the nested.
        output["hookSpecificOutput"] = {"hookEventName": "Stop", **output}
    print(json.dumps(output))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prompt", "stop"])
    parser.add_argument("--assistant", choices=sorted(ASSISTANTS), default="claude")
    args = parser.parse_args()
    # Copilot also reads .claude/settings.json; only Claude Code sets CLAUDE_PROJECT_DIR.
    if args.assistant == "claude" and not os.environ.get("CLAUDE_PROJECT_DIR"):
        return
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    data = json.loads(raw) if raw.strip() else {}
    if args.mode == "prompt":
        log_prompt(data, args.assistant)
    else:
        check_result(data, args.assistant)


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:  # a logging hook must never block the user
        print(f"prompt_log hook error: {exc!r}", file=sys.stderr)
    sys.exit(0)
