# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Shared settings and hooks: `.claude/settings.json`. Personal overrides go in
  `.claude/settings.local.json` / `CLAUDE.local.md` (both git-ignored).
- The prompt-log hooks run `tools/prompt_log.py --assistant claude`. Hooks are loaded at session
  start; after changing them, restart Claude Code.
- Teammates may use GitHub Copilot; its equivalent setup is `.github/copilot-instructions.md` and
  `.github/hooks/prompt-log.json`. Keep both setups in sync when changing shared behaviour.
