# Ops: CRM ↔ NC lifecycle mirror

## Stage matrix
| CRM | NC lifecycle | `public_archived` | Public website map |
|-----|--------------|-------------------|--------------------|
| New | (no station) | — | — |
| Qualified | virtual | false | hidden |
| Proposition | planned | false | Planeada |
| Installed | running | false | Em operação |
| **Archived** | running | **true** | **hidden** (stats still count) |

Notes:
- **Archived is not a fifth NC lifecycle_state.** NC stays `running` with boolean `public_archived`.
- CRM stage xmlid: `filantropia_solar_public.stage_archived` (sequence 80, `is_won=False`).
- Soft-remove is different: drops public membership entirely; not the same as Archive.

## Day-to-day
| Task | Where |
|------|--------|
| See all mirrored stations | Odoo **Filantropia → NC Stations** |
| Import / reconcile from NC | **Filantropia → NC Dashboard → Import NC stations** |
| Change lifecycle | CRM pipeline stage **or** NC main app **Set lifecycle** **or** NC admin |
| Archive / unarchive public map | NC **Set lifecycle → Archived / Running** **or** CRM drag to **Archived / Installed** **or** NC admin Archive map |
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
| queue_job profile storm / `could not serialize access` | CRM job + NC webhook both write `crm.lead`; cancel pending `fs-profile-*`; module ≥ **19.0.2.32.0** (echo dampen + safe write) |
| Station profile edit in NC not in CRM | NC `PUT /api/v1/installations/{id}` must notify webhook (3.2.14+); check lead match via `odoo_lead_id` / `fs_nc_db_id` (location changes rewrite `installation_id`) |
| Map list click / center broken | COW map host; `stations_map.js?v=`; hard refresh — see `ODOO-WEBSITE-COW-VIEWS.md` |
| No **Archived** CRM column | Module ≥ 19.0.2.31.0 + `-u filantropia_solar_public`; ensure xmlid `filantropia_solar_public.stage_archived` |
| NC Set lifecycle missing Archived | App ≥ 3.2.34; hard-refresh browser; open a **Running** station |
| Archive not mirrored CRM↔NC | Webhook payload includes `public_archived`; Odoo `set_public_archived` client path; lead `fs_nc_public_archived` |


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
| Soft-removed | (no CRM stage) | `soft_removed` | — | webhook / import (active=False if gone) |
| Public archived | `fs_nc_public_archived`, stage **Archived** | `public_archived` | CRM stage **or** NC Set lifecycle **or** admin / API | webhook / import |

### Intentionally not mirrored
- CRM contact-only: `email_from`, `phone`, `contact_name`, candidatura bill attachments / description dump
- NC internal: `serial_number` (derived), measured series, ML cache, dataset training corpus
- Public map computed metrics (savings totals) — read-only public API, not CRM fields

## Integration tests (local stack)

```bash
cd nextcloud-app/odoo/addons/filantropia_solar_public
python3 -m unittest tests.test_nc_lifecycle_client tests.test_async_enqueue -v
python3 -m unittest tests.test_crm_nc_field_sync_integration -v
```

`test_crm_nc_field_sync_integration` exercises the full snapshot matrix against
Docker NC+Odoo (profile, CRM push, lifecycle, installation_id rewrite, import).

