# MVP-5 — Odoo lead fields + NC lifecycle client

**Status:** Implemented and extended by CRM/NC lifecycle mirror (PR #29)  
**Odoo addon:** `19.0.2.19.0+`  
**NC app:** `3.2.13+`  
**Maps:** D1, D4, D7 (with MVP-6 queue_job)

## Delivered

1. **`crm.lead` fields** — NC installation/db id, lifecycle, sync state/error/origin,
   station snapshot, donation-application flag.
2. **`NcLifecycleClient`** — urllib client for lifecycle API; token redaction; env:
   - `FS_LIFECYCLE_API_BASE_URL` (default derived from `FS_API_BASE_URL`)
   - `FS_LIFECYCLE_API_TOKEN` (fallback `FS_PUBLIC_API_TOKEN`)
3. **Outbound CRM → NC**
   - Virtual / promote-planned / mark-installed
   - Demotion via `set-lifecycle`
   - Profile push via `POST .../profile`
4. **Inbound NC → CRM** — webhook `/filantropia/nc/lifecycle/http` +
   `fs.station.sync.import_all_from_nc` (hourly cron + dashboard button).
5. **Candidatura** — opportunity lead with snapshot; Virtual deferred until Qualified.
6. **CRM UI** — Filantropia NC page on lead; **Filantropia → NC Dashboard** and
   **NC Stations** menus.
7. **Unit tests** (no Odoo runtime): stage map (incl. demotion), redaction, HTTP client.

## Lifecycle stage map (ADR 0006)

| CRM | NC |
|-----|-----|
| New | none |
| Qualified | virtual |
| Proposition | planned |
| Installed | running |

## Upgrade (local)

```bash
# NC
docker exec -u 33 filantropia-nextcloud php occ upgrade
docker exec -u 33 filantropia-nextcloud php occ config:app:set filantropia_solar \
  odoo_lifecycle_webhook_url --value='http://filantropia-odoo:8069/filantropia/nc/lifecycle/http'

# Odoo (stop web container first if port 8069 is bound)
docker stop filantropia-odoo
docker run --rm --network container:filantropia-odoo-db \
  -e HOST=127.0.0.1 -e USER=odoo -e PASSWORD=odoo_dev_password \
  -v "$PWD/nextcloud-app/odoo/addons:/mnt/extra-addons" \
  -v "$PWD/nextcloud-app/odoo/config/odoo.conf:/etc/odoo/odoo.conf:ro" \
  filantropia-odoo:19.0 \
  odoo -d filantropia_public -u filantropia_solar_public --stop-after-init --without-demo=all
docker start filantropia-odoo
```

Export lifecycle/public token into Odoo env (`FS_PUBLIC_API_TOKEN` /
`FS_LIFECYCLE_API_TOKEN`) so the client and webhook auth match NC.

## Tests

```bash
cd nextcloud-app/odoo/addons/filantropia_solar_public
python3 -m unittest tests.test_nc_lifecycle_client -v
```

## Ops notes

- Reconcile: Filantropia → NC Dashboard → **Import NC stations to CRM**.
- Full station list without “My Pipeline”: Filantropia → **NC Stations**.
- Dataset/Mendeley stations are **not** mirrored into CRM.
