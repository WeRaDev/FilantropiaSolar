#!/usr/bin/env bash
# Bring-up FilantropiaSolar on TRL4 (wera-ss-pt-sn-1)
set -u
cd "$(dirname "$0")/.." || exit 1
export COMPOSE_FILE=docker-compose.yml:docker-compose.trl4.yml
NC=filantropia-nextcloud
NC_URL=http://127.0.0.1:18080
ML_URL=http://127.0.0.1:8501
TOKEN_FILE="$(cd ../.secrets && pwd)/filantropia_public_api_token"

echo "[1/8] Pull/build core + odoo stack..."
if [ -f "$TOKEN_FILE" ]; then
  export FS_PUBLIC_API_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi
docker compose pull nextcloud db redis odoo-db odoo 2>/dev/null || true
docker compose build ml-service
docker compose --profile odoo up -d nextcloud db redis ml-service odoo-db odoo

echo "[2/8] custom_apps ownership..."
docker exec -u root "$NC" chown www-data:www-data /var/www/html/custom_apps 2>/dev/null || true
docker exec -u root "$NC" chmod 775 /var/www/html/custom_apps 2>/dev/null || true

echo "[3/8] Wait Nextcloud..."
installed=""
for i in $(seq 1 80); do
  body=$(curl -sS -m 3 "$NC_URL/status.php" 2>/dev/null || echo "")
  case "$body" in *'"installed":true'*) installed=yes; break ;; esac
  if [ "$i" = "20" ] && [ -z "$installed" ]; then
    echo "    occ maintenance:install..."
    docker exec -u 33 "$NC" php occ maintenance:install \
      --database mysql --database-host db --database-name nextcloud \
      --database-user nextcloud --database-pass nextcloud_dev_password \
      --admin-user admin --admin-pass admin || true
    docker exec -u 33 "$NC" php occ config:system:set trusted_domains 1 --value=localhost || true
  fi
  sleep 3
done
echo "    installed=${installed:-no}"

echo "[4/8] NC config + app..."
docker exec -u 33 "$NC" php occ config:system:set allow_local_remote_servers --value=true --type=boolean || true
docker exec -u 33 "$NC" php occ config:system:set trusted_domains 2 --value=filantropia-nextcloud || true
docker exec -u 33 "$NC" php occ config:system:set trusted_domains 3 --value=filantropiasolar.wera.global || true
docker exec -u 33 "$NC" php occ app:enable filantropia_solar || true
docker exec -u 33 "$NC" php occ upgrade || true
docker exec -u 33 "$NC" php occ maintenance:mode --off || true

echo "[5/8] Public API token..."
if [ -f "$TOKEN_FILE" ]; then
  TOKEN=$(tr -d '\r\n' < "$TOKEN_FILE")
  docker exec -u 33 "$NC" php occ config:app:set filantropia_solar public_api_token --value="$TOKEN" || true
  echo "    token from file len=${#TOKEN}"
else
  TOKEN=$(docker exec -u 33 "$NC" php occ config:app:get filantropia_solar public_api_token 2>/dev/null | tr -d '\r\n')
  if [ -z "$TOKEN" ]; then
    TOKEN=$(openssl rand -hex 24)
    docker exec -u 33 "$NC" php occ config:app:set filantropia_solar public_api_token --value="$TOKEN" || true
  fi
  mkdir -p "$(dirname "$TOKEN_FILE")"
  printf '%s' "$TOKEN" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
fi
export FS_PUBLIC_API_TOKEN="$TOKEN"

echo "[6/8] Recreate Odoo with token env..."
docker compose --profile odoo up -d odoo

echo "[7/8] ML health + dataset + train..."
for i in $(seq 1 60); do
  case "$(curl -sS -m 3 "$ML_URL/health" 2>/dev/null || echo '')" in *'"status":"healthy"'*) break ;; esac
  sleep 3
done
docker exec -u 33 "$NC" php occ filantropia_solar:import-dataset || true
curl -sS -m 900 -X POST "$ML_URL/train" >/dev/null 2>&1 && echo "    models trained" || echo "    train skipped/failed"

echo "[8/8] Odoo module + public URL..."
for i in $(seq 1 40); do
  code=$(curl -sS -o /dev/null -w '%{http_code}' -m 3 http://127.0.0.1:8069/web/login 2>/dev/null || echo 0)
  [ "$code" = "200" ] && break
  sleep 3
done

docker exec filantropia-odoo odoo -d filantropia_public -i base,website,crm,filantropia_solar_public \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password \
  --stop-after-init --without-demo=all 2>&1 | tail -40 || true

docker exec -i filantropia-odoo odoo shell -d filantropia_public \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password --no-http <<'PY'
ICP = env['ir.config_parameter'].sudo()
ICP.set_param('web.base.url', 'https://filantropiasolar.wera.global')
ICP.set_param('web.base.url.freeze', 'True')
w = env['website'].search([], limit=1)
if w:
    w.write({'domain': 'https://filantropiasolar.wera.global', 'name': 'Filantropia Solar'})
env.cr.commit()
print('web.base.url', ICP.get_param('web.base.url'))
print('website', w.name if w else None, w.domain if w else None)
PY

if docker network inspect compose_city_internal >/dev/null 2>&1; then
  bash scripts/connect-trl4.sh || true
elif docker network inspect city-of-light >/dev/null 2>&1; then
  for c in filantropia-nextcloud filantropia-ml filantropia-odoo; do
    docker network connect city-of-light "$c" 2>/dev/null && echo "connected $c -> city-of-light" || true
  done
fi

echo "Done TRL4 setup."
curl -sS -o /dev/null -w "NC status %{http_code}\n" "$NC_URL/status.php" || true
curl -sS -o /dev/null -w "ML health %{http_code}\n" "$ML_URL/health" || true
curl -sS -o /dev/null -w "Odoo /inicio %{http_code}\n" http://127.0.0.1:8069/inicio || true
