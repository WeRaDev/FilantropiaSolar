# Series simulation, savings factor, FilantropiaSolarAdmin

NC app **3.2.18** · Odoo addon **19.0.2.22.0**

## What shipped

1. **Series provenance** on `oc_fs_readings.provenance`: `measured` | `simulated`.
   - Measured always wins; simulated only fills empty hours.
   - Hour buckets are **UTC**.
2. **`grid_connection_type`** on installations: `on_grid` | `off_grid`.
   - Seeded off-grid by name: **Penedo off-grid**, **WeRa Global**.
   - Savings: `kWh × grid_price_kwh × factor` with factor **0.4** (on-grid) / **1.0** (off-grid).
3. **List efficiency badge**: last series hour `production_kwh / capacity_kwp` (not the old ×1500 proxy).
4. **Jobs** (registered in `info.xml`):
   - `SeriesBackfillJob` — daily catch-up for **Running** ops stations; **7-day chunks** per station per run (`SeriesSimulationService::BACKFILL_CHUNK_DAYS`) so multi-year fleets do not timeout.
   - `SeriesRollForwardJob` — every **1h**, previous **2** complete hours (catch-up window).
5. **ML** `POST /simulate/hourly` — fleet-by-meta (lat/lon/capacity + range); NC persists.
6. **Auth group** `FilantropiaSolarAdmin` (or NC admin):
   - Required for lifecycle + master-data edit/delete.
   - Any logged-in user may **upload measured** readings (`POST .../import`).
   - Simulated persistence is jobs + admin only.

## Bootstrap

```bash
# After deploy / occ upgrade
docker exec -u 33 filantropia-nextcloud php occ upgrade
docker exec -u 33 filantropia-nextcloud php occ group:add FilantropiaSolarAdmin || true
docker exec -u 33 filantropia-nextcloud php occ group:adduser FilantropiaSolarAdmin <uid>
docker exec -u 33 filantropia-nextcloud php occ background:cron

# Optional manual job smoke (IDs from: occ background-job:list | grep Series)
docker exec -u 33 filantropia-nextcloud php occ background-job:execute <rollforward-id> --force-execute
docker exec -u 33 filantropia-nextcloud php occ background-job:execute <backfill-id> --force-execute

# Odoo module update (grid_connection_type field)
# update filantropia_solar_public to 19.0.2.22.0
```

## Notes

- Do not enable trust of empty series: empty → 0 / no series data.
- TRL5: run hourly roll-forward after ML health; repeat backfill daily until `complete` (see job logs). Full history is multi-run by design.
- List **Active** status = last complete UTC hour is **measured** (not merely any measured row in history).
- Analytics Historical mode reads **NC fs_readings** only for ops stations; badge HISTORICAL / SIMULATED / MIXED (n/m); Predicted mode badge always SIMULATED.
- CRM mirror carries `grid_connection_type` via lifecycle webhook / import.
- MVP-7 / TRL5 cutover checklist: `docs/mvp/MVP-7-GATES-TRL5.md`.
