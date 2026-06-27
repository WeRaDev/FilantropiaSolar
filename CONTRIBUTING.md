# Contributing to FilantropiaSolar
FilantropiaSolar is an independent `ProductionBase/*` project under WeRa Global. Contribute with minimal, traceable, well-verified changes.

## Required reading before implementation
1. `README.md`
2. `warp.md` (project governance/process; the project WARP.md)
3. `AGENTS.md` (provider-agnostic agent instructions)
4. `SOUL.md` (project constitutional layer; inherits umbrella `SOUL.md`)
5. The umbrella WeRa Global `README.md`, `WARP.md`, `AGENTS.md`, and `SOUL.md` for cross-project policy

## Branching
- Default branch: `main`; create short-lived, focused feature branches from `main`.
- Keep changes minimal and scoped to the task objective.

## Workflow
1. Confirm scope and acceptance criteria; surface assumptions and ambiguity first.
2. Implement minimal changes in focused commits.
3. Validate the components you touched:
   - Python desktop app: `ruff format .`, `ruff check .`, `mypy`, `pytest`
   - Nextcloud app (from `nextcloud-app/`): `npm run build`
4. Update docs and task artifacts in the same change cycle.
5. For pull requests and review rounds, apply the umbrella `revisor-pr-audit` standard (severity taxonomy plus structured, evidence-backed findings).

## Quality requirements
- Prefer the simplest sufficient solution; avoid speculative abstractions.
- Include explicit verification evidence for completed changes.
- Keep `README.md`, `warp.md`, `AGENTS.md`, and `SOUL.md` consistent when behavior or operations change.

## Security and operational hygiene
- Never commit secrets, credentials, private keys, or private customer data.
- Use Gitea (`origin`) with the WARP Gitea account; do not commit or push unless explicitly requested.
- For stateful or high-impact changes, document the rollback path and validation checks.
