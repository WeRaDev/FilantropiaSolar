# Changelog — FilantropiaSolar for Nextcloud

All notable changes to the Nextcloud app component. The desktop application
has its own changelog at the repository root (`CHANGELOG.md`).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.2.30] - 2026-08-14

### Fixed
- EnergyApiController parse error: missing `$` on `$out` (Internal Server Error)
- WeatherSyncJob: `getUniqueLocations()` arity + nearest known cities for ops fleet
- PredictionJob: add `WeatherService::getForecast()`; refresh ops stations only
- Restore original `app.png` asset (no generated icon)
- Series/dataset range labels use only `series_from_date`/`series_to_date` (not install date)
- View dataset opens full NC series table for validation (not Analysis)
- Historical analysis never ML-generates; NC readings only (no weather fetch fill)

### Added
- `ViewDatasetModal` + NC-backed `GET .../readings` with capacity/price/savings columns

### Changed
- App version **3.2.30**

## [3.2.29] - 2026-08-14

### Fixed
- Current efficiency uses latest series hour at or before last complete Lisbon hour (no more permanent 0%)
- Historical analysis no longer on-demand ML-fills; shows existing `oc_fs_readings` only (faster)
- Historical calendar clamped to actual series_from/series_to bounds
- Dataset range on info card uses series bounds; Edit exposes installation date + View/Populate dataset
- Regenerated branded `app.png` (256) for navigation/settings icon

### Added
- `POST /api/v1/installations/{id}/populate-series` (chunked sim fill; never overwrites measured)
- Design plan: `docs/architecture/ML-SERIES-POPULATE-PLAN.md`

### Changed
- App version **3.2.29**

## [3.2.28] - 2026-08-14

### Fixed
- Fleet seed uses real `install_date` (not year-01-01); Postgres AIO seed support via `FS_DB_ENGINE`
- CRM→NC: station title uses opportunity name; organisation (`partner_name`) not overwritten on reconcile
- CRM→NC: `grid_connection_type` sent on virtual create and profile push; NC createVirtual accepts it
- Odoo NC Dashboard link: strip API paths; prefer Tailscale origin; honor `FS_NC_ADMIN_URL`
- Favicon: SVG + JS re-apply after Nextcloud shell load
- Historical analytics: on-demand series fill for Running ops stations when `oc_fs_readings` empty

### Changed
- Odoo public module **19.0.2.24.0**
- App version **3.2.28**

## [3.2.27] - 2026-08-14

### Fixed
- Public map station list rebuilds from `FS_STATIONS` when Website COW lacks clickable items
- CRM station name no longer forced back to organisation; grid_connection_type CRM→NC profile sync
- Candidatura step 3: on-grid/off-grid; hide bill/price fields for off-grid
- NC admin URL for Odoo dashboard points at AIO/Tailscale app path
- Header version badge; favicon from `img/app.png`
- KPI totals exclude virtual stations
- Upload historical: computer file input overlay; NC filepicker z-index above analytics

### Changed
- Odoo public module **19.0.2.23.0**

## [3.2.26] - 2026-08-14

### Added
- Hourly NC series SoT (`oc_fs_readings.provenance`); `SeriesRollForwardJob` (3600s, Europe/Lisbon 05:00–22:00); chunked `SeriesBackfillJob`
- Analytics Historical path from NC readings; Predicted for ops stations; View data overlay
- Dual I/O: export/upload via computer or Nextcloud Files; upload modal teleport + z-index above analytics
- Lifecycle CRM mirror (Odoo queue_job), public API Planned+Running filter, grid_connection_type
- Europe/Lisbon timezone for series hours and efficiency; map location pin restore
- Ops docs: MVP-7 gates, TRL5 backup runbook, ML production accuracy verifier

### Changed
- App version **3.2.26** (`appinfo/info.xml`, `package.json`); desktop remains **1.3.0** API-client
- Odoo public module **19.0.2.22.0**

### Notes
- TRL5 may still run an older app until cutover; backup before deploy (`docs/ops/TRL5-BACKUP.md`)
- Full incremental history for 3.2.x lives in git log / PR #31 and related merges on `main`

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
