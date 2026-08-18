# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2026-08-18 — FilantropiaSolar public site / NC 3.2.32

- Nextcloud public API: dashboard energy aggregate for Odoo **O Nosso Progresso**.
- Odoo addon `filantropia_solar_public` **19.0.2.27.0**: Projetos page, homepage metrics, FAQ/key points (PT), ~1 km public map privacy.
- See `nextcloud-app/CHANGELOG.md` and `docs/ops/ODOO-WEBSITE-COW-VIEWS.md`.

## [1.2.3] - 2025-11-14

### Fixed
- Windows PyInstaller build now bundles SciPy, resolving `ModuleNotFoundError: scipy` at runtime.
- Bundled `average_values.csv` into the Windows EXE so Lisbon 4-year baseline overlays render correctly on charts.
- Updated NSIS installer script for compatibility with stock NSIS (SetRegView inside functions, logging commands removed).

### Notes
- Windows installer, PyInstaller spec, and main.py logging have been verified on a fresh Windows 10 environment.

---

## [1.2.2] - 2025-11-12

### Fixed
- Historical merge length mismatch with predictions when crossing DST boundaries (duplicate 01:00). We now deduplicate historical timestamps before merge.
- Path normalization: metadata fallback now resolves under "data/" instead of legacy "Data/".
- Ranking color/description mapping now derives from the DataFrame’s ranking column to avoid shape issues after merges.

### Notes
- No breaking API changes. Models and caches remain compatible.

---

## [1.2.1] - 2025-10-24

### Added
- Custom Station Simulation: simulate energy production by choosing a location and inputting capacity (kWp); rendered alongside existing installations in Simulation mode.
- 21-Day Analysis Window: extended range to chosen date ±10 days; charts, navigation, and summaries updated.

### Changed
- UX: Custom Station panel is only visible in Simulation mode (hidden for Historical).
- GUI version bump to v1.2.1.

### Fixed/Improved
- Weather API coordinate resolution: uses installation metadata first; falls back to Data/PV Plants Metadata.xlsx (match by PV Serial Number, else Location), then simulator coords.
- Installation-specific API calls prevent location-ambiguity gaps; main uses simulation fallback to avoid user-facing errors.

### Technical Notes
- main.py: added custom-station UI; 2-column installation section; 21-day constants; titles updated.
- enhanced_energy_predictor.py: installation-specific weather lookup; Excel fallback; predict_period_for_custom(); generalized day-window; no persistence for custom.
- Tests: 35 passed, 1 skipped.

---

## [1.1.2] - 2025-10-24

### Added
- Lisbon 4-year hourly baseline overlay (min/avg/max) as base layer in Hourly Energy chart
- Headless validation scripts: `scripts/smoke_run.py`, `scripts/validate_overlay.py`, and a weather API probe
- Safe heredoc usage guideline in `warp.md` to prevent stuck shells

### Fixed
- WeatherRankingSystem API now accepts date/datetime/str and normalizes inputs
- Enforced night zero radiation using sunrise/sunset elevation crossings; retained 06–20 clamp for test compatibility
- Baseline CSV loader supports PVHour/AvgkWh/MaxkWh/MinkWh (case-insensitive) and aggregates to hourly

### Changed
- GUI version bumped to v1.1.2 across titles and loading messages
- Hourly chart legend merges baseline and ranking entries

### Technical Notes
- Changes in `main.py` (baseline loader, overlay rendering, version bump)
- Updates in `src/prediction/weather_ranking_system.py` (input normalization)
- Tests: 35 passed, 1 skipped

---

## [1.1.1] - 2025-10-21

### Added
- **Smart Constants System**: Replaced all magic numbers with 19 well-named constants
- **Enhanced ML Capabilities**: Advanced ensemble models, feature engineering, and performance monitoring
- **Intelligent Model Ensemble**: Weighted voting system combining multiple ML models for superior predictions
- **Advanced Feature Engineering**: Rolling averages, seasonal patterns, weather interactions, and time-based indicators
- **ML Performance Analytics**: Comprehensive model comparison, feature importance analysis, and performance tracking
- **Enhanced Version Display**: Clear version indication in all application windows
- **Modernized Dependencies**: Updated to latest secure versions (NumPy 2.x support, Scikit-learn 1.5+, etc.)
- **Professional Code Quality**: Zero PLR2004 violations for maintainable codebase
- **Improved Loading Screen**: Updated feature descriptions highlighting v1.1.1 improvements

### Changed
- **GUI Constants**: Window dimensions, chart formatting now use named constants
- **Data Processing**: Ranking percentiles, default values replaced with clear constants
- **Chart Positioning**: All hardcoded positions replaced with meaningful constant names
- **Dependency Versions**: Updated for security patches and performance improvements
- **Application Title**: Shows version number in all windows

### Improved
- **Code Maintainability**: Single point of control for all configurable values
- **Developer Experience**: Self-documenting code with clear constant names
- **Visual Consistency**: Standardized spacing and positioning across all interfaces
- **Security**: Latest dependency versions with security patches
- **Performance**: Optimized libraries and rendering constants

### Fixed
- **Magic Numbers**: All PLR2004 violations eliminated (47+ replacements)
- **GUI Consistency**: Uniform spacing and positioning throughout application
- **Dependency Security**: Updated all packages to secure versions
- **Code Readability**: Enhanced with descriptive constant names

## [1.0.0] - 2024-01-14

### Added
- **Production-ready main application**: New `main.py` serves as the primary entry point for FilantropiaSolar
- **Enhanced data processing**: Upgraded to `comprehensive_data_processor.py` with improved performance and caching
- **Advanced ML models**: Implemented `enhanced_energy_predictor.py` with better prediction accuracy
- **Comprehensive GUI v1**: Full-featured graphical interface with progressive loading and caching
- **Multi-installation support**: Extended support to 9 Portuguese PV installations
- **Weather simulation integration**: Enhanced weather data processing for better predictions
- **Performance ranking system**: Intelligent 5-tier ranking system for energy production optimization
- **Project configuration**: Added `pyproject.toml` for proper Python packaging
- **Archive system**: Organized previous GUI versions in `archive/gui_versions/` directory

### Changed
- **Main entry point**: Changed from `filantropia_solar_app.py` to `main.py` as the primary application launcher
- **Application structure**: Refactored codebase for better organization and maintainability
- **Version number**: Bumped to 1.0.0 to reflect production readiness
- **Documentation**: Updated README.md and USAGE_GUIDE.md to reflect new application structure
- **CLI/GUI entry points**: Updated pyproject.toml entry points to use main:main

### Deprecated
- **Legacy GUI versions**: Moved older GUI implementations to archive directory
- **Old main.py**: Renamed previous main.py to main_old.py (archived)
- **Development scripts**: Archived various development and testing scripts

### Removed
- **Obsolete GUI files**: Cleaned up src/gui directory by archiving unused GUI versions
- **Development artifacts**: Moved development scripts and test files to archive

### Fixed
- **Model loading**: Improved ML model persistence and loading mechanisms
- **Data caching**: Enhanced data caching for faster application startup
- **GUI responsiveness**: Better handling of GUI updates and user interactions
- **Error handling**: Improved error handling throughout the application

### Security
- **No security changes in this release**

## [0.9.x] - Previous Development Versions
- Various development iterations and feature additions
- Multiple GUI prototypes and experiments
- Initial data processing and ML model implementations

---

## Migration Guide from Previous Versions

### If you were using `filantropia_solar_app.py`:
```bash
# Old command
python filantropia_solar_app.py

# New command (v1.0.0+)
python main.py
```

### If you were using other GUI versions:
All previous GUI versions have been archived but are still functional:
- Check `archive/gui_versions/` for previous implementations
- Use `main.py` for the latest production-ready application

### Project Structure Changes:
- Main application: `main.py` (was `filantropia_solar_app.py`)
- Data processor: `src/data_processing/comprehensive_data_processor.py`
- ML predictor: `src/prediction/enhanced_energy_predictor.py`
- Archived files: `archive/` directory

### Configuration Updates:
- Entry points updated in `pyproject.toml`
- Version set to 1.0.0 for production release
- All dependencies remain the same in `requirements.txt`