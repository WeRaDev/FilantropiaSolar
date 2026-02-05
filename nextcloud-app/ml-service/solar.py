"""
Solar Position Calculator

Direct port from FilantropiaSolar v1.2.x comprehensive_data_processor.py.
Calculates solar elevation angle for energy prediction.
"""

import numpy as np
from datetime import datetime
from typing import List, Tuple

# Solar calculation constants (from v1.2.x)
SOLAR_DECLINATION_AMPLITUDE = 23.45  # degrees
DAYS_IN_YEAR = 365.25
SOLAR_DECLINATION_OFFSET = 284
HOUR_ANGLE_MULTIPLIER = 15  # degrees per hour
SOLAR_NOON = 12


def calculate_solar_elevation(
    timestamp: datetime,
    latitude: float,
    longitude: float,
) -> float:
    """
    Calculate solar elevation angle for given time and location.
    
    The solar elevation angle is the angle between the sun and the horizon.
    Positive values indicate the sun is above the horizon.
    
    Args:
        timestamp: UTC datetime
        latitude: Latitude in degrees (-90 to 90)
        longitude: Longitude in degrees (-180 to 180)
        
    Returns:
        Solar elevation angle in degrees (0 = horizon, 90 = directly overhead)
    """
    day_of_year = timestamp.timetuple().tm_yday
    hour = timestamp.hour + timestamp.minute / 60
    
    # Adjust for longitude (approximate local solar time)
    # Each 15 degrees of longitude = 1 hour time difference
    solar_time_offset = longitude / 15
    local_solar_hour = hour + solar_time_offset
    
    # Solar declination (angle between sun and equator plane)
    # Varies from -23.45 (winter solstice) to +23.45 (summer solstice)
    declination = SOLAR_DECLINATION_AMPLITUDE * np.sin(
        np.radians(360 / DAYS_IN_YEAR * (day_of_year + SOLAR_DECLINATION_OFFSET))
    )
    
    # Hour angle (sun's position relative to local solar noon)
    # Negative in morning, zero at noon, positive in afternoon
    hour_angle = HOUR_ANGLE_MULTIPLIER * (local_solar_hour - SOLAR_NOON)
    
    # Convert to radians for trigonometry
    lat_rad = np.radians(latitude)
    dec_rad = np.radians(declination)
    ha_rad = np.radians(hour_angle)
    
    # Solar elevation formula
    # sin(elevation) = sin(lat)*sin(dec) + cos(lat)*cos(dec)*cos(hour_angle)
    sin_elevation = (
        np.sin(lat_rad) * np.sin(dec_rad) +
        np.cos(lat_rad) * np.cos(dec_rad) * np.cos(ha_rad)
    )
    
    # Convert to degrees and clamp to valid range
    elevation = np.degrees(np.arcsin(np.clip(sin_elevation, -1, 1)))
    
    # Solar elevation cannot be below horizon for our purposes
    return max(0.0, elevation)


def calculate_solar_elevations_batch(
    timestamps: List[datetime],
    latitude: float,
    longitude: float,
) -> List[float]:
    """
    Calculate solar elevation for multiple timestamps efficiently.
    
    Args:
        timestamps: List of UTC datetimes
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        
    Returns:
        List of solar elevation angles in degrees
    """
    return [
        calculate_solar_elevation(ts, latitude, longitude)
        for ts in timestamps
    ]


def calculate_sunrise_sunset(
    date: datetime,
    latitude: float,
    longitude: float,
) -> Tuple[float, float]:
    """
    Calculate approximate sunrise and sunset hours for a given date and location.
    
    Args:
        date: Date to calculate for
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        
    Returns:
        Tuple of (sunrise_hour, sunset_hour) in local solar time
    """
    day_of_year = date.timetuple().tm_yday
    
    # Solar declination
    declination = SOLAR_DECLINATION_AMPLITUDE * np.sin(
        np.radians(360 / DAYS_IN_YEAR * (day_of_year + SOLAR_DECLINATION_OFFSET))
    )
    
    lat_rad = np.radians(latitude)
    dec_rad = np.radians(declination)
    
    # Hour angle at sunrise/sunset (when elevation = 0)
    # cos(hour_angle) = -tan(lat)*tan(dec)
    cos_hour_angle = -np.tan(lat_rad) * np.tan(dec_rad)
    
    # Clamp for polar regions
    cos_hour_angle = np.clip(cos_hour_angle, -1, 1)
    
    hour_angle_sunrise = np.degrees(np.arccos(cos_hour_angle))
    
    # Convert hour angle to hours
    hours_from_noon = hour_angle_sunrise / HOUR_ANGLE_MULTIPLIER
    
    sunrise = SOLAR_NOON - hours_from_noon
    sunset = SOLAR_NOON + hours_from_noon
    
    return sunrise, sunset


def get_daylight_hours(
    date: datetime,
    latitude: float,
    longitude: float,
) -> float:
    """
    Calculate total daylight hours for a given date and location.
    
    Args:
        date: Date to calculate for
        latitude: Latitude in degrees
        longitude: Longitude in degrees
        
    Returns:
        Number of daylight hours
    """
    sunrise, sunset = calculate_sunrise_sunset(date, latitude, longitude)
    return max(0, sunset - sunrise)
