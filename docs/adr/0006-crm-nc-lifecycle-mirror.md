# ADR 0006 — CRM/NC lifecycle mirror (supersedes ADR 0004)

## Status
Accepted (implemented on `feat/crm-nc-lifecycle-mirror`, PR #29)

## Context
ADR 0004 kept CRM Won decoupled from NC Running so sales close did not imply
field installation. Ops now want a full bidirectional mirror and an explicit
**Installed** CRM stage for Running stations, plus station profile parity so
admins can manage stations from either NC or CRM.

## Decision
| CRM stage | NC lifecycle | Notes |
|-----------|--------------|--------|
| New | none (no station required) | |
| Qualified | Virtual | |
| Proposition | Planned | |
| Installed (ex-Won, `is_won`) | Running | public map visible |
| **Archived** (not won) | Running + `public_archived` | hidden from public map; stats kept |

Archived is a **CRM stage and NC flag**, not a fourth `lifecycle_state` value.

### CRM → NC
- Candidatura creates a donation **opportunity** on **New** with station snapshot
  fields (`fs_station_*`, city, website). No NC station until Qualified.
- Entering **Qualified** creates/ensures Virtual (`POST .../stations/virtual`).
- Entering **Proposition** promotes Planned.
- Entering **Installed** calls mark-installed (Running) and clears public archive.
- Entering **Archived** ensures Running then `POST .../set-public-archived` with true.
- Leaving **Archived** for **Installed** clears public archive.
- Demotions use `POST .../stations/{id}/set-lifecycle` (and clear archive when leaving Running):
  - Installed/Archived/Proposition → Qualified → Virtual
  - Installed/Archived → Proposition → Planned
- Editing station snapshot fields on the lead pushes
  `POST .../stations/{id}/profile` (name, location, coords, capacity, website,
  short_description, **grid_price_kwh**).
- NC→CRM payloads include the same snapshot set (including grid price) via webhook
  and reconcile import.

### NC → CRM
- NC admin/installation/lifecycle writes notify Odoo via
  `OdooLifecycleMirror` → `POST /filantropia/nc/lifecycle/http` (payload includes `public_archived`).
- Webhook and hourly reconcile (`fs.station.sync.import_all_from_nc`) upsert
  CRM leads (stage + snapshot fields) and bind missing `odoo_lead_id` on NC.
- Running + `public_archived` maps to CRM stage **Archived**; plain Running maps to **Installed**.
- Mirror scope is **ops stations only** (fleet/user/crm). Mendeley
  `source=dataset` is excluded from lifecycle list/import by default
  (`include_dataset=1` for diagnostics only). Orphan CRM links are archived (`active=False`).

### Loop prevention and UI
- Skip enqueue when NC state already matches target; stamp `fs_nc_sync_origin`
  (`crm` | `nc` | `sync`).
- Core CRM stages `crm.stage_lead1–4` plus addon stage `filantropia_solar_public.stage_archived`; Won renamed Installed.
- Mirrored leads assigned to admin (not OdooBot) so Pipeline “My Pipeline” shows them.
- Menu **Filantropia → NC Stations** lists all linked stations without
  `assigned_to_me` filter.

### Public website map
- List items are clickable (`.fs-station-list-item` + data attrs).
- Markers are lifecycle-colored; popups/list show Planeada / Em operação.
- Focus centers the station in the map pane (`autoPan: false` + `panTo`).
- Website COWs can freeze stale map DOM; see `docs/ops/ODOO-WEBSITE-COW-VIEWS.md`.

## Versions (reference)
| Component | Version |
|-----------|---------|
| NC app | 3.2.34+ (Archived in main Set lifecycle UI; 3.2.33+ flag/API) |
| Odoo addon | 19.0.2.31.0+ (CRM stage Archived) |

## Consequences
- ADR 0004 Won-noop is **superseded** for this product path.
- Existing Won stages must map to Installed on upgrade (core stage xmlids).
- TRL5: backup website/DB before `-u`; never set `reset_website_cows=1` without backup.
- Ops should use **Filantropia → NC Stations** or clear Pipeline filters to see
  Installed (won) stations.
