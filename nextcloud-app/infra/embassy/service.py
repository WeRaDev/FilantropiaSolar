"""Observe the Odoo origin, request lease takeover, and optionally promote."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from http import HTTPStatus
import json
import logging
import math
import os
from pathlib import Path
import re
import stat
import tomllib

from embassy.journal import EventJournal, JournalError, StateStore, operation_lock
from embassy.policy import (
    EmbassyPolicy,
    FencingEvidence,
    PrimaryObservation,
    StandbyObservation,
    evaluate,
)
from embassy.probe import probe_public_route, probe_readiness
from embassy.standby_status import collect_standby_status

_ENV_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_LOGGER = logging.getLogger("filantropia_embassy")
_HTTP_SUCCESS = HTTPStatus.OK


class EmbassyServiceError(RuntimeError):
    """Raised for invalid configuration or untrusted status inputs."""


def _read_status(path: Path) -> dict[str, object] | None:
    if path.is_symlink():
        raise EmbassyServiceError(f"Status file must not be a symlink: {path.name}")
    if not path.exists():
        return None
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise EmbassyServiceError(f"Status file is not private: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EmbassyServiceError(f"Status file is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise EmbassyServiceError(f"Status file shape is invalid: {path.name}")
    return value


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _optional_integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _positive_number(value: object, *, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise EmbassyServiceError(f"{name} must be a positive finite number")
    return float(value)


def _configured_path(section: dict[str, object], key: str) -> Path:
    value = section.get(key)
    if not isinstance(value, str) or not value:
        raise EmbassyServiceError(f"Embassy path setting is missing: {key}")
    return Path(value)


def _primary_observation(config: dict[str, object]) -> PrimaryObservation:
    url = config["readiness_url"]
    token_env = config["readiness_token_env"]
    timeout = config["timeout_seconds"]
    if not isinstance(url, str) or not isinstance(token_env, str):
        raise EmbassyServiceError("Primary readiness configuration is invalid")
    if not _ENV_NAME_PATTERN.fullmatch(token_env):
        raise EmbassyServiceError("Readiness token environment name is invalid")
    timeout = _positive_number(timeout, name="Readiness timeout")

    token = os.environ.get(token_env, "")
    if not token:
        return PrimaryObservation(reachable=None)
    result = probe_readiness(
        url,
        token=token,
        timeout_seconds=float(timeout),
    )
    if not result.reachable:
        return PrimaryObservation(reachable=False)

    payload = result.payload or {}
    return PrimaryObservation(
        reachable=True,
        ready=result.status_code == _HTTP_SUCCESS
        and _optional_bool(payload.get("ready")) is True,
        node_id=_optional_string(payload.get("node_id")),
        generation=_optional_string(payload.get("writer_generation")),
        database_is_primary=_optional_bool(payload.get("database_is_primary")),
        filestore_available=_optional_bool(payload.get("filestore_available")),
        public_routes_ready=None,
        maintenance_active=_optional_bool(payload.get("maintenance_active")) is True,
    )


def _public_routes_ready(
    route_urls: object,
    *,
    timeout_seconds: float,
) -> bool | None:
    if not isinstance(route_urls, list) or not all(
        isinstance(url, str) for url in route_urls
    ):
        raise EmbassyServiceError("Public route list must be an array of URLs")
    if not route_urls:
        return None
    results = [
        probe_public_route(url, timeout_seconds=timeout_seconds) for url in route_urls
    ]
    # Public edges may 303/302 before HTML; treat 2xx/3xx as healthy transport.
    return all(
        result.reachable
        and result.status_code is not None
        and 200 <= result.status_code < 400
        for result in results
    )


def _with_public_routes(
    primary: PrimaryObservation,
    route_urls: object,
    *,
    timeout_seconds: float,
) -> PrimaryObservation:
    return PrimaryObservation(
        reachable=primary.reachable,
        ready=primary.ready,
        node_id=primary.node_id,
        generation=primary.generation,
        database_is_primary=primary.database_is_primary,
        filestore_available=primary.filestore_available,
        public_routes_ready=_public_routes_ready(
            route_urls,
            timeout_seconds=timeout_seconds,
        ),
        maintenance_active=primary.maintenance_active,
    )


def _timestamp_age(
    status: dict[str, object],
    field: str,
    *,
    now: datetime,
) -> float | None:
    value = status.get(field)
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return None
    return (now.astimezone(UTC) - timestamp.astimezone(UTC)).total_seconds()


def _standby_observation(
    status: dict[str, object] | None,
    *,
    now: datetime,
) -> StandbyObservation:
    schema_version = status.get("schema_version") if status is not None else None
    if (
        status is None
        or isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        return StandbyObservation(
            database_reachable=None,
            database_in_recovery=None,
            source_node_id=None,
            source_generation=None,
            replication_heartbeat_age_seconds=None,
            replication_lag_bytes=None,
            filestore_source_generation=None,
            filestore_generation_age_seconds=None,
            all_attachments_verified=None,
            code_compatible=None,
            filestore_source_node_id=None,
        )
    return StandbyObservation(
        database_reachable=_optional_bool(status.get("database_reachable")),
        database_in_recovery=_optional_bool(status.get("database_in_recovery")),
        source_node_id=_optional_string(status.get("source_node_id")),
        source_generation=_optional_string(status.get("source_generation")),
        replication_heartbeat_age_seconds=_optional_number(
            status.get("replication_heartbeat_age_seconds")
        ),
        replication_lag_bytes=_optional_integer(status.get("replication_lag_bytes")),
        filestore_source_generation=_optional_string(
            status.get("filestore_source_generation")
        ),
        filestore_generation_age_seconds=_optional_number(
            status.get("filestore_generation_age_seconds")
        ),
        all_attachments_verified=_optional_bool(status.get("all_attachments_verified")),
        code_compatible=_optional_bool(status.get("code_compatible")),
        status_age_seconds=_timestamp_age(status, "observed_at_utc", now=now),
        attachment_verification_age_seconds=_timestamp_age(
            status,
            "attachment_verified_at_utc",
            now=now,
        ),
        filestore_source_node_id=_optional_string(
            status.get("filestore_source_node_id")
        ),
    )


def _fencing_evidence(
    status: dict[str, object] | None,
) -> FencingEvidence | None:
    schema_version = status.get("schema_version") if status is not None else None
    if (
        status is None
        or isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
    ):
        return None
    try:
        return FencingEvidence(
            target_node_id=str(status["target_node_id"]),
            target_generation=str(status["target_generation"]),
            source=str(status["source"]),
            proof_id=str(status["proof_id"]),
            verified_at=datetime.fromisoformat(
                str(status["verified_at_utc"]).replace("Z", "+00:00")
            ),
            expires_at=datetime.fromisoformat(
                str(status["expires_at_utc"]).replace("Z", "+00:00")
            ),
            acquirable=_optional_bool(status.get("acquirable")) is True,
            previous_epoch=_optional_integer(status.get("previous_epoch")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _load_config(path: Path) -> dict[str, object]:
    if path.is_symlink():
        raise EmbassyServiceError("Embassy TOML configuration must not be a symlink")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise EmbassyServiceError("Embassy TOML configuration must be private")
    try:
        with path.open("rb") as source:
            config = tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise EmbassyServiceError("Embassy TOML configuration is unreadable") from exc
    required_sections = {"primary", "standby", "fencing", "state", "policy"}
    if not required_sections.issubset(config):
        raise EmbassyServiceError("Embassy TOML configuration is incomplete")
    return config



def _lease_client_from_fencing(
    fencing_config: dict[str, object],
) -> tuple[object, Path] | tuple[None, None]:
    """Build a lease client + proof path when fencing is configured for software lease."""
    base_url = fencing_config.get("lease_authority_url")
    token_env = fencing_config.get("lease_token_env", "FS_LEASE_AUTHORITY_TOKEN")
    proof_file = fencing_config.get("proof_file")
    if not isinstance(base_url, str) or not base_url:
        return None, None
    if not isinstance(token_env, str) or not isinstance(proof_file, str) or not proof_file:
        return None, None
    from embassy.lease_client import HttpLeaseClient, LeaseClientConfig

    token = os.environ.get(token_env, "")
    client = HttpLeaseClient(
        LeaseClientConfig(base_url=base_url, token=token, timeout_seconds=5.0)
    )
    return client, Path(proof_file)


def _maybe_refresh_fencing_proof(
    fencing_config: dict[str, object],
    *,
    fence: FencingEvidence | None,
    policy: EmbassyPolicy,
    now: datetime,
) -> tuple[FencingEvidence | None, dict[str, object] | None]:
    """Refresh stale/draining local proofs from the live lease authority."""
    from embassy.policy import fencing_evidence_is_valid

    if fencing_evidence_is_valid(fence, policy=policy, now=now):
        return fence, None
    client, proof_path = _lease_client_from_fencing(fencing_config)
    if client is None or proof_path is None:
        return fence, None
    try:
        from embassy.promote import refresh_fencing_proof_from_status

        decision = refresh_fencing_proof_from_status(client, proof_path=proof_path)
        refreshed = _fencing_evidence(decision.fencing_proof)
        return refreshed, {
            "status": "fencing_proof_refreshed",
            "phase": decision.phase.value,
            "acquirable": bool((decision.fencing_proof or {}).get("acquirable")),
            "reason": decision.reason,
        }
    except Exception as exc:  # noqa: BLE001 - observer must stay fail-closed
        del exc
        _LOGGER.exception("Lease fencing proof refresh failed")
        return fence, {"status": "fencing_proof_refresh_failed"}


def _maybe_request_lease_takeover(
    fencing_config: dict[str, object],
    *,
    primary_id: str,
    primary_generation: str,
) -> dict[str, object] | None:
    """Request software-lease takeover when configured; never raises into decision path."""
    enabled = fencing_config.get("request_takeover_on_outage", False)
    if enabled is not True:
        return {"status": "takeover_not_configured"}
    base_url = fencing_config.get("lease_authority_url")
    token_env = fencing_config.get("lease_token_env", "FS_LEASE_AUTHORITY_TOKEN")
    requester = fencing_config.get("standby_node_id", "frank")
    proof_file = fencing_config.get("proof_file")
    if not isinstance(base_url, str) or not base_url:
        return {"status": "takeover_misconfigured", "reason": "missing_lease_url"}
    if not isinstance(token_env, str) or not isinstance(requester, str):
        return {"status": "takeover_misconfigured", "reason": "invalid_lease_settings"}
    if not isinstance(proof_file, str) or not proof_file:
        return {"status": "takeover_misconfigured", "reason": "missing_proof_file"}
    try:
        from embassy.lease_client import HttpLeaseClient, LeaseClientConfig
        from embassy.promote import request_takeover_and_persist_proof

        token = os.environ.get(token_env, "")
        client = HttpLeaseClient(
            LeaseClientConfig(base_url=base_url, token=token, timeout_seconds=5.0)
        )
        decision = request_takeover_and_persist_proof(
            client,
            requester_node_id=requester,
            target_node_id=primary_id,
            target_generation=primary_generation,
            proof_path=Path(proof_file),
            wait_for_acquirable=True,
            acquirable_timeout_seconds=60.0,
        )
        return {
            "status": "takeover_requested",
            "reason": decision.reason,
            "phase": decision.phase.value,
            "fencing_proof": decision.fencing_proof,
        }
    except Exception as exc:  # noqa: BLE001 - observer must stay fail-closed
        del exc
        _LOGGER.exception("Lease takeover request failed")
        return {"status": "takeover_failed", "reason": "lease_takeover_exception"}


def _maybe_execute_promotion(
    fencing_config: dict[str, object],
    standby_config: dict[str, object],
    *,
    decision_state: str,
    fence: FencingEvidence | None,
    primary_generation: str,
) -> dict[str, object]:
    """Run ordered promote when authorized and execute_promotion is true."""
    del primary_generation  # reserved for lineage checks / generation policies
    if fencing_config.get("execute_promotion", False) is not True:
        return {
            "status": "promotion_authorized_awaiting_executor",
            "note": "execute_promotion is false; authorization only",
        }
    base_url = fencing_config.get("lease_authority_url")
    token_env = fencing_config.get("lease_token_env", "FS_LEASE_AUTHORITY_TOKEN")
    requester = fencing_config.get("standby_node_id", "frank")
    proof_file = fencing_config.get("proof_file")
    if not isinstance(base_url, str) or not base_url:
        return {"status": "promotion_failed", "reason": "missing_lease_url"}
    if not isinstance(token_env, str) or not isinstance(requester, str):
        return {"status": "promotion_failed", "reason": "invalid_lease_settings"}
    if not isinstance(proof_file, str) or not proof_file:
        return {"status": "promotion_failed", "reason": "missing_proof_file"}

    standby_generation = fencing_config.get("standby_writer_generation")
    if not isinstance(standby_generation, str) or not standby_generation.strip():
        standby_generation = os.environ.get("FS_WRITER_GENERATION", "").strip()
    if not standby_generation:
        return {
            "status": "promotion_failed",
            "reason": "missing_standby_writer_generation",
        }

    previous_epoch = fence.previous_epoch if fence is not None else None
    database_container = standby_config.get("database_container", "filantropia-odoo-db")
    database_name = standby_config.get("database_name", "filantropia_public")
    odoo_container = standby_config.get("odoo_container", "filantropia-odoo")
    origin_container = fencing_config.get("origin_container", "filantropia-cloudflared")
    if origin_container is not None and not isinstance(origin_container, str):
        return {"status": "promotion_failed", "reason": "invalid_origin_container"}
    if not isinstance(database_container, str) or not isinstance(database_name, str):
        return {"status": "promotion_failed", "reason": "invalid_database_settings"}
    if not isinstance(odoo_container, str):
        return {"status": "promotion_failed", "reason": "invalid_odoo_container"}

    try:
        from embassy.lease_client import HttpLeaseClient, LeaseClientConfig
        from embassy.promote import PromoteContext, PromoteError, execute_promotion

        token = os.environ.get(token_env, "")
        client = HttpLeaseClient(
            LeaseClientConfig(base_url=base_url, token=token, timeout_seconds=5.0)
        )
        if previous_epoch is None:
            status = client.status()
            previous_epoch = status.state.previous_epoch
            if previous_epoch is None and status.state.epoch is not None:
                # Takeover-pending lineage stores the fenced owner's epoch as previous.
                previous_epoch = status.state.previous_epoch or status.state.epoch
        if previous_epoch is None:
            return {"status": "promotion_failed", "reason": "missing_previous_epoch"}

        context = PromoteContext(
            standby_node_id=requester,
            new_generation=standby_generation,
            previous_epoch=int(previous_epoch),
            database_container=database_container,
            database_name=database_name,
            odoo_container=odoo_container,
            origin_container=origin_container if origin_container else None,
        )
        result = execute_promotion(
            decision_state=decision_state,
            client=client,
            context=context,
            fencing_proof_path=Path(proof_file),
            start_writer=True,
        )
        return {"status": "promotion_executed", **result}
    except PromoteError as exc:
        _LOGGER.error("Promotion refused or failed: %s", exc)
        return {"status": "promotion_failed", "reason": str(exc)[:200]}
    except Exception as exc:  # noqa: BLE001 - observer must stay fail-closed
        del exc
        _LOGGER.exception("Promotion executor failed")
        return {"status": "promotion_failed", "reason": "promotion_exception"}


def run_once(config_path: Path, *, require_encrypted_mount: bool = True) -> str:
    """Run one observation cycle and persist only sanitized decision data."""
    config = _load_config(config_path)
    primary_config = config["primary"]
    standby_config = config["standby"]
    fencing_config = config["fencing"]
    state_config = config["state"]
    policy_config = config["policy"]
    if not all(
        isinstance(section, dict)
        for section in (
            primary_config,
            standby_config,
            fencing_config,
            state_config,
            policy_config,
        )
    ):
        raise EmbassyServiceError("Embassy configuration sections must be tables")

    state_dir = _configured_path(state_config, "directory")
    state_path = _configured_path(state_config, "state_file")
    journal_path = _configured_path(state_config, "journal_file")
    lock_path = _configured_path(state_config, "lock_file")
    if require_encrypted_mount:
        data_root = Path("/data")
        if not data_root.is_mount():
            raise EmbassyServiceError("Encrypted /data mount is unavailable")
        encrypted_root = (data_root / "filantropia-embassy").resolve(strict=False)
        if not all(
            path.resolve(strict=False).is_relative_to(encrypted_root)
            for path in (state_dir, state_path, journal_path, lock_path)
        ):
            raise EmbassyServiceError("Embassy state must remain under encrypted /data")

    primary_id = primary_config.get("node_id")
    primary_generation = primary_config.get("writer_generation")
    timeout = primary_config.get("timeout_seconds")
    if not isinstance(primary_id, str) or not isinstance(primary_generation, str):
        raise EmbassyServiceError("Expected primary identity is missing")
    timeout_seconds = _positive_number(timeout, name="Readiness timeout")
    try:
        failure_confirmations = policy_config.get("failure_confirmation_cycles", 2)
        if (
            isinstance(failure_confirmations, bool)
            or not isinstance(failure_confirmations, int)
            or failure_confirmations < 1
        ):
            raise ValueError
        maximum_gap = _positive_number(
            policy_config.get("maximum_recovery_gap_seconds", 60),
            name="Maximum recovery gap",
        )
        heartbeat_interval = _positive_number(
            policy_config.get("replication_heartbeat_interval_seconds", 15),
            name="Replication heartbeat interval",
        )
        maximum_filestore_age = _positive_number(
            policy_config.get("maximum_filestore_generation_age_seconds", 60),
            name="Maximum filestore age",
        )
        maximum_status_age = _positive_number(
            policy_config.get("maximum_standby_status_age_seconds", 60),
            name="Maximum standby status age",
        )
        maximum_attachment_age = _positive_number(
            policy_config.get("maximum_attachment_verification_age_seconds", 60),
            name="Maximum attachment verification age",
        )
    except (TypeError, ValueError) as exc:
        raise EmbassyServiceError("Embassy policy limits are invalid") from exc
    trusted_sources = fencing_config.get("trusted_sources", [])
    if not isinstance(trusted_sources, list) or not all(
        isinstance(value, str) for value in trusted_sources
    ):
        raise EmbassyServiceError("Trusted fencing sources must be an array")
    actions_enabled = policy_config.get("automatic_actions_enabled", False)
    if not isinstance(actions_enabled, bool):
        raise EmbassyServiceError("automatic_actions_enabled must be boolean")
    require_lease_acquirable = policy_config.get("require_lease_acquirable", True)
    if not isinstance(require_lease_acquirable, bool):
        raise EmbassyServiceError("require_lease_acquirable must be boolean")
    policy = EmbassyPolicy(
        primary_node_id=primary_id,
        primary_generation=primary_generation,
        failure_confirmation_cycles=failure_confirmations,
        maximum_recovery_gap_seconds=maximum_gap,
        replication_heartbeat_interval_seconds=heartbeat_interval,
        maximum_filestore_generation_age_seconds=maximum_filestore_age,
        maximum_standby_status_age_seconds=maximum_status_age,
        maximum_attachment_verification_age_seconds=maximum_attachment_age,
        actions_enabled=actions_enabled,
        trusted_fencing_sources=frozenset(trusted_sources),
        require_lease_acquirable=require_lease_acquirable,
    )

    with operation_lock(lock_path):
        store = StateStore(state_path)
        previous = store.read()
        refresh_status = standby_config.get("refresh_status", True)
        if not isinstance(refresh_status, bool):
            raise EmbassyServiceError("Standby refresh setting must be boolean")
        if refresh_status:
            collect_standby_status(
                standby_config,
                require_encrypted_mount=require_encrypted_mount,
            )
        now = datetime.now(UTC)
        primary = _primary_observation(primary_config)
        primary = _with_public_routes(
            primary,
            primary_config.get("public_routes", []),
            timeout_seconds=timeout_seconds,
        )
        standby = _standby_observation(
            _read_status(_configured_path(standby_config, "status_file")),
            now=now,
        )
        fence = _fencing_evidence(
            _read_status(_configured_path(fencing_config, "proof_file"))
        )
        # Stale draining/expired proofs must not permanently block promotion.
        fence, refresh_result = _maybe_refresh_fencing_proof(
            fencing_config,
            fence=fence,
            policy=policy,
            now=now,
        )
        decision = evaluate(
            policy=policy,
            primary=primary,
            standby=standby,
            now=now,
            previous_failure_cycles=int(previous["consecutive_primary_failures"]),
            fencing_evidence=fence,
        )
        action_result = refresh_result
        if decision.proposed_action == "request_lease_takeover":
            action_result = _maybe_request_lease_takeover(
                fencing_config,
                primary_id=primary_id,
                primary_generation=primary_generation,
            )
            if action_result is not None and action_result.get("fencing_proof"):
                fence = _fencing_evidence(action_result["fencing_proof"])
                decision = evaluate(
                    policy=policy,
                    primary=primary,
                    standby=standby,
                    now=now,
                    previous_failure_cycles=decision.consecutive_primary_failures,
                    fencing_evidence=fence,
                )
        elif (
            decision.state.value == "blocked_unfenced"
            and fence is not None
            and not (fence.acquirable if fence is not None else False)
        ):
            # Local proof still draining: refresh again so the next cycle can promote
            # once the authority marks the lease acquirable.
            fence, refresh_result = _maybe_refresh_fencing_proof(
                fencing_config,
                fence=None,
                policy=policy,
                now=datetime.now(UTC),
            )
            if refresh_result is not None:
                action_result = refresh_result
            if fence is not None:
                decision = evaluate(
                    policy=policy,
                    primary=primary,
                    standby=standby,
                    now=datetime.now(UTC),
                    previous_failure_cycles=decision.consecutive_primary_failures,
                    fencing_evidence=fence,
                )
        if decision.state.value == "promotion_authorized" and policy.actions_enabled:
            action_result = _maybe_execute_promotion(
                fencing_config,
                standby_config,
                decision_state=decision.state.value,
                fence=fence,
                primary_generation=primary_generation,
            )
        event = {
            "observed_at_utc": now.isoformat(),
            "state": decision.state.value,
            "consecutive_primary_failures": (decision.consecutive_primary_failures),
            "primary_reachable": primary.reachable,
            "primary_node_id": primary.node_id,
            "primary_generation": primary.generation,
            "public_routes_ready": primary.public_routes_ready,
            "standby_database_reachable": standby.database_reachable,
            "standby_replication_lag_bytes": standby.replication_lag_bytes,
            "standby_status_age_seconds": standby.status_age_seconds,
            "attachment_verification_age_seconds": (
                standby.attachment_verification_age_seconds
            ),
            "reasons": list(decision.reasons),
            "proposed_action": decision.proposed_action,
            "action_result_status": (
                None if action_result is None else action_result.get("status")
            ),
        }
        store.write(
            {
                "consecutive_primary_failures": (decision.consecutive_primary_failures),
                "last_observed_at_utc": now.isoformat(),
                "last_decision": decision.state.value,
                "last_writer_node_id": primary.node_id or primary_id,
                "last_writer_generation": (primary.generation or primary_generation),
            }
        )
        EventJournal(journal_path).append(event)

    return decision.state.value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("/etc/filantropia-embassy/embassy.toml"),
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        state = run_once(arguments.config)
    except (
        EmbassyServiceError,
        JournalError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        _LOGGER.error("Embassy observation failed closed: %s", exc)
        return 1
    _LOGGER.info("Embassy state: %s", state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
