# ADR 0003 — Per-installation ML models

## Status
Accepted

## Context
TRS called for one global model. Production loads per-installation models (`ml:<installation_id>`).

## Decision
**Keep per-installation models** and retrain per affected IDs (with debounce in V1).

## Consequences
- Reject global retrain-as-default.  
- Preserve feature-schema alignment guards already fixed in predictor code.