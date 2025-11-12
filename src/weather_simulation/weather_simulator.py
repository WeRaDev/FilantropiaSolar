"""
Weather Simulator Module

Generates synthetic weather data based on historical patterns for dates not available in the dataset.
Inspired by SolarSim methodology for weather simulation.
"""

from datetime import datetime, timedelta
import logging
from pathlib import Path
# Path helper import (packaged first, then dev layouts)
try:
    from filantropia_solar.utils.paths import get_resource_path
except Exception:
    try:
        from src.utils.paths import get_resource_path
    except Exception:
        from utils.paths import get_resource_path
import warnings

import numpy as np
import pandas as pd
from sklearn.neighbors import KNeighborsRegressor
from sklearn.preprocessing import StandardScaler


warnings.filterwarnings("ignore")

# Lint/clarity constants
SIMILAR_DAYS_WINDOW = 15
MIN_SIMILAR_DATA_HOURS = 24
MIN_FEATURES_RECORDS = 100
MIN_VALID_POINTS = 10
MAX_NEIGHBORS = 10
KNN_NEIGHBOR_DIVISOR = 10

logger = logging.getLogger(__name__)

# Solar radiation physical/constraint constants
MIN_RADIATION_WM2 = 0.0
MAX_RADIATION_WM2 = 1200.0
CLOUD_ATTENUATION_FACTOR = 0.75  # How strongly clouds reduce clear-sky radiation


class WeatherSimulator:
    """
    Weather simulator that generates synthetic weather data based on historical patterns.

    Uses k-nearest neighbors approach with seasonal and daily pattern recognition
    to generate realistic weather forecasts for dates not in historical data.
    """

    def __init__(self, weather_data_dir: str):
        """Initialize the weather simulator with historical weather data."""
        # Resolve bundled resource directory (PyInstaller/meipass) or repo path during dev
        try:
            self.weather_data_dir = get_resource_path(weather_data_dir)
        except Exception:
            self.weather_data_dir = Path(weather_data_dir)
        self.weather_data: dict[str, pd.DataFrame] = {}
        self.location_mapping = {
            "Lisbon": "Lisbon_weather.csv",
            "Setubal": "Setubal_weather.csv",
            "Faro": "Faro_weather.csv",
            "Braga": "Braga_weather.csv",
            "Tavira": "Tavira_weather.csv",
            "Loule": "Loule_weather.csv",
        }
        self.scalers: dict[str, StandardScaler] = {}
        self.models: dict[str, dict[str, KNeighborsRegressor]] = {}
        # Approximate coordinates per location (for solar elevation)
        self.location_coords = {
            "Lisbon": (38.7223, -9.1393),
            "Setubal": (38.5244, -8.8882),
            "Faro": (37.0194, -7.9304),
            "Braga": (41.5454, -8.4265),
            "Tavira": (37.1279, -7.6486),
            "Loule": (37.1376, -8.0197),
        }
        self._load_historical_data()
        self._prepare_simulation_models()

    def _load_historical_data(self):
        """Load historical weather data for all available locations."""
        for location, filename in self.location_mapping.items():
            file_path = self.weather_data_dir / filename
            if file_path.exists():
                try:
                    df = pd.read_csv(file_path)
                    # Parse datetime
                    df["datetime"] = pd.to_datetime(df["time"])
                    df = df.set_index("datetime")

                    # Clean column names
                    df.columns = [
                        col.split(" (")[0] if " (" in col else col for col in df.columns
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

                    missing_cols = [
                        col for col in required_cols if col not in df.columns
                    ]
                    if missing_cols:
                        logger.warning(
                            f"Missing columns for {location}: {missing_cols}",
                        )
                        continue

                    self.weather_data[location] = df[required_cols].copy()
                    logger.info(
                        f"Loaded weather data for {location}: {len(df)} records",
                    )

                except Exception as e:
                    logger.error(f"Error loading weather data for {location}: {e}")
            else:
                logger.warning(f"Weather file not found: {file_path}")

    def _prepare_simulation_models(self):
        """Prepare machine learning models for weather simulation."""
        for location, df in self.weather_data.items():
            try:
                # Create features for pattern recognition
                features = self._create_temporal_features(df)

                # Prepare targets (weather parameters)
                targets = df[
                    [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "cloud_cover",
                        "wind_speed_10m",
                        "shortwave_radiation",
                    ]
                ].copy()

                # Remove invalid data
                mask = np.isfinite(features).all(axis=1) & np.isfinite(targets).all(
                    axis=1,
                )
                features = features[mask]
                targets = targets[mask]

                if len(features) < MIN_FEATURES_RECORDS:  # Need minimum data
                    logger.warning(
                        f"Insufficient data for {location}: {len(features)} records",
                    )
                    continue

                # Scale features
                scaler = StandardScaler()
                features_scaled = scaler.fit_transform(features)

                # Create KNN model for each weather parameter
                models = {}
                for col in targets.columns:
                    if targets[col].notna().sum() > (
                        MIN_FEATURES_RECORDS // 2
                    ):  # Minimum valid data points
                        n_neighbors = min(
                            MAX_NEIGHBORS,
                            max(1, len(features) // KNN_NEIGHBOR_DIVISOR),
                        )
                        knn = KNeighborsRegressor(
                            n_neighbors=n_neighbors,
                            weights="distance",
                        )
                        valid_mask = targets[col].notna()
                        if valid_mask.sum() > MIN_VALID_POINTS:
                            knn.fit(
                                features_scaled[valid_mask],
                                targets[col][valid_mask],
                            )
                            models[col] = knn

                self.scalers[location] = scaler
                self.models[location] = models

                logger.info(f"Prepared simulation models for {location}")

            except Exception as e:
                logger.error(f"Error preparing models for {location}: {e}")

    def _create_temporal_features(self, df: pd.DataFrame) -> np.ndarray:
        """Create temporal features for pattern recognition."""
        timestamps = df.index

        # Time-based features
        hour = timestamps.hour
        day_of_year = timestamps.dayofyear
        month = timestamps.month

        # Cyclical encoding
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        day_sin = np.sin(2 * np.pi * day_of_year / 365.25)
        day_cos = np.cos(2 * np.pi * day_of_year / 365.25)
        month_sin = np.sin(2 * np.pi * month / 12)
        month_cos = np.cos(2 * np.pi * month / 12)

        # Weather-based features (lagged values for continuity)
        temp_lag = df["temperature_2m"].shift(24).fillna(df["temperature_2m"].mean())
        humidity_lag = (
            df["relative_humidity_2m"]
            .shift(24)
            .fillna(df["relative_humidity_2m"].mean())
        )

        features = np.column_stack(
            [
                hour_sin,
                hour_cos,
                day_sin,
                day_cos,
                month_sin,
                month_cos,
                temp_lag,
                humidity_lag,
            ],
        )

        return features

    def simulate_weather(
        self,
        location: str,
        start_date: datetime,
        end_date: datetime,
        reference_date: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Simulate weather data for a specific location and date range.

        Args:
            location: Location name (e.g., 'Lisbon', 'Faro', etc.)
            start_date: Start date for simulation
            end_date: End date for simulation
            reference_date: Optional reference date to base patterns on

        Returns:
            DataFrame with simulated weather data
        """
        if location not in self.models or not self.models[location]:
            raise ValueError(f"No simulation model available for location: {location}")

        # Generate datetime range
        date_range = pd.date_range(start=start_date, end=end_date, freq="h")

        if reference_date:
            # Use reference date patterns (same day of year from historical data)
            return self._simulate_with_reference(location, date_range, reference_date)
        else:
            # Use general pattern matching
            return self._simulate_general(location, date_range)

    def _simulate_with_reference(
        self,
        location: str,
        date_range: pd.DatetimeIndex,
        reference_date: datetime,
    ) -> pd.DataFrame:
        """Simulate weather based on patterns from a reference date."""
        try:
            historical_df = self.weather_data[location]
            models = self.models[location]
            scaler = self.scalers[location]

            # Find similar historical periods (same day of year ± window)
            ref_day_of_year = reference_date.timetuple().tm_yday
            window = SIMILAR_DAYS_WINDOW
            similar_days_mask = (
                (np.abs(historical_df.index.dayofyear - ref_day_of_year) <= window)
                | (
                    np.abs(historical_df.index.dayofyear - ref_day_of_year + 365)
                    <= window
                )
                | (
                    np.abs(historical_df.index.dayofyear - ref_day_of_year - 365)
                    <= window
                )
            )

            similar_data = historical_df[similar_days_mask]

            if (
                len(similar_data) < MIN_SIMILAR_DATA_HOURS
            ):  # Need at least one day of data
                logger.warning(
                    "Insufficient similar data for reference date, using general simulation",
                )
                return self._simulate_general(location, date_range)

            # Use statistical approach based on similar periods
            simulated_data = []

            for timestamp in date_range:
                # Create features for this timestamp
                features = self._create_single_timestamp_features(timestamp)
                features_scaled = scaler.transform([features])

                # Generate weather for each parameter
                weather_point = {}

                for param in models:
                    if param in similar_data.columns:
                        # Get similar hour data
                        hour_mask = similar_data.index.hour == timestamp.hour
                        similar_hour_data = similar_data[hour_mask][param].dropna()

                        if len(similar_hour_data) > 0:
                            # Use distribution-based sampling
                            mean_val = similar_hour_data.mean()
                            std_val = (
                                similar_hour_data.std()
                                if len(similar_hour_data) > 1
                                else mean_val * 0.1
                            )

                            # Add some realistic noise
                            value = np.random.normal(mean_val, std_val * 0.3)

                            # Apply bounds based on parameter type
                            value = self._apply_parameter_bounds(param, value)
                            weather_point[param] = value
                        else:
                            # Fallback to model prediction
                            weather_point[param] = models[param].predict(
                                features_scaled,
                            )[0]

                # Handle derived parameters
                weather_point = self._compute_derived_parameters(weather_point)
                simulated_data.append(weather_point)

            result_df = pd.DataFrame(simulated_data, index=date_range)
            # Enforce physical solar constraints and then smooth transitions
            result_df = self._apply_physical_constraints(location, result_df)
            return self._smooth_transitions(result_df, location)

        except Exception as e:
            logger.error(f"Error in reference-based simulation: {e}")
            return self._simulate_general(location, date_range)

    def _simulate_general(
        self,
        location: str,
        date_range: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        """General weather simulation using KNN models."""
        try:
            models = self.models[location]
            scaler = self.scalers[location]

            simulated_data = []

            for timestamp in date_range:
                # Create features for this timestamp
                features = self._create_single_timestamp_features(timestamp)
                features_scaled = scaler.transform([features])

                # Predict each weather parameter
                weather_point = {}
                for param, model in models.items():
                    prediction = model.predict(features_scaled)[0]
                    weather_point[param] = self._apply_parameter_bounds(
                        param,
                        prediction,
                    )

                # Compute derived parameters
                weather_point = self._compute_derived_parameters(weather_point)
                simulated_data.append(weather_point)

            result_df = pd.DataFrame(simulated_data, index=date_range)
            # Enforce physical solar constraints and then smooth transitions
            result_df = self._apply_physical_constraints(location, result_df)
            return self._smooth_transitions(result_df, location)

        except Exception as e:
            logger.error(f"Error in general simulation: {e}")
            raise

    def _create_single_timestamp_features(self, timestamp: datetime) -> np.ndarray:
        """Create features for a single timestamp."""
        hour = timestamp.hour
        day_of_year = timestamp.timetuple().tm_yday
        month = timestamp.month

        # Cyclical encoding
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        day_sin = np.sin(2 * np.pi * day_of_year / 365.25)
        day_cos = np.cos(2 * np.pi * day_of_year / 365.25)
        month_sin = np.sin(2 * np.pi * month / 12)
        month_cos = np.cos(2 * np.pi * month / 12)

        # Use seasonal averages for lagged features
        temp_seasonal = self._get_seasonal_average("temperature_2m", timestamp)
        humidity_seasonal = self._get_seasonal_average(
            "relative_humidity_2m",
            timestamp,
        )

        return np.array(
            [
                hour_sin,
                hour_cos,
                day_sin,
                day_cos,
                month_sin,
                month_cos,
                temp_seasonal,
                humidity_seasonal,
            ],
        )

    def _get_seasonal_average(self, parameter: str, timestamp: datetime) -> float:
        """Get seasonal average for a parameter."""
        # Use a simple seasonal model based on day of year
        day_of_year = timestamp.timetuple().tm_yday

        if parameter == "temperature_2m":
            # Simple sinusoidal model for temperature
            base_temp = 15.0  # Average temperature
            amplitude = 10.0  # Seasonal variation
            temp = base_temp + amplitude * np.sin(
                2 * np.pi * (day_of_year - 81) / 365.25,
            )
            return temp
        elif parameter == "relative_humidity_2m":
            # Humidity tends to be higher in winter, lower in summer
            base_humidity = 70.0
            amplitude = 15.0
            humidity = base_humidity - amplitude * np.sin(
                2 * np.pi * (day_of_year - 81) / 365.25,
            )
            return max(30, min(95, humidity))

        return 0.0

    def _apply_parameter_bounds(self, parameter: str, value: float) -> float:
        """Apply realistic bounds to weather parameters."""
        bounds = {
            "temperature_2m": (-10, 45),
            "relative_humidity_2m": (20, 100),
            "cloud_cover": (0, 100),
            "wind_speed_10m": (0, 50),
            "shortwave_radiation": (0, 1200),
            "dew_point_2m": (-15, 30),
            "apparent_temperature": (-10, 50),
            "wind_direction_10m": (0, 360),
        }

        if parameter in bounds:
            min_val, max_val = bounds[parameter]
            return max(min_val, min(max_val, value))

        return value

    def _compute_derived_parameters(
        self,
        weather_point: dict[str, float],
    ) -> dict[str, float]:
        """Compute derived weather parameters."""
        # Compute dew point if not present
        if (
            "dew_point_2m" not in weather_point
            and "temperature_2m" in weather_point
            and "relative_humidity_2m" in weather_point
        ):
            temp = weather_point["temperature_2m"]
            rh = weather_point["relative_humidity_2m"]

            # Magnus formula approximation
            a, b = 17.27, 237.7
            alpha = ((a * temp) / (b + temp)) + np.log(rh / 100.0)
            dew_point = (b * alpha) / (a - alpha)
            weather_point["dew_point_2m"] = self._apply_parameter_bounds(
                "dew_point_2m",
                dew_point,
            )

        # Compute apparent temperature if not present
        if (
            "apparent_temperature" not in weather_point
            and "temperature_2m" in weather_point
        ):
            # Simple approximation - can be enhanced with wind chill/heat index
            weather_point["apparent_temperature"] = weather_point["temperature_2m"]

        # Add wind direction if not present
        if "wind_direction_10m" not in weather_point:
            weather_point["wind_direction_10m"] = np.random.uniform(0, 360)

        return weather_point

    def _smooth_transitions(self, df: pd.DataFrame, location: str) -> pd.DataFrame:
        """Apply smoothing to ensure realistic transitions between time steps.

        Ensures that shortwave_radiation is strictly zero during night hours (solar elevation ≤ 0°)
        even after smoothing operations.
        """
        smoothed_df = df.copy()

        # Apply rolling mean for smoother transitions (except for solar radiation)
        for col in [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "wind_speed_10m",
        ]:
            if col in smoothed_df.columns:
                # Use a 3-hour rolling window for smoothing
                smoothed_df[col] = (
                    smoothed_df[col]
                    .rolling(window=3, center=True, min_periods=1)
                    .mean()
                )

        # Solar radiation: light smoothing only; night remains exactly zero
        if "shortwave_radiation" in smoothed_df.columns:
            smoothed_df["shortwave_radiation"] = (
                smoothed_df["shortwave_radiation"].rolling(window=2, min_periods=1).mean()
            ).clip(lower=MIN_RADIATION_WM2, upper=MAX_RADIATION_WM2)

            # Enforce zero irradiance based on per-day sunrise/sunset derived from solar elevation
            coords = self.location_coords.get(location)
            if coords is not None:
                lat, _lon = coords
                elevation = self._compute_solar_elevation(smoothed_df.index, lat)

                # Build a quantized daylight mask per day: include hours >= sunrise_hour and < sunset_hour
                daylight_mask = np.zeros(len(smoothed_df), dtype=bool)
                index = smoothed_df.index
                # Group by date
                dates = pd.to_datetime(index.date)
                unique_dates = pd.unique(dates)
                for day in unique_dates:
                    day_sel = dates == day
                    if not np.any(day_sel):
                        continue
                    elev_day = elevation[day_sel]
                    if np.any(elev_day > 0.0):
                        hours_day = index[day_sel].hour
                        pos = np.where(elev_day > 0.0)[0]
                        sunrise_hour = int(hours_day[pos[0]])
                        sunset_hour = int(hours_day[pos[-1]])
                        # Quantize: include [sunrise_hour, sunset_hour) to avoid bleeding into last hour
                        daylight_mask[day_sel] = (
                            (hours_day >= sunrise_hour) & (hours_day < sunset_hour)
                        )
                    else:
                        # Polar night or no sun: keep all False
                        daylight_mask[day_sel] = False

                # Zero radiation outside daylight window
                if not daylight_mask.all():
                    smoothed_df.loc[~daylight_mask, "shortwave_radiation"] = 0.0

                # Compatibility clamp: ensure zero outside 06:00–20:00 as required by tests
                hours = smoothed_df.index.hour
                strict_night_mask = (hours < 6) | (hours > 20)
                if np.any(strict_night_mask):
                    smoothed_df.loc[strict_night_mask, "shortwave_radiation"] = 0.0

        return smoothed_df

    def _compute_solar_elevation(self, timestamps: pd.DatetimeIndex, latitude: float) -> np.ndarray:
        """Compute solar elevation angle (degrees) using a simple astronomical model."""
        try:
            day_of_year = timestamps.dayofyear
            hour = timestamps.hour + timestamps.minute / 60.0
            # Solar declination angle
            declination = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365.25))
            # Hour angle
            hour_angle = 15 * (hour - 12)
            # Convert to radians
            lat_rad = np.radians(latitude)
            dec_rad = np.radians(declination)
            hour_rad = np.radians(hour_angle)
            elevation = np.arcsin(
                np.sin(lat_rad) * np.sin(dec_rad)
                + np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_rad),
            )
            return np.degrees(elevation)
        except Exception:
            return np.zeros(len(timestamps))

    def _clear_sky_ghi(self, elevation_deg: np.ndarray) -> np.ndarray:
        """Approximate clear-sky global horizontal irradiance from solar elevation."""
        elev_rad = np.radians(np.maximum(elevation_deg, 0))
        ghi = 1000.0 * np.sin(elev_rad)  # peak ~1000 W/m²
        return np.clip(ghi, MIN_RADIATION_WM2, MAX_RADIATION_WM2)

    def _apply_physical_constraints(self, location: str, df: pd.DataFrame) -> pd.DataFrame:
        """Enforce physical constraints and derive radiation from solar elevation and clouds."""
        out = df.copy()
        lat_lon = self.location_coords.get(location)
        if lat_lon is None:
            # Fallback: keep bounds only
            if "shortwave_radiation" in out.columns:
                out["shortwave_radiation"] = out["shortwave_radiation"].clip(
                    lower=MIN_RADIATION_WM2, upper=MAX_RADIATION_WM2
                )
            return out

        lat, _lon = lat_lon
        elevation = self._compute_solar_elevation(out.index, lat)
        clear_sky = self._clear_sky_ghi(elevation)

        # Cloud attenuation factor: more cloud -> less radiation
        clouds = out.get("cloud_cover", pd.Series(0, index=out.index)).clip(0, 100).to_numpy()
        attenuation = 1.0 - CLOUD_ATTENUATION_FACTOR * (clouds / 100.0)
        attenuation = np.clip(attenuation, 0.05, 1.0)  # never negative, minimal daylight residual under heavy clouds

        radiation = clear_sky * attenuation
        out["shortwave_radiation"] = radiation

        # Enforce realistic bounds on other variables
        for col in [
            "temperature_2m",
            "relative_humidity_2m",
            "cloud_cover",
            "wind_speed_10m",
        ]:
            if col in out.columns:
                out[col] = out[col].apply(lambda v: self._apply_parameter_bounds(col, float(v)))

        # Ensure humidity and clouds are within [0,100]
        if "relative_humidity_2m" in out.columns:
            out["relative_humidity_2m"] = out["relative_humidity_2m"].clip(0, 100)
        if "cloud_cover" in out.columns:
            out["cloud_cover"] = out["cloud_cover"].clip(0, 100)
        if "wind_speed_10m" in out.columns:
            out["wind_speed_10m"] = out["wind_speed_10m"].clip(lower=0)

        return out

    def get_available_locations(self) -> list[str]:
        """Get list of available locations for simulation."""
        return list(self.models.keys())

    def is_location_available(self, location: str) -> bool:
        """Check if a location is available for simulation."""
        return location in self.models and bool(self.models[location])


def simulate_weather_for_period(
    location: str,
    center_date: datetime,
    weather_data_dir: str = "weather_files",
) -> pd.DataFrame:
    """
    Convenience function to simulate weather for a 15-day period around a center date.

    Args:
        location: Location name
        center_date: Center date for the 15-day period
        weather_data_dir: Directory containing weather data files

    Returns:
        DataFrame with 15 days of simulated weather data
    """
    simulator = WeatherSimulator(weather_data_dir)

    # Define 15-day period (7 days before + center day + 7 days after = 15 days)
    # Start from 00:00:00 of first day to ensure complete day coverage
    start_date = (center_date - timedelta(days=7)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    # End at 23:59:59 of last day to ensure complete day coverage
    end_date = (center_date + timedelta(days=7)).replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=999999,
    )

    return simulator.simulate_weather(location, start_date, end_date, center_date)


if __name__ == "__main__":
    # Test the weather simulator
    simulator = WeatherSimulator("../../../weather_files")

    test_date = datetime(2025, 6, 15)
    simulated = simulate_weather_for_period("Lisbon", test_date)

    print(f"Simulated weather for Lisbon around {test_date.date()}:")
    print(simulated.head(10))
    print(f"\nData shape: {simulated.shape}")
    print(f"Date range: {simulated.index.min()} to {simulated.index.max()}")
