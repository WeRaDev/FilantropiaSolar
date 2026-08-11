# ADR 0005 — Measured immutable; predicted and savings recalc

## Status
Accepted

## Context
TRS both retained immutable historical field data and recalculated historical production after capacity edits.

## Decision
- **Immutable:** measured/historical kWh samples.  
- **Recalculate from effective date:** predicted series + **piecewise savings** when capacity or supplier price changes.  

## Consequences
- V1 jobs must not UPDATE measured fact tables for capacity edits.  
- Price history table (or equivalent) required for piecewise savings.