#!/usr/bin/env bash
#
# Backup Odoo website-critical data (views/pages/menus + optional full DB).
# Use BEFORE -u filantropia_solar_public on TRL5/prod.
#
# Local:
#   bash nextcloud-app/scripts/backup-odoo-website.sh
#
# TRL5:
#   TRL5_HOST=root@100.82.252.18 bash nextcloud-app/scripts/backup-odoo-website.sh --remote
#
# Full custom-format DB dump (recommended for TRL5):
#   bash nextcloud-app/scripts/backup-odoo-website.sh --full-db
#   bash nextcloud-app/scripts/backup-odoo-website.sh --remote --full-db
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${ROOT}/nextcloud-app/.local-backups"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
DB="${ODOO_DB:-filantropia_public}"
REMOTE=0
FULL_DB=0
HOST="${TRL5_HOST:-root@100.82.252.18}"

for arg in "$@"; do
  case "$arg" in
    --remote) REMOTE=1 ;;
    --full-db) FULL_DB=1 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

run_psql() {
  if [ "$REMOTE" = "1" ]; then
    ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" \
      "docker exec filantropia-odoo-db psql -U odoo -d ${DB} -v ON_ERROR_STOP=1"
  else
    docker exec -i filantropia-odoo-db psql -U odoo -d "$DB" -v ON_ERROR_STOP=1
  fi
}

run_pg_dump() {
  local args=("$@")
  if [ "$REMOTE" = "1" ]; then
    ssh -o BatchMode=yes -o ServerAliveInterval=30 "$HOST" \
      "docker exec filantropia-odoo-db pg_dump -U odoo ${args[*]} -d ${DB}"
  else
    docker exec filantropia-odoo-db pg_dump -U odoo "${args[@]}" -d "$DB"
  fi
}

prefix="odoo-website"
[ "$REMOTE" = "1" ] && prefix="odoo-website-trl5"
OUT_SQL="${OUT_DIR}/${prefix}-${STAMP}.sql"
OUT_DUMP="${OUT_DIR}/${prefix}-full-${STAMP}.dump"

echo "[1/3] Checking DB ${DB} (remote=${REMOTE})..."
echo "SELECT 1;" | run_psql >/dev/null

echo "[2/3] Inventory FS website COWs..."
echo "
SELECT key, website_id, active, length(arch_db::text) AS arch_len
FROM ir_ui_view
WHERE website_id IS NOT NULL
  AND key LIKE 'filantropia_solar_public.%'
ORDER BY arch_len DESC NULLS LAST;
" | run_psql | tee "${OUT_DIR}/${prefix}-cow-inventory-${STAMP}.txt"

if [ "$FULL_DB" = "1" ]; then
  echo "[3/3] Full custom-format dump -> ${OUT_DUMP}"
  run_pg_dump -Fc --no-owner > "$OUT_DUMP"
  ls -lah "$OUT_DUMP"
  echo "Wrote $OUT_DUMP"
  exit 0
fi

echo "[3/3] Data-only dump of website tables -> ${OUT_SQL}.gz"
tables=(
  ir_ui_view
  website
  website_page
  website_menu
  website_rewrite
  blog_blog
  blog_post
  ir_config_parameter
)
exists=()
for t in "${tables[@]}"; do
  if echo "SELECT 1 FROM information_schema.tables WHERE table_name='${t}';" \
    | run_psql -tAc 2>/dev/null | grep -q 1; then
    exists+=(-t "$t")
  fi
done

run_pg_dump --data-only --no-owner "${exists[@]}" > "$OUT_SQL"
gzip -f "$OUT_SQL"
ls -lah "${OUT_SQL}.gz"
echo "Wrote ${OUT_SQL}.gz"
echo "Inventory: ${OUT_DIR}/${prefix}-cow-inventory-${STAMP}.txt"
