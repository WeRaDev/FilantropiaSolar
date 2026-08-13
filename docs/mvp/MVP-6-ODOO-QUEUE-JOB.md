# MVP-6 — Odoo queue_job for NC lifecycle

**Status:** On `main` (PR #26); cold-start hardened via `scripts/setup-odoo.sh` + baked image  
**Addon:** `filantropia_solar_public` **19.0.2.11.0**  
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

## Image / dependencies

`queue_job` declares Python deps `openupgradelib` and `requests`. These are **baked** into the local Odoo image:

- `nextcloud-app/odoo/Dockerfile` (`FROM odoo:19.0`)
- Compose service `odoo` builds `filantropia-odoo:19.0` (not bare `odoo:19.0`)

Do **not** rely on one-off `pip install` inside a running container for cold-start.

## Deploy / local

Core stack first:

```bash
bash nextcloud-app/scripts/setup.sh
```

Odoo + jobrunner (idempotent):

```bash
bash nextcloud-app/scripts/setup-odoo.sh
# cold Odoo DB only (keeps Nextcloud volumes):
bash nextcloud-app/scripts/setup-odoo.sh --reset-volumes
# also enqueue one Virtual job and wait until done (no manual perform):
bash nextcloud-app/scripts/setup-odoo.sh --smoke
# combine:
bash nextcloud-app/scripts/setup-odoo.sh --reset-volumes --smoke
```

Manual equivalent:

```bash
export FS_PUBLIC_API_TOKEN="$(docker exec -u 33 filantropia-nextcloud php occ config:app:get filantropia_solar public_api_token)"
cd nextcloud-app
docker compose --profile odoo up -d --build odoo-db odoo
docker compose --profile odoo exec odoo odoo -d filantropia_public \
  -i queue_job,filantropia_solar_public --stop-after-init --without-demo=all
docker compose --profile odoo up -d odoo
```

Confirm jobrunner in logs:

```text
queue_job.jobrunner.runner: queue job runner ready for db filantropia_public
```

`odoo.conf`: `workers = 2`, `server_wide_modules = web,queue_job`.

### Cold-start acceptance

1. Odoo volumes reset (or first bring-up).
2. Image build succeeds; `python3 -c 'import openupgradelib'` inside container.
3. Modules install without manual pip.
4. Jobrunner ready line present.
5. One candidatura / smoke lead → `queue_job` row reaches **done** with **no** manual `perform`.

## Tests

```bash
cd nextcloud-app/odoo/addons/filantropia_solar_public
python3 -m unittest tests.test_nc_lifecycle_client tests.test_async_enqueue -v
```

## Not in this track

- MVP-7 end-to-end manual checklist automation
- Multi-worker production sizing / Redis job channels
- TRL4 cold-start (local Docker Desktop only for this hardening)
