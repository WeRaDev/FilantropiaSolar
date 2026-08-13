# Series simulation, savings factor, FilantropiaSolarAdmin

NC app **3.2.16** · Odoo addon **19.0.2.22.0**

## What shipped

1. **Series provenance** on `oc_fs_readings.provenance`: `measured` | `simulated`.
   - Measured always wins; simulated only fills empty hours.
   - Hour buckets are **UTC**.
2. **`grid_connection_type`** on installations: `on_grid` | `off_grid`.
   - Seeded off-grid by name: **Penedo off-grid**, **WeRa Global**.
   - Savings: `kWh × grid_price_kwh × factor` with factor **0.4** (on-grid) / **1.0** (off-grid).
3. **List efficiency badge**: last series hour `production_kwh / capacity_kwp` (not the old ×1500 proxy).
4. **Jobs** (registered in `info.xml`):
   - `SeriesBackfillJob` — daily catch-up install→now for **Running** ops stations.
   - `SeriesRollForwardJob` — every **12h**, previous 12 complete hours.
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

# Odoo module update (grid_connection_type field)
# update filantropia_solar_public to 19.0.2.22.0
```

## Notes

- Do not enable trust of empty series: empty → 0 / no series data.
- TRL5: run backfill only after local validation; 12h job is safe once ML `/simulate/hourly` responds on the station network.
- CRM mirror carries `grid_connection_type` via lifecycle webhook / import.
