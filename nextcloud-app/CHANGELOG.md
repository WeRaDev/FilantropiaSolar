# Changelog — FilantropiaSolar for Nextcloud

All notable changes to the Nextcloud app component. The desktop application
has its own changelog at the repository root (`CHANGELOG.md`).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.1.1] - 2026-07-28

### Added
- `components/analytics/ChartSection.vue` — chart markup, day navigation,
  data-mode badge, scoped CSS (extracted from AnalyticsModal; hands the
  canvas element up via `canvas-el`)
- `components/analytics/ModalStatePanel.vue` — loading and no-data states
  with their CSS
- `composables/useAnalyticsDateRange.js` — date/timeframe/analysis-mode
  orchestration (center-date clamping, effective max date, data-mode label)
  with the generate callback injected

### Changed
- `AnalyticsModal.vue` slimmed from 637 to 387 lines (under the ~400-line
  component guideline); now a thin orchestrator composing five subcomponents
  and two composables. `store.setAnalyticsTimeframe` side effect preserved

### Fixed
- `package.json` version aligned with `appinfo/info.xml` (was stale at 3.0.6)

### Verified (platform hardening)
- `scripts/setup.sh` idempotent bring-up (all 7 steps)
- Public API bearer auth (401 without token) and ML-backed estimates
- Odoo public quote flow creating CRM leads
- TRL4 network connection to the SolarSeed-v3 ops network

## [3.1.0] - 2026-07-08

### Added
- MariaDB as the canonical station source with a tokened public read API
  (`/api/public/v1/stations`, `/dashboard`)
- Public estimate endpoint (`POST /api/public/v1/estimate`) proxying the ML
  service for the Odoo quote flow
- Nextcloud admin dashboard: admin API and dashboard controls for global
  dataset stations and ML (cache status, model details, retraining,
  dataset re-import)
- ML integration (Workstream C): training, estimate contract, and dashboard
  cache in the ML microservice
- Odoo public site (Workstream D): `filantropia_solar_public` addon with
  public NGO dashboard and quote requests, plus the `odoo` compose profile
- One-command `scripts/setup.sh` platform bring-up and
  `scripts/connect-trl4.sh` TRL4 network-connect helper (Workstream E)

### Fixed
- Track `nextcloud-app/lib` PHP backend (was excluded by root `lib/` ignore)

## [3.0.6] - 2026-02-09

### Added
- Default Predicted mode; dynamic data-source labels; "Light Saved" (EUR)
  metric; Year timeframe; ML info popover with dataset citation
- Upload historical data (CSV/Excel) in CreateVirtualModal
- Persist installations (ML dataset + user DB merged); delete & restore
- ML admin panel with cache status, model details, clear cache; backend
  admin endpoints; simulate-weather limit raised to 400 days

### Fixed
- Historical mode loads measured energy from Excel; falls back to physics
  only for missing hours; `weather_source` traced end-to-end

## [3.0.5] - 2026-02-05

### Added
- Weather data layer toggles; virtual installations with star marker;
  lazy-loaded modals

### Fixed
- Duplicate info windows; normalized specific-energy ranking; Daily Summary
  hourly values; map marker icons; 500 error on virtual installations;
  list panel clicks; map coordinates from API values; ranking color
  consistency between chart and table

## [3.0.1] - 2026-01-17

### Added
- Data integration from the Mendeley PV dataset via PHP proxy
  (9 installations, 302.56 kWp)

### Fixed
- Internal host connection blocked (`allow_local_remote_servers` config)

## [3.0.0] - 2026-01-16

### Added
- Initial Nextcloud app: interactive map (Leaflet), installation management,
  energy charts (Chart.js), savings calculator, Open-Meteo integration,
  English and Portuguese translations
