#!/usr/bin/env bash
#
# Bring up the optional Odoo public site + CRM with queue_job jobrunner.
# Idempotent. Requires the core stack (Nextcloud) already running
# (bash nextcloud-app/scripts/setup.sh).
#
# Usage (from anywhere):
#   bash nextcloud-app/scripts/setup-odoo.sh
#   bash nextcloud-app/scripts/setup-odoo.sh --smoke   # also enqueue one Virtual job
#   bash nextcloud-app/scripts/setup-odoo.sh --reset-volumes  # wipe odoo_data + odoo_db_data only
#
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1   # -> nextcloud-app/

NC=filantropia-nextcloud
ODOO=filantropia-odoo
DB_NAME="${FS_ODOO_DB:-filantropia_public}"
SMOKE=0
RESET_VOLUMES=0

for arg in "$@"; do
  case "$arg" in
    --smoke) SMOKE=1 ;;
    --reset-volumes) RESET_VOLUMES=1 ;;
    -h|--help)
      sed -n '2,14p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

echo "[1/7] Checking Nextcloud is up..."
if ! docker ps --format '{{.Names}}' | grep -qx "$NC"; then
  echo "ERROR: container $NC is not running. Run scripts/setup.sh first." >&2
  exit 1
fi
if ! curl -sf -m 5 http://localhost:8080/status.php | grep -q '"installed":true'; then
  echo "ERROR: Nextcloud not installed/reachable at http://localhost:8080" >&2
  exit 1
fi

echo "[2/7] Resolving FS_PUBLIC_API_TOKEN from Nextcloud..."
TOKEN=$(docker exec -u 33 "$NC" php occ config:app:get filantropia_solar public_api_token 2>/dev/null | tr -d '\r\n' || true)
if [ -z "$TOKEN" ]; then
  echo "ERROR: public_api_token missing. Run scripts/setup.sh (step 5) first." >&2
  exit 1
fi
export FS_PUBLIC_API_TOKEN="$TOKEN"
export FS_LIFECYCLE_API_TOKEN="${FS_LIFECYCLE_API_TOKEN:-$TOKEN}"
# Do not echo token values
echo "    token loaded (len=${#TOKEN})"

if [ "$RESET_VOLUMES" = "1" ]; then
  echo "[3/7] Resetting Odoo volumes only (odoo_data, odoo_db_data)..."
  docker compose --profile odoo stop odoo odoo-db 2>/dev/null || true
  docker compose --profile odoo rm -f odoo odoo-db 2>/dev/null || true
  PROJECT=$(basename "$(pwd)")
  for vol in odoo_data odoo_db_data; do
    docker volume rm "${PROJECT}_${vol}" 2>/dev/null \
      || docker volume rm "$vol" 2>/dev/null \
      || true
  done
else
  echo "[3/7] Keeping existing Odoo volumes (pass --reset-volumes for cold DB)..."
fi

echo "[4/7] Building Odoo image (openupgradelib baked) and starting odoo-db + odoo..."
docker compose --profile odoo up -d --build odoo-db odoo

echo "[5/7] Waiting for Postgres and Odoo HTTP..."
for i in $(seq 1 60); do
  if docker exec filantropia-odoo-db pg_isready -U odoo >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
# Odoo may still be booting / first-time init
for i in $(seq 1 90); do
  code=$(curl -sS -o /dev/null -w '%{http_code}' -m 3 http://localhost:8069/web/login 2>/dev/null || echo 000)
  case "$code" in
    200|303|302|301) break ;;
  esac
  sleep 2
done
echo "    odoo HTTP probe done (last code=${code:-unknown})"

echo "[6/7] Ensuring openupgradelib importable + installing/updating modules..."
# Probe deps on the running image (before stop)
if ! docker compose --profile odoo exec -T odoo python3 -c 'import openupgradelib, requests'; then
  echo "ERROR: openupgradelib/requests missing in image. Check odoo/Dockerfile build." >&2
  exit 1
fi

# Detect whether filantropia_public already exists
DB_EXISTS=$(docker exec filantropia-odoo-db psql -U odoo -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null | tr -d '[:space:]' || true)

# stop-after-init cannot share port 8069 with the long-running server
echo "    stopping odoo for module install (avoids bind on :8069)..."
docker compose --profile odoo stop odoo

run_odoo_init() {
  # One-off container shares volumes/network; no port publish needed
  docker compose --profile odoo run --rm --no-deps -T odoo \
    odoo -d "$DB_NAME" --stop-after-init --without-demo=all "$@"
}

if [ "$DB_EXISTS" = "1" ]; then
  INSTALLED=$(docker exec filantropia-odoo-db psql -U odoo -d "$DB_NAME" -tAc \
    "SELECT COUNT(*) FROM ir_module_module WHERE name IN ('queue_job','filantropia_solar_public') AND state='installed';" \
    2>/dev/null | tr -d '[:space:]' || echo 0)
  if [ "${INSTALLED:-0}" = "2" ]; then
    echo "    modules installed; updating filantropia_solar_public + queue_job..."
    run_odoo_init -u queue_job,filantropia_solar_public
  else
    echo "    DB exists but modules missing; installing..."
    run_odoo_init -i queue_job,filantropia_solar_public
  fi
else
  echo "    creating DB ${DB_NAME} and installing base + website stack + queue_job..."
  run_odoo_init -i base,website,website_blog,crm,queue_job,filantropia_solar_public
fi

echo "    starting odoo so jobrunner attaches with workers>0..."
docker compose --profile odoo up -d odoo
sleep 5

echo "[7/7] Asserting queue job runner is ready..."
READY=0
for i in $(seq 1 30); do
  if docker logs "$ODOO" 2>&1 | grep -q "queue job runner ready for db ${DB_NAME}"; then
    READY=1
    break
  fi
  sleep 2
done
if [ "$READY" != "1" ]; then
  echo "ERROR: jobrunner ready line not found for db ${DB_NAME}" >&2
  docker logs "$ODOO" 2>&1 | tail -40 >&2 || true
  exit 1
fi
echo "    jobrunner ready for db ${DB_NAME}"

if [ "$SMOKE" = "1" ]; then
  echo "[smoke] Creating donation lead and waiting for queue_job done..."
  # shell as admin (uid 2) via odoo shell
  docker compose --profile odoo exec -T odoo odoo shell -d "$DB_NAME" --no-http <<'PY'
Lead = env["crm.lead"].sudo()
lead = Lead.create({
    "name": "Cold-start smoke candidatura",
    "partner_name": "Smoke NGO Coldstart",
    "contact_name": "Smoke Tester",
    "email_from": "smoke-coldstart@example.com",
    "fs_is_donation_application": True,
    "fs_station_capacity_kwp": 12.5,
    "fs_station_latitude": 38.7223,
    "fs_station_longitude": -9.1393,
    "fs_station_location_label": "Lisboa",
    "fs_station_website": "https://example.org/smoke-coldstart",
    "fs_station_short_description": "Cold-start smoke station",
})
env.cr.commit()
lead.fs_enqueue_create_virtual()
env.cr.commit()
print(f"SMOKE_LEAD_ID={lead.id}")
PY

  # Poll queue_job for latest Virtual create
  DONE=0
  for i in $(seq 1 40); do
    row=$(docker exec filantropia-odoo-db psql -U odoo -d "$DB_NAME" -tAc \
      "SELECT id||'|'||state||'|'||COALESCE(name,'') FROM queue_job WHERE name ILIKE '%Virtual create%' ORDER BY id DESC LIMIT 1;" \
      2>/dev/null | tr -d '\r' || true)
    echo "    poll: ${row:-none}"
    case "$row" in
      *"|done|"*) DONE=1; break ;;
      *"|failed|"*|*"|cancelled|"*)
        echo "ERROR: job not successful: $row" >&2
        docker exec filantropia-odoo-db psql -U odoo -d "$DB_NAME" -c \
          "SELECT id, state, name, exc_info FROM queue_job ORDER BY id DESC LIMIT 3;" >&2 || true
        exit 1
        ;;
    esac
    sleep 3
  done
  if [ "$DONE" != "1" ]; then
    echo "ERROR: queue_job did not reach done within timeout" >&2
    docker exec filantropia-odoo-db psql -U odoo -d "$DB_NAME" -c \
      "SELECT id, state, name FROM queue_job ORDER BY id DESC LIMIT 5;" >&2 || true
    exit 1
  fi
  echo "    smoke OK: Virtual create job done (no manual perform)"
fi

echo
echo "Done."
echo "  Odoo:     http://localhost:8069  (admin password from odoo.conf admin_passwd)"
echo "  DB:       ${DB_NAME}"
echo "  Jobrunner: ready"
echo "  Smoke:    bash scripts/setup-odoo.sh --smoke"
