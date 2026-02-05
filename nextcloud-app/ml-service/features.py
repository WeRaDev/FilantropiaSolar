"""
Feature Engineering Module

Direct port from FilantropiaSolar v1.2.x enhanced_energy_predictor.py.
Implements the exact 26-feature engineering pipeline for ML model compatibility.
"""

import numpy as np
import pandas as pd
from typing import List

# Base features (9) - raw weather data
BASE_FEATURES: List[str] = [
    "temperature_2m",
    "relative_humidity_2m",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
    "hour",
    "day_of_year",
    "month",
    "solar_elevation",
]

# Enhanced features (17) - engineered from base
ENHANCED_FEATURES: List[str] = [
    # Rolling averages (3)
    "temp_rolling_avg",
    "temp_rolling_std",
    "radiation_rolling_avg",
    # Seasonal patterns (4)
    "seasonal_sin_1",
    "seasonal_cos_1",
    "seasonal_sin_2",
    "seasonal_cos_2",
    # Weather interactions (6)
    "temp_cloud_interaction",
    "radiation_cloud_interaction",
    "temp_humidity_interaction",
    "wind_temp_interaction",
    "radiation_humidity_interaction",
    "cloud_wind_interaction",
    # Power transformations (1)
    "radiation_sqrt",
    # Time-based indicators (3)
    "peak_sun_indicator",
    "morning_ramp",
    "evening_ramp",
]

# Complete feature list in exact order expected by models
ALL_FEATURES: List[str] = BASE_FEATURES + ENHANCED_FEATURES

# Rolling window size for temporal features
ROLLING_WINDOW_HOURS = 24


def enhance_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply identical feature engineering as v1.2.x training pipeline.
    
    This function MUST produce features in the exact same order and with
    the same calculations as the training code to ensure model compatibility.
    
    Args:
        df: DataFrame with base weather columns and datetime index
        
    Returns:
        DataFrame with all 26 features in correct order
    """
    enhanced = df.copy()
    
    # Ensure datetime index
    if not isinstance(enhanced.index, pd.DatetimeIndex):
        if 'timestamp' in enhanced.columns:
            enhanced['timestamp'] = pd.to_datetime(enhanced['timestamp'])
            enhanced = enhanced.set_index('timestamp')
        else:
            raise ValueError("DataFrame must have datetime index or 'timestamp' column")
    
    # Extract time components if not present
    if 'hour' not in enhanced.columns:
        enhanced['hour'] = enhanced.index.hour
    if 'day_of_year' not in enhanced.columns:
        enhanced['day_of_year'] = enhanced.index.dayofyear
    if 'month' not in enhanced.columns:
        enhanced['month'] = enhanced.index.month
    
    # Rolling statistics (24-hour window)
    enhanced['temp_rolling_avg'] = (
        enhanced['temperature_2m']
        .rolling(ROLLING_WINDOW_HOURS, min_periods=1)
        .mean()
    )
    enhanced['temp_rolling_std'] = (
        enhanced['temperature_2m']
        .rolling(ROLLING_WINDOW_HOURS, min_periods=1)
        .std()
        .fillna(0)
    )
    enhanced['radiation_rolling_avg'] = (
        enhanced['shortwave_radiation']
        .rolling(ROLLING_WINDOW_HOURS, min_periods=1)
        .mean()
    )
    
    # Seasonal patterns (Fourier components for yearly cycle)
    day_of_year = enhanced.index.dayofyear
    enhanced['seasonal_sin_1'] = np.sin(2 * np.pi * day_of_year / 365.25)
    enhanced['seasonal_cos_1'] = np.cos(2 * np.pi * day_of_year / 365.25)
    enhanced['seasonal_sin_2'] = np.sin(4 * np.pi * day_of_year / 365.25)
    enhanced['seasonal_cos_2'] = np.cos(4 * np.pi * day_of_year / 365.25)
    
    # Weather interactions - capture non-linear relationships
    enhanced['temp_cloud_interaction'] = (
        enhanced['temperature_2m'] * enhanced['cloud_cover'] / 100
    )
    enhanced['radiation_cloud_interaction'] = (
        enhanced['shortwave_radiation'] * (1 - enhanced['cloud_cover'] / 100)
    )
    enhanced['temp_humidity_interaction'] = (
        enhanced['temperature_2m'] * enhanced['relative_humidity_2m'] / 100
    )
    enhanced['wind_temp_interaction'] = (
        enhanced['wind_speed_10m'] * enhanced['temperature_2m']
    )
    enhanced['radiation_humidity_interaction'] = (
        enhanced['shortwave_radiation'] * (1 - enhanced['relative_humidity_2m'] / 100)
    )
    enhanced['cloud_wind_interaction'] = (
        enhanced['cloud_cover'] * enhanced['wind_speed_10m'] / 100
    )
    
    # Power transformation for radiation (captures diminishing returns)
    enhanced['radiation_sqrt'] = np.sqrt(
        enhanced['shortwave_radiation'].clip(lower=0)
    )
    
    # Time-based indicators
    hour = enhanced.index.hour
    enhanced['peak_sun_indicator'] = ((hour >= 10) & (hour <= 14)).astype(float)
    enhanced['morning_ramp'] = np.where(hour < 12, hour / 12, 0)
    enhanced['evening_ramp'] = np.where(hour >= 12, (24 - hour) / 12, 0)
    
    # Return only the features in correct order
    return enhanced[ALL_FEATURES]


def prepare_features_for_prediction(
    weather_data: List[dict],
    solar_elevations: List[float],
) -> pd.DataFrame:
    """
    Prepare weather data for prediction by applying full feature engineering.
    
    Args:
        weather_data: List of hourly weather dictionaries from Open-Meteo
        solar_elevations: Pre-calculated solar elevation angles
        
    Returns:
        DataFrame ready for model prediction with 26 features
    """
    # Create DataFrame from weather data
    df = pd.DataFrame(weather_data)
    
    # Parse timestamps
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')
    
    # Add solar elevation
    df['solar_elevation'] = solar_elevations
    
    # Apply feature engineering
    return enhance_features(df)


def align_features_to_training(
    features_df: pd.DataFrame,
    expected_features: List[str],
) -> pd.DataFrame:
    """
    Align feature DataFrame to match exact training feature order.
    
    Handles missing features by filling with zeros and reorders columns.
    This ensures compatibility with models trained on different feature subsets.
    
    Args:
        features_df: DataFrame with computed features
        expected_features: List of feature names in expected order
        
    Returns:
        DataFrame with features aligned to expected order
    """
    aligned = features_df.copy()
    
    # Add missing features with zeros
    for col in expected_features:
        if col not in aligned.columns:
            aligned[col] = 0.0
    
    # Reorder to match expected
    return aligned[expected_features]
