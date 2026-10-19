#!/usr/bin/env bash
# Test C preflight — operator workstation. Exit 0 only when baseline is safe to arm.
# Does not arm flags, contact promote paths, or change hosts beyond read-only SSH/curl.
set -euo pipefail

LEASE_ENV="${FS_LEASE_ENV:-$HOME/.config/filantropia-embassy/lease-phase-a.env}"
TRL5_HOST="${TRL5_HOST:-100.82.252.18}"
FRANK_HOST="${FRANK_HOST:-100.82.194.96}"
UA="${FS_HTTP_UA:-Mozilla/5.0}"
FAIL=0

log() { printf '%s\n' "$*"; }
pass() { log "PASS: $*"; }
fail() { log "FAIL: $*"; FAIL=1; }

if [[ ! -f "$LEASE_ENV" ]]; then
  fail "missing lease env $LEASE_ENV"
  exit 1
fi
# shellcheck disable=SC1090
set -a && source "$LEASE_ENV" && set +a
: "${FS_LEASE_AUTHORITY_URL:?}"
: "${FS_LEASE_AUTHORITY_TOKEN:?}"

http_code() {
  local url=$1
  curl -sS -o /dev/null -w '%{http_code}' -A "$UA" --max-time 20 -L "$url" || echo ERR
}

log "== public / origins =="
APEX=$(http_code https://filantropiasolar.pt/inicio)
WWW=$(http_code https://www.filantropiasolar.pt/inicio)
TRL5O=$(http_code https://odoo-trl5.wera.global/web/login)
FRANKO=$(http_code https://odoo-frank.wera.global/web/login)
[[ "$APEX" == "200" ]] && pass "apex=$APEX" || fail "apex=$APEX (want 200)"
[[ "$WWW" == "200" ]] && pass "www=$WWW" || fail "www=$WWW (want 200)"
[[ "$TRL5O" == "200" ]] && pass "odoo-trl5=$TRL5O" || fail "odoo-trl5=$TRL5O (want 200)"
case "$FRANKO" in
  502|503|530) pass "odoo-frank=$FRANKO (standby expected 5xx)" ;;
  *) fail "odoo-frank=$FRANKO (want 502/503/530 while Odoo stopped)" ;;
esac

log "== lease status =="
STATUS_JSON=$(curl -sS -A 'filantropia-lease-client/1.0' \
  -H "Authorization: Bearer ${FS_LEASE_AUTHORITY_TOKEN}" \
  --max-time 20 \
  "${FS_LEASE_AUTHORITY_URL%/}/lease/status" || true)
python3 - <<'PY' "$STATUS_JSON" || FAIL=1
import json, sys
raw = sys.argv[1]
try:
    d = json.loads(raw)
except Exception as exc:
    print(f"FAIL: lease status not JSON: {exc}")
    raise SystemExit(1)
phase = d.get("phase")
state = d.get("state") or {}
owner = state.get("owner_node_id")
pending = state.get("takeover_pending")
print(f"lease phase={phase} owner={owner} epoch={state.get('epoch')} takeover_pending={pending}")
ok = phase == "active" and owner == "trl5" and pending in (False, None)
print("PASS: lease active/trl5" if ok else "FAIL: lease must be active owner trl5, takeover_pending false")
raise SystemExit(0 if ok else 1)
PY

log "== TRL5 read-only =="
if ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${TRL5_HOST}" 'true' 2>/dev/null; then
  ssh -o BatchMode=yes "root@${TRL5_HOST}" bash -s <<'REMOTE' || FAIL=1
set -euo pipefail
systemctl is-active filantropia-lease-guard.timer >/dev/null \
  && echo PASS: trl5 lease-guard.timer active \
  || { echo FAIL: trl5 lease-guard.timer not active; exit 1; }
test ! -f /etc/filantropia-embassy/odoo-fenced.json \
  && echo PASS: trl5 not odoo-fenced \
  || { echo FAIL: trl5 odoo-fenced.json present; exit 1; }
docker exec filantropia-odoo-db psql -U odoo -d postgres -Atc \
  "SELECT count(*) FROM pg_stat_replication WHERE state='streaming'" | grep -qx 1 \
  && echo PASS: trl5 has streaming replica \
  || { echo FAIL: trl5 streaming replica missing; exit 1; }
# Readiness must not 404 (compose env injection). Use host token file.
if [[ -f /etc/filantropia-embassy/readiness.env ]]; then
  # shellcheck disable=SC1091
  set -a && source /etc/filantropia-embassy/readiness.env && set +a
fi
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
  -H "Authorization: Bearer ${FS_EMBASSY_READINESS_TOKEN:-}" \
  http://127.0.0.1:8069/filantropia/embassy/readiness || echo ERR)
case "$code" in
  200) echo "PASS: trl5 readiness endpoint reachable ($code)" ;;
  401) echo "FAIL: trl5 readiness 401 (token mismatch)"; exit 1 ;;
  404) echo "FAIL: trl5 readiness 404 (env missing from Odoo container)"; exit 1 ;;
  *) echo "FAIL: trl5 readiness code=$code"; exit 1 ;;
esac
REMOTE
else
  fail "SSH root@${TRL5_HOST} unavailable"
fi

log "== Frank read-only =="
if ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${FRANK_HOST}" 'true' 2>/dev/null; then
  ssh -o BatchMode=yes "root@${FRANK_HOST}" bash -s <<'REMOTE' || FAIL=1
set -euo pipefail
docker exec filantropia-odoo-db psql -U odoo -d filantropia_public -Atc \
  "SELECT pg_is_in_recovery()" | grep -qx t \
  && echo PASS: frank pg_is_in_recovery=t \
  || { echo FAIL: frank not in recovery; exit 1; }
# Auto flags must be false before the approved arm window.
python3 - <<'PY'
from pathlib import Path
text = Path("/etc/filantropia-embassy/embassy.toml").read_text(encoding="utf-8")
need = {
    "request_takeover_on_outage": False,
    "execute_promotion": False,
    "automatic_actions_enabled": False,
}
bad = []
for key, want in need.items():
    for line in text.splitlines():
        if line.strip().startswith(key):
            val = line.split("=", 1)[1].strip().lower()
            got = val == "true"
            if got != want:
                bad.append(f"{key}={val}")
            break
    else:
        bad.append(f"{key} missing")
if bad:
    print("FAIL: frank flags not fully disarmed:", ", ".join(bad))
    raise SystemExit(1)
print("PASS: frank auto flags disarmed")
PY
status=$(docker inspect -f '{{.State.Status}}' filantropia-odoo 2>/dev/null || echo missing)
case "$status" in
  exited|created|dead) echo "PASS: frank odoo status=$status" ;;
  *) echo "FAIL: frank odoo status=$status (want stopped)"; exit 1 ;;
esac
REMOTE
elif ssh -o BatchMode=yes -o ConnectTimeout=10 "wera@${FRANK_HOST}" 'true' 2>/dev/null; then
  fail "root SSH to Frank unavailable (wera-only). Preflight requires root-readable embassy.toml/PG checks or an approved root path"
else
  fail "SSH to Frank (${FRANK_HOST}) unavailable"
fi

log "== summary =="
if [[ "$FAIL" -eq 0 ]]; then
  pass "Test C preflight OK — still keep flags OFF until approved window"
  exit 0
fi
fail "Test C preflight failed"
exit 1
