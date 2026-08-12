#!/usr/bin/env bash
#
# One-command bring-up for the FilantropiaSolar two-app platform.
#
# Brings up the Nextcloud stack + ML service, applies the environment fixes
# that are otherwise easy to miss (custom_apps ownership, allow_local_remote_servers),
# enables the app, provisions the public API token (also written to the
# SolarSeed-v3 secrets folder for Odoo), imports the dataset, and trains models.
#
# Idempotent: safe to re-run. Run from anywhere:
#   bash nextcloud-app/scripts/setup.sh
#
# Optional Odoo public site + queue_job afterwards:
#   bash nextcloud-app/scripts/setup-odoo.sh
#   bash nextcloud-app/scripts/setup-odoo.sh --smoke

cd "$(dirname "$0")/.." || exit 1   # -> nextcloud-app/

NC=filantropia-nextcloud

echo "[1/7] Starting core stack (nextcloud, db, redis, ml-service)..."
docker compose up -d --build nextcloud db redis ml-service

echo "[2/7] Fixing custom_apps ownership (the bind mount is created as root)..."
docker exec -u root "$NC" chown www-data:www-data /var/www/html/custom_apps 2>/dev/null || true
docker exec -u root "$NC" chmod 775 /var/www/html/custom_apps 2>/dev/null || true

echo "[3/7] Waiting for Nextcloud (installing if needed)..."
installed=""
for i in $(seq 1 60); do
    body=$(curl -sS -m 3 http://localhost:8080/status.php 2>/dev/null || echo "")
    case "$body" in
        *'"installed":true'*) installed="yes"; break ;;
    esac
    if [ "$i" = "15" ] && [ -z "$installed" ]; then
        echo "    running occ maintenance:install..."
        docker exec -u 33 "$NC" php occ maintenance:install \
            --database mysql --database-host db --database-name nextcloud \
            --database-user nextcloud --database-pass nextcloud_dev_password \
            --admin-user admin --admin-pass admin || true
        docker exec -u 33 "$NC" php occ config:system:set trusted_domains 1 --value=localhost || true
    fi
    sleep 3
done
[ -n "$installed" ] && echo "    Nextcloud installed" || echo "    (proceeding; check http://localhost:8080)"

echo "[4/7] Nextcloud config + app enable/upgrade..."
docker exec -u 33 "$NC" php occ config:system:set allow_local_remote_servers --value=true --type=boolean || true
docker exec -u 33 "$NC" php occ config:system:set trusted_domains 2 --value=filantropia-nextcloud || true
docker exec -u 33 "$NC" php occ app:enable filantropia_solar || true
docker exec -u 33 "$NC" php occ upgrade || true
docker exec -u 33 "$NC" php occ maintenance:mode --off || true

echo "[5/7] Public API token (generate if absent) + export to SolarSeed-v3..."
TOKEN=$(docker exec -u 33 "$NC" php occ config:app:get filantropia_solar public_api_token 2>/dev/null | tr -d '\r\n')
if [ -z "$TOKEN" ]; then
    TOKEN=$(openssl rand -hex 24)
    docker exec -u 33 "$NC" php occ config:app:set filantropia_solar public_api_token --value="$TOKEN" || true
fi
SECRET_DIR="../../SolarSeed-v3/.secrets"
mkdir -p "$SECRET_DIR" 2>/dev/null || true
printf '%s' "$TOKEN" > "$SECRET_DIR/filantropia_public_api_token" 2>/dev/null \
    && chmod 600 "$SECRET_DIR/filantropia_public_api_token" 2>/dev/null \
    && echo "    token stored in $(cd "$SECRET_DIR" 2>/dev/null && pwd)/filantropia_public_api_token" \
    || echo "    WARNING: could not write token to SolarSeed-v3/.secrets"

echo "[6/7] Waiting for ML service health, then importing Mendeley dataset stations..."
for i in $(seq 1 50); do
    case "$(curl -sS -m 3 http://localhost:8501/health 2>/dev/null || echo '')" in
        *'"status":"healthy"'*) break ;;
    esac
    sleep 3
done
docker exec -u 33 "$NC" php occ filantropia_solar:import-dataset || true

echo "[7/7] Training ML models (physics fallback remains if this fails)..."
curl -sS -m 600 -X POST http://localhost:8501/train >/dev/null 2>&1 \
    && echo "    models trained" || echo "    training skipped/failed"

# Optional: join the SolarSeed TRL4/TRL5 ops network when present
if docker network inspect "${CITY_NET:-compose_city_internal}" >/dev/null 2>&1; then
    echo "[+] SolarSeed ops network detected (${CITY_NET:-compose_city_internal}) - connecting..."
    bash "$(dirname "$0")/connect-trl4.sh"
else
    echo "[-] No SolarSeed ops network found; skipping TRL connect (run scripts/connect-trl4.sh later if needed)"
fi

echo
echo "Done."
echo "  Nextcloud admin dashboard: http://localhost:8080  (admin / admin)"
echo "  ML service:                http://localhost:8501"
echo "  Odoo public site (opt):    bash nextcloud-app/scripts/setup-odoo.sh"
echo "  Odoo + job smoke (opt):    bash nextcloud-app/scripts/setup-odoo.sh --smoke"
