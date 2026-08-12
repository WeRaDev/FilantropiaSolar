# Real fleet inventory (ops stations)

**Status:** Authoritative product input (2026-08-12)  
**Scope:** Stations that appear in the **NC ops dashboard** and drive portfolio metrics.  
**Not in scope:** Mendeley / `source=dataset` PV plants — **ML training corpus only**, not the real fleet.

## Capacity unit

Values below are stored as provided. **Confirm unit before seeding production:**

| Interpretation | Example Zoófila 18000 |
|----------------|----------------------|
| **W_p (likely)** | 18.0 kWp |
| kWp | 18 MWp (implausible for this program) |

Until confirmed, treat numbers as **watts peak (W)** and convert to kWp as `value / 1000` for NC `capacity_kwp`.

## Fleet table

| Year | Site | Capacity (raw) | Organisation / notes |
|------|------|----------------|----------------------|
| 2023 | Vazinha | 540 | (blank) |
| 2024 | ARIA Alcabideche | 4500 | NGO (spelling: Alcabideche) |
| 2024 | Gatos do Jardim | 3680 | NGO |
| 2024 | Almocagem Farm | 800 | |
| 2024 | Penedo off-grid | 960 | off-grid |
| 2024 | Diago farm | 900 | |
| 2025 | Gaela | 2190 | |
| 2025 | Catarina | 2200 | |
| 2025 | Rita | 1380 | |
| 2025 | Zoófila | 18000 | NGO |
| 2026 | PurposeFlow | 4600 | |

**Count:** 11 real stations.  
**Raw capacity sum:** 40 230 (if W → **40.23 kWp** total; if kWp → 40.23 MWp).

## Suggested NC defaults (until richer data exists)

| Field | Default |
|-------|---------|
| `source` | `fleet` (new) or `user` with tag — prefer dedicated `fleet` |
| `lifecycle_state` | `running` if year ≤ current and installed; else `planned` |
| `installed_at` / `installation_date` | `YYYY-01-01` of year column (placeholder) |
| `location` / lat-lon | TBD (geocode or ops entry) — required before weather/ML backfill |
| `is_virtual` | false for Running fleet |
| Public | Running → Existing; Planned → Planned |

## Explicit non-fleet

- Lisbon/Setúbal/Faro/… **Mendeley** rows currently `source=dataset` must **not** drive:
  - ops list (default)
  - portfolio Total energy / savings / kWp
  - public Existing map (unless deliberately published)
- They remain available to **ML service** for training only.

## Change control

Updates to this table require ops confirmation and a PR touching this file + any seed script.
