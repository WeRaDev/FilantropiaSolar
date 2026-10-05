# ADR 0007 — Availability-first Odoo failover through Embassy

## Status
Accepted for repository implementation; production activation remains deferred until the cooperative software lease and self-fence paths are rehearsed and explicitly approved. Power control of TRL5 is not available and is not required by this decision.

## Date
2026-10-01 (revised 2026-10-05)

## Context
TRL5 remains the normal Odoo/CRM writer and must continue accepting writes when Frank or Embassy is unavailable. Frank needs a near-current PostgreSQL standby and a matching Odoo filestore, but an unreachable probe cannot distinguish a stopped TRL5 host from a network partition. TRL5 cannot be power-fenced, so Embassy uses a software-only single-writer protocol that still fails closed when ownership is unclear.

## Decision
Use asynchronous PostgreSQL physical streaming replication and a one-way, no-delete filestore mirror. Embassy on Frank observes an origin-specific, uncached TRL5 readiness endpoint and public routes, and records decisions in an atomic, permission-restricted journal on encrypted `/data`.

Probe matrix: origin reachable + public down is ingress degradation; origin down + public up is split-path uncertainty and blocks promotion; both down across confirmation cycles is an outage candidate. Dual failure triggers takeover; it does not prove TRL5 stopped writing.

Independent fencing is a cooperative software lease: a Cloudflare Durable Object stores owner/epoch/expiry/takeover state; a Worker proxies public traffic only to the current epoch's origin; each host runs a lease guard that self-fences Odoo, queue/cron writers, and the public connector on refused renewal or expiry. Embassy may request takeover after confirmed dual-probe failure. Frank acquires the next epoch only after lease expiry, drain, self-fence grace, standby validation, and filestore lineage/integrity checks.

Embassy must fail closed. Missing/expired/non-acquirable lease proof, witness outage, stale replica data, or unknown filestore lineage blocks promotion. Automated actions remain disabled by default. This is software fencing, not physical STONITH; residual wedged-host risk must be tested, and automatic promotion stays disabled if any in-scope write path cannot be quiesced.

Daily Odoo DB + filestore bundles remain disaster-recovery fallback, not the normal promotion source. Failback after Frank accepts writes is a verified one-way transfer of Frank's authoritative DB + filestore to TRL5.

## Alternatives considered
- Frank-hosted shared lease: rejected because loss of Frank could block a healthy TRL5 writer.
- Automatic promotion on failed HTTP probes alone: rejected because partitions do not prove the old writer is fenced.
- Managed PDU/BMC power fence: unavailable for TRL5.
- Synchronous replication: rejected because TRL5 write availability must not depend on Frank.
- Reusing Frank's dormant Odoo database as the standby: rejected until lineage is reconciled.

## Consequences
### Positive
- TRL5 writes do not depend on Frank/Embassy availability while TRL5 holds a valid lease.
- Embassy can automatically request takeover and, when enabled, authorize promotion without TRL5 power control.
- Promotion eligibility is explicit and testable; uncertainty becomes a blocked state rather than a second writer.
- Continuous replication targets a recovery-point gap of at most 60 seconds without claiming zero data loss.

### Negative
- Cooperative fencing cannot guarantee stoppage of an arbitrary wedged process.
- Asynchronous replication can lose recent writes if the primary fails before they reach Frank.
- Public cutover and lease authority depend on Cloudflare and must fail closed when unclear.
- Continuous filestore mirroring retains superseded files until a separately verified cleanup policy exists.

## Validation plan
Unit-test the fail-closed policy, dual-probe matrix, lease epoch/takeover, lease-guard self-fence, journal atomicity, replica freshness, and filestore promotion. Rehearse bootstrap, blocked promotion, fenced promotion, former-primary restart, Tailscale-only loss with public route still live, and both failback branches in an isolated lab before any production activation.

## Follow-up actions
- Keep repository implementation fail-closed by default.
- Rehearse the isolated lab lease authority and host-level path before enabling `request_takeover_on_outage` or `automatic_actions_enabled`.
- Provision account-specific Durable Object/Worker secrets and origins only under separate approval; do not attach the production hostname from CI.
- Update TRL4/TRL5 runbooks with exact gates, residual risks, and rollback.
