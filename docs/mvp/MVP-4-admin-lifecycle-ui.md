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
| POST | `/api/v1/admin/stations/{installationId}/set-public-archived` | Running: hide/show on public map; stats kept |

Illegal transitions return **409**. Soft-remove is idempotent. Dataset hard-delete is unchanged and separate from soft-remove. Archive is only valid for **running** and not soft-removed.

### Admin UI

- `AdminGlobalStations.vue`: lifecycle/public badges, lifecycle + source filters, promote / install / soft-remove / **Archive map** / **Unarchive map** with confirms.
- `store/admin.js`: filter state + lifecycle + `setPublicArchived` actions.
- `MlAdminPanel.vue` / admin body: wires handlers and filter props.

### Main app UI (3.2.34+)

Ops can also archive without the admin panel:

- Dashboard **Set lifecycle** modal: **Virtual | Planned | Running | Archived**.
- List chip **Archived**.
- Session route: `POST /api/v1/installations/{id}/set-public-archived`.

## Manual checklist

1. Open Nextcloud **Settings → FilantropiaSolar** (or in-app admin panel).
2. Confirm dataset stations show `running` / public `existing`.
3. Create or use a Virtual station (`lifecycle_state=virtual`) → **Promote** → Planned + public planned.
4. **Install** → Running + public existing + `installed_at` set.
5. **Archive map** (or main Set lifecycle → Archived) → public map hidden; dashboard stats still count; CRM stage **Archived** after mirror.
6. **Unarchive** / Set lifecycle → Running → public map restored; CRM **Installed**.
7. **Soft-remove** → public hidden; row still listed when "Show soft-removed" is on (distinct from Archive).
8. Public API still excludes virtual, soft-removed, and public-archived from `/stations` (MVP-3 + 3.2.33).

## Deploy

```bash
docker exec -u 33 filantropia-nextcloud php occ upgrade
# rebuild frontend assets if not baked into image
cd nextcloud-app && npm run build
```

## Follow-ups (done later)

- Odoo CRM client / queue_job (MVP-5/6) and CRM **Archived** stage (3.2.34 / Odoo 19.0.2.31.0) — see `docs/ops/PUBLIC-ARCHIVED-LIFECYCLE.md`.
- Undo soft-remove / restore public (optional).
- Automated UI tests (optional).
