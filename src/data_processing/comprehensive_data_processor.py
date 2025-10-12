"""
Comprehensive Data Processor for All PV Installations

Loads energy production data and metadata from data/ directory,
combines with weather data from weather_files/ based on locations,
and handles all available installations across Portugal.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InstallationInfo:
    """Information about a PV installation."""

    serial_number: str
    location: str
    latitude: float
    longitude: float
    installed_power_kwp: float
    connection_power_kwn: float
    from_date: datetime
    to_date: datetime

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

    def __init__(self, data_dir: str = "data", weather_dir: str = "weather_files"):
        """Initialize the comprehensive data processor."""
        self.data_dir = Path(data_dir)
        self.weather_dir = Path(weather_dir)

        # Data storage
        self.installations: Dict[str, InstallationInfo] = {}
        self.energy_data: Dict[str, pd.DataFrame] = {}
        self.weather_data: Dict[str, pd.DataFrame] = {}
        self.combined_data: Dict[str, pd.DataFrame] = {}

        # Location to weather file mapping
        self.weather_file_mapping = {
            "Lisbon": "Lisbon_weather.csv",
            "Setubal": "Setubal_weather.csv",
            "Faro": "Faro_weather.csv",
            "Braga": "Braga_weather.csv",
            "Tavira": "Tavira_weather.csv",
            "Loule": "Loule_weather.csv",
        }

        # Load all data
        self._load_installations_metadata()
        self._load_energy_production_data()
        self._load_weather_data()
        self._combine_data()

    def _load_installations_metadata(self):
        """Load PV installations metadata from Excel file."""
        try:
            metadata_file = self.data_dir / "PV Plants Metadata.xlsx"
            if not metadata_file.exists():
                raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

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

        except Exception as e:
            logger.error(f"Error loading installations metadata: {e}")
            raise

    def _load_energy_production_data(self):
        """Load energy production data for all installations from Excel sheets."""
        try:
            datasets_file = self.data_dir / "PV Plants Datasets.xlsx"
            if not datasets_file.exists():
                raise FileNotFoundError(f"Datasets file not found: {datasets_file}")

            # Get all sheet names (which should correspond to serial numbers)
            excel_file = pd.ExcelFile(datasets_file)
            sheet_names = excel_file.sheet_names

            logger.info(f"Found {len(sheet_names)} data sheets: {sheet_names}")

            # Load data for each installation
            for installation_id, installation in self.installations.items():
                sheet_name = installation.serial_number

                if sheet_name in sheet_names:
                    try:
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

                        self.energy_data[installation_id] = df
                        logger.info(
                            f"Loaded {len(df)} energy records for {installation_id}"
                        )

                    except Exception as e:
                        logger.error(
                            f"Error loading energy data for {installation_id}: {e}"
                        )
                        continue
                else:
                    logger.warning(
                        f"No data sheet found for installation {installation_id} (sheet: {sheet_name})"
                    )

            logger.info(
                f"Successfully loaded energy data for {len(self.energy_data)} installations"
            )

        except Exception as e:
            logger.error(f"Error loading energy production data: {e}")
            raise

    def _load_weather_data(self):
        """Load weather data for all available locations."""
        try:
            # Get unique locations from installations
            locations = set(
                installation.location for installation in self.installations.values()
            )

            for location in locations:
                if location in self.weather_file_mapping:
                    weather_file = (
                        self.weather_dir / self.weather_file_mapping[location]
                    )

                    if weather_file.exists():
                        try:
                            df = pd.read_csv(weather_file)

                            # Parse datetime
                            df["datetime"] = pd.to_datetime(df["time"])
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
                    df["temperature_2m"] * (100 - df["cloud_cover"]) / 100
                )

            if "shortwave_radiation" in df.columns and "cloud_cover" in df.columns:
                df["radiation_cloud_interaction"] = (
                    df["shortwave_radiation"] * (100 - df["cloud_cover"]) / 100
                )

            # Power efficiency (actual vs theoretical)
            if (
                "Produced Energy (kWh)" in df.columns
                and "shortwave_radiation" in df.columns
            ):
                # Theoretical maximum power (simplified)
                df["theoretical_power"] = (
                    df["shortwave_radiation"] * installation.installed_power_kwp / 1000
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
        self, timestamps: pd.DatetimeIndex, latitude: float, longitude: float
    ) -> np.ndarray:
        """Compute approximate solar elevation angle."""
        try:
            # Simplified solar position calculation
            day_of_year = timestamps.dayofyear
            hour = timestamps.hour + timestamps.minute / 60.0

            # Solar declination angle
            declination = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365.25))

            # Hour angle
            hour_angle = 15 * (hour - 12)

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

    def get_installation_list(self) -> List[Tuple[str, InstallationInfo]]:
        """Get list of all available installations."""
        return [(id, info) for id, info in self.installations.items()]

    def get_installation_by_id(
        self, installation_id: str
    ) -> Optional[InstallationInfo]:
        """Get installation info by ID."""
        return self.installations.get(installation_id)

    def get_combined_data(self, installation_id: str) -> Optional[pd.DataFrame]:
        """Get combined data for a specific installation."""
        return self.combined_data.get(installation_id)

    def get_energy_data(self, installation_id: str) -> Optional[pd.DataFrame]:
        """Get energy data for a specific installation."""
        return self.energy_data.get(installation_id)

    def get_weather_data(self, location: str) -> Optional[pd.DataFrame]:
        """Get weather data for a specific location."""
        return self.weather_data.get(location)

    def get_locations(self) -> List[str]:
        """Get list of all available locations."""
        return list(
            set(installation.location for installation in self.installations.values())
        )

    def get_installations_by_location(
        self, location: str
    ) -> List[Tuple[str, InstallationInfo]]:
        """Get all installations for a specific location."""
        return [
            (id, info)
            for id, info in self.installations.items()
            if info.location == location
        ]

    def get_date_range(self) -> Tuple[datetime, datetime]:
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

    def get_data_summary(self) -> Dict[str, Any]:
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

    def is_date_in_historical_range(self, date: datetime) -> bool:
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
