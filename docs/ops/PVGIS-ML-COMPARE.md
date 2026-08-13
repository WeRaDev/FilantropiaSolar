# ML vs PVGIS production sanity check

Date: 2026-08-13

## Method
- **ML**: `POST http://127.0.0.1:8501/simulate/hourly` (and `predict/period` mode=simulated) for fleet stations.
- **PVGIS**: JRC classic `PVcalc` v5_2 monthly August `E_m` / 31 as mean daily kWh (tilt 35°, south, 14% loss).
- Spec artifact: `docs/ops/openapi.json` (PVGIS Web API 6). Live calls used public v5_2 JSON API because OpenAPI servers are relative `/api/v6`.

## Results (sample)
| Station | kWp | ML day kWh (2026-08-12) | kWh/kWp | PVGIS Aug mean daily | Ratio ML/PVGIS |
|---------|-----|-------------------------|---------|----------------------|----------------|
| Lisbon #1 | 46.0 | 278.9 | 6.06 | 251.7 | ~1.11 |
| Lisbon #2 | 16.32 | 99.0 | 6.06 | 89.7 | ~1.11 |
| Setubal #3 | 23.52 | 142.5 | 6.06 | 128.0 | ~1.11 |
| Lisbon #4 | 30.0 | 181.9 | 6.06 | 164.1 | ~1.11 |

Raw JSON: `docs/ops/pvgis-ml-compare-2026-08-13.json`

## Verdict
Production scale is **reasonable**. ML sits ~10–11% above PVGIS long-term August daily mean on a high-radiation API weather day (max GHI ~920 W/m²). That bias is expected versus a monthly average; no immediate retune of `system_efficiency` (0.85) for MVP.

## Follow-ups (optional)
1. Validate `seriescalc` hourly `P` with explicit `raddatabase` once non-zero responses are confirmed.
2. Per-station tilt/azimuth from metadata instead of 35°/0°.
3. Same-calendar-day match when PVGIS coverage reaches recent years.
