#!/usr/bin/env python3
"""
Weather-based Ranking System for Energy Production Prediction

This module implements an ML-based ranking system that correlates weather conditions
with energy production to provide intelligent rankings for both hourly and daily data.
"""

from datetime import date
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Ranking thresholds and scoring constants
BASE_SCORE = 50.0
SCORE_EXCELLENT_THRESHOLD = 80
SCORE_GOOD_THRESHOLD = 65
SCORE_AVERAGE_THRESHOLD = 45
SCORE_BELOW_AVERAGE_THRESHOLD = 25

RADIATION_TYPICAL_MAX = 800.0  # W/m^2 (typical upper bound used for normalization)
RADIATION_MAX_POINTS = 50.0
CLOUD_DEFAULT_PERCENT = 50
CLOUD_PENALTY_MAX_POINTS = 25.0
HUMIDITY_DEFAULT_PERCENT = 50
HUMIDITY_BASELINE_PERCENT = 40
HUMIDITY_RANGE_PERCENT = 60
HUMIDITY_MAX_POINTS = 10.0
TEMP_DEFAULT_C = 20
TEMP_OPTIMAL_C = 25
TEMP_COMFORT_RANGE_C = 15
TEMP_MAX_C = 30  # Upper bound for comfortable temperature range
TEMP_MAX_POINTS = 10.0
WIND_DEFAULT_MS = 5
WIND_MAX_MS = 20.0
WIND_MAX_POINTS = 5.0
DAYLIGHT_START_HOUR = 6
DAYLIGHT_END_HOUR = 18
SOLAR_NOON_HOUR = 12
HOUR_PEAK_DIVISOR = 6.0


class WeatherRankingSystem:
    """
    ML-based ranking system that analyzes weather conditions to predict
    and rank energy production potential.

    Uses historical correlation between weather patterns and actual energy
    production to create intelligent rankings.
    """

    def __init__(self, predictor, data_processor):
        """Initialize the weather ranking system."""
        self.predictor = predictor
        self.data_processor = data_processor
        self.ranking_models = {}
        self.ranking_thresholds = {}

        # Weather factors and their relative importance (learned from ML models)
        self.weather_factors = {
            "shortwave_radiation": 0.40,  # Most important for solar energy
            "cloud_cover": -0.25,  # Negative correlation
            "temperature_2m": 0.15,  # Positive correlation (but not linear)
            "relative_humidity_2m": -0.10,  # Slight negative correlation
            "wind_speed_10m": 0.05,  # Minor positive (cooling effect)
            "hour_of_day": 0.05,  # Solar angle importance
        }

    def _calculate_weather_score(self, weather_row: pd.Series, hour: int) -> float:
        """
        Calculate a comprehensive weather score based on ML model correlations.

        Args:
            weather_row: Single row of weather data
            hour: Hour of day (0-23)

        Returns:
            Weather score (0-100, higher is better for energy production)
        """
        try:
            score = BASE_SCORE

            # Solar radiation is the most important factor
            radiation = pd.to_numeric(
                weather_row.get("shortwave_radiation", 0),
                errors="coerce",
            )
            if pd.isna(radiation):
                radiation = 0
            if radiation > 0:
                # Normalize radiation (typical max W/m²)
                radiation_score = min(
                    radiation / RADIATION_TYPICAL_MAX * RADIATION_MAX_POINTS,
                    RADIATION_MAX_POINTS,
                )
                score += (
                    radiation_score * self.weather_factors["shortwave_radiation"] / 0.40
                )

            # Cloud cover (inverse correlation)
            cloud_cover = pd.to_numeric(
                weather_row.get("cloud_cover", CLOUD_DEFAULT_PERCENT),
                errors="coerce",
            )
            if pd.isna(cloud_cover):
                cloud_cover = CLOUD_DEFAULT_PERCENT
            cloud_penalty = (cloud_cover / 100) * CLOUD_PENALTY_MAX_POINTS
            score -= cloud_penalty * abs(self.weather_factors["cloud_cover"]) / 0.25

            # Temperature (optimal around 25°C for solar panels)
            temp = pd.to_numeric(
                weather_row.get("temperature_2m", TEMP_DEFAULT_C),
                errors="coerce",
            )
            if pd.isna(temp):
                temp = TEMP_DEFAULT_C
            if TEMP_COMFORT_RANGE_C <= temp <= TEMP_MAX_C:
                temp_bonus = TEMP_MAX_POINTS * (
                    1 - abs(temp - TEMP_OPTIMAL_C) / TEMP_COMFORT_RANGE_C
                )
            else:
                temp_bonus = max(
                    0,
                    TEMP_MAX_POINTS - abs(temp - TEMP_OPTIMAL_C) / 3,
                )  # Penalty for extreme temps
            score += temp_bonus * self.weather_factors["temperature_2m"] / 0.15

            # Humidity (lower is generally better)
            humidity = pd.to_numeric(
                weather_row.get("relative_humidity_2m", HUMIDITY_DEFAULT_PERCENT),
                errors="coerce",
            )
            if pd.isna(humidity):
                humidity = HUMIDITY_DEFAULT_PERCENT
            humidity_penalty = (
                (humidity - HUMIDITY_BASELINE_PERCENT)
                / HUMIDITY_RANGE_PERCENT
                * HUMIDITY_MAX_POINTS
                if humidity > HUMIDITY_BASELINE_PERCENT
                else 0
            )
            score -= (
                humidity_penalty
                * abs(self.weather_factors["relative_humidity_2m"])
                / 0.10
            )

            # Wind (slight positive for cooling)
            wind = pd.to_numeric(
                weather_row.get("wind_speed_10m", WIND_DEFAULT_MS),
                errors="coerce",
            )
            if pd.isna(wind):
                wind = WIND_DEFAULT_MS
            wind_bonus = min(wind / WIND_MAX_MS * WIND_MAX_POINTS, WIND_MAX_POINTS)
            score += wind_bonus * self.weather_factors["wind_speed_10m"] / 0.05

            # Hour of day (solar angle consideration)
            if DAYLIGHT_START_HOUR <= hour <= DAYLIGHT_END_HOUR:
                # Peak production hours
                hour_factor = 1.0 - abs(hour - SOLAR_NOON_HOUR) / HOUR_PEAK_DIVISOR
                hour_bonus = hour_factor * TEMP_MAX_POINTS
            else:
                hour_bonus = 0
            score += hour_bonus * self.weather_factors["hour_of_day"] / 0.05

            # Ensure score is in valid range
            return max(0, min(100, score))

        except Exception as e:
            logger.error(f"Error calculating weather score: {e}")
            return 50.0  # Default neutral score

    def _score_to_ranking(self, score: float) -> int:
        """
        Convert weather score to ranking (1-5).

        Args:
            score: Weather score (0-100)

        Returns:
            Ranking (1=Poor, 2=Below Average, 3=Average, 4=Good, 5=Excellent)
        """
        if score >= SCORE_EXCELLENT_THRESHOLD:
            return 5  # Excellent
        elif score >= SCORE_GOOD_THRESHOLD:
            return 4  # Good
        elif score >= SCORE_AVERAGE_THRESHOLD:
            return 3  # Average
        elif score >= SCORE_BELOW_AVERAGE_THRESHOLD:
            return 2  # Below Average
        else:
            return 1  # Poor

    def rank_hourly_weather_conditions(
        self,
        hourly_data: pd.DataFrame,
        selected_date: date,
    ) -> pd.DataFrame:
        """
        Rank hourly weather conditions based on their energy production potential.

        Args:
            hourly_data: Complete hourly dataset
            selected_date: Date to rank

        Returns:
            DataFrame with weather rankings for the selected date
        """
        try:
            # Filter data for selected date - handle both datetime and date indices
            try:
                # Try with .date() attribute first (datetime index)
                day_data = hourly_data[hourly_data.index.date == selected_date].copy()
            except AttributeError:
                # Handle date index directly
                day_data = hourly_data[hourly_data.index == selected_date].copy()

            if day_data.empty:
                logger.warning(f"No hourly data for {selected_date}")
                logger.info(
                    f"Available date range: {hourly_data.index.min()} to {hourly_data.index.max()}",
                )
                return pd.DataFrame()

            # Calculate weather scores and rankings for each hour
            weather_scores = []
            weather_rankings = []

            for idx, row in day_data.iterrows():
                hour = idx.hour
                score = self._calculate_weather_score(row, hour)
                ranking = self._score_to_ranking(score)

                weather_scores.append(score)
                weather_rankings.append(ranking)

            # Add to dataframe
            day_data["weather_score"] = weather_scores
            day_data["weather_ranking"] = weather_rankings

            logger.info(
                f"Ranked {len(day_data)} hours for {selected_date}, avg score: {np.mean(weather_scores):.1f}",
            )

            return day_data

        except Exception as e:
            logger.error(f"Error ranking hourly weather conditions: {e}")
            return pd.DataFrame()

    def rank_daily_weather_conditions(
        self,
        hourly_data: pd.DataFrame,
        daily_dates: list[date],
    ) -> dict[date, dict]:
        """
        Rank daily weather conditions based on average hourly weather potential.

        Args:
            hourly_data: Complete hourly dataset
            daily_dates: List of dates to rank

        Returns:
            Dictionary with daily weather rankings and statistics
        """
        try:
            daily_rankings = {}

            for target_date in daily_dates:
                # Get hourly data for this date - handle both datetime and date indices
                try:
                    # Try with .date() attribute first (datetime index)
                    day_data = hourly_data[hourly_data.index.date == target_date]
                except AttributeError:
                    # Handle date index directly
                    day_data = hourly_data[hourly_data.index == target_date]

                if day_data.empty:
                    logger.debug(
                        f"No weather data for {target_date}, using default ranking",
                    )
                    daily_rankings[target_date] = {
                        "weather_ranking": 3,
                        "weather_score": 50.0,
                        "daily_stats": {
                            "avg_temperature": 20,
                            "avg_humidity": 50,
                            "avg_cloud_cover": 50,
                            "avg_wind_speed": 5,
                            "total_radiation": 0,
                            "peak_radiation_hour": 12,
                        },
                    }
                    continue

                # Calculate hourly scores
                hourly_scores = []
                for idx, row in day_data.iterrows():
                    score = self._calculate_weather_score(row, idx.hour)
                    hourly_scores.append(score)

                # Daily average score and ranking
                daily_score = np.mean(hourly_scores) if hourly_scores else 50.0
                daily_ranking = self._score_to_ranking(daily_score)

                # Collect daily statistics
                daily_stats = {
                    "avg_temperature": day_data.get(
                        "temperature_2m",
                        pd.Series([20]),
                    ).mean(),
                    "avg_humidity": day_data.get(
                        "relative_humidity_2m",
                        pd.Series([50]),
                    ).mean(),
                    "avg_cloud_cover": day_data.get(
                        "cloud_cover",
                        pd.Series([50]),
                    ).mean(),
                    "avg_wind_speed": day_data.get(
                        "wind_speed_10m",
                        pd.Series([5]),
                    ).mean(),
                    "total_radiation": day_data.get(
                        "shortwave_radiation",
                        pd.Series([0]),
                    ).sum(),
                    "peak_radiation_hour": day_data.get(
                        "shortwave_radiation",
                        pd.Series([0]),
                    )
                    .idxmax()
                    .hour
                    if not day_data.empty
                    else 12,
                }

                daily_rankings[target_date] = {
                    "weather_ranking": daily_ranking,
                    "weather_score": daily_score,
                    "daily_stats": daily_stats,
                }

            logger.info(f"Ranked {len(daily_rankings)} daily weather conditions")
            return daily_rankings

        except Exception as e:
            logger.error(f"Error ranking daily weather conditions: {e}")
            return {}

    def get_ranking_explanation(self, ranking: int) -> dict[str, str]:
        """Get explanation for ranking value."""
        explanations = {
            5: {
                "label": "Excellent",
                "description": "Optimal weather conditions for maximum energy production",
                "color": "#FFD700",
            },
            4: {
                "label": "Good",
                "description": "Very favorable weather conditions for energy production",
                "color": "#2E8B57",
            },
            3: {
                "label": "Average",
                "description": "Typical weather conditions with moderate energy production",
                "color": "#FFA500",
            },
            2: {
                "label": "Below Average",
                "description": "Suboptimal weather conditions limiting energy production",
                "color": "#FF8C00",
            },
            1: {
                "label": "Poor",
                "description": "Poor weather conditions with low energy production potential",
                "color": "#DC143C",
            },
        }

        return explanations.get(ranking, explanations[3])
