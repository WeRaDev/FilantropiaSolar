# AGENTS.md
Provider-agnostic coding-agent instructions for FilantropiaSolar.
This is the canonical agent behavior file for this project.
## Scope and precedence
- Applies to the entire FilantropiaSolar project.
- Inherits the WeRa Global umbrella `AGENTS.md`; this project file takes precedence for FilantropiaSolar work.
- `warp.md` (the project WARP.md) remains the governance/process source of truth and must stay consistent with `SOUL.md`.
- On conflict, use the most specific file: this `AGENTS.md` > umbrella `AGENTS.md` > applicable `warp.md`/`WARP.md`.
## Principles
1. Think before coding: state assumptions and choose explicit interpretations; ask when requirements are ambiguous.
2. Simplicity first: implement only the minimum needed behavior; avoid speculative abstraction.
3. Surgical changes: touch only files required by task scope; preserve local style; clean up only your own artifacts.
4. Goal-driven validation: define success criteria, then verify with the project checks below after changes.
## FilantropiaSolar-specific guidance
- Two components: the Nextcloud platform (`nextcloud-app/`, the MAIN app: Nextcloud app + ml-service + Odoo addon) and the desktop client edition (`desktop/`, API-client mode since v1.3.0). Keep their contracts and versions independent and consistent.
- Python: target 3.11+; keep `README.md`, `desktop/pyproject.toml`, CI, and Docker aligned.
- Validate Python changes from `desktop/` with: `ruff format .`, `ruff check .`, `mypy`, and `pytest`.
- Validate Nextcloud changes from `nextcloud-app/` with: `npm run build` (use `npm run dev` for watch).
- The desktop is a client of the Nextcloud server: server-owned data and ML must not be re-implemented locally; new server needs go through the API (`desktop/src/nextcloud_backend.py` pattern).
- Datasets (`data/`, `weather_files/`) are tracked at root and shared; `archive/` is a permanent preservation area — archive stale files there, never delete from it.
- Preserve ML training/inference feature parity (persisted `feature_names`); do not reintroduce the StandardScaler feature-dimension mismatch.
- Data integrity: keep the source dataset citation (Mendeley Data, doi:10.17632/dbh93b6vp8.3) intact wherever data is used or exported.
- Shell: use quoted heredoc delimiters (`<<'EOF'`) with the closing delimiter alone on its own line; use `git --no-pager`.
- Secrets: never echo or commit secrets; pass them via environment variables.
- Version control: use Gitea (`origin`) with the WARP Gitea account; do not commit or push unless explicitly requested.
- Avoid emoji in code and comments except in user-facing UI content.
## Pull request review (Revisor)
- For PR or code-review requests, apply the umbrella `skills/revisor-pr-audit.md` standard: explicit severity taxonomy, location-based findings, evidence-backed blockers, honest review depth, and specific praise where merited.
## Compatibility
- `CLAUDE.md` is a compatibility shim that points here. Keep canonical rules in `AGENTS.md` to avoid provider-specific drift.
