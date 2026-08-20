# Ops: Public Archived lifecycle

**NC app:** 3.2.34+ (UI); 3.2.33+ (flag + APIs)  
**Odoo module:** 19.0.2.31.0+  
**PR:** Gitea `#32` (`feat/lifecycle-archive-ui-crm-stage`)

## What it means

| Concept | Meaning |
|---------|---------|
| NC `lifecycle_state` | Still `virtual` \| `planned` \| `running` only |
| NC `public_archived` | Boolean on **running** stations |
| Public map / `GET .../public/v1/stations` | Omits archived stations |
| Public dashboard / stats | **Includes** archived (`archived_count`) |
| CRM stage **Archived** | Mirrors `running` + `public_archived=true` |
| Soft-remove | Different: hides from public membership entirely |

## UI (Nextcloud main app)

**Set lifecycle** modal (station selected → lifecycle action) shows four rows:

1. Virtual  
2. Planned  
3. Running (on public map when not archived)  
4. **Archived** (hidden from public map; still in stats)

- Open a **Running** station to enable Archived.  
- List filter chip **Archived** filters the left list.  
- Admin panel still has **Archive map** / **Unarchive map**.

Hard-refresh the browser after deploy (async JS chunk).

## APIs

| Auth | Method | Path | Body |
|------|--------|------|------|
| Session (Filantropia admin) | POST | `/apps/filantropia_solar/api/v1/installations/{id}/set-public-archived` | `{"public_archived": true\|false}` |
| Bearer lifecycle token | POST | `/apps/filantropia_solar/api/lifecycle/v1/stations/{id}/set-public-archived` | same |
| Admin session | POST | `/apps/filantropia_solar/api/v1/admin/stations/{installationId}/set-public-archived` | same |

Rules:

- Only **running** stations can be archived.  
- Soft-removed stations cannot be archived.  
- Demoting lifecycle away from Running clears `public_archived`.

## CRM mirror

| Direction | Behaviour |
|-----------|-----------|
| NC → CRM | Webhook / reconcile: Running+archived → stage **Archived**; Running → **Installed** |
| CRM → NC | Drag to **Archived** → ensure Running + set flag; drag to **Installed** → clear flag |
| xmlid | `filantropia_solar_public.stage_archived` (seq 80, not won) |

See also `docs/ops/CRM-NC-LIFECYCLE-MIRROR.md` and ADR 0006.

## Deploy / upgrade (no in-app Upgrade button)

### Nextcloud (TRL5 AIO)

```bash
# From laptop (example): COPYFILE_DISABLE=1 tar, no AppleDouble
export COPYFILE_DISABLE=1
tar -czf /tmp/nc-app.tgz \
  --exclude=node_modules --exclude='._*' --exclude=.DS_Store \
  -C nextcloud-app appinfo lib js css img

scp /tmp/nc-app.tgz root@100.82.252.18:/tmp/
# On TRL5:
ssh root@100.82.252.18
HOST_NC=$(docker volume inspect nextcloud_aio_nextcloud -f '{{.Mountpoint}}')
APP="$HOST_NC/custom_apps/filantropia_solar"
mkdir -p "$APP"
tar -xzf /tmp/nc-app.tgz -C "$APP"
find "$APP" \( -name '._*' -o -name '.DS_Store' \) -delete
chown -R 33:33 "$APP"
tar -xzf /tmp/nc-app.tgz -C /opt/FilantropiaSolar/nextcloud-app
find /opt/FilantropiaSolar/nextcloud-app \( -name '._*' -o -name '.DS_Store' \) -delete
docker exec -u 33 nextcloud-aio-nextcloud php occ app:enable filantropia_solar || true
docker exec -u 33 nextcloud-aio-nextcloud php occ upgrade
docker exec -u 33 nextcloud-aio-nextcloud php occ maintenance:mode --off
docker exec nextcloud-aio-nextcloud find /var/www/html/custom_apps/filantropia_solar -name '._*' | wc -l
docker exec -u 33 nextcloud-aio-nextcloud php occ app:list | grep filantropia
```

Unauthenticated app URL should return **401/login**, never **500**.

### Odoo

```bash
# Addon path on TRL5 is bind-mounted from:
# /opt/FilantropiaSolar/nextcloud-app/odoo/addons → /mnt/extra-addons
docker exec filantropia-odoo odoo -d filantropia_public \
  -u filantropia_solar_public \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password \
  --stop-after-init --without-demo=all
docker restart filantropia-odoo
```

Confirm CRM stage **Archived** exists (`filantropia_solar_public.stage_archived`).  
If xml data did not create it on an already-installed DB, create stage + `ir.model.data` xmlid (one-time shell), or force module data reload carefully.

## Smoke checklist

1. NC: Running station → Set lifecycle → **Archived** → list badge / Archived chip.  
2. Public `GET /api/public/v1/stations` omits station; dashboard `archived_count` increments.  
3. NC: Set lifecycle → **Running** → station returns to public map.  
4. Odoo CRM: drag Installed ↔ Archived; lead `fs_nc_public_archived` and NC flag match after queue/webhook.  
5. Soft-remove still separate from Archive.

## Related

- `docs/ops/CRM-NC-LIFECYCLE-MIRROR.md`  
- `docs/ops/TRL5-NC-ACCESS.md`  
- `docs/mvp/MVP-3-PUBLIC-STATIONS-FILTER.md`  
- `docs/mvp/MVP-4-admin-lifecycle-ui.md`  
- `docs/adr/0006-crm-nc-lifecycle-mirror.md`  
