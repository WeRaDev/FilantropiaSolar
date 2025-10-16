"""
Enhanced Energy Predictor

Handles both historical and simulated weather data for energy production predictions.
Supports 15-day prediction periods (7 days past + chosen date + 7 days future).
"""

from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd

# Machine learning imports
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Local imports
from ..data_processing.comprehensive_data_processor import (
    ComprehensiveDataProcessor,
    InstallationInfo,
)
from ..weather_simulation.weather_simulator import (
    WeatherSimulator,
)

# from ..utils.ranking_system import RankingSystem, EnergyRank  # Temporary disabled

logger = logging.getLogger(__name__)


class EnhancedEnergyPredictor:
    """
    Enhanced energy predictor that can handle both historical and simulated weather data
    for energy production predictions over 15-day periods.
    """

    def __init__(
        self,
        data_processor: ComprehensiveDataProcessor,
        weather_simulator: WeatherSimulator | None = None,
        use_cache: bool = True,
    ):
        """Initialize the enhanced energy predictor with optional model caching."""
        self.data_processor = data_processor
        self.weather_simulator = weather_simulator
        self.use_cache = use_cache
        # self.ranking_system = RankingSystem()  # Temporary disabled

        # Get cache manager from data processor
        self.cache_manager = getattr(data_processor, 'cache_manager', None)

        # Model storage
        self.models: dict[
            str, dict[str, Any]
        ] = {}  # {installation_id: {model_type: model}}
        self.scalers: dict[str, StandardScaler] = {}  # {installation_id: scaler}
        self.model_performance: dict[
            str, dict[str, float]
        ] = {}  # {installation_id: {metric: value}}

        # Model configuration
        self.model_types = {
            "random_forest": RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1,
            ),
            "gradient_boost": GradientBoostingRegressor(
                n_estimators=100,
                max_depth=8,
                learning_rate=0.1,
                min_samples_split=5,
                random_state=42,
            ),
            "linear": LinearRegression(),
        }

        # Initialize models for all installations
        self._train_all_models()

    def _train_all_models(self):
        """Train prediction models for all available installations with caching."""
        # Check if all models are cached
        all_cached = True
        if self.cache_manager:
            for installation_id, _ in self.data_processor.get_installation_list():
                model_key = f"model_{installation_id}"
                scaler_key = f"scaler_{installation_id}"
                perf_key = f"performance_{installation_id}"
                
                if not (self.cache_manager.is_cached("models", model_key) and 
                       self.cache_manager.is_cached("models", scaler_key) and
                       self.cache_manager.is_cached("models", perf_key)):
                    all_cached = False
                    break
            
            if all_cached:
                logger.info("Loading all models from cache")
                for installation_id, _ in self.data_processor.get_installation_list():
                    try:
                        self._load_cached_models(installation_id)
                    except Exception as e:
                        logger.error(f"Error loading cached models for {installation_id}: {e}")
                        all_cached = False
                        break
                
                if all_cached:
                    logger.info(f"Successfully loaded models for {len(self.models)} installations from cache")
                    return
                    
        logger.info("Training models from source (not fully cached)")
        for (
            installation_id,
            installation_info,
        ) in self.data_processor.get_installation_list():
            try:
                self._train_installation_models(installation_id, installation_info)
            except Exception as e:
                logger.error(f"Error training models for {installation_id}: {e}")

    def _train_installation_models(
        self, installation_id: str, installation_info: InstallationInfo
    ):
        """Train prediction models for a specific installation."""
        logger.info(f"Training models for {installation_id}")

        # Get combined data
        data = self.data_processor.get_combined_data(installation_id)
        if data is None or len(data) < 100:
            logger.warning(
                f"Insufficient data for {installation_id}: {len(data) if data is not None else 0} records"
            )
            return

        # Prepare features and targets
        features, target = self._prepare_training_data(data)
        if features is None or len(features) == 0:
            logger.warning(f"No valid features for {installation_id}")
            return

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features, target, test_size=0.2, random_state=42, shuffle=True
        )

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Train models and select best
        models = {}
        performance = {}

        for model_name, model_template in self.model_types.items():
            try:
                # Clone the model template
                from sklearn.base import clone

                model = clone(model_template)

                # Train the model
                model.fit(X_train_scaled, y_train)

                # Evaluate
                y_pred = model.predict(X_test_scaled)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)

                models[model_name] = model
                performance[model_name] = {"mae": mae, "r2": r2}

                logger.info(
                    f"{installation_id} - {model_name}: MAE={mae:.3f}, R²={r2:.3f}"
                )

            except Exception as e:
                logger.error(f"Error training {model_name} for {installation_id}: {e}")

        # Select best model based on R²
        if models:
            best_model_name = max(
                performance.keys(), key=lambda k: performance[k]["r2"]
            )

            self.models[installation_id] = {
                "best_model": models[best_model_name],
                "best_model_name": best_model_name,
                "all_models": models,
            }
            self.scalers[installation_id] = scaler
            self.model_performance[installation_id] = performance

            logger.info(f"{installation_id} - Best model: {best_model_name}")
            
            # Cache the trained models
            if self.cache_manager:
                self._cache_models(installation_id)
        else:
            logger.warning(f"No models successfully trained for {installation_id}")

    def _load_cached_models(self, installation_id: str) -> bool:
        """Load cached models for an installation."""
        try:
            model_key = f"model_{installation_id}"
            scaler_key = f"scaler_{installation_id}"
            perf_key = f"performance_{installation_id}"
            
            # Load models
            cached_models = self.cache_manager.load_cached_data("models", model_key)
            cached_scaler = self.cache_manager.load_cached_data("models", scaler_key)
            cached_performance = self.cache_manager.load_cached_data("models", perf_key)
            
            if cached_models and cached_scaler and cached_performance:
                self.models[installation_id] = cached_models
                self.scalers[installation_id] = cached_scaler
                self.model_performance[installation_id] = cached_performance
                
                logger.info(f"Loaded cached models for {installation_id} - Best: {cached_models.get('best_model_name', 'unknown')}")
                return True
                
        except Exception as e:
            logger.error(f"Error loading cached models for {installation_id}: {e}")
            
        return False
    
    def _cache_models(self, installation_id: str) -> bool:
        """Cache trained models for an installation."""
        try:
            model_key = f"model_{installation_id}"
            scaler_key = f"scaler_{installation_id}"
            perf_key = f"performance_{installation_id}"
            
            # Cache models with metadata
            model_metadata = {
                "installation_id": installation_id,
                "best_model": self.models[installation_id].get("best_model_name", "unknown"),
                "model_count": len(self.models[installation_id].get("all_models", {})),
                "performance": self.model_performance[installation_id]
            }
            
            success = True
            success &= self.cache_manager.cache_data(
                self.models[installation_id], "models", model_key, model_metadata
            )
            success &= self.cache_manager.cache_data(
                self.scalers[installation_id], "models", scaler_key, 
                {"installation_id": installation_id, "scaler_type": "StandardScaler"}
            )
            success &= self.cache_manager.cache_data(
                self.model_performance[installation_id], "models", perf_key,
                {"installation_id": installation_id, "metrics": list(self.model_performance[installation_id].keys())}
            )
            
            if success:
                logger.info(f"Successfully cached models for {installation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error caching models for {installation_id}: {e}")
            return False

    def _prepare_training_data(
        self, data: pd.DataFrame
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Prepare training data from combined dataset."""
        try:
            # Define feature columns
            feature_columns = [
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

            # Add interaction features if they exist
            interaction_features = [
                "temp_cloud_interaction",
                "radiation_cloud_interaction",
            ]

            available_features = [col for col in feature_columns if col in data.columns]
            available_interactions = [
                col for col in interaction_features if col in data.columns
            ]

            all_features = available_features + available_interactions

            if not all_features:
                logger.error("No valid feature columns found")
                return None, None

            # Extract features and target
            features = data[all_features].copy()
            target = data["Specific Energy (kWh/kWp)"].copy()

            # Remove invalid data
            valid_mask = np.isfinite(features).all(axis=1) & np.isfinite(target)
            features = features[valid_mask]
            target = target[valid_mask]

            if len(features) == 0:
                logger.error("No valid training samples after cleaning")
                return None, None

            logger.debug(
                f"Prepared {len(features)} training samples with {len(all_features)} features"
            )
            return features.values, target.values

        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return None, None

    def predict_15day_period(
        self, installation_id: str, center_date: datetime, use_simulation: bool = False
    ) -> dict[str, Any]:
        """
        Predict energy production for a 15-day period around a center date.

        Args:
            installation_id: ID of the installation
            center_date: Center date for the 15-day period
            use_simulation: Whether to use weather simulation for missing data

        Returns:
            Dictionary with prediction results including rankings and weather data
        """
        try:
            # Get installation info
            installation_info = self.data_processor.get_installation_by_id(
                installation_id
            )
            if not installation_info:
                raise ValueError(f"Installation not found: {installation_id}")

            # Get model
            if installation_id not in self.models:
                raise ValueError(
                    f"No trained model for installation: {installation_id}"
                )

            model_info = self.models[installation_id]
            scaler = self.scalers[installation_id]

            # Define 15-day period (7 days before + center day + 7 days after = 15 days)
            # Start from 00:00:00 of first day to ensure complete day coverage
            start_date = (center_date - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            # End at 23:59:59 of last day to ensure complete day coverage
            end_date = (center_date + timedelta(days=7)).replace(hour=23, minute=59, second=59, microsecond=999999)

            # Get or simulate weather data
            weather_data = self._get_weather_data_for_period(
                installation_info.location,
                start_date,
                end_date,
                center_date,
                use_simulation,
            )

            # Prepare prediction features
            prediction_features = self._prepare_prediction_features(
                weather_data, installation_info
            )

            # Make predictions
            predictions = self._make_predictions(
                model_info, scaler, prediction_features
            )

            # Assign rankings
            rankings = self._assign_rankings(predictions, installation_id)

            # Combine results
            results = self._combine_prediction_results(
                weather_data,
                predictions,
                rankings,
                center_date,
                installation_info,
                use_simulation,
            )

            return results

        except Exception as e:
            logger.error(f"Error in 15-day prediction: {e}")
            raise

    def _get_weather_data_for_period(
        self,
        location: str,
        start_date: datetime,
        end_date: datetime,
        center_date: datetime,
        use_simulation: bool,
    ) -> pd.DataFrame:
        """Get weather data for the specified period."""
        try:
            # Check if all dates are in historical range
            historical_weather = self.data_processor.get_weather_data(location)

            if historical_weather is not None:
                # Filter historical data for the period
                period_mask = (historical_weather.index >= start_date) & (
                    historical_weather.index <= end_date
                )
                historical_period = historical_weather[period_mask]

                # Check coverage
                expected_hours = int((end_date - start_date).total_seconds() / 3600) + 1
                coverage_ratio = len(historical_period) / expected_hours

                if coverage_ratio >= 0.9:  # 90% coverage is sufficient
                    logger.info(
                        f"Using historical weather data for {location} (coverage: {coverage_ratio:.2%})"
                    )
                    return historical_period

            # Use simulation if requested or no historical data
            if use_simulation and self.weather_simulator:
                logger.info(f"Using simulated weather data for {location}")
                simulated_weather = self.weather_simulator.simulate_weather(
                    location, start_date, end_date, center_date
                )
                return simulated_weather
            # Fallback to available historical data or raise error
            elif historical_weather is not None and len(historical_period) > 0:
                logger.warning(
                    f"Using partial historical data for {location} (coverage: {coverage_ratio:.2%})"
                )
                return historical_period
            else:
                raise ValueError(
                    f"No weather data available for {location} and simulation not enabled"
                )

        except Exception as e:
            logger.error(f"Error getting weather data for period: {e}")
            raise

    def _prepare_prediction_features(
        self, weather_data: pd.DataFrame, installation_info: InstallationInfo
    ) -> np.ndarray:
        """Prepare features for prediction from weather data."""
        try:
            features_df = weather_data.copy()

            # Add time-based features
            features_df["hour"] = features_df.index.hour
            features_df["day_of_year"] = features_df.index.dayofyear
            features_df["month"] = features_df.index.month

            # Add solar elevation
            features_df["solar_elevation"] = self._compute_solar_elevation(
                features_df.index,
                installation_info.latitude,
                installation_info.longitude,
            )

            # Add interaction features
            if (
                "temperature_2m" in features_df.columns
                and "cloud_cover" in features_df.columns
            ):
                features_df["temp_cloud_interaction"] = (
                    features_df["temperature_2m"]
                    * (100 - features_df["cloud_cover"])
                    / 100
                )

            if (
                "shortwave_radiation" in features_df.columns
                and "cloud_cover" in features_df.columns
            ):
                features_df["radiation_cloud_interaction"] = (
                    features_df["shortwave_radiation"]
                    * (100 - features_df["cloud_cover"])
                    / 100
                )

            # Select feature columns (same as training)
            feature_columns = [
                "temperature_2m",
                "relative_humidity_2m",
                "cloud_cover",
                "wind_speed_10m",
                "shortwave_radiation",
                "hour",
                "day_of_year",
                "month",
                "solar_elevation",
                "temp_cloud_interaction",
                "radiation_cloud_interaction",
            ]

            available_features = [
                col for col in feature_columns if col in features_df.columns
            ]
            features = features_df[available_features].fillna(0)  # Fill missing values

            return features.values

        except Exception as e:
            logger.error(f"Error preparing prediction features: {e}")
            raise

    def _compute_solar_elevation(
        self, timestamps: pd.DatetimeIndex, latitude: float, longitude: float
    ) -> np.ndarray:
        """Compute solar elevation angle for timestamps."""
        # Use the same method as in comprehensive_data_processor
        try:
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

    def _make_predictions(
        self, model_info: dict[str, Any], scaler: StandardScaler, features: np.ndarray
    ) -> np.ndarray:
        """Make energy production predictions."""
        try:
            # Scale features
            features_scaled = scaler.transform(features)

            # Get best model
            model = model_info["best_model"]

            # Make predictions
            predictions = model.predict(features_scaled)

            # Ensure non-negative predictions
            predictions = np.maximum(predictions, 0)

            return predictions

        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            raise

    def _assign_rankings(
        self, predictions: np.ndarray, installation_id: str
    ) -> list[int]:
        """Assign rankings to predictions (simple version)."""
        try:
            # Get historical data for ranking context
            historical_data = self.data_processor.get_combined_data(installation_id)
            if (
                historical_data is not None
                and "Specific Energy (kWh/kWp)" in historical_data.columns
            ):
                historical_values = historical_data[
                    "Specific Energy (kWh/kWp)"
                ].dropna()

                # Simple percentile-based ranking
                rankings = []
                for pred in predictions:
                    percentile = (historical_values < pred).mean() * 100
                    if percentile >= 90:
                        rankings.append(5)  # Excellent
                    elif percentile >= 75:
                        rankings.append(4)  # Good
                    elif percentile >= 25:
                        rankings.append(3)  # Average
                    elif percentile >= 10:
                        rankings.append(2)  # Below average
                    else:
                        rankings.append(1)  # Poor
                return rankings
            else:
                # Use default ranking if no historical context
                return [3] * len(predictions)  # All average

        except Exception as e:
            logger.error(f"Error assigning rankings: {e}")
            return [3] * len(predictions)

    def _combine_prediction_results(
        self,
        weather_data: pd.DataFrame,
        predictions: np.ndarray,
        rankings: list[int],
        center_date: datetime,
        installation_info: InstallationInfo,
        used_simulation: bool,
    ) -> dict[str, Any]:
        """Combine all prediction results into a comprehensive output."""
        try:
            # Create results DataFrame
            results_df = weather_data.copy()
            results_df["predicted_specific_energy"] = predictions
            results_df["predicted_total_energy"] = (
                predictions * installation_info.installed_power_kwp
            )
            results_df["ranking"] = rankings
            
            # *** CRITICAL FIX: Add historical data when available ***
            # Get historical energy data from the data processor
            historical_data = self.data_processor.get_combined_data(installation_info.installation_id)
            if historical_data is not None and "Produced Energy (kWh)" in historical_data.columns:
                # Merge historical data with results based on datetime index
                historical_energy_cols = ["Produced Energy (kWh)", "Specific Energy (kWh/kWp)"]
                available_historical_cols = [col for col in historical_energy_cols if col in historical_data.columns]
                
                if available_historical_cols:
                    # Only merge rows that have matching timestamps
                    historical_subset = historical_data[available_historical_cols]
                    results_df = results_df.merge(
                        historical_subset, 
                        left_index=True, 
                        right_index=True, 
                        how='left'
                    )
                    logger.info(f"Successfully merged historical energy data: {len(results_df[results_df['Produced Energy (kWh)'].notna()])} historical records found")
                else:
                    logger.warning("Historical data columns not found in combined data")
            else:
                logger.info("No historical energy data available for merging")

            # Simple color and description mapping
            color_map = {
                1: "#e74c3c",
                2: "#e67e22",
                3: "#f1c40f",
                4: "#2ecc71",
                5: "#27ae60",
            }
            desc_map = {
                1: "Poor",
                2: "Below Average",
                3: "Average",
                4: "Good",
                5: "Excellent",
            }

            results_df["ranking_color"] = [
                color_map.get(rank, "#f1c40f") for rank in rankings
            ]
            results_df["ranking_description"] = [
                desc_map.get(rank, "Average") for rank in rankings
            ]

            # Calculate daily summaries
            daily_summary = (
                results_df.groupby(results_df.index.date)
                .agg(
                    {
                        "predicted_total_energy": "sum",
                        "predicted_specific_energy": "mean",
                        "temperature_2m": "mean",
                        "cloud_cover": "mean",
                        "shortwave_radiation": "mean",
                        "ranking": lambda x: x.mode().iloc[0]
                        if len(x.mode()) > 0
                        else 3,
                    }
                )
                .round(2)
            )

            # Calculate period statistics
            period_stats = {
                "total_energy_kwh": float(results_df["predicted_total_energy"].sum()),
                "average_specific_energy": float(
                    results_df["predicted_specific_energy"].mean()
                ),
                "peak_hour_energy": float(
                    results_df["predicted_specific_energy"].max()
                ),
                "peak_hour_time": str(
                    results_df.loc[
                        results_df["predicted_specific_energy"].idxmax()
                    ].name
                ),
                "average_temperature": float(results_df["temperature_2m"].mean())
                if "temperature_2m" in results_df.columns
                else None,
                "average_cloud_cover": float(results_df["cloud_cover"].mean())
                if "cloud_cover" in results_df.columns
                else None,
                "total_radiation": float(results_df["shortwave_radiation"].sum())
                if "shortwave_radiation" in results_df.columns
                else None,
            }

            # Identify center date data
            center_date_mask = results_df.index.date == center_date.date()
            center_date_data = (
                results_df[center_date_mask] if center_date_mask.any() else None
            )

            return {
                "installation_id": installation_info.installation_id,
                "installation_info": {
                    "location": installation_info.location,
                    "capacity_kwp": installation_info.installed_power_kwp,
                    "serial_number": installation_info.serial_number,
                },
                "prediction_period": {
                    "start": results_df.index.min(),
                    "end": results_df.index.max(),
                    "center_date": center_date,
                    "total_hours": len(results_df),
                },
                "hourly_data": results_df,
                "daily_summary": daily_summary,
                "period_statistics": period_stats,
                "center_date_data": center_date_data,
                "data_source": {
                    "used_simulation": used_simulation,
                    "model_used": self.models[installation_info.installation_id][
                        "best_model_name"
                    ],
                    "model_performance": self.model_performance.get(
                        installation_info.installation_id, {}
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error combining prediction results: {e}")
            raise

    def get_available_installations(self) -> list[tuple[str, InstallationInfo]]:
        """Get list of installations with trained models."""
        return [
            (id, info)
            for id, info in self.data_processor.get_installation_list()
            if id in self.models
        ]

    def get_model_performance(self, installation_id: str) -> dict[str, float] | None:
        """Get model performance metrics for an installation."""
        return self.model_performance.get(installation_id)

    def save_models(self, models_dir: str = "models"):
        """Save trained models to disk."""
        models_path = Path(models_dir)
        models_path.mkdir(exist_ok=True)

        for installation_id in self.models:
            try:
                # Save model
                model_file = models_path / f"{installation_id}_model.pkl"
                joblib.dump(self.models[installation_id], model_file)

                # Save scaler
                scaler_file = models_path / f"{installation_id}_scaler.pkl"
                joblib.dump(self.scalers[installation_id], scaler_file)

                logger.info(f"Saved models for {installation_id}")

            except Exception as e:
                logger.error(f"Error saving models for {installation_id}: {e}")

    def load_models(self, models_dir: str = "models"):
        """Load trained models from disk."""
        models_path = Path(models_dir)
        if not models_path.exists():
            logger.warning(f"Models directory not found: {models_path}")
            return

        for installation_id in self.data_processor.installations:
            try:
                # Load model
                model_file = models_path / f"{installation_id}_model.pkl"
                if model_file.exists():
                    self.models[installation_id] = joblib.load(model_file)

                # Load scaler
                scaler_file = models_path / f"{installation_id}_scaler.pkl"
                if scaler_file.exists():
                    self.scalers[installation_id] = joblib.load(scaler_file)

                logger.info(f"Loaded models for {installation_id}")

            except Exception as e:
                logger.error(f"Error loading models for {installation_id}: {e}")


if __name__ == "__main__":
    # Test the enhanced energy predictor
    data_processor = ComprehensiveDataProcessor()
    weather_simulator = WeatherSimulator("weather_files")

    predictor = EnhancedEnergyPredictor(data_processor, weather_simulator)

    # Test prediction
    installations = predictor.get_available_installations()
    if installations:
        test_installation = installations[0][0]
        test_date = datetime(2025, 6, 15)

        results = predictor.predict_15day_period(
            test_installation, test_date, use_simulation=True
        )

        print(f"Prediction results for {test_installation}:")
        print(f"Period: {results['prediction_period']}")
        print(
            f"Total energy: {results['period_statistics']['total_energy_kwh']:.2f} kWh"
        )
        print(
            f"Average specific energy: {results['period_statistics']['average_specific_energy']:.2f} kWh/kWp"
        )
