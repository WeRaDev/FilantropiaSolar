# ADR 0006 — NC series SoT; fleet vs Mendeley

## Status

Accepted (2026-08-12)

## Context

MVP-4 UI exposed portfolio energy/savings via capacity×1500. NC list mixed Mendeley `dataset` plants with real ops needs. Product clarified: Mendeley is **training corpus only**; real fleet is a fixed 11-site inventory.

## Decision

1. NC stores the canonical **hourly series** per ops station (`fs_readings` + provenance).
2. Stats/KPIs read **only** NC series for **fleet/user/crm** stations.
3. `source=dataset` (Mendeley) is excluded from default ops list and portfolio aggregates; ML training continues to use Mendeley via ML service.
4. ML fills gaps into NC; measured samples are immutable.

## Consequences

- Must seed fleet and stop treating dataset import as “the stations.”
- Must fix readings table name bugs before trusting sums.
- Public map should eventually track fleet lifecycle, not Mendeley.

## Alternatives rejected

- ML DB as series SoT.
- Keeping Mendeley rows as default dashboard stations.
- Fake yield factor as primary metric.
