#!/usr/bin/env bash
#
# Connect the FilantropiaSolar "Fortress" stack to the SolarSeed-v3 TRL4 ops
# network so Prometheus/Spirit (in the SolarSeed-v3 compose stack) can reach it.
#
# Prepare/deploy helper. Run on the TRL4 machine AFTER both stacks are up:
#   1. FilantropiaSolar: bash nextcloud-app/scripts/setup.sh
#   2. SolarSeed-v3:     docker compose -f compose/docker-compose.yml up -d
#   3. this script:      bash nextcloud-app/scripts/connect-trl4.sh
#
# Env:
#   CITY_NET     (default: compose_city_internal) - the SolarSeed-v3 network name
#   TRL4_DOMAIN  (optional) - external host/domain to add to NC trusted_domains

NET="${CITY_NET:-compose_city_internal}"

if ! docker network inspect "$NET" >/dev/null 2>&1; then
    echo "ERROR: network '$NET' not found. Bring up the SolarSeed-v3 compose stack first." >&2
    exit 1
fi

for c in filantropia-nextcloud filantropia-ml; do
    if ! docker ps --format '{{.Names}}' | grep -qx "$c"; then
        echo "WARN: container '$c' is not running; skipping." >&2
        continue
    fi
    if docker network connect "$NET" "$c" 2>/dev/null; then
        echo "connected $c -> $NET"
    else
        echo "$c already attached to $NET"
    fi
done

if [ -n "${TRL4_DOMAIN:-}" ]; then
    docker exec -u 33 filantropia-nextcloud php occ config:system:set trusted_domains 3 --value="$TRL4_DOMAIN" \
        && echo "added trusted domain: $TRL4_DOMAIN" || echo "WARN: could not set trusted domain"
fi

echo "Done. Spirit probes filantropia-nextcloud:80; ML at filantropia-ml:8501 on $NET."
