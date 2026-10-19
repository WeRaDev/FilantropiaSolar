#!/bin/bash
# Publish filantropia-odoo-db:5432 on the TRL5 Tailnet address for Frank streaming.
# Install on TRL5 as /usr/local/sbin/filantropia-pg-repl-publish.sh (mode 755)
# and point filantropia-pg-repl-publish.service ExecStart at this script.
# Do not combine with docker-compose.trl5-repl-publish.yml host-port bind.
set -euo pipefail

NETWORK_NAME="${FILANTROPIA_DB_NETWORK:-nextcloud-app_filantropia-net}"
CONTAINER_NAME="${FILANTROPIA_DB_CONTAINER:-filantropia-odoo-db}"
BIND_ADDR="${FILANTROPIA_PG_PUBLISH_ADDR:-100.82.252.18}"
BIND_PORT="${FILANTROPIA_PG_PUBLISH_PORT:-5432}"

CIP=$(docker inspect -f "{{(index .NetworkSettings.Networks \"${NETWORK_NAME}\").IPAddress}}" "${CONTAINER_NAME}")
if [ -z "${CIP}" ]; then
  echo "${CONTAINER_NAME} has no IP on ${NETWORK_NAME}" >&2
  exit 1
fi

echo "publishing ${BIND_ADDR}:${BIND_PORT} -> ${CIP}:5432"
exec socat "TCP-LISTEN:${BIND_PORT},bind=${BIND_ADDR},fork,reuseaddr" "TCP:${CIP}:5432"
