# Odoo PostgreSQL physical replication (repository-owned)

## Scope

- Primary: TRL5 `filantropia-odoo-db`
- Standby: Frank `filantropia-odoo-db`
- Mode: asynchronous streaming replication (ADR 0007)
- Recovery-gap target: <= 60 seconds

## Safety

1. Preserve and reconcile Frank's existing DB+filestore before any first seed.
2. `replication_bootstrap.seed_standby` refuses to overwrite a non-empty data directory.
3. Keep Frank's Odoo stopped (`restart=no`) while it is a standby.
4. Do not contact TRL5/Frank or change live Postgres settings without approval.

## Bootstrap outline

1. Create a least-privilege `replicator` role on TRL5 with REPLICATION login.
2. Apply `primary.conf` and a host-restricted `pg_hba` entry for Frank only.
3. On Frank, archive the existing data directory with `preserve_existing_data`.
4. Run guarded `pg_basebackup` via `embassy.replication_bootstrap`.
5. Start Postgres as standby only; leave Odoo stopped.
6. Verify `pg_is_in_recovery()`, slot lag, and Embassy standby status.
