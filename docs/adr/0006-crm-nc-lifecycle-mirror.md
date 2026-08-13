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
- NC lifecycle changes and fleet import update CRM stages the other way.
- Loop prevention: skip enqueue when NC state already matches; stamp `fs_nc_sync_origin`.

## Consequences
- ADR 0004 Won-noop is **superseded** for this product path.
- Existing Won stages should be renamed/mapped to Installed on upgrade.
- Release notes must call out the behaviour change.
- Negative tests for “Won does not install” are replaced by Installed→Running tests.
