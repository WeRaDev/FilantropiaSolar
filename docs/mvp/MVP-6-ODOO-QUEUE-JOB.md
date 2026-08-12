# MVP-6 — Odoo queue_job for NC lifecycle

**Status:** Implemented on `feat/mvp-6-odoo-queue-job`  
**Addon:** `filantropia_solar_public` **19.0.2.9.0**  
**Maps:** D7 (async CRM → NC)

## Decision

Use **OCA `queue_job` 19.0** (vendored under `nextcloud-app/odoo/addons/queue_job`).  
`base_sparse_field` is **core** in Odoo 19 Community (no separate vendor).  
ADR 0002 accepted path; no cron interim needed.

## Behaviour

| Event | Job |
|-------|-----|
| NGO candidatura lead create | `fs_enqueue_create_virtual` → `fs_create_virtual_station` |
| Stage → Qualified | `fs_enqueue_promote_planned` → `fs_promote_planned` |
| Stage → Won | **no job** (D4) |

Jobs use channel `root.filantropia`, identity keys `fs-virtual-{id}` / `fs-promote-{id}` (dedupe pending jobs).

CRM HTTP returns immediately after enqueue. Failures visible on:
- `crm.lead` → Filantropia NC tab (`fs_nc_sync_state` / `fs_nc_sync_error`)
- **Job Queue** menu (`queue.job`)

## Deploy / local

```bash
export FS_PUBLIC_API_TOKEN="$(docker exec -u 33 filantropia-nextcloud php occ config:app:get filantropia_solar public_api_token)"
cd nextcloud-app
# openupgradelib required by queue_job post_init
docker compose --profile odoo exec odoo pip install --break-system-packages openupgradelib requests || \
  docker compose --profile odoo exec -u root odoo pip install openupgradelib requests
docker compose --profile odoo up -d odoo
docker compose --profile odoo exec odoo odoo -d filantropia_public \
  -i queue_job -u filantropia_solar_public --stop-after-init
docker compose --profile odoo up -d odoo
```

Confirm jobrunner in logs:

```text
queue_job.jobrunner.runner: queue job runner ready for db filantropia_public
```

`odoo.conf`: `workers = 2`, `server_wide_modules = web,queue_job`.

## Tests

```bash
cd nextcloud-app/odoo/addons/filantropia_solar_public
python3 -m unittest tests.test_nc_lifecycle_client tests.test_async_enqueue -v
```

## Not in this PR

- MVP-7 end-to-end manual checklist automation
- Multi-worker production sizing / Redis job channels
