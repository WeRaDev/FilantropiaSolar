# MVP-5 — Odoo lead fields + NC lifecycle client

**Status:** Implemented on `feat/mvp-5-odoo-nc-lifecycle-client`  
**Addon version:** `19.0.2.8.0`  
**Maps:** D1, D4 (client only; queue_job is MVP-6)

## Delivered

1. **`crm.lead` fields** — NC installation id, lifecycle, sync state/error, station snapshot, donation-application flag.
2. **`NcLifecycleClient`** — urllib client for `/api/lifecycle/v1/*`; token redaction in logs; env:
   - `FS_LIFECYCLE_API_BASE_URL` (default derived from `FS_API_BASE_URL`)
   - `FS_LIFECYCLE_API_TOKEN` (fallback `FS_PUBLIC_API_TOKEN`)
3. **Candidatura NGO submit** — creates lead with snapshot + best-effort `fs_create_virtual_station()`.
4. **Stage change** — entering *Qualified* promotes Planned; **Won does not** mark installed.
5. **CRM form page** “Filantropia NC” with manual Sync / Promote buttons.
6. **Unit tests** (no Odoo runtime): stage map, redaction, HTTP mock client.

## Upgrade

```bash
docker compose --profile odoo up -d odoo
docker exec filantropia-odoo odoo -d filantropia_public -u filantropia_solar_public --stop-after-init
```

Export lifecycle token into Odoo env (same as public token is OK for local):

```bash
export FS_PUBLIC_API_TOKEN="$(docker exec -u 33 filantropia-nextcloud php occ config:app:get filantropia_solar public_api_token)"
# recreate odoo container so env picks up token
```

## Tests

```bash
cd nextcloud-app/odoo/addons/filantropia_solar_public
python3 -m unittest tests.test_nc_lifecycle_client -v
```

## Not in this PR

- OCA `queue_job` packaging (MVP-6)
- Async job runner / dead-letter UI beyond lead fields
