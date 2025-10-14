"""
Weather API Client for FilantropiaSolar
Provides weather data retrieval for current and forecast conditions
"""

from datetime import datetime, timedelta
import logging

import pandas as pd
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherClient:
    """Weather API client for retrieving current and forecast weather data"""

    def __init__(self, api_key=None):
        """
        Initialize Weather Client

        Args:
            api_key (str): API key for weather service
        """
        self.api_key = api_key
        self.base_url = "https://api.open-meteo.com/v1"
        self.lisbon_coordinates = {"latitude": 38.7223, "longitude": -9.1393}

    def get_current_weather(self):
        """
        Get current weather data for Lisbon

        Returns:
            dict: Current weather conditions
        """
        try:
            url = f"{self.base_url}/forecast"
            params = {
                "latitude": self.lisbon_coordinates["latitude"],
                "longitude": self.lisbon_coordinates["longitude"],
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                ],
                "timezone": "Europe/Lisbon",
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            current = data.get("current", {})

            return {
                "time": current.get("time", datetime.now().isoformat()),
                "temperature_2m": current.get("temperature_2m", 0),
                "relative_humidity_2m": current.get("relative_humidity_2m", 0),
                "apparent_temperature": current.get("apparent_temperature", 0),
                "cloud_cover": current.get("cloud_cover", 0),
                "wind_speed_10m": current.get("wind_speed_10m", 0),
                "wind_direction_10m": current.get("wind_direction_10m", 0),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching current weather: {e}")
            return self._get_default_weather()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return self._get_default_weather()

    def get_weather_forecast(self, days_ahead=7):
        """
        Get weather forecast for Lisbon

        Args:
            days_ahead (int): Number of days to forecast

        Returns:
            pd.DataFrame: Weather forecast data
        """
        try:
            end_date = datetime.now() + timedelta(days=days_ahead)

            url = f"{self.base_url}/forecast"
            params = {
                "latitude": self.lisbon_coordinates["latitude"],
                "longitude": self.lisbon_coordinates["longitude"],
                "hourly": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "dew_point_2m",
                    "apparent_temperature",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "shortwave_radiation",
                ],
                "end_date": end_date.strftime("%Y-%m-%d"),
                "timezone": "Europe/Lisbon",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            hourly = data.get("hourly", {})

            # Create DataFrame with proper column names
            df = pd.DataFrame(
                {
                    "time": pd.to_datetime(hourly.get("time", [])),
                    "temperature_2m (°C)": hourly.get("temperature_2m", []),
                    "relative_humidity_2m (%)": hourly.get("relative_humidity_2m", []),
                    "dew_point_2m (°C)": hourly.get("dew_point_2m", []),
                    "apparent_temperature (°C)": hourly.get("apparent_temperature", []),
                    "cloud_cover (%)": hourly.get("cloud_cover", []),
                    "wind_speed_10m (km/h)": hourly.get("wind_speed_10m", []),
                    "wind_direction_10m (°)": hourly.get("wind_direction_10m", []),
                    "shortwave_radiation (W/m²)": hourly.get("shortwave_radiation", []),
                }
            )

            if df.empty:
                return self._get_default_forecast_df(days_ahead)

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching weather forecast: {e}")
            return self._get_default_forecast_df(days_ahead)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return self._get_default_forecast_df(days_ahead)

    def get_historical_weather(self, start_date, end_date):
        """
        Get historical weather data for Lisbon

        Args:
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format

        Returns:
            pd.DataFrame: Historical weather data
        """
        try:
            url = f"{self.base_url}/archive"
            params = {
                "latitude": self.lisbon_coordinates["latitude"],
                "longitude": self.lisbon_coordinates["longitude"],
                "start_date": start_date,
                "end_date": end_date,
                "hourly": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "dew_point_2m",
                    "apparent_temperature",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "shortwave_radiation",
                ],
                "timezone": "Europe/Lisbon",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            hourly = data.get("hourly", {})

            # Create DataFrame with proper column names
            df = pd.DataFrame(
                {
                    "time": pd.to_datetime(hourly.get("time", [])),
                    "temperature_2m (°C)": hourly.get("temperature_2m", []),
                    "relative_humidity_2m (%)": hourly.get("relative_humidity_2m", []),
                    "dew_point_2m (°C)": hourly.get("dew_point_2m", []),
                    "apparent_temperature (°C)": hourly.get("apparent_temperature", []),
                    "cloud_cover (%)": hourly.get("cloud_cover", []),
                    "wind_speed_10m (km/h)": hourly.get("wind_speed_10m", []),
                    "wind_direction_10m (°)": hourly.get("wind_direction_10m", []),
                    "shortwave_radiation (W/m²)": hourly.get("shortwave_radiation", []),
                }
            )

            return df

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching historical weather: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return pd.DataFrame()

    def get_weather_for_date_range(self, target_date, days_before=7, days_after=7):
        """
        Get weather data for a specific date range (target_date ± days)

        Args:
            target_date (str or datetime): Target date
            days_before (int): Days before target date
            days_after (int): Days after target date

        Returns:
            pd.DataFrame: Weather data for the date range
        """
        if isinstance(target_date, str):
            target_date = datetime.strptime(target_date, "%Y-%m-%d")

        start_date = (target_date - timedelta(days=days_before)).strftime("%Y-%m-%d")
        end_date = (target_date + timedelta(days=days_after)).strftime("%Y-%m-%d")

        # Check if we need historical, current, or forecast data
        today = datetime.now().date()
        target_date_only = target_date.date()

        if end_date <= today.strftime("%Y-%m-%d"):
            # All historical
            return self.get_historical_weather(start_date, end_date)
        elif start_date >= today.strftime("%Y-%m-%d"):
            # All forecast
            days_ahead = (datetime.strptime(end_date, "%Y-%m-%d").date() - today).days
            return self.get_weather_forecast(days_ahead)
        else:
            # Mixed: combine historical and forecast
            historical_end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            historical_df = self.get_historical_weather(start_date, historical_end)

            days_ahead = (
                datetime.strptime(end_date, "%Y-%m-%d").date() - today
            ).days + 1
            forecast_df = self.get_weather_forecast(days_ahead)

            # Filter forecast to start from today
            forecast_df = forecast_df[forecast_df["time"].dt.date >= today]

            # Combine dataframes
            if not historical_df.empty and not forecast_df.empty:
                combined_df = pd.concat([historical_df, forecast_df], ignore_index=True)
                return combined_df
            elif not historical_df.empty:
                return historical_df
            else:
                return forecast_df

    def _get_default_weather(self):
        """Return default weather data when API fails"""
        return {
            "time": datetime.now().isoformat(),
            "temperature_2m (°C)": 20.0,
            "relative_humidity_2m (%)": 60.0,
            "dew_point_2m (°C)": 15.0,
            "apparent_temperature (°C)": 20.0,
            "cloud_cover (%)": 50.0,
            "wind_speed_10m (km/h)": 10.0,
            "wind_direction_10m (°)": 180.0,
            "shortwave_radiation (W/m²)": 200.0,
        }

    def _get_default_forecast_df(self, days_ahead):
        """Return default forecast DataFrame when API fails"""
        dates = pd.date_range(start=datetime.now(), periods=days_ahead * 24, freq="h")
        return pd.DataFrame(
            {
                "time": dates,
                "temperature_2m (°C)": [20.0] * len(dates),
                "relative_humidity_2m (%)": [60.0] * len(dates),
                "dew_point_2m (°C)": [15.0] * len(dates),
                "apparent_temperature (°C)": [20.0] * len(dates),
                "cloud_cover (%)": [50.0] * len(dates),
                "wind_speed_10m (km/h)": [10.0] * len(dates),
                "wind_direction_10m (°)": [180.0] * len(dates),
                "shortwave_radiation (W/m²)": [
                    200.0 if 8 <= date.hour <= 18 else 0.0 for date in dates
                ],
            }
        )

    def get_weather_data(self, location=None, start_date=None, end_date=None):
        """
        Generic weather data retrieval method - for backward compatibility
        
        Args:
            location (str): Location (ignored, always uses Lisbon)
            start_date (str): Start date for historical data
            end_date (str): End date for historical data
            
        Returns:
            pd.DataFrame or dict: Weather data
        """
        if start_date and end_date:
            # Return historical data
            return self.get_historical_weather(start_date, end_date)
        elif start_date:
            # Return data from start date to now
            end_date = datetime.now().strftime("%Y-%m-%d")
            return self.get_historical_weather(start_date, end_date)
        else:
            # Return current weather as dict
            return self.get_current_weather()


# Alternative weather client for other services (OpenWeatherMap, etc.)
class OpenWeatherMapClient:
    """OpenWeatherMap API client as an alternative"""

    def __init__(self, api_key):
        """
        Initialize OpenWeatherMap client

        Args:
            api_key (str): OpenWeatherMap API key
        """
        self.api_key = api_key
        self.base_url = "http://api.openweathermap.org/data/2.5"
        self.lisbon_coordinates = {"lat": 38.7223, "lon": -9.1393}

    def get_current_weather(self):
        """Get current weather from OpenWeatherMap"""
        try:
            url = f"{self.base_url}/weather"
            params = {
                "lat": self.lisbon_coordinates["lat"],
                "lon": self.lisbon_coordinates["lon"],
                "appid": self.api_key,
                "units": "metric",
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            return {
                "time": datetime.now().isoformat(),
                "temperature_2m": data.get("main", {}).get("temp", 20),
                "relative_humidity_2m": data.get("main", {}).get("humidity", 60),
                "apparent_temperature": data.get("main", {}).get("feels_like", 20),
                "cloud_cover": data.get("clouds", {}).get("all", 50),
                "wind_speed_10m": data.get("wind", {}).get("speed", 5)
                * 3.6,  # Convert m/s to km/h
                "wind_direction_10m": data.get("wind", {}).get("deg", 180),
            }

        except Exception as e:
            logger.error(f"OpenWeatherMap API error: {e}")
            return WeatherClient()._get_default_weather()
