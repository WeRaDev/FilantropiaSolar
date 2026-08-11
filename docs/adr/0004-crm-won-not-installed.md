# ADR 0004 — CRM Won does not mark station installed

## Status
Accepted

## Context
TRS mapped Qualified→Won to Running/Active. Active implies data/feed semantics; sales Won is not field installation.

## Decision
- New→Qualified ⇒ Virtual→**Planned**  
- Won ⇒ **no** lifecycle change  
- **Admin mark installed** ⇒ Planned→Running  

## Consequences
- Negative tests on Won.  
- NC admin action required for Existing.