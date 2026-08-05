#!/usr/bin/env bash
# Export Filantropia Odoo website-related data from the LOCAL stack for TRL5 import.
#
# Usage (Mac, stack up):
#   bash nextcloud-app/scripts/export-odoo-website.sh
#   # writes nextcloud-app/.local-backups/odoo-website-YYYYMMDD-HHMMSS.sql.gz
#
# Import on TRL5 (example):
#   scp dump.sql.gz root@100.82.252.18:/tmp/
#   ssh root@100.82.252.18 'bash -s' <<'REMOTE'
#   gunzip -c /tmp/dump.sql.gz | docker exec -i filantropia-odoo-db \
#     psql -U odoo -d filantropia_public
#   docker restart filantropia-odoo
#   REMOTE
#
# Prefer the Python JSON export path in clone-odoo-website-to-trl5.sh for safer
# view/page/menu merge without full DB replace.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="${ROOT}/nextcloud-app/.local-backups"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="${OUT_DIR}/odoo-website-${STAMP}.sql"
DB="${ODOO_DB:-filantropia_public}"

docker exec filantropia-odoo-db pg_isready -U odoo >/dev/null || {
  echo "filantropia-odoo-db not ready" >&2
  exit 1
}

# Schema-qualified dump of website-critical tables (+ module views via ir_ui_view)
tables=(
  ir_ui_view
  ir_ui_view_custom
  website
  website_page
  website_menu
  website_rewrite
  ir_translation
  ir_config_parameter
  blog_blog
  blog_post
  blog_tag
  blog_tag_blog_post_rel
)
exists=()
for t in "${tables[@]}"; do
  if docker exec filantropia-odoo-db psql -U odoo -d "$DB" -Atc \
    "SELECT 1 FROM information_schema.tables WHERE table_name='$t'" | grep -q 1; then
    exists+=(-t "$t")
  fi
done

docker exec filantropia-odoo-db pg_dump -U odoo -d "$DB" --data-only --no-owner \
  "${exists[@]}" > "$OUT"
gzip -f "$OUT"
echo "Wrote ${OUT}.gz"
