# Warp Agent: FilantropiaSolar Project Assistant

This repository includes a Warp Agent configured to help you maintain, refactor, test, and ship FilantropiaSolar with high engineering quality. It automates routine tasks while enforcing the project’s standards.

## What this agent does
- Codebase navigation: search files, grep symbols, read/edit files, batch edit patches.
- Quality automation: run formatters/linters (ruff), type checks (mypy), tests (pytest), and suggest fixes.
- CI/CD help: diagnose GitHub Actions failures, adjust workflows, and prepare release assets (no PyPI by default).
- Dependency hygiene: align Python version, consolidate requirements with pyproject, and modernize tooling.
- Security & ops guardrails: avoid leaking secrets, avoid pager traps, and use safe CLI flags.

## Model
- This agent uses the auto model (Warp dynamically selects the best model for your task).

## Project conventions the agent enforces
- Python: 3.11+ (align across README, pyproject, CI, Docker).
- Packaging: pyproject.toml is the source of truth; prefer optional extras over multiple requirements files when possible.
- Linting/formatting: ruff (format + check). The agent can auto-format and propose code changes to fix rules (e.g., PLC0415, F401, F841, PLR0912/0915, PLR2004, PTH*, C401/C408, E402).
- Typing: mypy (at minimum on src/filantropia_solar when migration completes). The agent can tighten configuration once code is compliant.
- Tests: pytest; add focused unit tests under tests/unit and integration/E2E under tests/integration. Coverage targets live in pyproject.
- Git/CI: always use --no-pager for git in CI; do not rely on interactive prompts. Use matrix for OS/Python when needed.

## Guardrails (how the agent runs commands)
- Secrets: never echo or write secrets in plain text. Use environment variables for secrets.
- Non-interactive: refuse interactive commands; prefer safe, idempotent commands.
- Pagers: add flags to avoid pagers (e.g., git --no-pager).
- Version control: the agent never commits unless you explicitly ask it to (or when you say “commit/push”).

## Typical workflows
- “Fix CI lint failures”: the agent will run ruff locally, apply safe autofixes, then propose or apply patches; for remaining issues, it will refactor code.
- “Align versions”: sync Python version, badges, and workflow Python across README/pyproject/CI/Docker.
- “Refactor for package layout”: move modules under src/filantropia_solar, update imports/entry points, and update tooling paths.
- “Add tests”: scaffold minimal pytest tests for import sanity, logging, or critical utilities.
- “Release hardening”: remove PyPI publishing, attach SBOMs, and publish GitHub Releases only.

## How to run this agent from Warp CLI
You can run this agent directly from any terminal with the Warp CLI.

- Start an agent with a one-off prompt:
  ```bash
  warp agent run --prompt "Fix ruff PLC0415 and F841 across the repo and open a PR"
  ```
- Follow along in the GUI:
  ```bash
  warp agent run --gui --prompt "Refactor main.py: move imports to top-level and reduce cyclomatic complexity in chart functions"
  ```
- With an agent profile and MCP server (optional):
  ```bash
  warp agent run \
    --profile <profile-id> \
    --mcp-server <server-id> \
    --prompt "Add a smoke test and update CI to fail on lint"
  ```
Tip: create a dedicated Agent Profile for CLI usage and pre-approve the commands and directories you want the agent to touch.

## Agent capabilities and tools
- File ops: read, search, and apply patches to multiple files atomically.
- Repo ops: run git commands (with safety flags), read VCS state, and push changes when asked.
- Code search: semantic search over the repo plus fast grep for exact tokens.
- Terminal: execute non-interactive, auditable commands; log every command it runs.

## Coding patterns the agent will propose
- Move all dynamic imports to top-level unless lazy import is critical.
- Replace magic numbers with named constants (module-level UPPER_CASE) when appropriate.
- Split long/branchy functions (PLR0912/0915) into smaller helpers.
- Prefer pathlib Path over os.path; replace open() with Path.open() where feasible.
- Use set/dict literals and comprehensions instead of generators when clearer and safe.

## Quality strategy
- Formatting first (ruff format), then lint autofix (ruff --fix), then targeted refactors for non-autofixable rules.
- Keep patches small and isolated by module; include unit tests for changed behavior.
- Avoid noisy changes to tests unless required; prefer additive tests.

## Limitations & expectations
- The agent can’t accept external secrets and won’t run interactive installers.
- For large refactors (package migration), it will propose a plan and apply in stages to keep CI green.

## Getting help
- Ask the agent in the terminal for next steps, or run:
  ```bash
  warp help
  ```
  For CLI-specific questions:
  ```bash
  warp help agent
  warp help mcp
  ```

---
If you want the agent to adopt stricter gates (e.g., fail CI on lint/type), ask it to “enforce quality gates” and it will tighten the workflows accordingly.
