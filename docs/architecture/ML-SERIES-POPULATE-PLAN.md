# ML series populate — design thinking plan

**Date:** 2026-08-14  
**Context:** Ops stations store hourly series in Nextcloud `oc_fs_readings` (SoT). Historical UI must show only existing rows. Populate fills gaps via ML without overwriting measured data.  
**App surface shipped in 3.2.29:** `POST /api/v1/installations/{id}/populate-series` + Edit modal actions.

## 1. Empathize / problem

| Pain | Evidence |
|------|----------|
| Empty / short series after fleet seed | Only roll-forward window filled; install_date years of history missing |
| Historical feels slow | On-demand `fillRange` during `/predict/period` historical path |
| Efficiency always 0% | Lookup required exact last-complete hour; series lagged wall clock |
| Wrong “dataset range” | UI mixed training Excel `from_date`/`to_date` with ops series bounds |
| Icons look stale | NC shell caches `app.png`; version badge/cache lag |

## 2. Define

**Job to be done:** For each ops station, maintain a continuous hourly series from **installation date → last complete Europe/Lisbon hour**, with:

1. **Measured** immutable when present  
2. **Simulated** only in empty hours  
3. Full row semantics: production + weather + capacity snapshot + grid price + savings factor  
4. Model choice: nearest trained corpus location (Lisbon, Setúbal, …)

**Non-goals (this plan phase):** live inverter feeds; piecewise tariff; training new site-specific models from ops measured data (V1 follow-up).

## 3. Ideate — model selection

### Current ML surface (`ml-service/main.py`)

- Trained ensembles per Mendeley installation id / location  
- `POST /simulate/hourly` — capacity + lat/lon + start/end UTC  
- `_nearest_installation_with_model(lat, lon)` — distance to corpus with loaded model  
- `POST /predict/period` — weather + simple physics or Excel historical (not NC SoT)

### Decision (target)

| Step | Behaviour |
|------|-----------|
| A | Resolve station lat/lon + capacity + `grid_connection_type` + `grid_price_kwh` |
| B | Call nearest-model helper (haversine to LOCATION_COORDS / trained sites) |
| C | Prefer `simulate/hourly` with that model’s feature pipeline when available |
| D | Fallback: physics `predict_production_simple` + Open-Meteo weather (today’s SeriesSimulationService path) |
| E | Persist only empty hours as `provenance=simulated` |

Document model id used on each fill batch in logs (`model_ref`, `distance_km`).

## 4. Prototype — data contract per hour

Each `oc_fs_readings` row (and future export) should expose:

| Field | Source |
|-------|--------|
| `timestamp` | Europe/Lisbon hour key |
| `production_kwh` | ML or measured |
| `temperature_c`, `cloud_cover_pct`, `solar_radiation_wm2`, humidity/wind when available | ML/weather API |
| `provenance` | `measured` \| `simulated` |
| Station-level (denormalized on read, not necessarily stored per hour) | `capacity_kwp`, `grid_price_kwh`, `grid_connection_type`, `self_consumption_factor`, `savings_eur = production * price * factor` |

**Export / View data:** join station snapshot at read time so every datapoint carries economics + capacity.

## 5. Test / acceptance

1. Populate WeRa Global from `2025-08-23` → now: inserted > 0; measured count unchanged on re-run  
2. Historical calendar min/max = `series_from_date` / `series_to_date`  
3. Historical `/predict/period` does **not** call ML fill (p95 latency << predicted)  
4. Predicted mode still generates for arbitrary center date  
5. Efficiency > 0 when latest daylight hour exists in series  
6. Edit → change installation date → populate starts at new date (optional purge simulated-before-date: **confirm with ops before auto-delete**)

## 6. Implementation phases

### Phase 0 — shipped 3.2.29 (NC app)

- Efficiency fallback to latest hour ≤ last complete  
- Historical = read-only series (no on-demand fill)  
- Calendar clamped to series bounds  
- Edit: installation date, View dataset, Populate dataset  
- `populate-series` API chunked via existing `SeriesSimulationService::fillRange`

### Phase 1 — ML service (next)

1. Public `GET /models` — list loaded models + lat/lon anchors  
2. Harden `POST /simulate/hourly` response: always include weather columns + `model_id` + `method`  
3. Unit tests: nearest model for Torres Vedras → Lisbon; Faro coords → Faro  
4. Optional: `POST /simulate/hourly/enriched` returning savings fields for client convenience  

### Phase 2 — NC wire-up

1. SeriesSimulationService passes lat/lon already; parse `model_id` into job logs  
2. Optional admin job: fleet-wide populate with concurrency limit 1  
3. Reading export includes station economics columns  

### Phase 3 — quality

1. Night hours: keep 0 production with simulated provenance (already)  
2. Cap efficiency display at sensible UI max (e.g. 1.2 kWh/kWp/h) for bad outliers  
3. PVGIS / production accuracy gate remains on deploy  

## 7. Risks

| Risk | Mitigation |
|------|------------|
| Long populate timeouts | 7-day chunks; background SeriesBackfillJob; UI progress message |
| Wrong model geography | Nearest + max distance threshold → physics fallback |
| Accidental measured overwrite | Only `insertSimulatedIfEmpty` |
| Icon/version cache | Bump app version; `occ maintenance:repair`; hard refresh |

## 8. Success metrics

- 10/10 running fleet stations: series_from ≈ installation_date (after populate)  
- Historical open < 1s when series warm  
- Zero “0% efficiency” for stations with daylight simulated/measured hours in last 48h  
