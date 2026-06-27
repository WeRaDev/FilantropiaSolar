# CLAUDE.md
Compatibility shim for tools that still look for Claude-specific instruction filenames.
## Canonical instruction file
- The provider-agnostic source of truth for this project is `AGENTS.md`.
- `warp.md` (the project WARP.md) remains the governance/process source of truth.
## Compatibility rule
- If a tool only reads `CLAUDE.md`, apply all instructions from `AGENTS.md`.
- If any guidance differs, `AGENTS.md` takes precedence.
