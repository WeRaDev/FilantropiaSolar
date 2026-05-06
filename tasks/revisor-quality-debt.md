# Quality Debt: Revisor QA Audit Findings

Surfaced by Revisor QA Audit on PR#1 (feat/add-revisor-workflow), run #188.

## Lint (ruff) — 158 errors

**Auto-fixable (113):** Run `ruff check --fix src tests` to clear PLR2004, E711, F401, F841, etc.

**Non-auto-fixable (45):** Includes:
- `PLR2004` — magic comparison values (e.g. hour thresholds in `weather_simulator.py:573`)
- `B023` — function definition does not bind loop variable (`weather_simulator.py:638`)

**Recommended action:** `ruff check --fix src tests` in a dedicated lint cleanup commit.

## Type check (mypy) — 195 errors in 28 files

Key categories:
- `[var-annotated]` — unannotated variables in `optimized_energy_predictor.py`
- `[index]` — unsupported indexed assignment on `Collection[Any]`
- `[misc]` — `Exception` not derived from `BaseException` in `async_weather_client.py:345`
- `[arg-type]` — incompatible `Exception | None` args in `core/exceptions.py`
- `[return-value]` — missing return in coroutine wrappers

**Recommended action:** Incremental type annotation pass, starting with `core/exceptions.py`.

## Security (bandit) — 17 findings

- **High (2):** Investigate individually
- **Medium (2):** Investigate individually
- **Low (13):** `B110` try/except/pass — review each for legitimate catch-all vs. silent failure

**Recommended action:** Audit `B110` instances; replace bare `except: pass` with
  `except Exception as exc: logger.debug(...)` where appropriate.

## Owner

WARP | Target sprint: W27+
