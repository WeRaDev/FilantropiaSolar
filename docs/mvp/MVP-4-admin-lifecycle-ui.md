# MVP-4 — NC admin UI lifecycle actions

**Status:** Implemented on `feat/mvp-4-admin-lifecycle-ui`  
**App version:** 3.2.3  
**Decisions:** D2, D4  

## Change

Ops manage station lifecycle from the Nextcloud admin dashboard (session auth),
without needing the bearer lifecycle token used by Odoo glue (MVP-2).

### Admin API (session)

| Method | Path | Effect |
|--------|------|--------|
| GET | `/api/v1/admin/stations` | List all sources by default; filters: `source`, `lifecycle_state`, `include_soft_removed` |
| POST | `/api/v1/admin/stations/{installationId}/promote-planned` | Virtual → Planned |
| POST | `/api/v1/admin/stations/{installationId}/mark-installed` | Planned → Running (`installed_at`) |
| POST | `/api/v1/admin/stations/{installationId}/soft-remove` | Hide from public (row kept) |

Illegal transitions return **409**. Soft-remove is idempotent. Dataset hard-delete is unchanged and separate from soft-remove.

### Admin UI

- `AdminGlobalStations.vue`: lifecycle/public badges, lifecycle + source filters, promote / install / soft-remove with confirms.
- `store/admin.js`: filter state + lifecycle actions.
- `MlAdminPanel.vue`: wires handlers and filter props.

## Manual checklist

1. Open Nextcloud **Settings → FilantropiaSolar** (or in-app admin panel).
2. Confirm dataset stations show `running` / public `existing`.
3. Create or use a Virtual station (`lifecycle_state=virtual`) → **Promote** → Planned + public planned.
4. **Install** → Running + public existing + `installed_at` set.
5. **Soft-remove** → public hidden; row still listed when "Show soft-removed" is on.
6. Public API still excludes virtual and soft-removed (MVP-3).

## Deploy

```bash
docker exec -u 33 filantropia-nextcloud php occ upgrade
# rebuild frontend assets if not baked into image
cd nextcloud-app && npm run build
```

## Not in this PR

- Odoo CRM client / queue_job (MVP-5/6)
- Undo soft-remove / restore public (can add later)
- Automated UI tests
