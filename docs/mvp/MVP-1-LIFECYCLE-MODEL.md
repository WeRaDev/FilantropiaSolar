# MVP-1 — NC lifecycle data model

**Status:** Implemented on branch `feat/mvp-1-nc-lifecycle-model`  
**Decisions:** D3, D4  
**App version:** 3.2.0

## Schema (`fs_installations`)

| Column | Type | Notes |
|--------|------|--------|
| `lifecycle_state` | string(16) | `virtual` \| `planned` \| `running` |
| `soft_removed` | bool | default false |
| `public_archived` | bool | default false; **running only** — hide public map, keep stats (3.2.33+) |
| `odoo_lead_id` | int nullable unique | CRM idempotency |
| `installed_at` | datetime nullable | set on mark-installed (MVP-2+) |

Indexes: `fs_inst_odoo_lead_uniq`, `fs_inst_lifecycle_idx`.

## Backfill (migration postSchema)

- `source=dataset` → `running`, not soft-removed  
- `source=user` or `is_virtual=1` → `virtual`  
- null lifecycle → `running`; null soft_removed → 0  

## Code

- `Service/StationLifecycle.php` — pure helpers  
- `Db/Installation.php` — fields + `applyLifecycleState` + JSON  
- `Db/InstallationMapper.php` — `findPublicStations`, `findByOdooLeadId`, `findByLifecycleStates`  
- `Db/EnergyReadingMapper.php` — `hasMeasuredData` for Active vs Offline  
- Admin/user API arrays include lifecycle fields  
- New dataset stations default `running`; user creates default `virtual`  

## Running mode

When `lifecycle_state=running`:

- **active** if measured readings with production_kwh > 0 exist  
- **offline** otherwise (predicted-only)  

(Derivation applied when callers set `hasMeasuredData` / use mapper helper — full wire-up in analysis UI is V1.)

## Deploy

```bash
docker exec -u 33 filantropia-nextcloud php occ upgrade
# or app:update filantropia_solar
```

## Tests

```bash
cd nextcloud-app && ./vendor/bin/phpunit --filter 'InstallationTest|StationLifecycleTest'
```

## Later stories (status)

- Lifecycle write HTTP API (MVP-2) — done  
- Public API `findPublicStations` (MVP-3) + `public_archived` map omit (3.2.33) — done  
- Admin + main UI lifecycle / archive (MVP-4, 3.2.34) — done; see `docs/ops/PUBLIC-ARCHIVED-LIFECYCLE.md`  
