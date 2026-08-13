# Ops: CRM ↔ NC lifecycle mirror

## Stage matrix
| CRM | NC | Public map |
|-----|-----|------------|
| New | (no station) | — |
| Qualified | virtual | hidden |
| Proposition | planned | Planeada |
| Installed | running | Em operação |

## Day-to-day
| Task | Where |
|------|--------|
| See all mirrored stations | Odoo **Filantropia → NC Stations** |
| Import / reconcile from NC | **Filantropia → NC Dashboard → Import NC stations** |
| Change lifecycle | CRM pipeline stage **or** NC admin lifecycle actions |
| Edit name/location/capacity/website/description | CRM lead Filantropia NC tab **or** NC station edit (both sync) |
| NGO application | Website `/candidatura` → CRM opportunity (New); promote to Qualified to create Virtual |

## Config checklist
- NC `public_api_token` or `lifecycle_api_token`
- NC `odoo_lifecycle_webhook_url` → `http://filantropia-odoo:8069/filantropia/nc/lifecycle/http` (compose network)
- Odoo env `FS_PUBLIC_API_TOKEN` / `FS_LIFECYCLE_API_TOKEN` / `FS_LIFECYCLE_API_BASE_URL`
- Odoo module `filantropia_solar_public` upgraded; queue_job channel `root.filantropia`

## Not mirrored
- Mendeley `source=dataset` training stations (ops list / CRM import exclude them)

## Troubleshooting
| Symptom | Check |
|---------|--------|
| CRM missing stations | Import button; lead `user_id` not OdooBot; open **NC Stations** not only My Pipeline |
| NC change not in CRM | Webhook URL + token; Odoo logs; lead `fs_nc_sync_*` fields |
| CRM stage not in NC | queue_job pending/failed; `fs_nc_sync_error` on lead |
| Station profile edit in NC not in CRM | NC `PUT /api/v1/installations/{id}` must notify webhook (3.2.14+); check lead match via `odoo_lead_id` / `fs_nc_db_id` (location changes rewrite `installation_id`) |
| Map list click / center broken | COW map host; `stations_map.js?v=`; hard refresh — see `ODOO-WEBSITE-COW-VIEWS.md` |


## Station field matrix (canonical sync)

| Field | CRM | NC | CRM→NC | NC→CRM |
|-------|-----|----|--------|--------|
| Name | `name`, `partner_name` | `name` | profile / virtual | webhook / import |
| Location label | `fs_station_location_label`, `city` | `location` | profile / virtual | webhook / import |
| Latitude / longitude | `fs_station_latitude/longitude` | `latitude` / `longitude` | profile / virtual | webhook / import |
| Capacity kWp | `fs_station_capacity_kwp` | `capacity_kwp` | profile / virtual | webhook / import |
| Grid price EUR/kWh | `fs_station_grid_price_kwh` | `grid_price_kwh` | profile / virtual | webhook / import (3.2.15+) |
| Website | `fs_station_website`, `website` | `website` | profile / virtual | webhook / import |
| Short description | `fs_station_short_description` | `short_description` | profile / virtual | webhook / import |
| Lifecycle | `fs_nc_lifecycle_state`, `stage_id` | `lifecycle_state` | stage actions / set-lifecycle | webhook / import |
| Link keys | `fs_nc_installation_id`, `fs_nc_db_id` | `installation_id`, `id` | bind-lead / virtual | webhook / import |
| Soft-removed | (no CRM stage; archived if missing from ops list) | `soft_removed` | — | webhook / import (active=False if gone) |

### Intentionally not mirrored
- CRM contact-only: `email_from`, `phone`, `contact_name`, candidatura bill attachments / description dump
- NC internal: `serial_number` (derived), measured series, ML cache, dataset training corpus
- Public map computed metrics (savings totals) — read-only public API, not CRM fields
