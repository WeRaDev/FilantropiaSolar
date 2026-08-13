# MVP-2 — Lifecycle write HTTP API

**Status:** Implemented (extended by CRM/NC mirror, NC app 3.2.13+)  
**App version:** 3.2.13+  
**Contract:** `docs/architecture/nc-odoo-lifecycle-api.openapi.yaml`

## Endpoints (bearer token)

Auth: `Authorization: Bearer <token>`  
Token: app config `lifecycle_api_token`, fallback `public_api_token`.

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/api/lifecycle/v1/stations/virtual` | Create Virtual; idempotent on `odoo_lead_id` (200 if exists); notifies Odoo webhook |
| POST | `/api/lifecycle/v1/stations/{id}/promote-planned` | Virtual→Planned; OK if already Planned; 409 from Running/soft-removed |
| POST | `/api/lifecycle/v1/stations/{id}/mark-installed` | Planned→Running; OK if already Running |
| POST | `/api/lifecycle/v1/stations/{id}/set-lifecycle` | Explicit virtual\|planned\|running (supports demotion); notifies Odoo |
| POST | `/api/lifecycle/v1/stations/{id}/profile` | Update snapshot fields from CRM (name, location, coords, capacity, website, description) |
| POST | `/api/lifecycle/v1/stations/{id}/bind-lead` | Attach `odoo_lead_id` on ops station (idempotent) |
| POST | `/api/lifecycle/v1/stations/{id}/soft-remove` | Hide from public/admin lists; notifies Odoo |
| GET | `/api/lifecycle/v1/stations` | Ops list for CRM mirror (excludes `source=dataset` unless `include_dataset=1`) |
| GET | `/api/lifecycle/v1/stations/{id}` | Lifecycle view |

`{id}` = `location_serial` installation id or numeric DB id.

## Virtual create body (JSON)

```json
{
  "odoo_lead_id": 123,
  "name": "ONG Example",
  "latitude": 38.72,
  "longitude": -9.14,
  "capacity_kwp": 12.5,
  "location_label": "Lisbon",
  "organization_name": "ONG Example",
  "grid_price_kwh": 0.15
}
```

## Deploy

```bash
docker exec -u 33 filantropia-nextcloud php occ upgrade
# ensure token set:
# occ config:app:get filantropia_solar public_api_token
```

## Tests

```bash
cd nextcloud-app
docker run --rm -v "$PWD":/app -w /app composer:2 \
  ./vendor/bin/phpunit --bootstrap tests/bootstrap.php \
  tests/Unit/Service/StationLifecycleTest.php
```

## Odoo webhook (mirror)

NC pushes station snapshots to Odoo (best-effort):

- Config: `odoo_lifecycle_webhook_url` (default `http://filantropia-odoo:8069/filantropia/nc/lifecycle/http`)
- Auth: same bearer as lifecycle/public token
- Fired from lifecycle API, NC admin lifecycle actions, and installation lifecycle writes

## Not in original MVP-2 PR (now done elsewhere)

- Public API switch to `findPublicStations` (MVP-3)  
- Odoo queue_job client (MVP-5/6)  
- Admin UI buttons (MVP-4)  
- Bidirectional CRM mirror + profile sync (PR #29 / ADR 0006)  
