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

Do **not** commit dumps, `config.php`, or tokens. Keep them under `.local-backups/` or on the TRL5 host only.

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

**Odoo full DB** (destructive — stop Odoo writers first):

```bash
# On TRL5
docker exec -i filantropia-odoo-db pg_restore -U odoo -d filantropia_public --clean --if-exists \
  < /opt/FilantropiaSolar/backups/trl5-STAMP/odoo-filantropia_public.dump
docker compose --profile odoo up -d odoo
```

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
