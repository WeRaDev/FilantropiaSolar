# ADR 0002 — Odoo async via OCA queue_job

## Status
Accepted (with interim escape hatch)

## Context
CRM stage changes must not block on NC/ML HTTP. D7 requires visible retries.

## Decision
Use **OCA `queue_job`** for Odoo→NC lifecycle calls when Odoo 19 Community packaging allows.

## Escape hatch
If packaging blocks: `ir.cron` + `nc_sync_state` on lead, documented in a follow-up ADR, migrate to queue_job later.

## Consequences
- Compose/addons_path must include queue_job.  
- Need job runner process/channel in deploy.
## Implementation note (2026-08-12)
Vendored OCA `queue_job` 19.0.2.0.3; jobrunner via `workers=2` + `server_wide_modules=web,queue_job`. Filantropia channel `root.filantropia`.
