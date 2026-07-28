# Quality Debt: Revisor QA Audit Findings

Surfaced by Revisor QA Audit on PR#1 (feat/add-revisor-workflow), run #188.

## Status: RESOLVED (2026-07-28)

All findings from the audit have been addressed and are now enforced by Gitea CI
gates (`.gitea/workflows/ci.yml`, job `quality-gates`): ruff format check, ruff lint,
mypy, bandit, and pytest run on every push and PR. Current state: all gates green.

- **Lint (ruff):** 0 errors repo-wide (was 158 on `src tests`, plus 384 repo-wide
  including `nextcloud-app/ml-service`, `scripts`, `main.py`, Odoo addon). Fixes:
  auto-fixes, magic-value constants (ranking thresholds, cloud/radiation bounds,
  simulation limits), pathlib conversions, `raise ... from None`, duplicate endpoint
  rename (`get_installation_quick_stats`), cache-clear via `.clear()` instead of
  rebinding globals, Odoo framework idioms handled via per-file ignores.
- **Type check (mypy):** 0 errors in 56 source files (was 195+). Fixes: pydantic v2
  `Field(env=...)` cleanup (runtime no-op), protocol variance typevars, `Optional`
  narrowing guards, `retry_async` `Awaitable` retype, circuit-breaker fall-through
  fix, annotations for caches/reports, ErrorCode enum instead of raw strings,
  type stub packages (`types-requests`, `types-psutil`, `types-PyYAML`).
- **Security (bandit):** 0 findings (was 17). MD5 calls marked
  `usedforsecurity=False` (cache-key use only), pickle load scoped with justified
  `nosec`, bind-all defaults documented for container use, `B110` try/except/pass
  converted to debug logging. **Tooling note:** bandit pinned to `>=1.9.0` — 1.8.x
  crashes on Python 3.14 (`ast.Num` removed).

## Latent issues found during the paydown (fixed)

- `OptimizedDataProcessor._combine_installation_weather` called nonexistent
  `_add_derived_features` (crashed every incremental add); now calls the parent's
  `_add_computed_features` with a real `InstallationInfo`.
- `CircuitBreaker.call` returned `None` on OPEN→HALF_OPEN transition instead of
  executing the function.
- `LoggingManager.set_context` crashed on first call (`self._local` unset).
- `ModelValidator._test_installation` called `predict_15_day_period` (typo) with
  kwargs the real method does not accept; validation silently produced no
  predictions. Fixed the call, but the cross-validation design still cannot
  predict for excluded installations (no trained model for them) — flagged as
  future work below.

## Transitional layout notes (for future sessions)

- `src/filantropia_solar/{prediction,utils,data_processing,weather_api,
  weather_simulation,gui}` are committed **symlinks** to the legacy `src/*` dirs
  (single physical file per module, committed once under the legacy path).
- `src/core/__init__.py` is a shim re-exporting the packaged core API so legacy
  `from ..core import ...` keeps working; the legacy-only `src/core/exceptions.py`
  (retry/circuit-breaker) remains as-is.
- A proper mypy src-layout setup (`mypy_path = "src"`, `py.typed`) was evaluated
  and deferred: with the editable install it triggers duplicate-module errors.
  Revisit during the package-layout migration.

## Remaining future work (not CI-blocking)

- ModelValidator cross-validation design: use `predict_period_for_custom`-style
  reference models so excluded-installation predictions actually run.
- Package-layout migration: complete the move to `src/filantropia_solar`, drop the
  symlinks/shims, then enable `py.typed` + strict mypy src-layout config.
- Coverage gate: pytest currently runs without the `--cov-fail-under=80` gate
  (`pytest.ini` has no cov opts); re-enable when coverage improves.

## Owner

WARP | Resolved: 2026-07-28
