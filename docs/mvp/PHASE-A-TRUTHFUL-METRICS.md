# Phase A — Truthful metrics + fleet boundary

**App version:** 3.2.5  
**Branch:** `feat/phase-a-truthful-metrics`

## Done

1. **Ops list excludes Mendeley** — `GET /api/v1/installations` uses `findOpsStations()` (`source != dataset`). Optional `?include_dataset=1` for training corpus views later.
2. **Public API** — `findPublicStations()` also excludes `dataset`; no fallback to Mendeley. Empty until real fleet is seeded/published.
3. **Readings table mapping** — `filantropia_readings` / `filantropia_installations` → `fs_readings` / `fs_installations` in SavingsService, EnergyApiController, DashboardApiController.
4. **Series stats on list payload** — `total_production_kwh`, `total_savings_eur`, `readings_count`, `has_series_data`, `has_measured_data`, `series_source` from `oc_fs_readings` sums (not capacity×1500).
5. **UI** — store/MapPanel/Header use NC series fields; empty → 0 / “No series data”; Active KPI = measured Running (live Online still future).

## Verified locally

- Ops installations: **4** rows (`user`+`crm`), **0** dataset.
- All `total_production_kwh === 0` with `has_series_data === false`.
- Public stations: **0** (no non-dataset Planned/Running yet).

## Follow-ups (not this PR)

- Seed 11 fleet sites from `docs/ops/REAL-FLEET-INVENTORY.md` (confirm W vs kWp; add lat/lon) so ops list and public map refill.
- Phase B: provenance + ML gap-fill.
- Clean smoke CRM test rows if undesired.


## Fleet seed (follow-up)

- `nextcloud-app/data/real_fleet.json` + `scripts/seed_real_fleet.py`
- Capacity: inventory W / 1000 → kWp (40.23 kWp total)
- PurposeFlow 2026 → `planned`; others → `running`
- Coords: approximate placeholders until survey GPS
