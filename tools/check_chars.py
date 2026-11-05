"""Check the repository's character rules (see "Characters and emojis" in AGENTS.md).

Code, config and Markdown files may contain only keyboard characters (printable ASCII, tab,
newline). Anything else must be written as a code: an escape in code, an HTML entity in
Markdown (`&rarr;`, `&#x21B;`). Exception: the verbatim prompts in fenced blocks of PROMPTS.md.

Usage:  python tools/check_chars.py [paths...]
        (default: all tracked and untracked, non-ignored files)
Exit code 1 if a violation is found.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CHECKED_SUFFIXES = {
    ".py", ".pyi", ".md", ".toml", ".json", ".yml", ".yaml", ".ini", ".cfg",
    ".js", ".ts", ".css", ".html", ".sh", ".ps1", ".bat",
}  # fmt: skip
CHECKED_NAMES = {".gitignore", ".gitattributes", ".editorconfig"}
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def is_keyboard(ch: str) -> bool:
    return ch in "\t\n\r" or " " <= ch <= "~"


def repo_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return [Path(line) for line in out.stdout.splitlines() if line]


def exempt_lines(lines: list[str]) -> set[int]:
    """Line numbers inside fenced blocks (PROMPTS.md only: the verbatim prompts)."""
    exempt, fence = set(), None
    for no, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
        elif m and line.strip() == m.group(1) and m.group(1)[0] == fence[0] \
                and len(m.group(1)) >= len(fence):  # fmt: skip
            fence = None
        else:
            exempt.add(no)
    return exempt


def check(path: Path) -> list[str]:
    if path.suffix not in CHECKED_SUFFIXES and path.name not in CHECKED_NAMES:
        return []
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeDecodeError):
        return []
    skip = exempt_lines(lines) if path.name == "PROMPTS.md" else set()
    problems = []
    for no, line in enumerate(lines, 1):
        if no in skip:
            continue
        for col, ch in enumerate(line, 1):
            if not is_keyboard(ch):
                code = f"U+{ord(ch):04X}"
                hint = f"&#x{ord(ch):X};" if path.suffix == ".md" else f"\\u{ord(ch):04x}"
                problems.append(f"{path}:{no}:{col}: {code} -> use a keyboard equivalent or {hint}")
    return problems


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or repo_files()
    problems = [msg for p in paths if p.is_file() for msg in check(p)]
    for msg in problems:
        print(msg)
    print(f"{len(problems)} character-rule violation(s)." if problems else "Character rules: OK.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
