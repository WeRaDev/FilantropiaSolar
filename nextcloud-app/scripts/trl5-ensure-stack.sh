#!/usr/bin/env bash
# TRL5: ensure Filantropia Odoo + supporting services + cloudflared are up.
# Invoked by systemd filantropia-stack.service on boot and safe to re-run.
set -u

APP_ROOT="${FILANTROPIA_APP_ROOT:-/opt/FilantropiaSolar/nextcloud-app}"
SECRETS_DIR="${FILANTROPIA_SECRETS_DIR:-/opt/FilantropiaSolar/.secrets}"
CF_DIR="${FILANTROPIA_CF_DIR:-/home/wera-admin/cloudflared-nc}"
COMPOSE_BIN="${DOCKER_COMPOSE_BIN:-docker}"
LOG_TAG="trl5-ensure-stack"
ODOO_FENCE_FILE="${FILANTROPIA_ODOO_FENCE_FILE:-/etc/filantropia-embassy/odoo-fenced.json}"
ODOO_CONTROL_LOCK="${FILANTROPIA_ODOO_CONTROL_LOCK:-/run/lock/filantropia-odoo-control.lock}"
LEASE_GUARD_STATE="${FILANTROPIA_LEASE_GUARD_STATE:-/etc/filantropia-embassy/lease-guard-state.json}"

log() { printf '%s %s\n' "[$LOG_TAG]" "$*"; }
die() { log "ERROR: $*"; exit 1; }

[ -d "$APP_ROOT" ] || die "missing APP_ROOT=$APP_ROOT"
cd "$APP_ROOT" || die "cd $APP_ROOT failed"
command -v flock >/dev/null 2>&1 || die "flock is required for Odoo start/fence serialization"
mkdir -p "$(dirname "$ODOO_CONTROL_LOCK")" || die "cannot create Odoo control lock directory"
exec 9>"$ODOO_CONTROL_LOCK" || die "cannot open Odoo control lock"
flock -x 9 || die "cannot acquire Odoo control lock"

export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml:docker-compose.trl5.yml}"
ODOO_FENCED=0
if [ -e "$ODOO_FENCE_FILE" ] || [ -L "$ODOO_FENCE_FILE" ]; then
  ODOO_FENCED=1
  log "persistent Odoo fence is present at $ODOO_FENCE_FILE"
fi
if [ -f "$LEASE_GUARD_STATE" ]; then
  if grep -q '"fenced": true' "$LEASE_GUARD_STATE" 2>/dev/null; then
    ODOO_FENCED=1
    log "lease guard reports fenced state at $LEASE_GUARD_STATE"
  fi
fi

if [ -f "$SECRETS_DIR/filantropia_public_api_token" ]; then
  # shellcheck disable=SC2155
  export FS_PUBLIC_API_TOKEN="$(tr -d '\r\n' <"$SECRETS_DIR/filantropia_public_api_token")"
  export FS_LIFECYCLE_API_TOKEN="${FS_LIFECYCLE_API_TOKEN:-$FS_PUBLIC_API_TOKEN}"
fi

# Prefer AIO Nextcloud for FS_* if not already set in environment.
export FS_API_BASE_URL="${FS_API_BASE_URL:-http://nextcloud-aio-apache:11000/index.php/apps/filantropia_solar/api/public/v1}"
export FS_LIFECYCLE_API_BASE_URL="${FS_LIFECYCLE_API_BASE_URL:-http://nextcloud-aio-apache:11000/index.php/apps/filantropia_solar/api/lifecycle/v1}"
export FS_NC_ADMIN_URL="${FS_NC_ADMIN_URL:-https://wera-ss-pt-tv-1.wera.global}"
export FS_NC_PUBLIC_ORIGIN="${FS_NC_PUBLIC_ORIGIN:-https://wera-ss-pt-tv-1.wera.global}"

log "COMPOSE_FILE=$COMPOSE_FILE"

# Core data plane used by Odoo/ML (legacy filantropia-nextcloud intentionally omitted).
if [ "$ODOO_FENCED" = "1" ]; then
  $COMPOSE_BIN compose --profile odoo up -d db redis ml-service odoo-db \
    || die "compose up supporting services failed while Odoo is fenced"
  if docker ps -a --format '{{.Names}}' | grep -qx filantropia-odoo; then
    docker update --restart=no filantropia-odoo >/dev/null 2>&1 \
      || die "cannot disable Odoo restart policy while fenced"
    if docker ps --format '{{.Names}}' | grep -qx filantropia-odoo; then
      docker stop filantropia-odoo >/dev/null 2>&1 \
        || die "cannot stop fenced Odoo container"
    fi
    ODOO_RUNNING="$(docker inspect filantropia-odoo --format '{{.State.Running}}' 2>/dev/null || true)"
    [ "$ODOO_RUNNING" = "false" ] \
      || die "Odoo did not remain stopped under the persistent fence"
  fi
else
  $COMPOSE_BIN compose --profile odoo up -d db redis ml-service odoo-db odoo \
    || die "compose up odoo stack failed"
fi

# Keep legacy NC stopped on TRL5 (AIO is SoT).
if docker ps -a --format '{{.Names}}' | grep -qx filantropia-nextcloud; then
  docker update --restart=no filantropia-nextcloud >/dev/null 2>&1 || true
  docker stop filantropia-nextcloud >/dev/null 2>&1 || true
fi

# Cloudflare tunnel sidecar (public website + NC hostnames).
# TRL5 production uses network_mode: host + localhost origins (see infra/cloudflared).
# A fenced/stale node must not start the public connector.
if [ "$ODOO_FENCED" = "1" ]; then
  if docker ps -a --format '{{.Names}}' | grep -qx filantropia-cloudflared; then
    docker update --restart=no filantropia-cloudflared >/dev/null 2>&1 || true
    docker stop filantropia-cloudflared >/dev/null 2>&1 || true
    log "cloudflared kept stopped while Odoo is fenced"
  fi
elif [ -f "$CF_DIR/docker-compose.yml" ] && [ -f "$CF_DIR/config.yml" ] && [ -f "$CF_DIR/credentials.json" ]; then
  chmod 644 "$CF_DIR/config.yml" "$CF_DIR/credentials.json" 2>/dev/null || true
  $COMPOSE_BIN compose -f "$CF_DIR/docker-compose.yml" up -d \
    || log "WARN: cloudflared compose up failed"
else
  log "WARN: cloudflared dir incomplete at $CF_DIR"
fi

cf_uses_host_net() {
  grep -qE '^[[:space:]]*network_mode:[[:space:]]*host' "$CF_DIR/docker-compose.yml" 2>/dev/null
}

ensure_net() {
  local container="$1"
  local network="$2"
  docker ps -a --format '{{.Names}}' | grep -qx "$container" || return 0
  docker network inspect "$network" >/dev/null 2>&1 || return 0
  if docker inspect "$container" --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}' \
    | grep -qx "$network"; then
    return 0
  fi
  log "connecting $container -> $network"
  docker network connect "$network" "$container" 2>/dev/null || true
}

# Heal network membership (this is what broke Odoo after reboot: empty Networks).
ensure_net filantropia-odoo-db nextcloud-app_filantropia-net
if [ "$ODOO_FENCED" != "1" ]; then
  ensure_net filantropia-odoo nextcloud-app_filantropia-net
fi
ensure_net filantropia-ml nextcloud-app_filantropia-net
ensure_net filantropia-db nextcloud-app_filantropia-net
ensure_net filantropia-redis nextcloud-app_filantropia-net
# Bridge-mode cloudflared only: host-network mode has no Docker networks to heal.
if ! cf_uses_host_net; then
  ensure_net filantropia-cloudflared nextcloud-app_filantropia-net
  ensure_net filantropia-cloudflared nextcloud-aio
fi
# AIO apache also needs filantropia-net for Odoo→NC API from same overlay path when used.
ensure_net nextcloud-aio-apache nextcloud-app_filantropia-net 2>/dev/null || true
ensure_net nextcloud-aio-nextcloud nextcloud-app_filantropia-net 2>/dev/null || true
if [ "$ODOO_FENCED" = "1" ]; then
  log "Odoo and public connector remain stopped under the persistent fence"
  exit 0
fi

# If Odoo is up but not publishing HTTP yet, wait briefly.
for i in $(seq 1 40); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' -m 3 http://127.0.0.1:8069/web/login 2>/dev/null || echo 0)"
  if [ "$code" = "200" ]; then
    log "Odoo HTTP ready (try $i)"
    break
  fi
  # Empty networks / DNS failure: force recreate once mid-wait.
  if [ "$i" = "10" ]; then
    nets="$(docker inspect filantropia-odoo --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null || true)"
    if [ -z "${nets// /}" ]; then
      log "Odoo has no networks — force recreate"
      $COMPOSE_BIN compose --profile odoo up -d --force-recreate odoo-db odoo || true
      ensure_net filantropia-odoo nextcloud-app_filantropia-net
      ensure_net filantropia-odoo-db nextcloud-app_filantropia-net
    fi
  fi
  sleep 3
done

code="$(curl -sS -o /dev/null -w '%{http_code}' -m 5 http://127.0.0.1:8069/web/login 2>/dev/null || echo 0)"
if [ "$code" != "200" ]; then
  log "WARN: Odoo still not HTTP-ready code=$code"
  docker inspect filantropia-odoo --format 'status={{.State.Status}} restarts={{.RestartCount}} nets={{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null || true
  docker logs --tail 40 filantropia-odoo 2>&1 | tail -40 || true
  exit 1
fi

log "stack OK"
exit 0
