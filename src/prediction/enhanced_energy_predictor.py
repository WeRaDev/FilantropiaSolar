"""
Enhanced Energy Predictor

Handles both historical and simulated weather data for energy production predictions.
Supports 15-day prediction periods (7 days past + chosen date + 7 days future).
"""

from datetime import datetime, timedelta
import hashlib
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
# Path helper import (packaged first, then dev layouts)
try:
    from filantropia_solar.utils.paths import get_resource_path
except Exception:
    try:
        from src.utils.paths import get_resource_path
    except Exception:
        from utils.paths import get_resource_path

# Machine learning imports
from sklearn.base import clone
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
from ..weather_api.providers import OpenMeteoWeatherProvider
from ..weather_simulation.weather_simulator import (
    WeatherSimulator,
)

logger = logging.getLogger(__name__)

# Training and prediction constants (v1.1.1 Enhanced)
MINIMUM_TRAINING_SAMPLES = 100  # Minimum samples required for model training
WEATHER_COVERAGE_THRESHOLD = 0.9  # Required weather data coverage ratio (90%)
RANKING_EXCELLENT_PERCENTILE = 90  # Percentile threshold for excellent ranking
RANKING_GOOD_PERCENTILE = 75  # Percentile threshold for good ranking
RANKING_AVERAGE_PERCENTILE = 25  # Percentile threshold for average ranking
RANKING_POOR_PERCENTILE = 10  # Percentile threshold for poor ranking
DEFAULT_RANKING = 3  # Default ranking when no context available

# ML Model Configuration Constants (v1.1.1)
RANDOM_FOREST_ESTIMATORS = 150  # Increased from 100 for better performance
RANDOM_FOREST_MAX_DEPTH = 20  # Increased from 15 for more complex patterns
RANDOM_FOREST_MIN_SAMPLES_SPLIT = 4  # Reduced from 5 for better granularity
RANDOM_FOREST_MIN_SAMPLES_LEAF = 2  # Optimal leaf size
GRADIENT_BOOST_ESTIMATORS = 120  # Increased from 100
GRADIENT_BOOST_MAX_DEPTH = 10  # Increased from 8
GRADIENT_BOOST_LEARNING_RATE = 0.08  # Reduced from 0.1 for better convergence
GRADIENT_BOOST_MIN_SAMPLES_SPLIT = 4  # Reduced from 5

# Ensemble Model Constants (v1.1.1 New Feature)
ENSEMBLE_WEIGHT_RF = 0.4  # Random Forest weight in ensemble
ENSEMBLE_WEIGHT_GB = 0.35  # Gradient Boosting weight in ensemble
ENSEMBLE_WEIGHT_LINEAR = 0.25  # Linear Regression weight in ensemble
MIN_R2_FOR_ENSEMBLE = 0.3  # Minimum R² to include model in ensemble
ENSEMBLE_PERFORMANCE_THRESHOLD = 0.05  # Performance improvement threshold

# Feature Engineering Constants (v1.1.1 Enhanced)
ROLLING_WINDOW_HOURS = 24  # Rolling average window size
SEASONAL_FEATURE_COUNT = 4  # Number of seasonal components
WEATHER_INTERACTION_COUNT = 6  # Number of weather interaction features
FEATURE_IMPORTANCE_THRESHOLD = 0.01  # Minimum feature importance to keep

# Physical constraints for production (no PV output at night / very low irradiance)
PRODUCTION_RADIATION_THRESHOLD = (
    20.0  # W/m² threshold below which production is forced to 0
)
# Minimal physically plausible specific energy floor proportional to irradiance (kWh/kWp)
MIN_SPECIFIC_FLOOR_COEF = 0.2  # floor = coef * (GHI_Wm2 / 1000)


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
        # Initialize weather provider with cache
        try:
            self.weather_provider = OpenMeteoWeatherProvider(
                cache_manager=getattr(data_processor, "cache_manager", None),
            )
        except Exception:
            self.weather_provider = None

        # Get cache manager from data processor
        self.cache_manager = getattr(data_processor, "cache_manager", None)

        # Model storage
        self.models: dict[
            str,
            dict[str, Any],
        ] = {}  # {installation_id: {model_type: model}}
        self.scalers: dict[str, StandardScaler] = {}  # {installation_id: scaler}
        self.model_performance: dict[
            str,
            dict[str, float],
        ] = {}  # {installation_id: {metric: value}}

        # Feature persistence for consistent training/inference (v1.1.1 Fix)
        self.feature_columns: dict[
            str, list[str]
        ] = {}  # {installation_id: [feature_names]}

        # Model configuration
        self.model_types = {
            "random_forest": RandomForestRegressor(
                n_estimators=RANDOM_FOREST_ESTIMATORS,
                max_depth=RANDOM_FOREST_MAX_DEPTH,
                min_samples_split=RANDOM_FOREST_MIN_SAMPLES_SPLIT,
                min_samples_leaf=RANDOM_FOREST_MIN_SAMPLES_LEAF,
                random_state=42,
                n_jobs=-1,
            ),
            "gradient_boost": GradientBoostingRegressor(
                n_estimators=GRADIENT_BOOST_ESTIMATORS,
                max_depth=GRADIENT_BOOST_MAX_DEPTH,
                learning_rate=GRADIENT_BOOST_LEARNING_RATE,
                min_samples_split=GRADIENT_BOOST_MIN_SAMPLES_SPLIT,
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
                features_key = f"features_{installation_id}"

                if not (
                    self.cache_manager.is_cached("models", model_key)
                    and self.cache_manager.is_cached("models", scaler_key)
                    and self.cache_manager.is_cached("models", perf_key)
                    and self.cache_manager.is_cached("models", features_key)
                ):
                    all_cached = False
                    break

            if all_cached:
                logger.info("Loading all models from cache")
                for installation_id, _ in self.data_processor.get_installation_list():
                    try:
                        self._load_cached_models(installation_id)
                    except Exception as e:
                        logger.error(
                            f"Error loading cached models for {installation_id}: {e}",
                        )
                        all_cached = False
                        break

                if all_cached:
                    logger.info(
                        f"Successfully loaded models for {len(self.models)} installations from cache",
                    )
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
        self,
        installation_id: str,
        _installation_info: InstallationInfo,
    ):
        """Train prediction models for a specific installation."""
        logger.info(f"Training models for {installation_id}")

        # Get combined data
        data = self.data_processor.get_combined_data(installation_id)
        if data is None or len(data) < MINIMUM_TRAINING_SAMPLES:
            logger.warning(
                f"Insufficient data for {installation_id}: {len(data) if data is not None else 0} records",
            )
            return

        # Prepare features and targets
        features, target, feature_names = self._prepare_training_data(data)
        if features is None or len(features) == 0 or feature_names is None:
            logger.warning(f"No valid features for {installation_id}")
            return

        # Store feature names for consistent inference (v1.1.1 Fix)
        self.feature_columns[installation_id] = feature_names
        logger.info(
            f"Captured {len(feature_names)} feature names for {installation_id}: {feature_names[:5]}..."
        )

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            features,
            target,
            test_size=0.2,
            random_state=42,
            shuffle=True,
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
                    f"{installation_id} - {model_name}: MAE={mae:.3f}, R²={r2:.3f}",
                )

            except Exception as e:
                logger.error(f"Error training {model_name} for {installation_id}: {e}")

        # Create ensemble model (v1.1.1 New Feature)
        ensemble_model = None
        ensemble_performance = None

        if models and len(models) >= 2:
            try:
                ensemble_model, ensemble_performance = self._create_ensemble_model(
                    models, performance, X_test_scaled, y_test
                )
                if ensemble_model:
                    models["ensemble"] = ensemble_model
                    performance["ensemble"] = ensemble_performance
                    logger.info(
                        f"{installation_id} - Ensemble: MAE={ensemble_performance['mae']:.3f}, R²={ensemble_performance['r2']:.3f}"
                    )
            except Exception as e:
                logger.warning(f"Failed to create ensemble for {installation_id}: {e}")

        # Select best model based on R² (now including ensemble)
        if models:
            best_model_name = max(
                performance.keys(),
                key=lambda k: performance[k]["r2"],
            )

            self.models[installation_id] = {
                "best_model": models[best_model_name],
                "best_model_name": best_model_name,
                "all_models": models,
                "ensemble_weights": getattr(ensemble_model, "weights_", None)
                if ensemble_model
                else None,
            }
            self.scalers[installation_id] = scaler
            self.model_performance[installation_id] = performance

            improvement_msg = ""
            if ensemble_model and best_model_name == "ensemble":
                improvement_msg = " (🚀 Ensemble outperformed individual models!)"

            logger.info(
                f"{installation_id} - Best model: {best_model_name}{improvement_msg}"
            )

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
            features_key = f"features_{installation_id}"

            # Load models and features
            cached_models = self.cache_manager.load_cached_data("models", model_key)
            cached_scaler = self.cache_manager.load_cached_data("models", scaler_key)
            cached_performance = self.cache_manager.load_cached_data("models", perf_key)
            cached_features = self.cache_manager.load_cached_data(
                "models", features_key
            )

            if cached_models and cached_scaler and cached_performance:
                self.models[installation_id] = cached_models
                self.scalers[installation_id] = cached_scaler
                self.model_performance[installation_id] = cached_performance

                # Restore feature names (v1.1.1 Fix)
                if cached_features:
                    self.feature_columns[installation_id] = cached_features
                    logger.info(
                        f"Loaded cached models for {installation_id} - Best: {cached_models.get('best_model_name', 'unknown')}, "
                        f"Features: {len(cached_features)}"
                    )
                else:
                    logger.warning(
                        f"No cached feature names for {installation_id} - may cause prediction issues"
                    )
                    logger.info(
                        f"Loaded cached models for {installation_id} - Best: {cached_models.get('best_model_name', 'unknown')}",
                    )
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
            features_key = f"features_{installation_id}"

            # Cache models with metadata
            model_metadata = {
                "installation_id": installation_id,
                "best_model": self.models[installation_id].get(
                    "best_model_name",
                    "unknown",
                ),
                "model_count": len(self.models[installation_id].get("all_models", {})),
                "performance": self.model_performance[installation_id],
            }

            success = True
            success &= self.cache_manager.cache_data(
                self.models[installation_id],
                "models",
                model_key,
                model_metadata,
            )
            success &= self.cache_manager.cache_data(
                self.scalers[installation_id],
                "models",
                scaler_key,
                {"installation_id": installation_id, "scaler_type": "StandardScaler"},
            )
            success &= self.cache_manager.cache_data(
                self.model_performance[installation_id],
                "models",
                perf_key,
                {
                    "installation_id": installation_id,
                    "metrics": list(self.model_performance[installation_id].keys()),
                },
            )

            # Cache feature names for consistent inference (v1.1.1 Fix)
            if installation_id in self.feature_columns:
                success &= self.cache_manager.cache_data(
                    self.feature_columns[installation_id],
                    "models",
                    features_key,
                    {
                        "installation_id": installation_id,
                        "feature_count": len(self.feature_columns[installation_id]),
                        "schema_version": 1,  # For future compatibility
                    },
                )

            # Also register best model in model_cache table for status visibility
            try:
                best_name = self.models[installation_id].get(
                    "best_model_name", "unknown"
                )
                best_model = self.models[installation_id].get("best_model")
                perf = self.model_performance[installation_id].get(best_name, {})
                train_hash = hashlib.md5(
                    repr(self.model_performance[installation_id]).encode()
                ).hexdigest()
                if best_model and hasattr(self.cache_manager, "cache_model"):
                    self.cache_manager.cache_model(
                        best_model,
                        installation_id,
                        best_name,
                        perf,
                        train_hash,
                    )
            except Exception as e:
                logger.warning(f"Could not register model in model_cache: {e}")

            if success:
                logger.info(f"Successfully cached models for {installation_id}")

            return success

        except Exception as e:
            logger.error(f"Error caching models for {installation_id}: {e}")
            return False

    def _prepare_training_data(
        self,
        data: pd.DataFrame,
    ) -> tuple[np.ndarray | None, np.ndarray | None, list[str] | None]:
        """Prepare training data from combined dataset with enhanced features (v1.1.1).

        Returns:
            Tuple of (features_array, target_array, feature_names)
        """
        try:
            # Ensure target exists (compute if missing)
            if (
                "Specific Energy (kWh/kWp)" not in data.columns
                and "Produced Energy (kWh)" in data.columns
                and "installed_power_kwp" in data.columns
            ):
                with np.errstate(divide="ignore", invalid="ignore"):
                    se = data["Produced Energy (kWh)"] / data[
                        "installed_power_kwp"
                    ].replace(0, np.nan)
                data = data.copy()
                data["Specific Energy (kWh/kWp)"] = np.clip(
                    pd.to_numeric(se, errors="coerce").fillna(0), 0, None
                )

            # Apply enhanced feature engineering
            enhanced_data = self._enhance_features(data)

            # Define base feature columns
            base_feature_columns = [
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

            # Enhanced features (v1.1.1)
            enhanced_feature_columns = [
                # Rolling averages
                "temp_rolling_avg",
                "temp_rolling_std",
                "radiation_rolling_avg",
                # Seasonal patterns
                "seasonal_sin_1",
                "seasonal_cos_1",
                "seasonal_sin_2",
                "seasonal_cos_2",
                # Weather interactions
                "temp_cloud_interaction",
                "radiation_cloud_interaction",
                "temp_humidity_interaction",
                "wind_temp_interaction",
                "radiation_humidity_interaction",
                "cloud_wind_interaction",
                # Power transformations
                "radiation_sqrt",
                # Time-based indicators
                "peak_sun_indicator",
                "morning_ramp",
                "evening_ramp",
            ]

            # Collect available features
            available_base = [
                col for col in base_feature_columns if col in enhanced_data.columns
            ]
            available_enhanced = [
                col for col in enhanced_feature_columns if col in enhanced_data.columns
            ]
            all_features = available_base + available_enhanced

            if not all_features:
                logger.error("No valid feature columns found")
                return None, None, None

            # Extract features and target
            features = enhanced_data[all_features].copy()
            target = enhanced_data.get("Specific Energy (kWh/kWp)")
            if target is None:
                logger.error("Missing target column 'Specific Energy (kWh/kWp)'")
                return None, None, None
            target = pd.to_numeric(target, errors="coerce")

            # Clean features: coerce non-numeric, replace inf, fill NaN with column medians (fallback 0)
            for col in features.columns:
                features[col] = pd.to_numeric(features[col], errors="coerce").replace(
                    [np.inf, -np.inf], np.nan
                )
                if features[col].isna().all():
                    features[col] = 0
                else:
                    median = features[col].median(skipna=True)
                    features[col] = features[col].fillna(
                        0 if pd.isna(median) else median
                    )

            # Clean target: non-negative, drop NaN
            target = target.replace([np.inf, -np.inf], np.nan).fillna(0)
            target = np.clip(target, 0, None)

            # Remove rows where any feature is still NaN after fill (should be none)
            valid_mask = ~features.isna().any(axis=1)
            features = features[valid_mask]
            target = target[valid_mask]

            if len(features) == 0:
                logger.error("No valid training samples after cleaning")
                return None, None, None

            # Final safety: ensure equal length
            if len(features) != len(target):
                min_len = min(len(features), len(target))
                features = features.iloc[:min_len]
                target = target.iloc[:min_len]

            # Feature selection based on importance (v1.1.1 Enhancement)
            if len(features) > MINIMUM_TRAINING_SAMPLES and len(all_features) > 10:
                try:
                    # Quick feature importance using Random Forest
                    from sklearn.ensemble import RandomForestRegressor

                    feature_selector = RandomForestRegressor(
                        n_estimators=50, random_state=42
                    )
                    feature_selector.fit(features, target)

                    # Get feature importance
                    importance = feature_selector.feature_importances_
                    important_features = importance >= FEATURE_IMPORTANCE_THRESHOLD

                    if np.sum(important_features) >= len(
                        base_feature_columns
                    ):  # Keep minimum base features
                        features = features.iloc[:, important_features]
                        selected_features = [
                            all_features[i]
                            for i, keep in enumerate(important_features)
                            if keep
                        ]
                        logger.debug(
                            f"Selected {len(selected_features)} important features from {len(all_features)}"
                        )
                    else:
                        logger.debug(
                            "Feature selection kept all features (insufficient importance threshold)"
                        )

                except Exception as e:
                    logger.warning(f"Feature selection failed, using all features: {e}")

            # Capture final feature names for persistence
            final_feature_names = list(features.columns)

            logger.info(
                f"Prepared {len(features)} training samples with {len(features.columns)} features "
                f"({len(available_enhanced)} enhanced features added)"
            )
            return features.values, target.values, final_feature_names

        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return None, None, None

    def _create_ensemble_model(
        self,
        models: dict[str, Any],
        performance: dict[str, dict[str, float]],
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> tuple[Any, dict[str, float]] | tuple[None, None]:
        """Create weighted ensemble model based on individual model performance (v1.1.1)."""
        try:
            # Filter models with acceptable performance
            qualified_models = {
                name: model
                for name, model in models.items()
                if performance[name]["r2"] >= MIN_R2_FOR_ENSEMBLE
            }

            if len(qualified_models) < 2:
                logger.debug("Not enough qualified models for ensemble")
                return None, None

            # Calculate performance-based weights
            r2_scores = {name: performance[name]["r2"] for name in qualified_models}
            total_r2 = sum(r2_scores.values())

            # Normalize weights
            if total_r2 > 0:
                base_weights = {name: r2 / total_r2 for name, r2 in r2_scores.items()}
            else:
                # Equal weights fallback
                base_weights = {
                    name: 1.0 / len(qualified_models) for name in qualified_models
                }

            # Apply predefined model preferences (if available)
            final_weights = {}
            weight_mapping = {
                "random_forest": ENSEMBLE_WEIGHT_RF,
                "gradient_boost": ENSEMBLE_WEIGHT_GB,
                "linear": ENSEMBLE_WEIGHT_LINEAR,
            }

            for name in qualified_models:
                if name in weight_mapping:
                    # Blend performance-based and predefined weights
                    final_weights[name] = (
                        0.7 * base_weights[name] + 0.3 * weight_mapping[name]
                    )
                else:
                    final_weights[name] = base_weights[name]

            # Normalize final weights
            total_weight = sum(final_weights.values())
            final_weights = {
                name: w / total_weight for name, w in final_weights.items()
            }

            # Create ensemble predictions
            ensemble_predictions = np.zeros(len(X_test))
            for name, weight in final_weights.items():
                pred = qualified_models[name].predict(X_test)
                ensemble_predictions += weight * pred

            # Evaluate ensemble performance
            ensemble_mae = mean_absolute_error(y_test, ensemble_predictions)
            ensemble_r2 = r2_score(y_test, ensemble_predictions)

            # Check if ensemble improves performance significantly
            best_individual_r2 = max(r2_scores.values())
            improvement = ensemble_r2 - best_individual_r2

            if improvement < ENSEMBLE_PERFORMANCE_THRESHOLD:
                logger.debug(
                    f"Ensemble improvement ({improvement:.3f}) below threshold"
                )
                return None, None

            # Create ensemble model wrapper
            class EnsembleModel:
                def __init__(self, models, weights):
                    self.models = models
                    self.weights_ = weights

                def predict(self, X):
                    predictions = np.zeros(len(X))
                    for name, weight in self.weights_.items():
                        pred = self.models[name].predict(X)
                        predictions += weight * pred
                    return predictions

                def get_feature_importance(self):
                    """Get weighted feature importance from ensemble."""
                    importance = None
                    for name, weight in self.weights_.items():
                        if hasattr(self.models[name], "feature_importances_"):
                            model_importance = self.models[name].feature_importances_
                            if importance is None:
                                importance = weight * model_importance
                            else:
                                importance += weight * model_importance
                    return importance

            ensemble_model = EnsembleModel(qualified_models, final_weights)
            ensemble_performance = {"mae": ensemble_mae, "r2": ensemble_r2}

            return ensemble_model, ensemble_performance

        except Exception as e:
            logger.error(f"Error creating ensemble model: {e}")
            return None, None

    def _enhance_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add advanced feature engineering (v1.1.1 Enhanced)."""
        try:
            enhanced_data = data.copy()

            # Rolling averages for weather stability indicators
            if "temperature_2m" in data.columns:
                enhanced_data["temp_rolling_avg"] = (
                    data["temperature_2m"]
                    .rolling(window=ROLLING_WINDOW_HOURS, min_periods=1)
                    .mean()
                )
                enhanced_data["temp_rolling_std"] = (
                    data["temperature_2m"]
                    .rolling(window=ROLLING_WINDOW_HOURS, min_periods=1)
                    .std()
                    .fillna(0)
                )

            if "shortwave_radiation" in data.columns:
                enhanced_data["radiation_rolling_avg"] = (
                    data["shortwave_radiation"]
                    .rolling(window=ROLLING_WINDOW_HOURS, min_periods=1)
                    .mean()
                )

            # Seasonal patterns (v1.1.1)
            if "day_of_year" in data.columns:
                day_of_year = data["day_of_year"]
                for i in range(1, SEASONAL_FEATURE_COUNT + 1):
                    enhanced_data[f"seasonal_sin_{i}"] = np.sin(
                        2 * np.pi * i * day_of_year / 365.25
                    )
                    enhanced_data[f"seasonal_cos_{i}"] = np.cos(
                        2 * np.pi * i * day_of_year / 365.25
                    )

            # Enhanced weather interactions
            weather_cols = [
                "temperature_2m",
                "relative_humidity_2m",
                "cloud_cover",
                "wind_speed_10m",
                "shortwave_radiation",
            ]
            available_weather = [col for col in weather_cols if col in data.columns]

            # Create interaction features
            interactions = [
                ("temperature_2m", "cloud_cover", "temp_cloud_interaction"),
                ("shortwave_radiation", "cloud_cover", "radiation_cloud_interaction"),
                ("temperature_2m", "relative_humidity_2m", "temp_humidity_interaction"),
                ("wind_speed_10m", "temperature_2m", "wind_temp_interaction"),
                (
                    "shortwave_radiation",
                    "relative_humidity_2m",
                    "radiation_humidity_interaction",
                ),
                ("cloud_cover", "wind_speed_10m", "cloud_wind_interaction"),
            ]

            for col1, col2, interaction_name in interactions[
                :WEATHER_INTERACTION_COUNT
            ]:
                if col1 in available_weather and col2 in available_weather:
                    enhanced_data[interaction_name] = data[col1] * data[col2]

            # Power transformations for highly skewed features
            if "shortwave_radiation" in data.columns:
                # Square root transformation for radiation (often has long tail)
                enhanced_data["radiation_sqrt"] = np.sqrt(
                    np.maximum(data["shortwave_radiation"], 0)
                )

            # Time-based efficiency indicators
            if "hour" in data.columns:
                hour = data["hour"]
                # Peak sun hours indicator (10 AM to 4 PM typically most efficient)
                enhanced_data["peak_sun_indicator"] = (
                    (hour >= 10) & (hour <= 16)
                ).astype(float)
                # Morning/evening ramp indicators
                enhanced_data["morning_ramp"] = ((hour >= 6) & (hour <= 10)).astype(
                    float
                )
                enhanced_data["evening_ramp"] = ((hour >= 16) & (hour <= 20)).astype(
                    float
                )

            logger.debug(
                f"Enhanced features: {len(enhanced_data.columns) - len(data.columns)} new features added"
            )
            return enhanced_data

        except Exception as e:
            logger.error(f"Error enhancing features: {e}")
            return data

    def predict_15day_period(
        self,
        installation_id: str,
        center_date: datetime,
        use_simulation: bool = False,
        days: int = 21,
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
                installation_id,
            )
            if not installation_info:
                raise ValueError(f"Installation not found: {installation_id}")

            # Get model
            if installation_id not in self.models:
                raise ValueError(
                    f"No trained model for installation: {installation_id}",
                )

            model_info = self.models[installation_id]
            scaler = self.scalers[installation_id]

            # Define period (center ± half-window days)
            half = max(1, days // 2)
            # Start from 00:00:00 of first day to ensure complete day coverage
            start_date = (center_date - timedelta(days=half)).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            # End at 23:59:59 of last day to ensure complete day coverage
            end_date = (center_date + timedelta(days=half)).replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999,
            )

            # Get or simulate weather data (use installation-specific metadata for coordinates)
            weather_data, weather_source_info = self._get_weather_data_for_period(
                installation_info,
                start_date,
                end_date,
                center_date,
                use_simulation,
            )

            # Prepare prediction features
            prediction_features = self._prepare_prediction_features(
                weather_data,
                installation_info,
                installation_id,
            )

            # Make predictions
            predictions = self._make_predictions(
                model_info,
                scaler,
                prediction_features,
                installation_id,
            )

            # Enforce physical constraint: zero production at night / very low irradiance
            try:
                # Use irradiance-only gating to avoid timezone/elevation mismatches
                radiation = (
                    weather_data["shortwave_radiation"].to_numpy()
                    if "shortwave_radiation" in weather_data.columns
                    else np.zeros(len(weather_data))
                )
                positive_mask = radiation > PRODUCTION_RADIATION_THRESHOLD
                predictions = np.where(positive_mask, predictions, 0)
                # Apply minimal positive floor when irradiance is present to avoid zero with nonzero sun
                floor = (radiation / 1000.0) * MIN_SPECIFIC_FLOOR_COEF
                predictions = np.where(
                    positive_mask & (predictions < floor), floor, predictions
                )
            except Exception as _e:
                # If any issue occurs, keep original non-negative clamp only
                predictions = np.maximum(predictions, 0)

            # Assign rankings using corrected predictions
            rankings = self._assign_rankings(predictions, installation_id)

            # Combine results
            results = self._combine_prediction_results(
                weather_data,
                predictions,
                rankings,
                center_date,
                installation_info,
                use_simulation,
                weather_source_info,
            )

            return results

        except Exception as e:
            logger.error(f"Error in 15-day prediction: {e}")
            raise

    def _get_weather_data_for_period(
        self,
        installation_info,
        start_date: datetime,
        end_date: datetime,
        center_date: datetime,
        use_simulation: bool,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Get weather data for the specified period and return source metadata.

        Uses installation-specific latitude/longitude sourced from metadata. Falls back to
        Data/PV Plants Metadata.xlsx if missing, then to simulator's location coords.
        """
        try:
            location = installation_info.location
            lat = getattr(installation_info, "latitude", None)
            lon = getattr(installation_info, "longitude", None)

            # Excel fallback when coordinates are missing or zero
            if (not lat or not lon or lat == 0.0 or lon == 0.0):
                try:
                    # Prefer lowercase 'data' directory; keep compatibility if packaging bundles resources differently
                    meta_path = get_resource_path("data/PV Plants Metadata.xlsx")
                    if meta_path.exists():
                        mdf = pd.read_excel(meta_path)
                        cols = {c.lower(): c for c in mdf.columns}
                        sn_col = cols.get("pv serial number") or cols.get("pv_serial_number")
                        loc_col = cols.get("location")
                        lat_col = cols.get("latitude")
                        lon_col = cols.get("longitude")
                        row = None
                        if sn_col and getattr(installation_info, "serial_number", None):
                            row = mdf[mdf[sn_col] == installation_info.serial_number]
                        if (row is None or row.empty) and loc_col:
                            row = mdf[mdf[loc_col] == location]
                        if row is not None and not row.empty and lat_col and lon_col:
                            try:
                                lat = float(row.iloc[0][lat_col])
                                lon = float(row.iloc[0][lon_col])
                            except Exception:
                                pass
                except Exception:
                    pass

            # Fallback to simulator's stored coords
            if (not lat or not lon) and getattr(self, "weather_simulator", None):
                coords = self.weather_simulator.location_coords.get(location)
                if coords:
                    lat, lon = coords

            # 1) Try real weather via provider (historical or forecast)
            if (lat and lon) and getattr(self, "weather_provider", None):
                provider = self.weather_provider
                prefer_historical = end_date <= datetime.utcnow()
                df_api = provider.get_hourly_weather(
                    latitude=float(lat),
                    longitude=float(lon),
                    start=start_date,
                    end=end_date,
                    prefer_historical=prefer_historical,
                )
                if df_api is not None and not df_api.empty:
                    # Coverage check
                    expected_hours = (
                        int((end_date - start_date).total_seconds() / 3600) + 1
                    )
                    coverage_ratio = (
                        len(df_api) / expected_hours if expected_hours > 0 else 0
                    )
                    if coverage_ratio >= WEATHER_COVERAGE_THRESHOLD:
                        logger.info(
                            f"Using Open-Meteo weather data for {location} (coverage: {coverage_ratio:.2%})",
                        )
                        df_api = df_api.copy()
                        df_api["is_simulated_weather"] = False
                        return df_api, {
                            "weather_source": "api",
                            "provider": "open-meteo",
                            "provider_source": "archive"
                            if prefer_historical
                            else "forecast",
                            "coverage_ratio": coverage_ratio,
                            "simulated_points": 0,
                        }
                    else:
                        logger.warning(
                            f"Open-Meteo coverage low ({coverage_ratio:.2%}); filling gaps via simulator",
                        )
                        # Fill missing hours with simulator to complete dataset
                        simulated = (
                            self.weather_simulator.simulate_weather(
                                location,
                                start_date,
                                end_date,
                                center_date,
                            )
                            if self.weather_simulator
                            else None
                        )
                        # Build full index and stitch
                        full_index = pd.date_range(start_date, end_date, freq="h")
                        stitched = pd.DataFrame(index=full_index)
                        if simulated is not None and not simulated.empty:
                            stitched = stitched.join(simulated, how="left")
                        stitched = stitched.combine_first(df_api)
                        # Mark simulated rows
                        is_sim = ~stitched.index.isin(df_api.index)
                        stitched["is_simulated_weather"] = is_sim
                        sim_count = int(is_sim.sum())
                        return stitched, {
                            "weather_source": "api+simulation",
                            "provider": "open-meteo",
                            "provider_source": "archive"
                            if prefer_historical
                            else "forecast",
                            "coverage_ratio": coverage_ratio,
                            "simulated_points": sim_count,
                        }

            # 2) Fallback to local historical weather (if present)
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

                if coverage_ratio >= WEATHER_COVERAGE_THRESHOLD:
                    logger.info(
                        f"Using historical weather data for {location} (coverage: {coverage_ratio:.2%})",
                    )
                    hist = historical_period.copy()
                    hist["is_simulated_weather"] = False
                    return hist, {
                        "weather_source": "historical",
                        "coverage_ratio": coverage_ratio,
                        "simulated_points": 0,
                    }

            # Use simulation if requested or no historical data
            if use_simulation and self.weather_simulator:
                logger.info(f"Using simulated weather data for {location}")
                simulated_weather = self.weather_simulator.simulate_weather(
                    location,
                    start_date,
                    end_date,
                    center_date,
                )
                sim = simulated_weather.copy()
                sim["is_simulated_weather"] = True
                return sim, {
                    "weather_source": "simulation",
                    "simulated_points": len(sim),
                }
            # Fallback to available historical data or raise error
            elif historical_weather is not None and len(historical_period) > 0:
                logger.warning(
                    f"Using partial historical data for {location} (coverage: {coverage_ratio:.2%})",
                )
                hist = historical_period.copy()
                hist["is_simulated_weather"] = False
                return hist, {
                    "weather_source": "historical",
                    "coverage_ratio": coverage_ratio,
                    "simulated_points": 0,
                }
            else:
                raise ValueError(
                    f"No weather data available for {location} and simulation not enabled",
                )

        except Exception as e:
            logger.error(f"Error getting weather data for period: {e}")
            raise

    def predict_period_for_custom(
        self,
        location: str,
        capacity_kwp: float,
        center_date: datetime,
        days: int = 21,
    ) -> dict[str, Any]:
        """Simulate predictions for a custom station at given location/capacity.

        Uses a reference installation model from the same location and runs the
        standard pipeline with installation_info overridden for capacity/location.
        """
        # Pick a reference installation from this location with a trained model
        ref_id = None
        ref_info = None
        for inst_id, info in self.get_available_installations():
            if info.location == location:
                ref_id, ref_info = inst_id, info
                break
        if ref_id is None or ref_info is None:
            # Fallback: take any available installation
            avail = self.get_available_installations()
            if not avail:
                raise ValueError("No trained installations available for custom simulation")
            ref_id, ref_info = avail[0]

        # Build a shallow copy of installation_info with overridden capacity/location
        class _Proxy:
            pass
        proxy = _Proxy()
        proxy.installation_id = ref_info.installation_id
        proxy.location = location
        proxy.installed_power_kwp = float(capacity_kwp)
        proxy.serial_number = getattr(ref_info, "serial_number", "CUSTOM")
        proxy.latitude = getattr(ref_info, "latitude", None)
        proxy.longitude = getattr(ref_info, "longitude", None)

        # Compute period
        half = max(1, days // 2)
        start_date = (center_date - timedelta(days=half)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (center_date + timedelta(days=half)).replace(hour=23, minute=59, second=59, microsecond=999999)

        # Weather
        weather_data, weather_source_info = self._get_weather_data_for_period(
            proxy,
            start_date,
            end_date,
            center_date,
            True,
        )
        # Features and predictions using reference model
        prediction_features = self._prepare_prediction_features(weather_data, proxy, ref_id)
        predictions = self._make_predictions(
            self.models[ref_id],
            self.scalers[ref_id],
            prediction_features,
            ref_id,
        )
        rankings = self._assign_rankings(predictions, ref_id)
        return self._combine_prediction_results(
            weather_data,
            predictions,
            rankings,
            center_date,
            proxy,
            True,
            weather_source_info,
        )

    def _prepare_prediction_features(
        self,
        weather_data: pd.DataFrame,
        installation_info: InstallationInfo,
        installation_id: str = None,
    ) -> np.ndarray:
        """Prepare features for prediction from weather data (v1.1.1 Enhanced).

        Uses identical feature engineering as training and aligns with persisted feature names.
        """
        try:
            features_df = weather_data.copy()

            # Add time-based features (same as training)
            features_df["hour"] = features_df.index.hour
            features_df["day_of_year"] = features_df.index.dayofyear
            features_df["month"] = features_df.index.month

            # Add solar elevation
            features_df["solar_elevation"] = self._compute_solar_elevation(
                features_df.index,
                installation_info.latitude,
                installation_info.longitude,
            )

            # Apply SAME enhanced feature engineering as training (v1.1.1 Fix)
            features_df = self._enhance_features(features_df)

            # Get expected feature order from training (v1.1.1 Fix)
            expected_features = None
            if installation_id and installation_id in self.feature_columns:
                expected_features = self.feature_columns[installation_id]
                logger.debug(
                    f"Using {len(expected_features)} expected features for {installation_id}"
                )

            if expected_features:
                # Align features to training order
                missing_features = []
                for col in expected_features:
                    if col not in features_df.columns:
                        features_df[col] = 0.0  # Fill missing features with zeros
                        missing_features.append(col)

                if missing_features:
                    logger.debug(
                        f"Filled {len(missing_features)} missing features with zeros: {missing_features[:3]}..."
                    )

                # Reorder to match training exactly
                features_df = features_df[expected_features]
                logger.debug(
                    f"Aligned prediction features to training order: {len(expected_features)} features"
                )
            else:
                # Fallback: use basic feature set (legacy behavior)
                logger.warning(
                    f"No expected features found for {installation_id} - using fallback feature set"
                )
                fallback_columns = [
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

                # Add basic interactions
                if (
                    "temperature_2m" in features_df.columns
                    and "cloud_cover" in features_df.columns
                ):
                    features_df["temp_cloud_interaction"] = (
                        features_df["temperature_2m"]
                        * (100 - features_df["cloud_cover"])
                        / 100
                    )
                    fallback_columns.append("temp_cloud_interaction")

                if (
                    "shortwave_radiation" in features_df.columns
                    and "cloud_cover" in features_df.columns
                ):
                    features_df["radiation_cloud_interaction"] = (
                        features_df["shortwave_radiation"]
                        * (100 - features_df["cloud_cover"])
                        / 100
                    )
                    fallback_columns.append("radiation_cloud_interaction")

                available_features = [
                    col for col in fallback_columns if col in features_df.columns
                ]
                features_df = features_df[available_features]

            # Fill any remaining NaN values
            features_df = features_df.fillna(0)

            logger.debug(f"Prepared prediction features: {features_df.shape}")
            return features_df.values

        except Exception as e:
            logger.error(f"Error preparing prediction features: {e}")
            raise

    def _compute_solar_elevation(
        self,
        timestamps: pd.DatetimeIndex,
        latitude: float,
        _longitude: float,
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
                + np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_rad),
            )

            return np.degrees(elevation)

        except Exception as e:
            logger.error(f"Error computing solar elevation: {e}")
            return np.zeros(len(timestamps))

    def _make_predictions(
        self,
        model_info: dict[str, Any],
        scaler: StandardScaler,
        features: np.ndarray,
        installation_id: str = None,
    ) -> np.ndarray:
        """Make energy production predictions with feature alignment guard rails (v1.1.1)."""
        try:
            # Feature dimension guard rail (v1.1.1 Fix)
            expected_features = scaler.n_features_in_
            actual_features = features.shape[1]

            if actual_features != expected_features:
                error_msg = (
                    f"Feature mismatch for {installation_id}: "
                    f"expected {expected_features} features, got {actual_features}"
                )
                logger.error(error_msg)

                # Try to provide helpful context
                if installation_id and installation_id in self.feature_columns:
                    expected_names = self.feature_columns[installation_id]
                    logger.error(
                        f"Expected features ({len(expected_names)}): {expected_names[:5]}..."
                    )

                raise ValueError(
                    f"Feature alignment failed: {error_msg}. "
                    "This typically means the model cache is stale. "
                    "Try clearing the cache or retraining the model."
                )

            # Scale features
            features_scaled = scaler.transform(features)

            # Get best model
            model = model_info["best_model"]

            # Make predictions
            predictions = model.predict(features_scaled)

            # Ensure non-negative predictions
            predictions = np.maximum(predictions, 0)

            logger.debug(
                f"Successfully made predictions: {predictions.shape} with {actual_features} features"
            )
            return predictions

        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            raise

    def _assign_rankings(
        self,
        predictions: np.ndarray,
        installation_id: str,
    ) -> list[int]:
        """Assign rankings to predictions based on fixed specific-energy bins."""
        # predictions are specific energy (kWh/kWp)
        ranks: list[int] = []
        for val in predictions:
            if val < 0.05:
                ranks.append(0)
            elif val < 0.2:
                ranks.append(1)
            elif val < 0.4:
                ranks.append(2)
            elif val < 0.6:
                ranks.append(3)
            elif val < 0.8:
                ranks.append(4)
            else:
                ranks.append(5)
        return ranks
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
                    if percentile >= RANKING_EXCELLENT_PERCENTILE:
                        rankings.append(5)  # Excellent
                    elif percentile >= RANKING_GOOD_PERCENTILE:
                        rankings.append(4)  # Good
                    elif percentile >= RANKING_AVERAGE_PERCENTILE:
                        rankings.append(3)  # Average
                    elif percentile >= RANKING_POOR_PERCENTILE:
                        rankings.append(2)  # Below average
                    else:
                        rankings.append(1)  # Poor
                return rankings
            else:
                # Use default ranking if no historical context
                return [DEFAULT_RANKING] * len(predictions)

        except Exception as e:
            logger.error(f"Error assigning rankings: {e}")
            return [DEFAULT_RANKING] * len(predictions)

    def _combine_prediction_results(
        self,
        weather_data: pd.DataFrame,
        predictions: np.ndarray,
        rankings: list[int],
        center_date: datetime,
        installation_info: InstallationInfo,
        used_simulation: bool,
        weather_source_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Combine all prediction results into a comprehensive output."""
        try:
            # Create results DataFrame
            results_df = weather_data.copy()
            # Align lengths defensively (handles DST 23/25-hour days, gaps, feature drops)
            min_len = min(len(results_df), len(predictions), len(rankings))
            if len(results_df) != min_len:
                results_df = results_df.iloc[:min_len].copy()
            if len(predictions) != min_len:
                predictions = predictions[:min_len]
            if len(rankings) != min_len:
                rankings = rankings[:min_len]
            # Now lengths are consistent
            results_df["predicted_specific_energy"] = predictions
            results_df["predicted_total_energy"] = (
                predictions * installation_info.installed_power_kwp
            )
            results_df["ranking"] = rankings

            # *** CRITICAL FIX: Add historical data when available ***
            # Get historical energy data from the data processor
            historical_data = self.data_processor.get_combined_data(
                installation_info.installation_id,
            )
            if (
                historical_data is not None
                and "Produced Energy (kWh)" in historical_data.columns
            ):
                # Merge historical data with results based on datetime index
                historical_energy_cols = [
                    "Produced Energy (kWh)",
                    "Specific Energy (kWh/kWp)",
                ]
                available_historical_cols = [
                    col
                    for col in historical_energy_cols
                    if col in historical_data.columns
                ]

                if available_historical_cols:
                    # Only merge rows that have matching timestamps
                    historical_subset = historical_data[available_historical_cols].copy()
                    # Deduplicate any ambiguous local-time duplicates (e.g., DST end 01:00 occurs twice)
                    # Keep the first occurrence to maintain a single row per timestamp before merge
                    if historical_subset.index.has_duplicates:
                        dup_count = int(historical_subset.index.duplicated(keep="first").sum())
                        historical_subset = historical_subset[~historical_subset.index.duplicated(keep="first")]
                        logger.debug(
                            f"Deduplicated {dup_count} duplicate historical timestamp rows before merge"
                        )
                    results_df = results_df.merge(
                        historical_subset,
                        left_index=True,
                        right_index=True,
                        how="left",
                    )
                    logger.info(
                        f"Successfully merged historical energy data: {len(results_df[results_df['Produced Energy (kWh)'].notna()])} historical records found",
                    )
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

            # Map colors/descriptions from the DataFrame's ranking column to avoid length mismatches after merge
            results_df["ranking_color"] = results_df["ranking"].map(color_map).fillna("#f1c40f")
            results_df["ranking_description"] = results_df["ranking"].map(desc_map).fillna("Average")

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
                    },
                )
                .round(2)
            )

            # Calculate period statistics
            period_stats = {
                "total_energy_kwh": float(results_df["predicted_total_energy"].sum()),
                "average_specific_energy": float(
                    results_df["predicted_specific_energy"].mean(),
                ),
                "peak_hour_energy": float(
                    results_df["predicted_specific_energy"].max(),
                ),
                "peak_hour_time": str(
                    results_df.loc[
                        results_df["predicted_specific_energy"].idxmax()
                    ].name,
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
                        installation_info.installation_id,
                        {},
                    ),
                    **(weather_source_info or {}),
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

    def get_enhanced_model_metrics(self, installation_id: str) -> dict[str, Any] | None:
        """Get comprehensive model metrics including ensemble information (v1.1.1)."""
        if (
            installation_id not in self.models
            or installation_id not in self.model_performance
        ):
            return None

        model_info = self.models[installation_id]
        performance = self.model_performance[installation_id]

        metrics = {
            "installation_id": installation_id,
            "best_model": model_info.get("best_model_name", "unknown"),
            "model_count": len(model_info.get("all_models", {})),
            "performance_metrics": performance,
            "ensemble_info": {
                "has_ensemble": "ensemble" in model_info.get("all_models", {}),
                "ensemble_weights": model_info.get("ensemble_weights"),
                "ensemble_performance": performance.get("ensemble"),
            },
            "model_comparison": self._compare_model_performance(performance),
            "feature_importance": self._get_feature_importance(installation_id),
        }

        return metrics

    def _compare_model_performance(
        self, performance: dict[str, dict[str, float]]
    ) -> dict[str, Any]:
        """Compare performance across different models (v1.1.1)."""
        if not performance:
            return {}

        # Find best and worst performing models
        r2_scores = {name: metrics["r2"] for name, metrics in performance.items()}
        mae_scores = {name: metrics["mae"] for name, metrics in performance.items()}

        best_r2_model = max(r2_scores.keys(), key=lambda k: r2_scores[k])
        worst_r2_model = min(r2_scores.keys(), key=lambda k: r2_scores[k])
        best_mae_model = min(mae_scores.keys(), key=lambda k: mae_scores[k])

        return {
            "best_r2_model": best_r2_model,
            "best_r2_score": r2_scores[best_r2_model],
            "worst_r2_model": worst_r2_model,
            "worst_r2_score": r2_scores[worst_r2_model],
            "best_mae_model": best_mae_model,
            "best_mae_score": mae_scores[best_mae_model],
            "performance_spread": {
                "r2_range": r2_scores[best_r2_model] - r2_scores[worst_r2_model],
                "mae_range": max(mae_scores.values()) - min(mae_scores.values()),
            },
            "model_rankings": sorted(
                r2_scores.items(), key=lambda x: x[1], reverse=True
            ),
        }

    def _get_feature_importance(self, installation_id: str) -> dict[str, Any] | None:
        """Get feature importance from the best model (v1.1.1)."""
        if installation_id not in self.models:
            return None

        try:
            model_info = self.models[installation_id]
            best_model = model_info.get("best_model")

            if hasattr(best_model, "feature_importances_"):
                return {
                    "has_importance": True,
                    "importances": best_model.feature_importances_.tolist(),
                    "model_type": model_info.get("best_model_name", "unknown"),
                }
            elif hasattr(best_model, "get_feature_importance"):  # For ensemble models
                importance = best_model.get_feature_importance()
                if importance is not None:
                    return {
                        "has_importance": True,
                        "importances": importance.tolist(),
                        "model_type": "ensemble",
                        "ensemble_weights": model_info.get("ensemble_weights"),
                    }

            return {
                "has_importance": False,
                "reason": "Model does not support feature importance",
            }

        except Exception as e:
            logger.error(f"Error getting feature importance for {installation_id}: {e}")
            return {"has_importance": False, "error": str(e)}

    def retrain_models(self):
        """Public API: retrain all models for all installations."""
        try:
            # Clear existing in-memory models to avoid stale references
            self.models.clear()
            self.scalers.clear()
            self.model_performance.clear()
            self._train_all_models()
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
            raise

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
            test_installation,
            test_date,
            use_simulation=True,
        )

        print(f"Prediction results for {test_installation}:")
        print(f"Period: {results['prediction_period']}")
        print(
            f"Total energy: {results['period_statistics']['total_energy_kwh']:.2f} kWh",
        )
        print(
            f"Average specific energy: {results['period_statistics']['average_specific_energy']:.2f} kWh/kWp",
        )
