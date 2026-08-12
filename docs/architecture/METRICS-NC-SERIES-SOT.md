# Metrics & series — NC as station data platform

**Status:** Accepted (design-thinking 2026-08-12)  
**Companion to:** `docs/architecture/TRS-ADDENDUM-D1-D10.md`  
**Related:** `docs/ops/REAL-FLEET-INVENTORY.md`

## Problem

Dashboard energy/savings used **capacity × 1500 × price**. That is not truthful. NC must manage **per-station datasets** (historical and/or simulated) for stations that may **never** appear in the ML training corpus. Stats (portfolio and per-station) are computed from **those** series. If NC lacks coverage for a period, it asks ML to generate missing samples and (per policy) persists them.

## Locked decisions

### M0 — Two populations (NEW, critical)

| Population | Role in product |
|------------|-----------------|
| **Real fleet** | Ops list, KPIs, public Existing/Planned (when lifecycle allows). Inventory: `docs/ops/REAL-FLEET-INVENTORY.md` |
| **Mendeley / `source=dataset`** | **ML training only.** Not “real stations.” Do not use for portfolio kWp/energy/savings or default ops map list |

**Supersedes (product):** treating imported Mendeley plants as the live Filantropia fleet in the NC UI.

Implementation implication: default `GET /api/v1/installations` for the dashboard must return **fleet + user + crm** (and not dataset), or filter `source != dataset` unless an explicit “Training corpus” admin view is open. ML keeps reading Mendeley via ML service / dataset import paths.

### M1 — Canonical series in NC

- Single **hourly** production series per **fleet/user/crm** station in NC (`oc_fs_readings` / app `fs_readings`).
- Provenance per sample: `measured` | `simulated` | `backfilled_ml` (later `live`).
- Station need not exist in Mendeley.

### M2 — Gap fill (hybrid)

- **Running fleet:** job fills operation window (measured first; gaps → ML → persist).
- **Virtual/Planned:** on-demand for analysis; persist sparingly.

### M3 — Stats

- Totals = Σ NC series over each **fleet** station’s operation window.
- Savings = Σ kWh × price (piecewise when D6 exists).
- Show data **mix**; never silent ×1500.
- Phase A: empty series → **0** / “No series data”.

### M4 — Online / Offline / Active

- **Online:** future **live feed** only (KPI 0/hidden until then).
- **Active (measured):** Running + sufficient measured samples.
- **Offline:** Running on simulated/backfilled only.
- Do not label measured-file stations as Online.

### M5 — Overwrite (D6)

- `measured` immutable.
- `simulated` / `backfilled_ml` regenerable.

### M6 — ML role

- Train on Mendeley (and later on fleet measured when enough exists).
- Generate gap series for fleet stations by meta (lat/lon/capacity/weather).
- NC remains series SoT for stats.

### M7 — Operation window

`[installed_at | installation_date | from_date | created_at] .. [to_date | now]`.

## Phasing

### Phase A — Truthful read + fleet boundary (now)

1. Fix `filantropia_readings` → `fs_readings` in Savings/Energy/Dashboard controllers.
2. Stats service from NC readings only; kill ×1500 in UI.
3. **Hide dataset from default ops list/KPIs**; optional Training corpus view later.
4. Seed **11 real fleet** stations from inventory (after capacity unit confirm W vs kWp).
5. Upload historical → `measured`.
6. Tests: no dataset in portfolio sum; no ×1500.

### Phase B — ML gap-fill + provenance

- `provenance` column; backfill job; on-demand Virtual/Planned; mix labels.

### Phase C

- Piecewise price/capacity; live → Online.

## Risks

- Dataset currently dominates UI kWp (~300 kWp Mendeley vs ~40 kWp fleet if raw÷1000).
- Wrong readings table name zeros real sums.
- Fleet lat/lon still missing for weather backfill.
- Capacity unit ambiguity (W vs kWp).

## Success

Ops open NC and see **Filantropia’s 11 sites** (plus CRM/user virtuals), not Mendeley plants; energy/savings are sums of NC series or honest zero; Mendeley remains behind the ML train door only.
