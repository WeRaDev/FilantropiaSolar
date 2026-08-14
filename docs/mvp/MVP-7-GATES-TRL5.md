# MVP-7 — Automated + manual gates + TRL5 deploy

**Status:** Automated gates green on `main` (PR #31 / NC **3.2.26**). **Local CRM lifecycle script signed eng 2026-08-14** (lead 56 → NC 38). **TRL5 backup taken** (`20260814-000958`, see `docs/ops/TRL5-BACKUP.md`). TRL5 code cutover (3.2.26 deploy) and remaining TRL5 smoke sign-off still open.  
**Depends on:** MVP-1…6, series epic (NC 3.2.16+ / Odoo 19.0.2.22.0), analytics PR #31.

## Automated gates

| Gate | How | Local result (2026-08-14) |
|------|-----|---------------------------|
| CI quality gates | Gitea Actions on PR #31 tip `c0fb7ae` | PASS (run 229) |
| Revisor QA | Gitea Actions on PR #31 tip `c0fb7ae` | PASS (run 230) |
| PR merge | Gitea PR #31 → `main` | **merged** `ad444b7` |
| Desktop pytest | `cd desktop && ../.ci-venv/bin/python -m pytest -q` | 42 passed, 1 skipped |
| Ruff format/lint (desktop) | `.ci-venv/bin/ruff format --check desktop && ruff check desktop` | PASS |
| NC vitest | `cd nextcloud-app && npm test` | 18 passed |
| NC app version | `occ` / `appinfo/info.xml` | **3.2.26** (`needsDbUpgrade: false`) |
| Migration columns | MySQL `oc_fs_readings.provenance`, `oc_fs_installations.grid_connection_type` | present |
| Off-grid seeds | Penedo off-grid, WeRa Global | `off_grid` + `running` |
| ML `/health` | `curl :8501/health` | healthy, 9 models |
| ML production accuracy | `python3 nextcloud-app/scripts/verify-ml-production.py --skip-pvgis` | **PASS** (linearity 10.0; PVGIS optional full run also PASS ~1.15) |
| Predicted ops stations | `/predict/period` simulated + capacity (NC id not in Excel) | success (WeRa etc.; PR #31) |
| FilantropiaSolarAdmin ACL | viewer 403 on edit/lifecycle; measured upload 200 | PASS (prior) |
| CRM field | `crm_lead.fs_station_grid_connection_type` | present (module 19.0.2.22.0) |
| Series jobs registered | `occ background-job:list` | Backfill **id 68**, RollForward **id 69** |
| SeriesRollForward interval | `occ background-job:execute 69 --force-execute -vvv` | **timed**, next = last + **3600s** (1h) |
| Measured wins | import measured over simulated | PASS (prior / PR #31 upload path) |
| Analytics UX (PR #31) | Historical SoT, Predicted chart, Lisbon TZ, dual I/O, map pin, upload stacking | shipped 3.2.22–3.2.26 |

App-only PHPUnit (SavingsService/FilantropiaAccess) needs full Nextcloud OCP bootstrap; treat as SKIP_ENV when CI desktop gates are green.

### Remaining automated (optional)

| Gate | Notes |
|------|--------|
| Full PVGIS verifier | `verify-ml-production.py` without `--skip-pvgis` (network); already PASS historically |
| ACL re-probe | Re-run viewer vs FilantropiaSolarAdmin on fresh TRL5 after cutover |

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
   - After SeriesRollForwardJob / SeriesBackfillJob chunk: ops list shows `has_series_data`, non-zero production when hours filled; efficiency = last complete Europe/Lisbon hour kWh/kWp; savings use 0.4/1.0 by `grid_connection_type`.  
   - Upload measured hour as non-admin: provenance `measured`; sim cannot overwrite.  
   - Upload modal stacks above Analysis (z-index 20050) with black text.

**Sign-off (operator):**

| Step | Pass | Initials | Date |
|------|------|----------|------|
| 1 New → no NC | **Y** (local) | eng | 2026-08-14 |
| 2 Qualify → Virtual | **Y** (local) | eng | 2026-08-14 |
| 3 Proposition → Planned on map | **Y** (local; public API after Running) | eng | 2026-08-14 |
| 4 Installed → Running | **Y** (local) | eng | 2026-08-14 |
| 5 Demotion | **Y** (local → planned) | eng | 2026-08-14 |
| 6 Profile mirror | **Y** (local; capacity 3.1 / location updated on NC) | eng | 2026-08-14 |
| 7 Series + measured upload | **Y** partial (local) | eng | 2026-08-14 |

**Local CRM script evidence (2026-08-14, non-prod stack):**

| Check | Result |
|-------|--------|
| Test lead | CRM `crm_lead` **id 56** `MVP7-SIGNOFF-*`, `fs_is_donation_application=true` |
| Step 1 New | No `fs_nc_installation_id` / no lifecycle until Qualify |
| Step 2 Qualified | NC **virtual** via queue_job; install id `Lisbon MVP7_lead56` |
| Step 3 Proposition | NC **planned** |
| Step 4 Installed | NC **running**, `fs_nc_db_id=38`, source `crm` |
| Step 5 Demotion → Proposition | NC **planned** via set-lifecycle |
| Step 5b re-Installed | NC **running** again |
| Step 6 Profile | NC `capacity_kwp=3.10`, `location=Lisbon MVP7 Updated`, `grid_price_kwh=0.18`; public API lists station (`public_category=existing`) |
| Step 7 Series job | `SeriesRollForwardJob` id 69 force-execute **timed**, next = last+1h |
| Step 7 Night window | 00:18 UTC force-run inserted **0** sim hours (outside Europe/Lisbon 05:00–22:00) — expected |
| Step 7 Measured | Row `oc_fs_readings` installation 38 @ 2026-08-13 12:00, `production_kwh=0.42`, `provenance=measured` |
| Modules | Odoo `filantropia_solar_public` **19.0.2.22.0**, `queue_job` installed; NC webhook URL set; NC app **3.2.26** |
| UI measured upload | Not re-clicked in browser this run (API is session-auth); stacking/font shipped 3.2.26 — operator may spot-check UI |


## TRL5 deploy note (wera-ss-pt-tv-1)

**Hostname:** `wera-ss-pt-tv-1.tailfb390c.ts.net` · public `filantropiasolar.wera.global`  
**Compose:** `docker-compose.yml` + `docker-compose.trl5.yml` (NC `:18080`, Odoo `:8069`, ML `:8501`).  
**Minimum NC on cutover:** **3.2.26** (PR #31 analytics + series roll-forward hourly).

### Before touch

1. **Backup first (mandatory)** — **DONE 2026-08-14**  
   - Runbook + checksums: [`docs/ops/TRL5-BACKUP.md`](../ops/TRL5-BACKUP.md) stamp **`20260814-000958`**.  
   - Remote: `/opt/FilantropiaSolar/backups/trl5-20260814-000958/` (+ bundle `.tgz`).  
   - Local (gitignored): `nextcloud-app/.local-backups/trl5-20260814-000958/`.  
   - Odoo full `pg_dump -Fc` 4.5M; NC `mysqldump` gz; COW `page_inicio` arch_len **235554**.  
   - TRL5 NC app **at backup time:** 3.1.1 (cutover still needed for 3.2.26).  
   - **Never** `reset_website_cows=1` without a restore path.

2. Confirm automated table above is green on the `main` SHA you deploy (currently `59d3bb5`+ / PR #31 merge `ad444b7`+).

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
- **SeriesRollForwardJob** is a **TimedJob** with **interval 3600s (1 hour)**; production window 05:00–22:00 Europe/Lisbon; fills last 1–2 complete hours only.  
- **Do not** force full multi-year backfill in one shot on first boot under load.  
- Prefer: verify ML `POST /simulate/hourly` from NC network, then  
  `occ background-job:execute <rollforward-id> --force-execute`  
  then optional backfill (chunked: 7 days/station/run).  
- Backfill is incremental (`BACKFILL_CHUNK_DAYS = 7`); repeat runs catch up history.  
- Note: `occ background-job:list` does **not** show interval; use `background-job:execute -vvv` (Next execution = last + 1h) or runtime `TimedJob::interval`.

### Post-deploy smoke

| Check | Expect |
|-------|--------|
| `curl NC/status.php` | installed, needsDbUpgrade false |
| NC app version | **3.2.26+** |
| `curl ML/health` | healthy |
| `verify-ml-production.py` | exit 0 PASS |
| Odoo `/web/login`, `/instalacoes` | 200; COW map intact |
| Public API stations | Planned+Running only; grid fields present |
| Ops list | efficiency/savings keys; off-grid factor 1.0 |
| CRM NC Stations | import/reconcile symmetry |
| Analytics Predicted (ops station) | chart + SIMULATED badge |
| Analytics Historical + upload | chart; upload above modal; black text |
| SeriesRollForward | force-execute; next +1h |

**TRL5 sign-off:**

| Item | Pass | Initials | Date |
|------|------|----------|------|
| Backup taken | **Y** (`20260814-000958`) | eng | 2026-08-14 |
| NC 3.2.26+ + upgrade | | | |
| Odoo 19.0.2.22.0 | | | |
| COW map OK | pre-check **Y** (arch_len 235554 at backup) | eng | 2026-08-14 |
| Webhook/token OK | | | |
| ML hourly OK | | | |
| ML production accuracy gate | | | |
| Series job smoke (1h interval) | | | |
| Public site smoke | | | |
| Analytics Historical + Predicted smoke | | | |

## Related

- `docs/ops/TRL5-BACKUP.md`  
- `docs/ops/SERIES-SIM-GRID-ADMIN.md`  
- `docs/ops/CRM-NC-LIFECYCLE-MIRROR.md`  
- `docs/ops/ODOO-WEBSITE-COW-VIEWS.md`  
- `docs/ops/ML-PRODUCTION-ACCURACY.md`  
- `docs/ops/PR31-DEPLOY-SMOKE.md`  
- `nextcloud-app/scripts/verify-ml-production.py`  
- `nextcloud-app/scripts/setup-trl5.sh`  
- Gitea PR #31: `/wera-global/FilantropiaSolar/pulls/31` (merged)
