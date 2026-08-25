#!/usr/bin/env bash
# Deploy Filantropia Solar public edge:
#   - TRL4 network join (Nextcloud + ML + Odoo)
#   - Odoo proxy_mode + public hostname
#   - Cloudflare tunnel -> filantropiasolar.pt
#
# Usage:
#   bash nextcloud-app/scripts/deploy-public-tunnel.sh           # full deploy if credentials exist
#   bash nextcloud-app/scripts/deploy-public-tunnel.sh login     # interactive CF login only
#   bash nextcloud-app/scripts/deploy-public-tunnel.sh create    # create tunnel + DNS after login
#   bash nextcloud-app/scripts/deploy-public-tunnel.sh up        # start tunnel container
#   bash nextcloud-app/scripts/deploy-public-tunnel.sh status
#
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/nextcloud-app"
CF_DIR="$APP/infra/cloudflared"
HOST_NAME="${PUBLIC_HOSTNAME:-filantropiasolar.pt}"
TUNNEL_NAME="${TUNNEL_NAME:-filantropia-solar}"
CITY_NET="${CITY_NET:-compose_city_internal}"
ODOO_URL="${ODOO_URL:-http://127.0.0.1:8069}"

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

need_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing command: $1"; }

join_trl4() {
  need_cmd docker
  if ! docker network inspect "$CITY_NET" >/dev/null 2>&1; then
    log "WARN: network $CITY_NET not found (TRL4 SolarSeed stack may be down); skipping network join"
    return 0
  fi
  for c in filantropia-nextcloud filantropia-ml filantropia-odoo; do
    if ! docker ps --format '{{.Names}}' | grep -qx "$c"; then
      log "WARN: $c not running; skip network join"
      continue
    fi
    if docker network connect "$CITY_NET" "$c" 2>/dev/null; then
      log "connected $c -> $CITY_NET"
    else
      log "$c already on $CITY_NET (or connect failed non-fatally)"
    fi
  done
  # trusted domains for Nextcloud if public host set
  if docker ps --format '{{.Names}}' | grep -qx filantropia-nextcloud; then
    docker exec -u 33 filantropia-nextcloud php occ config:system:set trusted_domains 3 --value="$HOST_NAME" >/dev/null 2>&1 \
      && log "Nextcloud trusted_domains += $HOST_NAME" \
      || log "WARN: could not set Nextcloud trusted domain"
  fi
}

ensure_odoo_proxy() {
  need_cmd docker
  docker ps --format '{{.Names}}' | grep -qx filantropia-odoo || die "filantropia-odoo not running"
  # conf is mounted read-only path may be file mount; rewrite via compose recreate preferred
  if [ -f "$APP/odoo/config/odoo.conf" ]; then
    log "odoo.conf present with proxy_mode"
  fi
  # Ensure website knows public base URL via system param if possible
  docker exec -i filantropia-odoo odoo shell -d filantropia_public \
    --db_host=odoo-db --db_user=odoo --db_password=odoo_dev_password --no-http <<PY
ICP = env['ir.config_parameter'].sudo()
ICP.set_param('web.base.url', 'https://$HOST_NAME')
ICP.set_param('web.base.url.freeze', 'True')
# brand + lang already handled by module hooks; refresh
w = env['website'].search([], limit=1)
if w:
    w.write({'domain': 'https://$HOST_NAME', 'name': 'Filantropia Solar'})
env.cr.commit()
print('web.base.url=', ICP.get_param('web.base.url'))
print('website.domain=', w.domain if w else None)
PY
  log "Odoo public URL set to https://$HOST_NAME"
}

cf_login() {
  need_cmd cloudflared
  log "Opening Cloudflare login (browser). Authorize the wera.global zone."
  cloudflared tunnel login
  log "Login complete. cert at ~/.cloudflared/cert.pem"
}

cf_create() {
  need_cmd cloudflared
  [ -f "$HOME/.cloudflared/cert.pem" ] || die "run: $0 login first"
  mkdir -p "$CF_DIR"
  # create tunnel if missing
  if cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    log "tunnel $TUNNEL_NAME already exists"
  else
    cloudflared tunnel create "$TUNNEL_NAME"
  fi
  # resolve tunnel id
  TID=$(cloudflared tunnel list 2>/dev/null | awk -v n="$TUNNEL_NAME" '$2==n {print $1; exit}')
  [ -n "$TID" ] || die "could not resolve tunnel id for $TUNNEL_NAME"
  log "tunnel id=$TID"
  # copy credentials json
  CREDS="$HOME/.cloudflared/${TID}.json"
  [ -f "$CREDS" ] || die "missing credentials $CREDS"
  cp "$CREDS" "$CF_DIR/credentials.json"
  chmod 600 "$CF_DIR/credentials.json"
  # write config with real id, local service to host odoo
  cat > "$CF_DIR/config.yml" <<YML
tunnel: $TID
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: $HOST_NAME
    service: http://host.docker.internal:8069
    originRequest:
      httpHostHeader: $HOST_NAME
  - service: http_status:404
YML
  # also keep a host-run config
  cat > "$CF_DIR/config.host.yml" <<YML
tunnel: $TID
credentials-file: $CF_DIR/credentials.json

ingress:
  - hostname: $HOST_NAME
    service: http://127.0.0.1:8069
    originRequest:
      httpHostHeader: $HOST_NAME
  - service: http_status:404
YML
  # DNS route
  cloudflared tunnel route dns "$TUNNEL_NAME" "$HOST_NAME" \
    && log "DNS $HOST_NAME -> tunnel $TUNNEL_NAME" \
    || log "WARN: dns route failed (may already exist)"
  log "create done"
}

cf_up() {
  need_cmd docker
  [ -f "$CF_DIR/credentials.json" ] || die "missing $CF_DIR/credentials.json — run create"
  [ -f "$CF_DIR/config.yml" ] || die "missing $CF_DIR/config.yml"
  # Prefer host cloudflared if docker network external name issues; try docker first
  if docker network inspect nextcloud-app_filantropia-net >/dev/null 2>&1; then
    docker compose -f "$CF_DIR/docker-compose.yml" up -d
    log "cloudflared container started"
  else
    log "docker network missing; starting host cloudflared"
    cf_up_host
  fi
}

cf_up_host() {
  need_cmd cloudflared
  [ -f "$CF_DIR/config.host.yml" ] || die "missing host config"
  # stop previous if any
  if pgrep -f "cloudflared.*filantropia" >/dev/null 2>&1; then
    pkill -f "cloudflared tunnel --config .*cloudflared/config.host.yml" || true
  fi
  nohup cloudflared tunnel --config "$CF_DIR/config.host.yml" run \
    > /tmp/filantropia-cloudflared.log 2>&1 &
  echo $! > /tmp/filantropia-cloudflared.pid
  log "host cloudflared pid=$(cat /tmp/filantropia-cloudflared.pid) log=/tmp/filantropia-cloudflared.log"
}

cf_status() {
  log "=== local Odoo ==="
  curl -sS -o /dev/null -w "local /inicio %{http_code}\n" "$ODOO_URL/inicio" || true
  log "=== tunnel process/container ==="
  docker ps --format '{{.Names}} {{.Status}}' 2>/dev/null | grep cloudflared || true
  if [ -f /tmp/filantropia-cloudflared.pid ]; then
    pid=$(cat /tmp/filantropia-cloudflared.pid)
    if kill -0 "$pid" 2>/dev/null; then log "host cloudflared running pid=$pid"; else log "host pid file stale"; fi
  fi
  log "=== public probe ==="
  curl -sS -o /dev/null -w "https://$HOST_NAME/inicio %{http_code}\n" --max-time 20 "https://$HOST_NAME/inicio" || log "public probe failed"
  log "=== cloudflared list ==="
  cloudflared tunnel list 2>/dev/null || log "not logged in / no cert"
}

cmd="${1:-all}"
case "$cmd" in
  login) cf_login ;;
  create) cf_create ;;
  up) cf_up ;;
  up-host) cf_up_host ;;
  status) cf_status ;;
  trl4) join_trl4 ;;
  odoo-url) ensure_odoo_proxy ;;
  all)
    join_trl4
    ensure_odoo_proxy
    if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
      log "No Cloudflare cert — run: bash $0 login"
      log "Then: bash $0 create && bash $0 up && bash $0 status"
      exit 2
    fi
    if [ ! -f "$CF_DIR/credentials.json" ]; then
      cf_create
    fi
    cf_up
    cf_status
    ;;
  *) die "unknown command: $cmd" ;;
esac
