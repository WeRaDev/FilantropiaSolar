#!/usr/bin/env bash
# Run on TRL5 with sudo. Clears sticky lease-guard fence and re-arms the timer.
# /opt/FilantropiaSolar/nextcloud-app is root-only (0700); never cd there as wera-admin.
# Drive the one-shot via systemd so WorkingDirectory/PYTHONPATH match production.
set -euo pipefail

STATE_FILE="${FILANTROPIA_LEASE_GUARD_STATE:-/etc/filantropia-embassy/lease-guard-state.json}"
FENCE_FILE="${FILANTROPIA_ODOO_FENCE_FILE:-/etc/filantropia-embassy/odoo-fenced.json}"

echo "== stop lease-guard units =="
sudo systemctl stop filantropia-lease-guard.timer filantropia-lease-guard.service || true

echo "== clear fence marker =="
sudo rm -f "$FENCE_FILE"

echo "== reset lease-guard state (not fenced) =="
sudo python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
path = Path("${STATE_FILE}")
path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
payload = {
    "schema_version": 1,
    "highest_epoch_seen": 0,
    "fenced": False,
    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    "reset_reason": "manual_unfence_after_aborted_takeover",
}
path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
path.chmod(0o600)
print(f"wrote {path}")
PY

echo "== ensure origin containers =="
docker start filantropia-odoo-db filantropia-odoo filantropia-cloudflared >/dev/null
docker network connect --alias odoo-db --alias filantropia-odoo-db \
  nextcloud-app_filantropia-net filantropia-odoo-db 2>/dev/null || true
sleep 3
curl -fsS -o /dev/null -w "local8069=%{http_code}\n" --max-time 15 http://127.0.0.1:8069/web/login

echo "== one-shot lease-guard via systemd (root WorkingDirectory) =="
sudo systemctl reset-failed filantropia-lease-guard.service || true
sudo systemctl start filantropia-lease-guard.service
systemctl show filantropia-lease-guard.service -p Result -p ExecMainStatus --no-pager
status="$(systemctl show -p ExecMainStatus --value filantropia-lease-guard.service)"
if [ "$status" != "0" ]; then
  echo "one-shot failed; journal:" >&2
  sudo journalctl -u filantropia-lease-guard.service -n 40 --no-pager >&2
  exit 1
fi
sudo cat "$STATE_FILE"

echo "== re-arm timer =="
sudo systemctl start filantropia-lease-guard.timer
sudo systemctl is-active filantropia-lease-guard.timer
sleep 20
systemctl show filantropia-lease-guard.service -p ActiveState -p Result -p ExecMainStatus --no-pager
sudo journalctl -u filantropia-lease-guard.service -n 15 --no-pager

echo "OK: host lease-guard renewing."
