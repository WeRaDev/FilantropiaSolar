# MVP-3 — Public API Existing + Planned filter

**Status:** Implemented on `feat/mvp-3-public-stations-filter`  
**App version:** 3.2.2  
**Decisions:** D3, D9  

## Change

`GET /api/public/v1/stations` and `GET /api/public/v1/dashboard` now use
`InstallationMapper::findPublicStations()`:

- `lifecycle_state` in (`planned`, `running`)
- not `soft_removed`
- never Virtual

Each station includes `public_category` (`planned` | `existing`) and
`lifecycle_state` for Odoo map/list consumers.

Dashboard also returns `planned_count` and `existing_count`.

## Fallback

If lifecycle columns are missing (pre-MVP-1 upgrade), falls back to
`findAllBySource('dataset')` and logs a warning.

## Deploy

```bash
docker exec -u 33 filantropia-nextcloud php occ upgrade
# Odoo map smoke:
# curl -sS -H "Authorization: Bearer $TOKEN" \
#   http://filantropia-nextcloud/apps/filantropia_solar/api/public/v1/stations
```

## Odoo compatibility

Existing Odoo fields (`id`, `name`, `location`, lat/lng, `capacity_kwp`,
dates) unchanged. Extra keys are additive.

## Not in this PR

- Odoo CRM lifecycle client (MVP-5/6)
- Admin UI (MVP-4)
