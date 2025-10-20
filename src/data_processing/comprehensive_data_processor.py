"""
Comprehensive Data Processor for All PV Installations

Loads energy production data and metadata from data/ directory,
combines with weather data from weather_files/ based on locations,
and handles all available installations across Portugal.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

import numpy as np
import pandas as pd

# Import the cache manager
from .data_cache_manager import DataCacheManager

# Constants for solar calculations
SOLAR_DECLINATION_AMPLITUDE = 23.45  # degrees
DAYS_IN_YEAR = 365.25
SOLAR_DECLINATION_OFFSET = 284
HOUR_ANGLE_MULTIPLIER = 15  # degrees per hour
SOLAR_NOON = 12  # hours
PERCENT_TO_FRACTION = 100  # for percentage calculations
THEORETICAL_POWER_DIVISOR = 1000  # for power calculations

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InstallationInfo:
    """Information about a PV installation."""

    serial_number: str
    location: str
    latitude: float
    longitude: float
    installed_power_kwp: float
    connection_power_kwn: float
    from_date: datetime.datetime
    to_date: datetime.datetime

    @property
    def installation_id(self) -> str:
        """Generate a unique installation ID."""
        return f"{self.location}_{self.serial_number}"


class ComprehensiveDataProcessor:
    """
    Comprehensive data processor that handles all PV installations.

    Loads metadata, energy production data, and weather data,
    then combines them based on location matching.
    """

    def __init__(
        self,
        data_dir: str = "data",
        weather_dir: str = "weather_files",
        use_cache: bool = True,
    ):
        """Initialize the comprehensive data processor with optional caching."""
        self.data_dir = Path(data_dir)
        self.weather_dir = Path(weather_dir)
        self.use_cache = use_cache

        # Initialize cache manager
        self.cache_manager = DataCacheManager() if use_cache else None

        # Data storage
        self.installations: dict[str, InstallationInfo] = {}
        self.energy_data: dict[str, pd.DataFrame] = {}
        self.weather_data: dict[str, pd.DataFrame] = {}
        self.combined_data: dict[str, pd.DataFrame] = {}

        # Location to weather file mapping
        self.weather_file_mapping = {
            "Lisbon": "Lisbon_weather.csv",
            "Setubal": "Setubal_weather.csv",
            "Faro": "Faro_weather.csv",
            "Braga": "Braga_weather.csv",
            "Tavira": "Tavira_weather.csv",
            "Loule": "Loule_weather.csv",
        }

        # Load all data (with caching if enabled)
        self._load_installations_metadata()
        self._load_energy_production_data()
        self._load_weather_data()
        self._combine_data()

    def _load_installations_metadata(self):
        """Load PV installations metadata from Excel file with caching."""
        cache_key = "installations_metadata"

        # Try to load from cache first
        if self.cache_manager and self.cache_manager.is_cached("metadata", cache_key):
            cached_installations = self.cache_manager.load_cached_data(
                "metadata", cache_key
            )
            if cached_installations:
                self.installations = cached_installations
                logger.info(
                    f"Loaded {len(self.installations)} installations from cache"
                )
                return

        try:
            metadata_file = self.data_dir / "PV Plants Metadata.xlsx"
            if not metadata_file.exists():
                raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

            logger.info("Loading installations metadata from source (not cached)")

            # Read metadata with proper header handling
            df = pd.read_excel(metadata_file, header=1)
            df = df.dropna(how="all").reset_index(drop=True)

            # Clean column names
            df.columns = df.columns.str.strip()

            logger.info(f"Loaded metadata for {len(df)} installations")
            logger.debug(f"Metadata columns: {list(df.columns)}")

            # Process each installation
            for idx, row in df.iterrows():
                try:
                    serial_number = str(int(row["PV Serial Number"]))
                    location = str(row["Location"]).strip()

                    installation = InstallationInfo(
                        serial_number=serial_number,
                        location=location,
                        latitude=float(row["Latitude"]),
                        longitude=float(row["Longitude"]),
                        installed_power_kwp=float(row["Installed Power (kWp)"]),
                        connection_power_kwn=float(row["Connection Power (kWn)"]),
                        from_date=pd.to_datetime(row["From date"]),
                        to_date=pd.to_datetime(row["To date"]),
                    )

                    self.installations[installation.installation_id] = installation
                    logger.info(
                        f"Loaded installation: {installation.installation_id} "
                        f"({installation.installed_power_kwp} kWp in {installation.location})"
                    )

                except Exception as e:
                    logger.error(f"Error processing installation at row {idx}: {e}")
                    continue

            logger.info(f"Successfully loaded {len(self.installations)} installations")

            # Cache the installations metadata
            if self.cache_manager:
                self.cache_manager.cache_data(
                    self.installations,
                    "metadata",
                    cache_key,
                    metadata={
                        "total_installations": len(self.installations),
                        "locations": list(
                            {inst.location for inst in self.installations.values()}
                        ),
                    },
                )

        except Exception as e:
            logger.error(f"Error loading installations metadata: {e}")
            raise

    def _load_energy_production_data(self):
        """Load energy production data for all installations from Excel sheets with caching."""
        # Try to load all from cache first
        if self._try_load_all_energy_from_cache():
            return

        # Load from source files
        self._load_energy_from_source_files()

    def _try_load_all_energy_from_cache(self) -> bool:
        """Try to load all energy data from cache. Returns True if successful."""
        if not self.cache_manager:
            return False

        # Check if all energy data is cached
        all_cached = all(
            self.cache_manager.is_cached("energy_data", installation_id)
            for installation_id in self.installations
        )

        if not all_cached:
            return False

        logger.info("Loading all energy data from cache")
        for installation_id in self.installations:
            cached_data = self.cache_manager.load_cached_data(
                "energy_data", installation_id
            )
            if cached_data is not None:
                self.energy_data[installation_id] = cached_data

        logger.info(
            f"Loaded energy data for {len(self.energy_data)} installations from cache"
        )
        return True

    def _load_energy_from_source_files(self):
        """Load energy production data from Excel source files."""
        try:
            datasets_file = self.data_dir / "PV Plants Datasets.xlsx"
            if not datasets_file.exists():
                raise FileNotFoundError(f"Datasets file not found: {datasets_file}")

            # Get all sheet names
            excel_file = pd.ExcelFile(datasets_file)
            sheet_names = excel_file.sheet_names

            logger.info(f"Found {len(sheet_names)} data sheets: {sheet_names}")
            logger.info("Loading energy production data from source (not fully cached)")

            # Load data for each installation
            for installation_id, installation in self.installations.items():
                self._load_single_installation_energy_data(
                    installation_id, installation, datasets_file, sheet_names
                )

            logger.info(
                f"Successfully loaded energy data for {len(self.energy_data)} installations"
            )

        except Exception as e:
            logger.error(f"Error loading energy production data: {e}")
            raise

    def _load_single_installation_energy_data(
        self,
        installation_id: str,
        installation: InstallationInfo,
        datasets_file: Path,
        sheet_names: list[str],
    ):
        """Load energy data for a single installation."""
        # Check cache for individual installation
        if self._try_load_installation_from_cache(installation_id):
            return

        sheet_name = installation.serial_number
        if sheet_name not in sheet_names:
            logger.warning(
                f"No data sheet found for installation {installation_id} (sheet: {sheet_name})"
            )
            return

        try:
            # Load and process the sheet data
            df = self._process_energy_sheet_data(
                datasets_file, sheet_name, installation_id, installation
            )

            self.energy_data[installation_id] = df
            logger.info(f"Loaded {len(df)} energy records for {installation_id}")

            # Cache the energy data
            self._cache_installation_energy_data(df, installation_id, installation)

        except Exception as e:
            logger.error(f"Error loading energy data for {installation_id}: {e}")

    def _try_load_installation_from_cache(self, installation_id: str) -> bool:
        """Try to load single installation data from cache."""
        if not (
            self.cache_manager
            and self.cache_manager.is_cached("energy_data", installation_id)
        ):
            return False

        cached_data = self.cache_manager.load_cached_data(
            "energy_data", installation_id
        )
        if cached_data is not None:
            self.energy_data[installation_id] = cached_data
            logger.info(
                f"Loaded {len(cached_data)} energy records for {installation_id} from cache"
            )
            return True
        return False

    def _process_energy_sheet_data(
        self,
        datasets_file: Path,
        sheet_name: str,
        installation_id: str,
        installation: InstallationInfo,
    ) -> pd.DataFrame:
        """Process energy data from Excel sheet."""
        # Load the sheet data
        df = pd.read_excel(datasets_file, sheet_name=sheet_name)

        # Clean and process the data
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")

        # Ensure numeric columns
        numeric_columns = [
            "Produced Energy (kWh)",
            "Specific Energy (kWh/kWp)",
            "CO2 Avoided (tons)",
        ]
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Remove invalid data
        df = df.dropna(subset=["Produced Energy (kWh)"])

        # Add installation metadata
        df["installation_id"] = installation_id
        df["location"] = installation.location
        df["installed_power_kwp"] = installation.installed_power_kwp
        df["connection_power_kwn"] = installation.connection_power_kwn

        return df

    def _cache_installation_energy_data(
        self, df: pd.DataFrame, installation_id: str, installation: InstallationInfo
    ):
        """Cache energy data for an installation."""
        if self.cache_manager:
            self.cache_manager.cache_data(
                df,
                "energy_data",
                installation_id,
                metadata={
                    "records": len(df),
                    "location": installation.location,
                    "power_kwp": installation.installed_power_kwp,
                },
            )

    def _load_weather_data(self):
        """Load weather data for all available locations."""
        try:
            # Get unique locations from installations
            locations = {
                installation.location for installation in self.installations.values()
            }

            for location in locations:
                if location in self.weather_file_mapping:
                    weather_file = (
                        self.weather_dir / self.weather_file_mapping[location]
                    )

                    if weather_file.exists():
                        try:
                            df = pd.read_csv(weather_file)

                            # Parse datetime with robust format handling to avoid UserWarning
                            try:
                                # Try primary format first (most common)
                                df["datetime"] = pd.to_datetime(
                                    df["time"],
                                    format="%m/%d/%y %I:%M %p",
                                    errors="raise",
                                )
                            except (ValueError, TypeError):
                                logger.info(
                                    f"Primary datetime format failed for {location}, trying fallback formats"
                                )
                                # Try common alternative formats
                                for fmt in [
                                    "%m/%d/%Y %I:%M %p",
                                    "%Y-%m-%d %H:%M:%S",
                                    "%m/%d/%y %H:%M",
                                    "%m/%d/%Y %H:%M",
                                ]:
                                    try:
                                        df["datetime"] = pd.to_datetime(
                                            df["time"], format=fmt, errors="raise"
                                        )
                                        logger.info(
                                            f"Successfully parsed datetime using format: {fmt}"
                                        )
                                        break
                                    except (ValueError, TypeError):
                                        continue
                                else:
                                    # Final fallback with infer_datetime_format=True to suppress warning
                                    logger.warning(
                                        f"All explicit formats failed for {location}, using infer_datetime_format"
                                    )
                                    df["datetime"] = pd.to_datetime(
                                        df["time"], infer_datetime_format=True
                                    )
                            df = df.set_index("datetime")

                            # Clean column names
                            df.columns = [
                                col.split(" (")[0] if " (" in col else col
                                for col in df.columns
                            ]

                            # Ensure we have required columns
                            required_cols = [
                                "temperature_2m",
                                "relative_humidity_2m",
                                "dew_point_2m",
                                "apparent_temperature",
                                "cloud_cover",
                                "wind_speed_10m",
                                "wind_direction_10m",
                                "shortwave_radiation",
                            ]

                            available_cols = [
                                col for col in required_cols if col in df.columns
                            ]
                            if len(available_cols) < len(required_cols):
                                missing = set(required_cols) - set(available_cols)
                                logger.warning(
                                    f"Missing weather columns for {location}: {missing}"
                                )

                            self.weather_data[location] = df[available_cols].copy()
                            logger.info(
                                f"Loaded {len(df)} weather records for {location}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Error loading weather data for {location}: {e}"
                            )
                    else:
                        logger.warning(
                            f"Weather file not found for {location}: {weather_file}"
                        )
                else:
                    logger.warning(f"No weather file mapping for location: {location}")

        except Exception as e:
            logger.error(f"Error loading weather data: {e}")
            raise

    def _combine_data(self):
        """Combine energy production data with weather data based on location."""
        try:
            for installation_id, energy_df in self.energy_data.items():
                installation = self.installations[installation_id]
                location = installation.location

                if location in self.weather_data:
                    weather_df = self.weather_data[location]

                    # Merge on datetime index
                    combined = energy_df.merge(
                        weather_df, left_index=True, right_index=True, how="inner"
                    )

                    # Add additional computed features
                    combined = self._add_computed_features(combined, installation)

                    self.combined_data[installation_id] = combined
                    logger.info(
                        f"Combined {len(combined)} records for {installation_id}"
                    )

                else:
                    logger.warning(
                        f"No weather data available for location: {location}"
                    )
                    # Store energy data only
                    self.combined_data[installation_id] = energy_df.copy()

        except Exception as e:
            logger.error(f"Error combining data: {e}")
            raise

    def _add_computed_features(
        self, df: pd.DataFrame, installation: InstallationInfo
    ) -> pd.DataFrame:
        """Add computed features to the combined dataset."""
        try:
            # Time-based features
            df["hour"] = df.index.hour
            df["day_of_year"] = df.index.dayofyear
            df["month"] = df.index.month
            df["year"] = df.index.year
            df["weekday"] = df.index.weekday

            # Solar elevation approximation
            df["solar_elevation"] = self._compute_solar_elevation(
                df.index, installation.latitude, installation.longitude
            )

            # Weather-energy interaction features
            if "temperature_2m" in df.columns and "cloud_cover" in df.columns:
                df["temp_cloud_interaction"] = (
                    df["temperature_2m"]
                    * (PERCENT_TO_FRACTION - df["cloud_cover"])
                    / PERCENT_TO_FRACTION
                )

            if "shortwave_radiation" in df.columns and "cloud_cover" in df.columns:
                df["radiation_cloud_interaction"] = (
                    df["shortwave_radiation"]
                    * (PERCENT_TO_FRACTION - df["cloud_cover"])
                    / PERCENT_TO_FRACTION
                )

            # Power efficiency (actual vs theoretical)
            if (
                "Produced Energy (kWh)" in df.columns
                and "shortwave_radiation" in df.columns
            ):
                # Theoretical maximum power (simplified)
                df["theoretical_power"] = (
                    df["shortwave_radiation"]
                    * installation.installed_power_kwp
                    / THEORETICAL_POWER_DIVISOR
                )
                df["power_efficiency"] = np.where(
                    df["theoretical_power"] > 0,
                    df["Produced Energy (kWh)"] / df["theoretical_power"],
                    0,
                )
                df["power_efficiency"] = df["power_efficiency"].clip(
                    0, 1
                )  # Cap at 100% efficiency

            return df

        except Exception as e:
            logger.error(f"Error adding computed features: {e}")
            return df

    def _compute_solar_elevation(
        self, timestamps: pd.DatetimeIndex, latitude: float, _longitude: float
    ) -> np.ndarray:
        """Compute approximate solar elevation angle."""
        try:
            # Simplified solar position calculation
            day_of_year = timestamps.dayofyear
            hour = timestamps.hour + timestamps.minute / 60.0

            # Solar declination angle
            declination = SOLAR_DECLINATION_AMPLITUDE * np.sin(
                np.radians(
                    360 * (SOLAR_DECLINATION_OFFSET + day_of_year) / DAYS_IN_YEAR
                )
            )

            # Hour angle
            hour_angle = HOUR_ANGLE_MULTIPLIER * (hour - SOLAR_NOON)

            # Solar elevation
            lat_rad = np.radians(latitude)
            dec_rad = np.radians(declination)
            hour_rad = np.radians(hour_angle)

            elevation = np.arcsin(
                np.sin(lat_rad) * np.sin(dec_rad)
                + np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_rad)
            )

            return np.degrees(elevation)

        except Exception as e:
            logger.error(f"Error computing solar elevation: {e}")
            return np.zeros(len(timestamps))

    def get_installation_list(self) -> list[tuple[str, InstallationInfo]]:
        """Get list of all available installations."""
        return [(id, info) for id, info in self.installations.items()]

    def get_installation_by_id(self, installation_id: str) -> InstallationInfo | None:
        """Get installation info by ID."""
        return self.installations.get(installation_id)

    def get_combined_data(self, installation_id: str) -> pd.DataFrame | None:
        """Get combined data for a specific installation."""
        return self.combined_data.get(installation_id)

    def get_energy_data(self, installation_id: str) -> pd.DataFrame | None:
        """Get energy data for a specific installation."""
        return self.energy_data.get(installation_id)

    def get_weather_data(self, location: str) -> pd.DataFrame | None:
        """Get weather data for a specific location."""
        return self.weather_data.get(location)

    def get_locations(self) -> list[str]:
        """Get list of all available locations."""
        return list(
            {installation.location for installation in self.installations.values()}
        )

    def get_installations_by_location(
        self, location: str
    ) -> list[tuple[str, InstallationInfo]]:
        """Get all installations for a specific location."""
        return [
            (id, info)
            for id, info in self.installations.items()
            if info.location == location
        ]

    def get_date_range(self) -> tuple[datetime.datetime, datetime.datetime]:
        """Get the overall date range of available data."""
        if not self.combined_data:
            return None, None

        min_date = None
        max_date = None

        for df in self.combined_data.values():
            if len(df) > 0:
                df_min = df.index.min()
                df_max = df.index.max()

                if min_date is None or df_min < min_date:
                    min_date = df_min
                if max_date is None or df_max > max_date:
                    max_date = df_max

        return min_date, max_date

    def get_data_summary(self) -> dict[str, Any]:
        """Get a summary of loaded data."""
        date_min, date_max = self.get_date_range()

        return {
            "total_installations": len(self.installations),
            "locations": self.get_locations(),
            "installations_with_data": len(self.combined_data),
            "date_range": {
                "start": date_min.strftime("%Y-%m-%d") if date_min else None,
                "end": date_max.strftime("%Y-%m-%d") if date_max else None,
            },
            "total_records": sum(len(df) for df in self.combined_data.values()),
            "installations_by_location": {
                location: len(self.get_installations_by_location(location))
                for location in self.get_locations()
            },
        }

    def is_date_in_historical_range(self, date: datetime.datetime) -> bool:
        """Check if a date is within the historical data range."""
        date_min, date_max = self.get_date_range()
        if date_min is None or date_max is None:
            return False
        return date_min <= date <= date_max


if __name__ == "__main__":
    # Test the comprehensive data processor
    processor = ComprehensiveDataProcessor()

    print("Data Summary:")
    summary = processor.get_data_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("\nAvailable Installations:")
    for inst_id, inst_info in processor.get_installation_list():
        print(
            f"  {inst_id}: {inst_info.installed_power_kwp} kWp in {inst_info.location}"
        )
