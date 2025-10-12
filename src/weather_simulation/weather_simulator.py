"""
Weather Simulator Module

Generates synthetic weather data based on historical patterns for dates not available in the dataset.
Inspired by SolarSim methodology for weather simulation.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsRegressor
from scipy.stats import norm
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class WeatherSimulator:
    """
    Weather simulator that generates synthetic weather data based on historical patterns.
    
    Uses k-nearest neighbors approach with seasonal and daily pattern recognition
    to generate realistic weather forecasts for dates not in historical data.
    """
    
    def __init__(self, weather_data_dir: str):
        """Initialize the weather simulator with historical weather data."""
        self.weather_data_dir = Path(weather_data_dir)
        self.weather_data = {}
        self.location_mapping = {
            'Lisbon': 'Lisbon_weather.csv',
            'Setubal': 'Setubal_weather.csv',
            'Faro': 'Faro_weather.csv',
            'Braga': 'Braga_weather.csv',
            'Tavira': 'Tavira_weather.csv',
            'Loule': 'Loule_weather.csv'
        }
        self.scalers = {}
        self.models = {}
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
                    df['datetime'] = pd.to_datetime(df['time'])
                    df = df.set_index('datetime')
                    
                    # Clean column names
                    df.columns = [col.split(' (')[0] if ' (' in col else col for col in df.columns]
                    
                    # Ensure we have required columns
                    required_cols = ['temperature_2m', 'relative_humidity_2m', 'dew_point_2m', 
                                   'apparent_temperature', 'cloud_cover', 'wind_speed_10m', 
                                   'wind_direction_10m', 'shortwave_radiation']
                    
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        logger.warning(f"Missing columns for {location}: {missing_cols}")
                        continue
                        
                    self.weather_data[location] = df[required_cols].copy()
                    logger.info(f"Loaded weather data for {location}: {len(df)} records")
                    
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
                targets = df[['temperature_2m', 'relative_humidity_2m', 'cloud_cover', 
                            'wind_speed_10m', 'shortwave_radiation']].copy()
                
                # Remove invalid data
                mask = np.isfinite(features).all(axis=1) & np.isfinite(targets).all(axis=1)
                features = features[mask]
                targets = targets[mask]
                
                if len(features) < 100:  # Need minimum data
                    logger.warning(f"Insufficient data for {location}: {len(features)} records")
                    continue
                
                # Scale features
                scaler = StandardScaler()
                features_scaled = scaler.fit_transform(features)
                
                # Create KNN model for each weather parameter
                models = {}
                for col in targets.columns:
                    if targets[col].notna().sum() > 50:  # Minimum valid data points
                        knn = KNeighborsRegressor(n_neighbors=min(10, len(features)//10), weights='distance')
                        valid_mask = targets[col].notna()
                        if valid_mask.sum() > 10:
                            knn.fit(features_scaled[valid_mask], targets[col][valid_mask])
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
        temp_lag = df['temperature_2m'].shift(24).fillna(df['temperature_2m'].mean())
        humidity_lag = df['relative_humidity_2m'].shift(24).fillna(df['relative_humidity_2m'].mean())
        
        features = np.column_stack([
            hour_sin, hour_cos, day_sin, day_cos, month_sin, month_cos,
            temp_lag, humidity_lag
        ])
        
        return features
        
    def simulate_weather(self, location: str, start_date: datetime, end_date: datetime, 
                        reference_date: Optional[datetime] = None) -> pd.DataFrame:
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
        date_range = pd.date_range(start=start_date, end=end_date, freq='H')
        
        if reference_date:
            # Use reference date patterns (same day of year from historical data)
            return self._simulate_with_reference(location, date_range, reference_date)
        else:
            # Use general pattern matching
            return self._simulate_general(location, date_range)
            
    def _simulate_with_reference(self, location: str, date_range: pd.DatetimeIndex, 
                               reference_date: datetime) -> pd.DataFrame:
        """Simulate weather based on patterns from a reference date."""
        try:
            historical_df = self.weather_data[location]
            models = self.models[location]
            scaler = self.scalers[location]
            
            # Find similar historical periods (same day of year ± 15 days)
            ref_day_of_year = reference_date.timetuple().tm_yday
            similar_days_mask = (
                np.abs(historical_df.index.dayofyear - ref_day_of_year) <= 15
            ) | (
                np.abs(historical_df.index.dayofyear - ref_day_of_year + 365) <= 15
            ) | (
                np.abs(historical_df.index.dayofyear - ref_day_of_year - 365) <= 15
            )
            
            similar_data = historical_df[similar_days_mask]
            
            if len(similar_data) < 24:  # Need at least one day of data
                logger.warning(f"Insufficient similar data for reference date, using general simulation")
                return self._simulate_general(location, date_range)
            
            # Use statistical approach based on similar periods
            simulated_data = []
            
            for timestamp in date_range:
                # Create features for this timestamp
                features = self._create_single_timestamp_features(timestamp)
                features_scaled = scaler.transform([features])
                
                # Generate weather for each parameter
                weather_point = {}
                
                for param in models.keys():
                    if param in similar_data.columns:
                        # Get similar hour data
                        hour_mask = similar_data.index.hour == timestamp.hour
                        similar_hour_data = similar_data[hour_mask][param].dropna()
                        
                        if len(similar_hour_data) > 0:
                            # Use distribution-based sampling
                            mean_val = similar_hour_data.mean()
                            std_val = similar_hour_data.std() if len(similar_hour_data) > 1 else mean_val * 0.1
                            
                            # Add some realistic noise
                            value = np.random.normal(mean_val, std_val * 0.3)
                            
                            # Apply bounds based on parameter type
                            value = self._apply_parameter_bounds(param, value)
                            weather_point[param] = value
                        else:
                            # Fallback to model prediction
                            weather_point[param] = models[param].predict(features_scaled)[0]
                
                # Handle derived parameters
                weather_point = self._compute_derived_parameters(weather_point)
                simulated_data.append(weather_point)
            
            result_df = pd.DataFrame(simulated_data, index=date_range)
            return self._smooth_transitions(result_df)
            
        except Exception as e:
            logger.error(f"Error in reference-based simulation: {e}")
            return self._simulate_general(location, date_range)
            
    def _simulate_general(self, location: str, date_range: pd.DatetimeIndex) -> pd.DataFrame:
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
                    weather_point[param] = self._apply_parameter_bounds(param, prediction)
                
                # Compute derived parameters
                weather_point = self._compute_derived_parameters(weather_point)
                simulated_data.append(weather_point)
            
            result_df = pd.DataFrame(simulated_data, index=date_range)
            return self._smooth_transitions(result_df)
            
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
        temp_seasonal = self._get_seasonal_average('temperature_2m', timestamp)
        humidity_seasonal = self._get_seasonal_average('relative_humidity_2m', timestamp)
        
        return np.array([hour_sin, hour_cos, day_sin, day_cos, month_sin, month_cos,
                        temp_seasonal, humidity_seasonal])
        
    def _get_seasonal_average(self, parameter: str, timestamp: datetime) -> float:
        """Get seasonal average for a parameter."""
        # Use a simple seasonal model based on day of year
        day_of_year = timestamp.timetuple().tm_yday
        
        if parameter == 'temperature_2m':
            # Simple sinusoidal model for temperature
            base_temp = 15.0  # Average temperature
            amplitude = 10.0  # Seasonal variation
            temp = base_temp + amplitude * np.sin(2 * np.pi * (day_of_year - 81) / 365.25)
            return temp
        elif parameter == 'relative_humidity_2m':
            # Humidity tends to be higher in winter, lower in summer
            base_humidity = 70.0
            amplitude = 15.0
            humidity = base_humidity - amplitude * np.sin(2 * np.pi * (day_of_year - 81) / 365.25)
            return max(30, min(95, humidity))
        
        return 0.0
        
    def _apply_parameter_bounds(self, parameter: str, value: float) -> float:
        """Apply realistic bounds to weather parameters."""
        bounds = {
            'temperature_2m': (-10, 45),
            'relative_humidity_2m': (20, 100),
            'cloud_cover': (0, 100),
            'wind_speed_10m': (0, 50),
            'shortwave_radiation': (0, 1200),
            'dew_point_2m': (-15, 30),
            'apparent_temperature': (-10, 50),
            'wind_direction_10m': (0, 360)
        }
        
        if parameter in bounds:
            min_val, max_val = bounds[parameter]
            return max(min_val, min(max_val, value))
            
        return value
        
    def _compute_derived_parameters(self, weather_point: Dict[str, float]) -> Dict[str, float]:
        """Compute derived weather parameters."""
        # Compute dew point if not present
        if 'dew_point_2m' not in weather_point and 'temperature_2m' in weather_point and 'relative_humidity_2m' in weather_point:
            temp = weather_point['temperature_2m']
            rh = weather_point['relative_humidity_2m']
            
            # Magnus formula approximation
            a, b = 17.27, 237.7
            alpha = ((a * temp) / (b + temp)) + np.log(rh / 100.0)
            dew_point = (b * alpha) / (a - alpha)
            weather_point['dew_point_2m'] = self._apply_parameter_bounds('dew_point_2m', dew_point)
        
        # Compute apparent temperature if not present
        if 'apparent_temperature' not in weather_point and 'temperature_2m' in weather_point:
            # Simple approximation - can be enhanced with wind chill/heat index
            weather_point['apparent_temperature'] = weather_point['temperature_2m']
            
        # Add wind direction if not present
        if 'wind_direction_10m' not in weather_point:
            weather_point['wind_direction_10m'] = np.random.uniform(0, 360)
            
        return weather_point
        
    def _smooth_transitions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply smoothing to ensure realistic transitions between time steps."""
        smoothed_df = df.copy()
        
        # Apply rolling mean for smoother transitions (except for solar radiation)
        for col in ['temperature_2m', 'relative_humidity_2m', 'cloud_cover', 'wind_speed_10m']:
            if col in smoothed_df.columns:
                # Use a 3-hour rolling window for smoothing
                smoothed_df[col] = smoothed_df[col].rolling(window=3, center=True, min_periods=1).mean()
        
        # Solar radiation should have more natural daily patterns
        if 'shortwave_radiation' in smoothed_df.columns:
            # Ensure nighttime values are zero or very low
            night_mask = (smoothed_df.index.hour < 6) | (smoothed_df.index.hour > 19)
            smoothed_df.loc[night_mask, 'shortwave_radiation'] = np.random.uniform(0, 10, night_mask.sum())
            
            # Apply gentle smoothing to daytime values
            day_mask = ~night_mask
            if day_mask.sum() > 0:
                smoothed_df.loc[day_mask, 'shortwave_radiation'] = (
                    smoothed_df.loc[day_mask, 'shortwave_radiation']
                    .rolling(window=2, min_periods=1).mean()
                )
        
        return smoothed_df
        
    def get_available_locations(self) -> List[str]:
        """Get list of available locations for simulation."""
        return list(self.models.keys())
        
    def is_location_available(self, location: str) -> bool:
        """Check if a location is available for simulation."""
        return location in self.models and bool(self.models[location])


def simulate_weather_for_period(location: str, center_date: datetime, 
                              weather_data_dir: str = "weather_files") -> pd.DataFrame:
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
    
    start_date = center_date - timedelta(days=7)
    end_date = center_date + timedelta(days=7)
    
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