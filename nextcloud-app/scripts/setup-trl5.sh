#!/usr/bin/env bash
# Bring-up FilantropiaSolar on TRL5 (wera-ss-pt-tv-1)
set -u
cd "$(dirname "$0")/.." || exit 1
export COMPOSE_FILE=docker-compose.yml:docker-compose.trl5.yml
NC=filantropia-nextcloud
NC_URL=http://127.0.0.1:18080
ML_URL=http://127.0.0.1:8501
TOKEN_FILE="$(cd ../.secrets && pwd)/filantropia_public_api_token"
PUBLIC_HOST="${PUBLIC_HOSTNAME:-filantropiasolar.pt}"

echo "[1/9] Pull/build core + odoo stack..."
if [ -f "$TOKEN_FILE" ]; then
  export FS_PUBLIC_API_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi
docker compose pull nextcloud db redis odoo-db odoo 2>/dev/null || true
docker compose build ml-service
docker compose --profile odoo up -d nextcloud db redis ml-service odoo-db odoo

echo "[2/9] custom_apps ownership..."
docker exec -u root "$NC" chown www-data:www-data /var/www/html/custom_apps 2>/dev/null || true
docker exec -u root "$NC" chmod 775 /var/www/html/custom_apps 2>/dev/null || true

echo "[3/9] Wait Nextcloud..."
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

echo "[4/9] NC config + app..."
docker exec -u 33 "$NC" php occ config:system:set allow_local_remote_servers --value=true --type=boolean || true
docker exec -u 33 "$NC" php occ config:system:set trusted_domains 2 --value=filantropia-nextcloud || true
docker exec -u 33 "$NC" php occ config:system:set trusted_domains 3 --value="$PUBLIC_HOST" || true
docker exec -u 33 "$NC" php occ app:enable filantropia_solar || true
docker exec -u 33 "$NC" php occ upgrade || true
docker exec -u 33 "$NC" php occ maintenance:mode --off || true

echo "[5/9] Public API token..."
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

echo "[6/9] Recreate Odoo with token env..."
docker compose --profile odoo up -d odoo

echo "[7/9] ML health + dataset + train..."
for i in $(seq 1 60); do
  case "$(curl -sS -m 3 "$ML_URL/health" 2>/dev/null || echo '')" in *'"status":"healthy"'*) break ;; esac
  sleep 3
done
docker exec -u 33 "$NC" php occ filantropia_solar:import-dataset || true
curl -sS -m 900 -X POST "$ML_URL/train" >/dev/null 2>&1 && echo "    models trained" || echo "    train skipped/failed"

echo "[8/9] Odoo DB wait + module install..."
for i in $(seq 1 40); do
  if docker exec filantropia-odoo-db pg_isready -U odoo >/dev/null 2>&1; then
    echo "    postgres ready"
    break
  fi
  sleep 2
done
sleep 5

# Install base stack + public module into fresh DB
docker exec filantropia-odoo odoo -d filantropia_public \
  -i base,website,crm,filantropia_solar_public \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password \
  --stop-after-init --without-demo=all 2>&1 | tail -50 || true

docker compose --profile odoo up -d odoo
sleep 8
for i in $(seq 1 30); do
  code=$(curl -sS -o /dev/null -w '%{http_code}' -m 3 http://127.0.0.1:8069/web/login 2>/dev/null || echo 0)
  echo "    login $i $code"
  [ "$code" = "200" ] && break
  sleep 3
done

docker exec -i filantropia-odoo odoo shell -d filantropia_public \
  --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password --no-http <<PY
ICP = env['ir.config_parameter'].sudo()
ICP.set_param('web.base.url', 'https://$PUBLIC_HOST')
ICP.set_param('web.base.url.freeze', 'True')
mods = env['ir.module.module'].search([('name', '=', 'filantropia_solar_public')])
print('module state', mods.state if mods else None)
w = env['website'].search([], limit=1)
if w:
    w.write({'domain': 'https://$PUBLIC_HOST', 'name': 'Filantropia Solar'})
env.cr.commit()
print('web.base.url', ICP.get_param('web.base.url'))
print('website', w.name if w else None, w.domain if w else None)
PY

echo "[9/9] Cloudflare tunnel sidecar..."
CF_DIR="$(pwd)/infra/cloudflared"
if [ -f "$CF_DIR/credentials.json" ] && [ -f "$CF_DIR/config.yml" ]; then
  chmod 644 "$CF_DIR/credentials.json" "$CF_DIR/config.yml" || true
  NET=$(docker inspect filantropia-odoo --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' 2>/dev/null | head -1)
  NET=${NET:-nextcloud-app_filantropia-net}
  cat > "$CF_DIR/config.yml" <<YML
tunnel: 6571cd54-a08d-46da-a4ca-9630c1a0d090
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: $PUBLIC_HOST
    service: http://filantropia-odoo:8069
    originRequest:
      httpHostHeader: $PUBLIC_HOST
  - service: http_status:404
YML
  cat > "$CF_DIR/docker-compose.yml" <<YML
services:
  cloudflared:
    image: cloudflare/cloudflared:2025.8.1
    container_name: filantropia-cloudflared
    restart: unless-stopped
    command: tunnel --config /etc/cloudflared/config.yml run
    volumes:
      - ./config.yml:/etc/cloudflared/config.yml:ro
      - ./credentials.json:/etc/cloudflared/credentials.json:ro
    networks:
      - filantropia-net
networks:
  filantropia-net:
    external: true
    name: $NET
YML
  docker compose -f "$CF_DIR/docker-compose.yml" up -d
  echo "    cloudflared started on network $NET"
else
  echo "    WARN: missing tunnel credentials/config"
fi

echo "Done TRL5 setup."
curl -sS -o /dev/null -w "NC status %{http_code}\n" "$NC_URL/status.php" || true
curl -sS -o /dev/null -w "ML health %{http_code}\n" "$ML_URL/health" || true
for path in /web/login /inicio /candidatura /contacto /instalacoes; do
  curl -sS -o /dev/null -w "Odoo $path %{http_code}\n" -m 10 "http://127.0.0.1:8069$path" || true
done
