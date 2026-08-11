# NC admin gap inventory vs MVP (D1–D4, D6–D9)

**Date:** 2026-08-11  
**Codebase:** `nextcloud-app/` (app v3.1.1)  
**Decisions:** TRS addendum D1–D10  

## Current state (what exists)

### Data model (`lib/Db/Installation.php`)

| Field | Present | Notes |
|-------|---------|--------|
| `isVirtual` | Yes | Boolean only |
| `source` | Yes | `dataset` \| `user` (and similar) |
| Lifecycle label Planned/Running/Offline/Active | **No** | Not modeled |
| Soft-remove / hidden from dashboard | **No** | |
| Soft-remove / hidden from public map | **No** | |
| Effective-dated capacity/price | **No** | Single `capacityKwp`, `gridPriceKwh` |
| Odoo lead id / external refs | **No** | |

### Public API (`PublicApiController`, bearer `public_api_token`)

| Endpoint | Behavior | MVP gap |
|----------|----------|---------|
| `GET /api/public/v1/stations` | `findAllBySource('dataset')` only | Must also expose **Planned** (+ Existing Running); never Virtual |
| `GET /api/public/v1/dashboard` | Aggregates dataset only | Should include Planned/Existing rules for metrics |
| `POST /api/public/v1/estimate` | Proxies ML `/estimate` | OK for funnel; no station create |

Public API correctly **excludes user virtuals** today by only listing `dataset`. After CRM creates Virtual/Planned rows, filters must be **label-based**, not only `source=dataset`.

### Admin API (`AdminApiController`)

- Dataset station CRUD, reimport, ML cache/train/settings.  
- Creates stations as `source=dataset`, `isVirtual=false`.  
- **No** promote/install/soft-delete/hard-delete-with-retention endpoints.  
- **No** lifecycle state machine.

### User installation API (`InstallationApiController`)

- Per-user CRUD; **hard delete** only.  
- `restoreDashboard` is a no-op; comment admits soft-delete is future.  
- Export proxies ML; not ops soft-remove.

### ML / jobs

- Train all / train one via admin API.  
- `WeatherSyncJob` background job exists.  
- No documented debounce on retrain-after-upload (V1).  
- Per-installation models — aligns with **D5**.

## Gaps mapped to MVP build

| MVP need | Gap | Suggested work |
|----------|-----|----------------|
| Labels Virtual \| Planned \| Running(Offline/Active-by-data) | No lifecycle column(s) | Migration: e.g. `lifecycle_state`, optional `visibility`, `installed_at`; derive Active vs Offline from presence of measured readings |
| Soft-remove vs hard-delete | Hard delete only; restore no-op | Soft-remove flags; hard-delete removes station-linked generated data only (V1 data classes) |
| Public API hide Virtual | Dataset-only list | Filter `lifecycle_state in (planned, running)` (names TBD); include Planned stations created from CRM |
| Admin list/form + map filtered | Admin UI exists for dataset | Extend admin UI for lifecycle actions: promote, mark installed, soft-remove |
| CRM creates Virtual | **No NC station on candidatura** | Idempotent `POST .../lifecycle/virtual` from Odoo after lead create |
| Qualify → Planned | No promote API | `POST .../lifecycle/{id}/promote-planned` |
| Admin mark installed | No install API | `POST .../lifecycle/{id}/mark-installed` |
| Link Odoo lead ↔ NC station | No fields | Store `odoo_lead_id` / return `installation_id` on create |

## Non-gaps (already aligned)

- NC is admin surface (D2).  
- ML called from NC, not from browser (D1/D2).  
- Public estimate proxy for Odoo funnel.  
- Bearer token public API pattern.  
- Per-installation train endpoints (D5).

## V1 gaps (tracked, not MVP-blocking)

- Upload schema validation before ML.  
- Effective-dated capacity/price + piecewise savings.  
- Capacity factor metric in analysis UI.  
- Nightly Lisbon forecast job for offline running stations.  
- PDF/XLSX reports from NC.  
- Retrain debounce.

## Risk notes

1. **Candidatura today creates CRM lead only** — no Virtual station in NC. Public map never shows applicant sites; CRM Qualify cannot promote what does not exist. **Highest MVP priority.**  
2. Expanding public `stations` beyond `dataset` without lifecycle filters could leak Virtual/user rows — implement filters before widening query.  
3. `source=dataset` vs CRM-origin stations needs a clear rule (e.g. `source=crm` + lifecycle Planned).

## Update (MVP-1)
Lifecycle columns and helpers landed on `feat/mvp-1-nc-lifecycle-model` (app 3.2.0). Remaining gaps: lifecycle HTTP API (MVP-2), public filter switch (MVP-3), admin UI (MVP-4).
