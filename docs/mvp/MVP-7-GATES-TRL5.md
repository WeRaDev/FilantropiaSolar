# MVP-7 — Automated + manual gates + TRL5 deploy

**Status:** Local gates exercised post PR #30 merge (`893a8eb`). TRL5 production cutover remains operator-signed.  
**Depends on:** MVP-1…6, series epic (NC 3.2.16 / Odoo 19.0.2.22.0).

## Automated gates

| Gate | How | Local result (2026-08-13) |
|------|-----|---------------------------|
| CI quality gates | Gitea Actions on PR #30 | PASS |
| Revisor QA | Gitea Actions on PR #30 | PASS |
| Desktop pytest | `cd desktop && pytest -q` | 42 passed, 1 skipped |
| Ruff format/lint | `ruff format --check . && ruff check .` | PASS |
| NC app version | `occ` / `appinfo/info.xml` | **3.2.21** (PR #31 analytics + ML ops sim) |
| Migration columns | MySQL `provenance`, `grid_connection_type` | present |
| Off-grid seeds | Penedo off-grid, WeRa Global | `off_grid` |
| ML `/simulate/hourly` | POST fleet-by-meta | success |
| ML production accuracy | `python3 nextcloud-app/scripts/verify-ml-production.py` | **PASS** (2026-08-13; mean ML/PVGIS ~1.15, linearity 10.0) |
| Predicted ops stations | `/predict/period` simulated + capacity (NC id not in Excel) | success (WeRa etc.) |
| FilantropiaSolarAdmin ACL | viewer 403 on edit/lifecycle; measured upload 200 | PASS |
| CRM field | `crm_lead.fs_station_grid_connection_type` | present (module 19.0.2.22.0) |
| Series jobs registered | `occ background-job:list` | Backfill + RollForward IDs present |
| Measured wins | import measured over simulated | PASS |

App-only PHPUnit (SavingsService/FilantropiaAccess) needs full Nextcloud OCP bootstrap; treat as SKIP_ENV when CI desktop gates are green.

## Manual CRM ↔ NC lifecycle script

Run on a non-production CRM lead (or TRL5 after backup). Do **not** log tokens.

1. **New application (no NC station)**  
   - Create/submit donation form → CRM lead in **New**.  
   - Expect: no NC station / no `fs_nc_installation_id`.

2. **Qualify → Virtual**  
   - Move lead to **Qualified**.  
   - Expect: queue job creates NC **virtual**; CRM shows NC installation id + lifecycle `virtual`.

3. **Proposition → Planned**  
   - Move to **Proposition**.  
   - Expect: NC **planned**; public map lists station as Planned (not Virtual).

4. **Installed → Running**  
   - Move to **Installed** / Won.  
   - Expect: NC **running**; public category Existing/Running; ops list shows Running.

5. **Demotion**  
   - Move CRM stage back (e.g. Running → Proposition/Qualified).  
   - Expect: NC lifecycle follows via set-lifecycle (ADR 0006).

6. **Profile edit**  
   - Change name/location/capacity/grid price/grid connection in NC or CRM.  
   - Expect: mirror both ways within reconcile window.

7. **Series / metrics (Running)**  
   - After SeriesRollForwardJob / SeriesBackfillJob chunk: ops list shows `has_series_data`, non-zero production when hours filled; efficiency = last hour kWh/kWp; savings use 0.4/1.0 by `grid_connection_type`.  
   - Upload measured hour as non-admin: provenance `measured`; sim cannot overwrite.

**Sign-off (operator):**

| Step | Pass | Initials | Date |
|------|------|----------|------|
| 1 New → no NC | | | |
| 2 Qualify → Virtual | | | |
| 3 Proposition → Planned on map | | | |
| 4 Installed → Running | | | |
| 5 Demotion | | | |
| 6 Profile mirror | | | |
| 7 Series + measured upload | | | |

## TRL5 deploy note (wera-ss-pt-tv-1)

**Hostname:** `wera-ss-pt-tv-1.tailfb390c.ts.net` · public `filantropiasolar.wera.global`  
**Compose:** `docker-compose.yml` + `docker-compose.trl5.yml` (NC `:18080`, Odoo `:8069`, ML `:8501`).

### Before touch

1. **Backup first (mandatory)**  
   - Odoo DB dump + website COW export (`docs/ops/ODOO-WEBSITE-COW-VIEWS.md`).  
   - NC DB dump.  
   - **Never** `reset_website_cows=1` without a restore path.

2. Confirm local PR #30 validation is green (this doc automated table).

### Deploy sequence

```bash
# On TRL5, from FilantropiaSolar/nextcloud-app (or use setup-trl5.sh for cold start)
export COMPOSE_FILE=docker-compose.yml:docker-compose.trl5.yml
git fetch origin && git checkout main && git pull --ff-only origin main

docker compose pull
docker compose build ml-service
docker compose --profile odoo up -d

docker exec -u 33 filantropia-nextcloud php occ upgrade
docker exec -u 33 filantropia-nextcloud php occ maintenance:mode --off
docker exec -u 33 filantropia-nextcloud php occ group:add FilantropiaSolarAdmin || true
docker exec -u 33 filantropia-nextcloud php occ group:adduser FilantropiaSolarAdmin admin || true

# Odoo module to 19.0.2.22.0 (grid_connection_type) — use free HTTP port if server already bound
docker exec filantropia-odoo odoo -c /etc/odoo/odoo.conf -d filantropia_public \
  -u filantropia_solar_public --stop-after-init --http-port=8070 --workers=0
docker compose --profile odoo up -d odoo

# Webhook + token (no echo of secrets)
# occ config:app:set filantropia_solar odoo_lifecycle_webhook_url --value=http://filantropia-odoo:8069/filantropia/nc/lifecycle/http
# ensure public_api_token / lifecycle token match Odoo ICP / env

# CRM: Import NC stations from Filantropia dashboard (or wait hourly reconcile)
```

### Series jobs on TRL5

- Jobs are registered via `info.xml` after app enable/upgrade: `SeriesBackfillJob`, `SeriesRollForwardJob`.  
- **Do not** force full multi-year backfill in one shot on first boot under load.  
- Prefer: verify ML `POST /simulate/hourly` from NC network, then  
  `occ background-job:execute <rollforward-id> --force-execute`  
  then optional backfill (chunked: 7 days/station/run).  
- Backfill is incremental (`BACKFILL_CHUNK_DAYS = 7`); repeat runs catch up history.

### Post-deploy smoke

| Check | Expect |
|-------|--------|
| `curl NC/status.php` | installed, needsDbUpgrade false |
| `curl ML/health` | healthy |
| `verify-ml-production.py` | exit 0 PASS |
| Odoo `/web/login`, `/instalacoes` | 200; COW map intact |
| Public API stations | Planned+Running only; grid fields present |
| Ops list | efficiency/savings keys; off-grid factor 1.0 |
| CRM NC Stations | import/reconcile symmetry |
| Analytics Predicted (ops station) | chart + SIMULATED badge |

**TRL5 sign-off:**

| Item | Pass | Initials | Date |
|------|------|----------|------|
| Backup taken | | | |
| NC 3.2.21+ + upgrade | | | |
| Odoo 19.0.2.22.0 | | | |
| COW map OK | | | |
| Webhook/token OK | | | |
| ML hourly OK | | | |
| ML production accuracy gate | | | |
| Series job smoke (12h) | | | |
| Public site smoke | | | |
| Analytics Historical + Predicted smoke | | | |

## Related

- `docs/ops/SERIES-SIM-GRID-ADMIN.md`  
- `docs/ops/CRM-NC-LIFECYCLE-MIRROR.md`  
- `docs/ops/ODOO-WEBSITE-COW-VIEWS.md`  
- `docs/ops/ML-PRODUCTION-ACCURACY.md`  
- `docs/ops/PR31-DEPLOY-SMOKE.md`  
- `nextcloud-app/scripts/verify-ml-production.py`  
- `nextcloud-app/scripts/setup-trl5.sh`  
