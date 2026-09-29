# TRL5 backup (Odoo + Nextcloud)

**Host:** `wera-ss-pt-tv-1` · Tailscale `wera-ss-pt-tv-1.tailfb390c.ts.net` / `100.82.252.18`  
**SSH:** `root@100.82.252.18` (Tailscale policy; other users denied)  
**Compose root on host:** `/opt/FilantropiaSolar/nextcloud-app`  
**Backup root on host:** `/opt/FilantropiaSolar/backups/`  
**Local (dev machine) copy:** `nextcloud-app/.local-backups/` (**gitignored**)

Take a backup **before** any TRL5 deploy, `occ upgrade`, Odoo `-u filantropia_solar_public`, or `reset_website_cows`.

## What to capture

| Component | Artifact | Why |
|-----------|----------|-----|
| Odoo DB | `pg_dump -Fc` of `filantropia_public` | Full CRM + website + queue_job |
| Odoo website tables | data-only SQL (views/pages/menus/ICP) | Faster COW-focused restore |
| Odoo COW inventory | SQL listing `ir_ui_view` FS keys + `arch_len` | Prove published home still large |
| Nextcloud DB | `mysqldump` of `nextcloud` | Stations, series, app config |
| NC app tree | tarball of `custom_apps/filantropia_solar` | Code/version reference |
| NC `config.php` | file mode `600` on host only | Secrets; do not commit |
| Checksums | `SHA256SUMS.txt` + `MANIFEST.txt` | Integrity |

Do **not** commit dumps, `config.php`, or tokens. Keep local copies under
gitignored `.local-backups/`; host recovery sets may be stored on TRL5 or
Frank's encrypted `/data/backups/filantropia/odoo/` under restricted access.

## Automated TRL5 → Frank Odoo recovery set

TRL5's `filantropia-odoo-backup.timer` runs daily at **02:00 UTC** and invokes
`filantropia-odoo-backup.service`. The job creates a custom-format PostgreSQL
dump plus the Odoo filestore, writes a manifest and component checksums,
validates both archives, uploads through restricted SFTP with a pinned Frank
host key, downloads a round-trip copy for SHA-256 verification, and only then
publishes the bundle atomically under Frank's encrypted
`/data/backups/filantropia/odoo/`. Successful bundles are retained for 30 days.

Routine backups only write recovery bundles; they **do not** update Frank's
dormant Odoo database/filestore or start its Odoo container. The bundle does
not include addon source, container configuration, or secrets. It is a
TRL5-originated promotion snapshot and does not capture writes accepted by
Frank after promotion. On failback, if Frank is proven to have accepted no
writes, keep TRL5's pre-outage database/filestore in place and do not restore
a TRL5-originated bundle from Frank back onto TRL5. If Frank accepted writes
or that cannot be ruled out, create and verify a fresh Frank-originated
database/filestore recovery set; preserve TRL5's pre-failback state for
rollback before restoring that set to TRL5.

Monitor the timer and latest run from an operator workstation:

```bash
ssh root@100.82.252.18 'systemctl is-active filantropia-odoo-backup.timer'
ssh root@100.82.252.18 'systemctl list-timers --all filantropia-odoo-backup.timer --no-pager'
ssh root@100.82.252.18 'systemctl show filantropia-odoo-backup.service -p Result -p ExecMainStatus -p ExecMainStartTimestamp'
ssh root@100.82.252.18 'journalctl -u filantropia-odoo-backup.service -n 50 --no-pager'
```

For a candidate bundle on Frank, compare its outer and component hashes to a
trusted run record, then parse both archives without starting Odoo:

```bash
B=/data/backups/filantropia/odoo/filantropia-odoo-20260929T020002Z.tar
sha256sum "$B"
tar -xOf "$B" odoo.dump | sha256sum
tar -xOf "$B" filestore.tar | sha256sum
tar -xOf "$B" odoo.dump | docker exec -i filantropia-odoo-db pg_restore --list >/dev/null
tar -xOf "$B" filestore.tar | tar -tf - >/dev/null
```

## Verification log — 2026-09-29

| Item | Verified value |
|------|----------------|
| Recovery bundle | `/data/backups/filantropia/odoo/filantropia-odoo-20260929T020002Z.tar` |
| Size | 145,735,680 bytes |
| Bundle SHA-256 | `33cd2a1f49d700a81f3966c17f5f2a26ac54180263c7b0640edc4f81de6e92c2` |
| `odoo.dump` SHA-256 | `2856d0d8e55c360258fd6071b4ac88c98b77d58820f9b25bdc36bdab1143b0c9` |
| `filestore.tar` SHA-256 | `109cbc496733be54d89830cb5ae033687316b0581a504b8e8c1509716a71fde6` |
| Validation | Manifest component hashes match streamed component hashes; Frank's `pg_restore --list` passed; timer run and publication succeeded |
| Daily timer | Active; service exit 0 at 2026-09-29 02:00:01 UTC; next run 2026-09-30 02:00 UTC |
| Frank Odoo | `filantropia-odoo` exited with restart policy `no`; no restore or promotion performed |

## Verification log — 2026-09-28

| Item | Verified value |
|------|----------------|
| Recovery bundle | `/data/backups/filantropia/odoo/filantropia-odoo-20260928T170237Z.tar` |
| Size | 145,694,720 bytes |
| Bundle SHA-256 | `6029381fecdc935820bbecb20d806f0fad12164e870603d1e2f0abf94bf47561` |
| `odoo.dump` SHA-256 | `3d44b889dd377e42cd9a1c41f6b7c9a1e029701ced2694d6a50d5e2df9b4fedc` |
| `filestore.tar` SHA-256 | `5ef2bfaf3db80be769c849f6ded7bc14e34fc46480feec03e620ec838a2dd81e` |
| Validation | Round-trip copy matched; `pg_restore --list` passed on TRL5 and Frank; filestore archive passed content validation |
| Daily timer | Active; latest service result success, exit 0; next run 2026-09-29 02:00 UTC |
| Frank Odoo | `filantropia-odoo` exited with restart policy `no`; no restore or promotion performed |

## Quick path (recommended)

### A. Odoo only (script)

```bash
# From laptop (repo root), full custom-format DB on TRL5 → nextcloud-app/.local-backups/
TRL5_HOST=root@100.82.252.18 \
  bash nextcloud-app/scripts/backup-odoo-website.sh --remote --full-db
```

### B. Full Odoo + Nextcloud (host script pattern)

SSH as root and run a stamped backup directory (example used 2026-08-14):

```bash
ssh root@100.82.252.18
STAMP=$(date -u +%Y%m%d-%H%M%S)
BK=/opt/FilantropiaSolar/backups/trl5-${STAMP}
mkdir -p "$BK"

# Odoo COW inventory
docker exec filantropia-odoo-db psql -U odoo -d filantropia_public -c "
SELECT key, website_id, active, length(arch_db::text) AS arch_len
FROM ir_ui_view
WHERE website_id IS NOT NULL AND key LIKE 'filantropia_solar_public.%'
ORDER BY arch_len DESC NULLS LAST;" | tee "$BK/odoo-cow-inventory.txt"

# Odoo full DB
docker exec filantropia-odoo-db pg_dump -U odoo -Fc --no-owner -d filantropia_public \
  > "$BK/odoo-filantropia_public.dump"

# Odoo website-focused SQL
docker exec filantropia-odoo-db pg_dump -U odoo --data-only --no-owner \
  -t ir_ui_view -t website -t website_page -t website_menu -t ir_config_parameter \
  -d filantropia_public | gzip -c > "$BK/odoo-website-tables.sql.gz"

# Nextcloud MySQL (compose env inside filantropia-db)
docker exec filantropia-db sh -c \
  'mysqldump -unextcloud -p"$MYSQL_PASSWORD" --single-transaction --routines --triggers --events nextcloud' \
  | gzip -c > "$BK/nextcloud-mysql.sql.gz"

# NC status / app version
docker exec -u 33 filantropia-nextcloud php occ status | tee "$BK/nextcloud-occ-status.txt"
docker exec -u 33 filantropia-nextcloud php occ app:list | grep -i filantropia | tee -a "$BK/nextcloud-occ-status.txt"

# Optional: app tree + config (config stays 600 on host)
docker exec filantropia-nextcloud tar -C /var/www/html/custom_apps -czf - filantropia_solar \
  > "$BK/nextcloud-app-filantropia_solar.tgz"
docker exec filantropia-nextcloud cat /var/www/html/config/config.php > "$BK/nextcloud-config.php"
chmod 600 "$BK/nextcloud-config.php"

(cd "$BK" && sha256sum odoo-filantropia_public.dump odoo-website-tables.sql.gz \
  nextcloud-mysql.sql.gz odoo-cow-inventory.txt nextcloud-occ-status.txt > SHA256SUMS.txt)
tar -C /opt/FilantropiaSolar/backups -czf "trl5-${STAMP}-bundle.tgz" "trl5-${STAMP}"
```

Copy to laptop (gitignored):

```bash
LOCAL="nextcloud-app/.local-backups"
mkdir -p "$LOCAL/trl5-${STAMP}"
scp root@100.82.252.18:/opt/FilantropiaSolar/backups/trl5-${STAMP}-bundle.tgz "$LOCAL/"
scp root@100.82.252.18:/opt/FilantropiaSolar/backups/trl5-${STAMP}/{odoo-filantropia_public.dump,odoo-website-tables.sql.gz,nextcloud-mysql.sql.gz,odoo-cow-inventory.txt,nextcloud-occ-status.txt,SHA256SUMS.txt,MANIFEST.txt} \
  "$LOCAL/trl5-${STAMP}/"
(cd "$LOCAL/trl5-${STAMP}" && shasum -a 256 -c SHA256SUMS.txt)
```

## Run log — 2026-08-14 (`20260814-000958`)

| Item | Value |
|------|--------|
| Host | `wera-ss-pt-tv-1` |
| UTC | `2026-08-14T00:10:01Z` |
| Remote dir | `/opt/FilantropiaSolar/backups/trl5-20260814-000958/` |
| Remote bundle | `/opt/FilantropiaSolar/backups/trl5-20260814-000958-bundle.tgz` (4.4M) |
| Local dir | `nextcloud-app/.local-backups/trl5-20260814-000958/` |
| Local bundle | `nextcloud-app/.local-backups/trl5-20260814-000958-bundle.tgz` |
| Odoo dump | `odoo-filantropia_public.dump` **4.5M** |
| Odoo website SQL | `odoo-website-tables.sql.gz` **757K** |
| NC MySQL | `nextcloud-mysql.sql.gz` **24K** (105 tables; fleet small) |
| NC app on TRL5 at backup | **filantropia_solar 3.1.1** |
| NC core | 28.0.14, maintenance off, needsDbUpgrade false |
| COW `page_inicio` | website_id=2, active, **arch_len 235554** |
| COW other | `page_contacto` 11369; `snippet_steps` 4379 |
| Checksums | local `shasum -a 256 -c SHA256SUMS.txt` **OK** |

### SHA256 (primary dumps)

```
fe309cb3a7b126899d56bbfc4e575639d14556a787c761faa66698302cdc6f64  odoo-filantropia_public.dump
d36a8fa76beda11e68c8cc0f351c9d9ce6093af56fbfcc8a6433db2c9041c9e6  odoo-website-tables.sql.gz
aacb374b79d7dcc8797e7f3e02c828ba36fa683db76b4b870e233f3460c62de3  nextcloud-mysql.sql.gz
```

## Restore notes (emergency)

**Odoo full DB** (destructive — stop Odoo writers first; if Frank was promoted,
fence it before restoring/restarting TRL5):

```bash
# On TRL5
docker exec -i filantropia-odoo-db pg_restore -U odoo -d filantropia_public --clean --if-exists \
  < /opt/FilantropiaSolar/backups/trl5-STAMP/odoo-filantropia_public.dump
docker compose --profile odoo up -d odoo
```

### Frank failover restore (explicitly gated)

Do this only during an explicitly approved promotion, after the current
public writer is fenced. This replaces Frank's database/filestore with a
TRL5-originated snapshot. Before proceeding, rule out prior unreconciled
Frank-originated writes; if that cannot be proved, stop and capture/reconcile
them first. Keep `filantropia-odoo` stopped throughout the restore. Confirm
the addon source and Odoo configuration on Frank match the database being
restored (currently module `19.0.2.35.0`); these are not in the bundle. Do not
route traffic or start Frank merely because the bundle validates.

On Frank as root, select the exact verified bundle and validate it before any
destructive operation:

```bash
B=/data/backups/filantropia/odoo/filantropia-odoo-20260929T020002Z.tar
WORK=$(mktemp -d /data/filantropia-restore.XXXXXX)
STORE=/data-bulk/docker/volumes/nextcloud-app_odoo_data/_data/filestore
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
STAGE="$STORE/.filantropia_public.restore-$STAMP"
TARGET="$STORE/filantropia_public"
OLD="$STORE/filantropia_public.before-$STAMP"

docker inspect --format '{{.State.Status}}' filantropia-odoo  # must be exited
sha256sum "$B"  # compare with the trusted bundle SHA-256 in the run log
tar -xf "$B" -C "$WORK"
(cd "$WORK" && sha256sum -c SHA256SUMS.txt)
docker exec -i filantropia-odoo-db pg_restore --list < "$WORK/odoo.dump" >/dev/null
tar -tf "$WORK/filestore.tar" >/dev/null
```

Only after all checks succeed, restore both components while Odoo remains
stopped. The filestore archive contains a top-level `filantropia_public/`
directory; stage it on the same volume, keep the old tree for rollback, and
do not remove that old tree until the promoted service is verified:

```bash
docker exec -i filantropia-odoo-db pg_restore \
  -U odoo -d filantropia_public --clean --if-exists --exit-on-error --no-owner \
  < "$WORK/odoo.dump"

mkdir -p "$STAGE"
tar -xf "$WORK/filestore.tar" -C "$STAGE"
test -d "$STAGE/filantropia_public"
if [ -d "$TARGET" ]; then mv "$TARGET" "$OLD"; fi
mv "$STAGE/filantropia_public" "$TARGET"
```

If restoration or the filestore swap fails, leave Odoo stopped. Retain the
old filestore tree and any pre-restore Frank recovery set required because of
known/uncertain divergence; otherwise retry only from the selected verified
TRL5 bundle. After restore, validate the module version and database/filestore,
then follow
`docs/ops/TRL5-ODOO-BOOT.md` and `docs/ops/TRL4-ODOO-FAILOVER.md` for explicit
promotion, ingress, one-writer, and failback gates.

**Nextcloud MySQL** (destructive):

```bash
gunzip -c nextcloud-mysql.sql.gz | docker exec -i filantropia-db \
  sh -c 'mysql -unextcloud -p"$MYSQL_PASSWORD" nextcloud'
docker exec -u 33 filantropia-nextcloud php occ maintenance:mode --off
```

Prefer restore drills on a non-prod clone. After restore, re-check COW inventory and `occ status`.

## Related

- `docs/ops/ODOO-WEBSITE-COW-VIEWS.md` — COW policy; never reset without backup  
- `docs/mvp/MVP-7-GATES-TRL5.md` — cutover checklist (Backup taken)  
- `nextcloud-app/scripts/backup-odoo-website.sh` — Odoo website / full-db helper  
