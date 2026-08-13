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
| Map list click / center broken | COW map host; `stations_map.js?v=`; hard refresh — see `ODOO-WEBSITE-COW-VIEWS.md` |
