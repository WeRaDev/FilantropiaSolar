#!/usr/bin/env python3
"""Offline structural checks; admission is a separate, fail-closed decision.

This tool reads only declared, repository-confined files. It never imports or
executes project code, contacts a service, issues a grant, or proves sandboxing.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker

UPSTREAM_COMMIT = "d842a1bb34a42e9d7c0d54a1b12ead9e0e59e283"
CATALOGUE_SHA256 = "06cd3966513c595b7cb455caebc01d9b0c5907f168b7e97ab3b98e1f5c56ae8f"
BUNDLE_FILES = (
    "validate.py", "requirements.txt", "policy.yaml", "control-map.yaml",
    "schemas/records.schema.json", "upstream/controls.yaml",
    "upstream/LICENSE", "upstream/LICENSE-schemas", "upstream.lock.json",
)
BASELINE = ("README.md", "AGENTS.md", "SOUL.md", "CONTRIBUTING.md",
            "docs/adr", "tasks", "skills")
STATES = {"unassessed", "gap", "designed", "implemented-unverified",
          "verified", "exception-approved"}


class Invalid(ValueError):
    pass


class UniqueSafeLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently accepting the last policy."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise Invalid("mapping keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def confined(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise Invalid("absolute paths and parent traversal are forbidden")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise Invalid("path escapes repository")
    return resolved


def read(path: Path):
    try:
        if path.stat().st_size > 2_000_000:
            raise Invalid("record exceeds size limit")
        return yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueSafeLoader)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise Invalid(f"invalid or missing record: {path.name}") from exc


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc)
    except (AttributeError, ValueError) as exc:
        raise Invalid("invalid timezone-aware timestamp") from exc


def schema_check(document, schema: dict, kind: str) -> None:
    wrapper = {"$ref": f"#/$defs/{kind}", "$defs": schema["$defs"]}
    if list(Draft202012Validator(wrapper, format_checker=FormatChecker()).iter_errors(document)):
        raise Invalid(f"schema violation: {kind}")


def check_local_schema(node) -> None:
    """Never resolve network or filesystem references from a policy schema."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"$ref", "$dynamicRef"} and (
                not isinstance(value, str) or not value.startswith("#/")
            ):
                raise Invalid("schema references must be local")
            check_local_schema(value)
    elif isinstance(node, list):
        for value in node:
            check_local_schema(value)


def ids_unique(items: list[dict], key="id") -> set[str]:
    ids = [item[key] for item in items]
    if len(ids) != len(set(ids)):
        raise Invalid(f"duplicate {key}")
    return set(ids)


def validate(root: Path, bundle: Path, *, admission=False, now=None) -> dict:
    root, bundle = root.resolve(), bundle.resolve()
    now = now or datetime.now(timezone.utc)
    overlay = confined(root, "security/agents")
    schema = read(confined(bundle, "schemas/records.schema.json"))
    check_local_schema(schema)
    Draft202012Validator.check_schema(schema)
    lock = read(confined(overlay, "policy.lock.json"))
    schema_check(lock, schema, "policy_lock")
    if lock["upstream_commit"] != UPSTREAM_COMMIT:
        raise Invalid("unsupported upstream commit")
    if set(lock["files"]) != set(BUNDLE_FILES):
        raise Invalid("incomplete or unexpected policy bundle")
    for relative, expected in lock["files"].items():
        if digest(confined(bundle, relative)) != expected:
            raise Invalid(f"policy bundle drift: {relative}")
    if digest(bundle / "upstream/controls.yaml") != CATALOGUE_SHA256:
        raise Invalid("catalogue differs from reviewed upstream bytes")
    upstream = read(bundle / "upstream.lock.json")
    if upstream["commit"] != UPSTREAM_COMMIT:
        raise Invalid("upstream provenance mismatch")
    catalogue = read(bundle / "upstream/controls.yaml")
    controls = ids_unique(catalogue["controls"])
    if len(controls) != 35 or catalogue["version"] != "1.0-draft":
        raise Invalid("unexpected catalogue")
    policy = read(bundle / "policy.yaml")
    if (policy.get("status") != "implementation-pilot"
            or policy.get("certification") is not False
            or set(policy.get("profiles", {})) != {
                "dev-sandbox", "runtime-observer", "business-action", "critical-action"
            }):
        raise Invalid("unsupported pilot policy")
    for profile in policy["profiles"].values():
        if (profile.get("live_actions") is not False
                or profile.get("production_credentials") is not False):
            raise Invalid("pilot policy cannot enable live authority")
    if policy["version"] != lock["bundle_version"]:
        raise Invalid("policy version mismatch")
    if policy["upstream_commit"] != UPSTREAM_COMMIT:
        raise Invalid("policy upstream mismatch")
    mapping = read(bundle / "control-map.yaml")
    if mapping["upstream_commit"] != UPSTREAM_COMMIT:
        raise Invalid("mapping upstream mismatch")
    if ids_unique(mapping["controls"]) != controls:
        raise Invalid("control map must cover the exact catalogue")
    for item in mapping["controls"]:
        if not all(item.get(k) for k in ("owner_role", "enforcement", "test_method", "evidence")):
            raise Invalid("control mapping lacks proof requirements")
    manifest = read(confined(overlay, "manifest.yaml"))
    assessment = read(confined(overlay, "assessment.yaml"))
    components = read(confined(overlay, "components.lock.json"))
    exceptions = read(confined(overlay, "exceptions.yaml"))
    for kind, doc in (("manifest", manifest), ("assessment", assessment),
                      ("components", components), ("exceptions", exceptions)):
        schema_check(doc, schema, kind)
    if assessment["project_id"] != manifest["project_id"]:
        raise Invalid("assessment project mismatch")
    if assessment["upstream_commit"] != UPSTREAM_COMMIT:
        raise Invalid("assessment upstream mismatch")
    if ids_unique(assessment["controls"]) != controls:
        raise Invalid("assessment must cover every control exactly once")
    if manifest["profile"] not in policy["profiles"]:
        raise Invalid("unknown profile")
    for required in BASELINE:
        path = confined(root, required)
        if not (path.is_file() if required.endswith(".md") else path.is_dir()):
            raise Invalid(f"missing baseline: {required}")
    if not any(confined(root, p).is_file() for p in ("WARP.md", "warp.md")):
        raise Invalid("missing WARP.md/warp.md")
    ids_unique(components["components"])
    declared_paths = set()
    for item in components["components"]:
        path = confined(root, item["path"])
        if item["path"] in declared_paths:
            raise Invalid("duplicate component path")
        declared_paths.add(item["path"])
        if digest(path) != item["sha256"]:
            raise Invalid(f"component drift: {item['path']}")
    # Discover additions in known loading locations without scanning data/secrets.
    observed = set(component_paths(root))
    if observed != declared_paths:
        raise Invalid("instruction/skill/runtime component inventory drift")
    ids_unique(exceptions["exceptions"])
    exception_by_id = {e["id"]: e for e in exceptions["exceptions"]}
    for entry in exceptions["exceptions"]:
        if set(entry["controls"]) - controls:
            raise Invalid("exception refers to unknown controls")
        if timestamp(entry["expires_at"]) <= now:
            raise Invalid("expired exception")
        if entry["requester"] == entry["approver"]:
            raise Invalid("self-approved exception")
    blockers = []
    owners = manifest["owners"]
    if (owners["review_status"] != "approved"
            or not (owners["business"] or "").strip()
            or not (owners["technical"] or "").strip()):
        blockers.append("named owners not approved")
    if manifest["runtime"]["status"] == "unassessed":
        blockers.append("runtime inventory unassessed")
    if manifest["runtime"]["status"] == "none" and not manifest["runtime"]["rationale"]:
        raise Invalid("runtime absence needs a rationale")
    if manifest["runtime"]["status"] == "present" and not manifest["runtime"]["agents"]:
        raise Invalid("present runtime inventory is empty")
    if manifest["runtime"]["status"] == "none" and manifest["runtime"]["agents"]:
        raise Invalid("runtime absence conflicts with agent records")
    ids_unique(manifest["runtime"]["agents"])
    for agent in manifest["runtime"]["agents"]:
        if agent["profile"] not in policy["profiles"]:
            raise Invalid("runtime agent has unknown profile")
        if agent["status"] != "approved":
            blockers.append(f"{agent['id']}: runtime agent not approved")
    if manifest["profile"] != "dev-sandbox":
        blockers.append("runtime execution profiles are disabled in the pilot policy")
    if any(c["review_status"] != "approved" for c in components["components"]):
        blockers.append("component approval pending")
    for control in assessment["controls"]:
        if control["verified_at"] is not None:
            timestamp(control["verified_at"])
        if control["state"] not in STATES:
            raise Invalid("unknown assessment state")
        if control["applicability"] == "not-applicable":
            if control["id"] in policy["requirements"]["non_waivable_controls"]:
                raise Invalid("mandatory security floor cannot be marked not-applicable")
            if not control["reviewer"] or not control["reason"]:
                raise Invalid("not-applicable requires independent review and rationale")
            if control["state"] in {"verified", "exception-approved"}:
                raise Invalid("not-applicable is not verification or an exception")
            continue
        if control["state"] == "exception-approved":
            entry = exception_by_id.get(control.get("exception_id"))
            if not entry or control["id"] not in entry["controls"]:
                raise Invalid("missing matching exception")
            blockers.append(f"{control['id']}: exception is not verification")
        elif control["state"] != "verified":
            blockers.append(f"{control['id']}: {control['state']}")
        else:
            if not control["reviewer"] or not control["evidence"] or not control["enforcement"]:
                raise Invalid("verified control lacks reviewer, evidence or enforcement")
            checked = timestamp(control["verified_at"])
            if checked > now or now - checked > timedelta(days=policy["requirements"]["evidence_max_age_days"]):
                raise Invalid("verified evidence is stale or future-dated")
            for evidence in control["evidence"]:
                if not evidence["uri"].startswith(("https://", "evidence:")):
                    raise Invalid("evidence must use a protected reference")
    if manifest["admission"] != "approved":
        blockers.append("deployment admission pending")
    result = {
        "project_id": manifest["project_id"],
        "structure": "valid",
        "admission": "denied" if blockers else "eligible-for-independent-review",
        "counts": dict(Counter(c["state"] for c in assessment["controls"])),
        "verified_applicable_controls": sum(
            c["state"] == "verified" and c["applicability"] == "applicable"
            for c in assessment["controls"]
        ),
        "applicability_counts": dict(Counter(c["applicability"] for c in assessment["controls"])),
        "blockers": blockers,
        "runtime_enforcement_verified_by_this_tool": False,
    }
    if admission and blockers:
        raise Invalid("admission denied: " + "; ".join(blockers[:5]))
    return result


def component_paths(root: Path) -> list[str]:
    """Known composition candidates; runtime/provider discovery remains separate."""
    paths = set()
    for name in ("AGENTS.md", "WARP.md", "warp.md", "SOUL.md", "CLAUDE.md"):
        if confined(root, name).is_file():
            paths.add(name)
    for directory, patterns in (
        ("skills", ("*.md", "*.yaml", "*.json")),
        ("config/skills", ("*.yaml", "*.yml", "*.json")),
        ("openfang", ("*.toml",)),
        ("spirit", ("RULES.md", "HEARTBEAT.md")),
    ):
        parent = confined(root, directory)
        if parent.is_dir():
            for pattern in patterns:
                for path in parent.rglob(pattern):
                    if path.is_file():
                        relative = (Path(directory) / path.relative_to(parent)).as_posix()
                        confined(root, relative)
                        paths.add(relative)
    return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--admission", action="store_true")
    parser.add_argument("--fleet", action="store_true")
    parser.add_argument("--native-only", action="store_true")
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    try:
        results = [validate(args.root, bundle, admission=args.admission)]
        if args.fleet or args.native_only:
            registry = read(args.root / "ProductionBase/repos.yaml")
            for project in registry["repos"]:
                if args.native_only and project["vcs_mode"] != "native":
                    continue
                child = confined(args.root, project["path"])
                result = validate(child, child / "security/agents/bundle", admission=args.admission)
                if result["project_id"] != project["id"]:
                    raise Invalid("registry/project identity mismatch")
                if project.get("agent_security_manifest") != "security/agents/manifest.yaml":
                    raise Invalid("missing registry security manifest reference")
                if project.get("agent_security_policy") != read(bundle / "policy.yaml")["version"]:
                    raise Invalid("registry security policy mismatch")
                results.append(result)
        print(json.dumps({"results": results}, indent=2))
        return 0
    except (Invalid, OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
        print(f"agent-baseline: FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
