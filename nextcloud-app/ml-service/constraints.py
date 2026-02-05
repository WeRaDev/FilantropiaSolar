"""
Physical Constraints Module

Direct port from FilantropiaSolar v1.2.x.
Enforces physical plausibility on ML predictions.
"""

import numpy as np
from typing import Optional

# Physical constraint constants (from v1.2.x)
PRODUCTION_RADIATION_THRESHOLD = 20.0  # W/m2 - minimum radiation for production
MIN_RADIATION_WM2 = 0.0
MAX_RADIATION_WM2 = 1200.0  # Maximum realistic solar radiation

# Cloud attenuation
CLOUD_ATTENUATION_FACTOR = 0.75  # Maximum cloud attenuation effect

# Temperature effects
MIN_PANEL_EFFICIENCY_TEMP = -10  # Celsius
MAX_PANEL_EFFICIENCY_TEMP = 45   # Celsius
TEMP_COEFFICIENT = -0.004  # 0.4% efficiency loss per degree above 25C
REFERENCE_TEMP = 25  # Celsius


def enforce_physical_constraints(
    predictions: np.ndarray,
    radiation: np.ndarray,
    cloud_cover: Optional[np.ndarray] = None,
    temperature: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Enforce physical plausibility on energy production predictions.
    
    Rules:
    1. No production when radiation is below threshold
    2. Predictions must be non-negative
    3. Optional cloud and temperature adjustments
    
    Args:
        predictions: Raw model predictions (kWh)
        radiation: Solar radiation values (W/m2)
        cloud_cover: Optional cloud cover percentages (0-100)
        temperature: Optional temperature values (Celsius)
        
    Returns:
        Physically constrained predictions
    """
    constrained = predictions.copy()
    
    # Rule 1: Zero production when radiation is below threshold
    low_radiation_mask = radiation < PRODUCTION_RADIATION_THRESHOLD
    constrained[low_radiation_mask] = 0.0
    
    # Rule 2: Non-negative predictions
    constrained = np.clip(constrained, 0, None)
    
    # Rule 3: Apply cloud attenuation if provided
    if cloud_cover is not None:
        # High cloud cover reduces production
        # At 100% cloud cover, reduce by CLOUD_ATTENUATION_FACTOR
        cloud_factor = 1 - (cloud_cover / 100) * CLOUD_ATTENUATION_FACTOR
        cloud_factor = np.clip(cloud_factor, 1 - CLOUD_ATTENUATION_FACTOR, 1)
        # Only apply to positive predictions
        constrained = constrained * cloud_factor
    
    # Rule 4: Temperature derating if provided
    if temperature is not None:
        # Panels lose efficiency at high temperatures
        temp_delta = temperature - REFERENCE_TEMP
        temp_factor = 1 + TEMP_COEFFICIENT * np.clip(temp_delta, 0, None)
        temp_factor = np.clip(temp_factor, 0.7, 1.1)  # Reasonable bounds
        constrained = constrained * temp_factor
    
    return constrained


def validate_weather_data(
    radiation: np.ndarray,
    temperature: np.ndarray,
    cloud_cover: np.ndarray,
    humidity: np.ndarray,
) -> dict:
    """
    Validate weather data for physical plausibility.
    
    Returns:
        Dictionary with validation results and warnings
    """
    warnings = []
    
    # Check radiation bounds
    if np.any(radiation < MIN_RADIATION_WM2):
        warnings.append("Negative radiation values detected - clipping to 0")
        radiation = np.clip(radiation, MIN_RADIATION_WM2, None)
    
    if np.any(radiation > MAX_RADIATION_WM2):
        warnings.append(f"Radiation exceeds {MAX_RADIATION_WM2} W/m2 - clipping")
        radiation = np.clip(radiation, None, MAX_RADIATION_WM2)
    
    # Check cloud cover bounds
    if np.any((cloud_cover < 0) | (cloud_cover > 100)):
        warnings.append("Cloud cover outside 0-100% range - clipping")
        cloud_cover = np.clip(cloud_cover, 0, 100)
    
    # Check humidity bounds
    if np.any((humidity < 0) | (humidity > 100)):
        warnings.append("Humidity outside 0-100% range - clipping")
        humidity = np.clip(humidity, 0, 100)
    
    return {
        "valid": len(warnings) == 0,
        "warnings": warnings,
        "corrected": {
            "radiation": radiation,
            "temperature": temperature,
            "cloud_cover": cloud_cover,
            "humidity": humidity,
        }
    }


def calculate_theoretical_max(
    capacity_kwp: float,
    radiation: np.ndarray,
    panel_efficiency: float = 0.18,
) -> np.ndarray:
    """
    Calculate theoretical maximum production for validation.
    
    Args:
        capacity_kwp: Installation capacity in kWp
        radiation: Solar radiation values (W/m2)
        panel_efficiency: Panel efficiency factor (default 18%)
        
    Returns:
        Theoretical maximum production per hour (kWh)
    """
    # Convert W/m2 to kWh/m2 (1 hour period)
    # Then scale by capacity
    # Standard test conditions: 1000 W/m2 = 1 kWp output
    theoretical = (radiation / 1000) * capacity_kwp * panel_efficiency / 0.18
    return np.clip(theoretical, 0, None)
