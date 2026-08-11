# ADR 0001 — Nextcloud remains station source of truth

## Status
Accepted

## Context
TRS proposed ML service as sole station store with Odoo calling ML directly. Production already uses NC DB + public API + ML sidecar.

## Decision
Keep **Nextcloud** as station master. Path: Odoo → NC API → ML. No ML-only station migration this program.

## Consequences
- Lifecycle APIs live on NC.  
- ML stays compute/series oriented.  
- Avoid dual writes from Odoo station forms.