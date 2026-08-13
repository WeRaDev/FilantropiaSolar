# ADR 0006 — CRM/NC lifecycle mirror (supersedes ADR 0004)

## Status
Accepted

## Context
ADR 0004 kept CRM Won decoupled from NC Running so sales close did not imply
field installation. Ops now want a full bidirectional mirror and an explicit
**Installed** CRM stage for Running stations.

## Decision
| CRM stage | NC lifecycle |
|-----------|--------------|
| New | none (no station required) |
| Qualified | Virtual |
| Proposition | Planned |
| Installed (ex-Won, `is_won`) | Running |

- Candidatura creates a donation lead on **New** without NC Virtual.
- Entering **Qualified** creates/ensures Virtual.
- Entering **Proposition** promotes Planned.
- Entering **Installed** calls mark-installed (Running).
- Demotions also mirror: Installed/Proposition → Qualified sets NC Virtual;
  Installed → Proposition sets NC Planned (`POST .../set-lifecycle`).
- NC lifecycle changes and fleet import update CRM stages the other way.
- Loop prevention: skip enqueue when NC state already matches; stamp `fs_nc_sync_origin`.
- Mirror scope is **ops stations only** (fleet/user/crm). Mendeley `source=dataset`
  training corpus is excluded from lifecycle list/import so NC admin and CRM stay
  one-to-one. Reconcile binds `odoo_lead_id` back onto NC and archives CRM leads
  whose installation is no longer on the ops list.

## Consequences
- ADR 0004 Won-noop is **superseded** for this product path.
- Existing Won stages should be renamed/mapped to Installed on upgrade.
- Release notes must call out the behaviour change.
- Negative tests for “Won does not install” are replaced by Installed→Running tests.
