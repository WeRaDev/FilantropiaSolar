# TRS Addendum — Locked decisions D1–D10

**Status:** Accepted (design-thinking session)  
**Applies to:** FilantropiaSolar Technical Requirements Specification (external draft)  
**Supersedes:** Conflicting TRS clauses listed under each decision  
**Audience:** Engineering implementing admin/ML/CRM work after public website freeze

## Purpose

The original TRS assumed ML-as-sole station store, Odoo-native full admin (map/reports), a single global ML model, and CRM `Won → Active`. The running system is different. This addendum is the **authoritative product/architecture rule set** for the next development phases. Implement against this document, not the conflicting TRS sections.

## Locked decisions

### D1 — Station source of truth

**Decision:** Nextcloud remains the station store. Integration path: **Odoo → Nextcloud API → ML service**.

**Supersedes:** TRS “ML service is the single source of truth for station records” and “Odoo calls ML only.”

**Do not:** Migrate station master data into ML-only persistence in this program.

### D2 — Component roles

| Component | Role |
|-----------|------|
| **Nextcloud app** | Ops admin: stations, map, analysis, upload, reports, retrain |
| **Odoo website** | Public only: content, Existing+Planned map, candidatura, contact (feature-frozen) |
| **Odoo backend** | CRM + settings + thin lifecycle glue (not a second station admin UI) |
| **ML service** | Train/predict, weather, historical vs predicted series (per installation) |

**Supersedes:** TRS “Odoo custom addon (backend)” as full station admin with native map/PDF/XLSX for ops.

### D3 — Live feed / Active (this cycle)

**Decision:** **Offline-first.** No live telemetry ingest API in this cycle.

- Ops labels: Virtual | Planned | Running, with Running split **Offline** (predicted) vs **Active** (has sufficient file/historical measured data).
- Public taxonomy: **Existing** (Running Active∪Offline) + **Planned** only. Virtual never public.

**Supersedes:** TRS requirements that imply live field feed for Active without specifying ingest.

### D4 — CRM lifecycle

| Event | Station effect |
|-------|----------------|
| Candidatura submit | CRM lead + **Virtual** station (not public) |
| CRM **New → Qualified** | **Virtual → Planned** (public as planned) |
| CRM **Qualified → Won** | Station **stays Planned** |
| Admin **mark installed** | Planned → Running (Existing on public) |

Manual promote/remove remain on **NC admin**. CRM automation is only required for Virtual→Planned.

**Supersedes:** TRS `Qualified → Won` promotes to Running/Active automatically.

### D5 — ML models

**Decision:** Keep **per-installation** models (current production). Retrain per affected installation ID(s), not one global wipe.

**Supersedes:** TRS “retraining is always global / single model.”

### D6 — Immutability and effective-dated edits

- **Immutable:** measured/historical production from datasets (and future live samples).
- **Recalculate from effective date:** predicted production series and **piecewise savings** when capacity or supplier energy price changes.
- Background job; do not block UI.

**Supersedes:** TRS language that recalculates “historical production” after capacity change.

### D7 — Async

**Decision:** Odoo-side CRM→NC promotions and heavy Odoo-initiated calls use **OCA `queue_job`** (or documented equivalent if packaging blocks OCA). Idempotent APIs + retry/dead-letter.

NC continues to own long ML train/estimate HTTP calls; surface job status where Odoo waits on NC.

### D8 — Efficiency metric (NC admin)

**Hourly capacity factor:** `kWh / (kWp × 1 h)`, ~0 at night, display 0–100%.  
**Drop** TRS “~85% ideal” claim.

### D9 — Scope freeze

**Public website feature-frozen.** New development = NC admin + ML + Odoo CRM glue. Public changes limited to regressions, security, deploy.

### D10 — Cadence

No fixed calendar deadline. Ship by **quality gates** (lint, types, tests, deploy smoke, acceptance checklists).

## Explicitly out of scope (unchanged)

- Nextcloud end-customer scheduling app  
- ML as sole station database migration  
- Single global ML model rewrite  
- Live telemetry pipeline (until a later spike after V1)  
- Public website redesign / P3 unless regression  

## Related docs

- `docs/mvp/NC-ADMIN-GAP-INVENTORY.md`  
- `docs/mvp/ODOO-CRM-QUEUE-JOB-INVENTORY.md`  
- `docs/architecture/nc-odoo-lifecycle-api.openapi.yaml`  
- `docs/mvp/EPIC-MVP.md`  
- `docs/adr/0001`–`0005`  
- `docs/architecture/METRICS-NC-SERIES-SOT.md` (fleet vs Mendeley; truthful series)  
- `docs/ops/REAL-FLEET-INVENTORY.md`  
- `docs/adr/0006-nc-series-sot-and-fleet-vs-mendeley.md`  

## Change control

Amendments require an ADR and an update to this addendum. Do not silently reintroduce superseded TRS clauses in tickets.