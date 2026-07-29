#!/usr/bin/env bash
set -euo pipefail

# Creates tracking issues and a milestone for FilantropiaSolar
# Prereqs:
# - export GITHUB_TOKEN={{YOUR_TOKEN}}  (with repo scope)
# - network access to api.github.com
# The script is idempotent-ish for labels/milestone; re-running may create duplicates if names change.

REPO="WeRaDev/FilantropiaSolar"
API="https://api.github.com"
AUTH_HEADER="Authorization: Bearer ${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
CT_JSON="Content-Type: application/json"
UA="User-Agent: filantropia-warp-agent"

api() {
  local method="$1" path="$2" data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS -X "$method" -H "$AUTH_HEADER" -H "$CT_JSON" -H "$UA" "$API$path" -d "$data"
  else
    curl -sS -X "$method" -H "$AUTH_HEADER" -H "$UA" "$API$path"
  fi
}

ensure_label() {
  local name="$1" color="$2" desc="$3"
  api GET "/repos/$REPO/labels/$name" >/dev/null 2>&1 || \
  api POST "/repos/$REPO/labels" "$(jq -n --arg name "$name" --arg color "$color" --arg desc "$desc" '{name:$name,color:$color,description:$desc}')" >/dev/null
}

# Ensure labels
ensure_label "dependency" "0366d6" "Dependency management"
ensure_label "techdebt" "6e7781" "Technical debt"
ensure_label "P0" "d73a4a" "Priority 0"
ensure_label "P1" "fbca04" "Priority 1"
ensure_label "P2" "0e8a16" "Priority 2"
ensure_label "CI/CD" "1d76db" "CI pipelines"
ensure_label "quality" "b60205" "Quality gates"
ensure_label "testing" "7057ff" "Tests & coverage"
ensure_label "maintenance" "c2e0c6" "Maintenance"
ensure_label "security" "a2eeef" "Security & compliance"
ensure_label "release" "5319e7" "Release process"
ensure_label "documentation" "0075ca" "Docs"
ensure_label "ML" "5319e7" "Machine learning"
ensure_label "observability" "0e8a16" "Logs & telemetry"

# Create milestone (or get ID if exists)
M_TITLE="ML enhancement milestone"
M_DESC="Milestone to track ML and CI quality improvements, SBOM, coverage, and docs sync."
M_ID=$(api GET "/repos/$REPO/milestones?state=all" | jq -r --arg t "$M_TITLE" '.[]|select(.title==$t)|.number' | head -n1)
if [[ -z "$M_ID" ]]; then
  M_ID=$(api POST "/repos/$REPO/milestones" "$(jq -n --arg t "$M_TITLE" --arg d "$M_DESC" '{title:$t,description:$d}')" | jq -r '.number')
fi
echo "Using milestone #$M_ID ($M_TITLE)"

create_issue() {
  local title="$1" body="$2" labels_csv="$3"
  local data
  # Convert comma-separated labels to array JSON
  local labels_json
  IFS=',' read -r -a arr <<< "$labels_csv"
  labels_json=$(printf '%s
' "${arr[@]}" | jq -R . | jq -s .)
  data=$(jq -n --arg t "$title" --arg b "$body" --argjson labels "$labels_json" --argjson milestone "$M_ID" '{title:$t, body:$b, labels:$labels, milestone:$milestone}')
  api POST "/repos/$REPO/issues" "$data"
}

I1=$(create_issue \
  "Migrate All Dependencies to pyproject.toml" \
  "Audit and migrate all development, test, and production dependencies from requirements files to pyproject.toml. Remove legacy requirements files if no longer needed.\n\nAcceptance Criteria:\n- All dependencies are managed via pyproject.toml.\n- CI and docs are updated to reference only pyproject.toml.\n\nAssignee: warp agent\nLabels: dependency, techdebt, P1" \
  "dependency,techdebt,P1" | jq -r '.number')

echo "Created issue #$I1"

I2=$(create_issue \
  "Enforce Quality Gates in CI/CD" \
  "Remove continue-on-error for critical quality jobs (lint, format, type check, unit/integration/ML/security tests) so workflows fail if gates are not met.\n\nAcceptance Criteria:\n- CI fails when a critical quality gate fails.\n- Non-critical/legacy exceptions are documented.\n\nAssignee: warp agent\nLabels: CI/CD, quality, P0" \
  "CI/CD,quality,P0" | jq -r '.number')

echo "Created issue #$I2"

I3=$(create_issue \
  "Set and Enforce Test Coverage Threshold" \
  "Define a project-wide code coverage threshold (e.g., 80%) in CI. Fail PRs that do not meet threshold.\n\nAcceptance Criteria:\n- Coverage report step occurs on all test matrix jobs.\n- Workflow fails when coverage drops below threshold.\n\nAssignee: warp agent\nLabels: CI/CD, testing, P0" \
  "CI/CD,testing,P0" | jq -r '.number')

echo "Created issue #$I3"

I4=$(create_issue \
  "Clean Up Legacy Workflows" \
  "Archive or remove .github/workflows/ci-complex.yml.disabled and any other unused workflow files.\n\nAcceptance Criteria:\n- Only active, maintained workflows remain.\n- Repository housekeeping documented.\n\nAssignee: warp agent\nLabels: maintenance, techdebt, P2" \
  "maintenance,techdebt,P2" | jq -r '.number')

echo "Created issue #$I4"

I5=$(create_issue \
  "Add SBOM Generation to Build/Release" \
  "Integrate automated SBOM (Software Bill of Materials) generation into main build/release workflow jobs, ensuring compliance with supply chain best practices.\n\nAcceptance Criteria:\n- SBOM artifact generated for every release.\n- Included in release assets.\n\nBlocked by: #$I2\nAssignee: warp agent\nLabels: security, release, P1" \
  "security,release,P1" | jq -r '.number')

echo "Created issue #$I5"

I6=$(create_issue \
  "Document ML Module Acceptance Criteria" \
  "Clearly define what constitutes ‘realistic results’ for the ML module and add acceptance tests/benchmarks in the CI workflow.\n\nAcceptance Criteria:\n- ML test/benchmarking step included and documented.\n- Pass/fail criteria for ML output published to docs/tests.\n\nBlocked by: #$I2, #$I3\nAssignee: warp agent\nLabels: ML, quality, documentation, P0" \
  "ML,quality,documentation,P0" | jq -r '.number')

echo "Created issue #$I6"

I7=$(create_issue \
  "Enhance Logging and Observability in CI" \
  "Ensure all workflow steps, especially failures, output actionable error messages and links to artifact logs; document process for log triage.\n\nAcceptance Criteria:\n- Build/test errors have clear, actionable logs.\n- Documentation section for CI log triage.\n\nAssignee: warp agent\nLabels: CI/CD, observability, P2" \
  "CI/CD,observability,P2" | jq -r '.number')

echo "Created issue #$I7"

I8=$(create_issue \
  "Continuous Docs Sync" \
  "Ensure every major workflow or architecture change triggers mkdocs build/deploy and pushes updated documentation to gh-pages.\n\nAcceptance Criteria:\n- Documentation auto-updates with code changes.\n- gh-pages always reflects main branch state.\n\nAssignee: warp agent\nLabels: CI/CD, documentation, P1" \
  "CI/CD,documentation,P1" | jq -r '.number')

echo "Created issue #$I8"

# Summary
printf "\nCreated issues: #%s, #%s, #%s, #%s, #%s, #%s, #%s, #%s\n" "$I1" "$I2" "$I3" "$I4" "$I5" "$I6" "$I7" "$I8"
