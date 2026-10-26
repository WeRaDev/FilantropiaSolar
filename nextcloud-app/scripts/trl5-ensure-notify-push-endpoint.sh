#!/usr/bin/env bash
# Reapply the public notify_push endpoint after AIO starts Nextcloud.

CONTAINER="nextcloud-aio-nextcloud"
TARGET_ENDPOINT="https://wera-ss-pt-tv-1.wera.global/push"
STATE_FILE="/run/filantropia-notify-push-endpoint/nextcloud-started-at"
LOG_TAG="filantropia-notify-push-endpoint"

log() {
  printf '%s %s\n' "[$LOG_TAG]" "$*"
}

main() {
  local snapshot container_state started_at health_status
  local last_started_at current_endpoint result

  snapshot="$(docker inspect --format '{{.State.Status}}|{{.State.StartedAt}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER" 2>/dev/null)"
  if [ -z "$snapshot" ]; then
    log "AIO Nextcloud container is unavailable; will retry"
    return 0
  fi

  IFS='|' read -r container_state started_at health_status <<< "$snapshot"
  if [ "$container_state" != "running" ] || [ "$health_status" != "healthy" ]; then
    log "AIO Nextcloud is not healthy yet; will retry"
    return 0
  fi

  last_started_at=""
  if [ -r "$STATE_FILE" ]; then
    IFS= read -r last_started_at < "$STATE_FILE"
  fi
  if [ "$started_at" = "$last_started_at" ]; then
    return 0
  fi

  current_endpoint="$(docker exec -u 33 "$CONTAINER" php occ config:app:get notify_push base_endpoint 2>/dev/null)"
  result=$?
  if [ "$result" -ne 0 ]; then
    log "could not read notify_push.base_endpoint; will retry"
    return 1
  fi

  if [ "$current_endpoint" != "$TARGET_ENDPOINT" ]; then
    docker exec -u 33 "$CONTAINER" php occ config:app:set notify_push base_endpoint --value="$TARGET_ENDPOINT"
    result=$?
    if [ "$result" -ne 0 ]; then
      log "could not set notify_push.base_endpoint; will retry"
      return 1
    fi
    log "set notify_push.base_endpoint to the public Nextcloud origin"
  else
    log "notify_push.base_endpoint already uses the public Nextcloud origin"
  fi

  mkdir -p "$(dirname "$STATE_FILE")" || return 1
  printf '%s\n' "$started_at" > "$STATE_FILE.tmp" || return 1
  mv "$STATE_FILE.tmp" "$STATE_FILE" || return 1
}

main "$@"
