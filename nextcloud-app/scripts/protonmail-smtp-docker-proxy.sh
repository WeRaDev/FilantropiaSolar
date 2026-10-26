#!/usr/bin/env bash
# Forward Docker bridge gateway SMTP to Proton Bridge on localhost.
set -euo pipefail

SOCAT_BIN="/usr/bin/socat"
PRIMARY_GATEWAY="172.18.0.1"
GATEWAY_WAIT_ATTEMPTS=60
GATEWAY_WAIT_INTERVAL_SEC=2
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

has_host_ip() {
  ip -4 -o addr show | grep -F "inet $1/" >/dev/null
}

wait_for_primary_gateway() {
  local attempt
  local max_wait_sec=$((GATEWAY_WAIT_ATTEMPTS * GATEWAY_WAIT_INTERVAL_SEC))
  echo "Waiting up to ${max_wait_sec}s for Docker gateway ${PRIMARY_GATEWAY}"
  for ((attempt = 1; attempt <= GATEWAY_WAIT_ATTEMPTS; attempt++)); do
    if has_host_ip "$PRIMARY_GATEWAY"; then
      echo "Docker gateway ${PRIMARY_GATEWAY} is available"
      return 0
    fi
    sleep "$GATEWAY_WAIT_INTERVAL_SEC"
  done
  echo "Required Docker gateway ${PRIMARY_GATEWAY} did not appear" >&2
  return 1
}

start_one() {
  local bind_ip="$1"
  local required="${2:-false}"
  if ! has_host_ip "$bind_ip"; then
    echo "Skip ${bind_ip}: not present on host"
    [[ "$required" != "true" ]]
    return
  fi

  echo "Starting SMTP proxy on ${bind_ip}:1025 -> 127.0.0.1:1025"
  "$SOCAT_BIN" "TCP-LISTEN:1025,bind=${bind_ip},fork,reuseaddr" \
    TCP:127.0.0.1:1025 &
  local pid="$!"
  sleep 0.2
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "SMTP proxy failed to bind ${bind_ip}:1025" >&2
    wait "$pid" || true
    return 1
  fi
  PIDS+=("$pid")
}

wait_for_primary_gateway
start_one "$PRIMARY_GATEWAY" true
start_one 172.17.0.1 || true
start_one 172.19.0.1 || true
start_one 172.20.0.1 || true
start_one 172.22.0.1 || true

if [ "${#PIDS[@]}" -eq 0 ]; then
  echo "No Docker gateway IPs found to bind" >&2
  exit 1
fi

if wait -n "${PIDS[@]}"; then
  echo "SMTP proxy process exited unexpectedly" >&2
  exit 1
else
  status="$?"
  echo "SMTP proxy process exited with status ${status}" >&2
  exit "$status"
fi
