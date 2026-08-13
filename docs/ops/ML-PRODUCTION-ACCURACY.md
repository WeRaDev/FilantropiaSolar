# ML energy production accuracy — validation report

**Date:** 2026-08-13  
**Status:** **PASS** (local stack NC 3.2.21 + ML healthy)  
**Branch:** `feat/analytics-nc-historical-hourly-status` (PR #31)  
**Re-run:** `python3 nextcloud-app/scripts/verify-ml-production.py --json docs/ops/ml-production-accuracy-latest.json`

## Scope

Validate that fleet-by-meta production used for:

- Predicted analytics (`POST /predict/period` mode=`simulated`)
- Series gap-fill (`POST /simulate/hourly`)

is **physically plausible** and **scale-consistent** vs PVGIS long-term August means for Portugal sites.

This is a **scale / physics gate**, not a same-calendar-day GHI match (PVGIS classic series coverage lags current years).

## Method

| Check | Source |
|-------|--------|
| Health | `GET {ML}/health` — models loaded, locations |
| Day energy | `POST /simulate/hourly` for target UTC day |
| Predicted path | `POST /predict/period` mode=`simulated` + capacity/coords |
| PVGIS baseline | JRC `PVcalc` v5_2 monthly August `E_m` / 31 (tilt 35°, south, loss 14%) |
| Physics | peak hour ≤ ~capacity; night ≈ 0; capacity linearity 1.2→12 kWp = 10×; P/STC ≈ 0.82–0.85 |
| Consistency | day sum `predict/period` ≈ `simulate/hourly` |

OpenAPI reference for PVGIS v6 (relative servers): `docs/ops/openapi.json`. Live PVGIS calls use public v5_2 JSON.

## Results (2026-08-12, weather_source=api)

| Station | kWp | ML kWh | kWh/kWp | Peak/kWp | PVGIS Aug mean daily | ML/PVGIS | Flags |
|---------|-----|--------|---------|----------|----------------------|----------|-------|
| Lisbon | 46.0 | 278.9 | 6.06 | 0.76 | 251.7 (5.47) | 1.11 | none |
| Setúbal | 23.52 | 142.5 | 6.06 | 0.77 | 128.0 (5.44) | 1.11 | none |
| Faro | 7.0 | 44.2 | 6.31 | 0.79 | 38.2 (5.46) | 1.16 | none |
| Braga | 64.93 | 389.1 | 5.99 | 0.75 | 324.1 (4.99) | 1.20 | none |
| WeRa Global | 1.2 | 7.28 | 6.06 | 0.76 | 6.36 (5.30) | 1.15 | none |
| Vazinha | 0.54 | 3.27 | 6.06 | 0.76 | 2.90 (5.36) | 1.13 | none |
| ARIA | 4.5 | 27.3 | 6.06 | 0.76 | 24.7 (5.50) | 1.10 | none |

### Physics / consistency

- **Mean ML / PVGIS Aug daily:** **1.15** (clear high-GHI day vs monthly average — expected)
- **Capacity linearity (WeRa coords):** 1.2 kWp → 12 kWp = **10.000×**
- **Peak hour:** always **&lt; 1.0 × capacity** (~0.75–0.79×)
- **P / STC** (`cap × GHI/1000`): **~0.82–0.85** — matches physics `system_efficiency ≈ 0.85` + light temp derate
- **Night production:** none
- **`predict/period` vs `simulate/hourly`:** ratio ≈ **1.0**
- **Ops stations outside Mendeley corpus:** Predicted path works via sim mode + capacity/coords (NC 3.2.21)

Raw JSON snapshot: `docs/ops/ml-production-accuracy-2026-08-13.json`  
Earlier sample note: `docs/ops/PVGIS-ML-COMPARE.md`

## Verdict

**PASS — production scale consistent with PVGIS August means and physics bounds.**

No retune of ML `system_efficiency` (0.85) required for MVP / local deploy.

## Pass criteria (gate)

Use before merge or TRL5 cutover:

1. `GET /health` → `status=healthy`, models_loaded ≥ 1  
2. `python3 nextcloud-app/scripts/verify-ml-production.py` exit **0**  
3. Mean ML/PVGIS in **0.85–1.25** on a clear summer day (or **0.75–1.35** with notes)  
4. Linearity ratio 12/1.2 in **9.5–10.5**  
5. Zero impossible peaks (`peak_over_kwp > 1.05`)  
6. Predicted UI: ops station (e.g. WeRa) opens chart with SIMULATED badge (manual)

## Deploy notes

### Local (already applied for PR #31)

```bash
# App is bind-mounted; after pull:
docker exec -u 33 filantropia-nextcloud php occ upgrade
docker restart filantropia-ml   # pick up ml-service/main.py if needed
curl -sS http://127.0.0.1:8501/health
python3 nextcloud-app/scripts/verify-ml-production.py --json /tmp/ml-acc.json
```

NC app version for this validation: **3.2.21**.

### TRL5 (operator — after backup)

See `docs/mvp/MVP-7-GATES-TRL5.md`. Additional ML steps:

1. Rebuild/restart `ml-service` with current `nextcloud-app/ml-service`  
2. From host or NC network: `curl ML:8501/health`  
3. Run verifier with `ML_BASE=http://127.0.0.1:8501` (or internal URL)  
4. Smoke Predicted analytics on one ops station + one dataset station  
5. Confirm SeriesRollForward can call `/simulate/hourly` (no “installation not found”)

## Optional follow-ups (non-blocking)

1. Same-calendar-day PVGIS `seriescalc` once hourly `P` is non-zero with explicit `raddatabase`  
2. Per-station tilt/azimuth from metadata instead of 35°/0°  
3. Wire verifier into CI as a scheduled/manual job (needs network to JRC or `--skip-pvgis` physics-only mode)
