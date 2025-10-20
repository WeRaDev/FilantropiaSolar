#!/usr/bin/env python3
"""
Optimized Energy Predictor with Smart Model Caching
Extends EnhancedEnergyPredictor with intelligent ML model caching
for instant loading and improved performance.
"""

from collections.abc import Callable
import logging
import time
from typing import Any

import numpy as np

from ..data_processing.optimized_data_processor import OptimizedDataProcessor
from ..weather_simulation.weather_simulator import WeatherSimulator
from .enhanced_energy_predictor import EnhancedEnergyPredictor

logger = logging.getLogger(__name__)

# Constants for model performance thresholds and timing
FAST_TRAINING_THRESHOLD_SECONDS = 5
SLOW_TRAINING_THRESHOLD_SECONDS = 10
VERY_SLOW_TRAINING_THRESHOLD_SECONDS = 120
STRONG_CORRELATION_THRESHOLD = 0.7
MODERATE_CORRELATION_THRESHOLD = 0.3
OUTSTANDING_R2_THRESHOLD = 0.9
GOOD_R2_THRESHOLD = 0.8
MODERATE_R2_THRESHOLD = 0.7


class OptimizedEnergyPredictor(EnhancedEnergyPredictor):
    """
    Performance-optimized energy predictor with smart model caching.

    Features:
    - Intelligent ML model caching and loading
    - Performance monitoring and metrics
    - Progress callbacks for training updates
    - Model validation and integrity checks
    - Incremental model updates
    """

    def __init__(
        self,
        data_processor: OptimizedDataProcessor,
        weather_simulator: WeatherSimulator = None,
        progress_callback: Callable | None = None,
    ):
        """Initialize optimized energy predictor."""
        self.progress_callback = progress_callback
        self.training_start_time = None
        self.model_performance_metrics = {}

        # Use the cache manager from data processor
        self.cache_manager = (
            data_processor.cache_manager
            if hasattr(data_processor, "cache_manager")
            else None
        )

        # Always set these first
        self.data_processor = data_processor
        self.weather_simulator = weather_simulator

        # Check if we can load cached models
        if self._can_use_cached_models():
            logger.info("Loading ML models from cache...")
            self._load_models_from_cache()
            # Initialize without training
            self._initialize_without_training()
        else:
            logger.info("Cache miss - training ML models...")
            self._report_progress("Initializing ML model training...", 0)
            super().__init__(data_processor, weather_simulator)
            if self.cache_manager:
                self._cache_all_models()

        self._calculate_training_metrics()

    def _report_progress(self, message: str, progress: float):
        """Report training progress to callback."""
        if self.progress_callback:
            self.progress_callback(message, progress)
        logger.info(f"ML Progress: {progress:.1f}% - {message}")

    def _can_use_cached_models(self) -> bool:
        """Check if all required models are cached and valid."""
        if not self.cache_manager:
            return False

        # Check if models exist for all installations
        installations = list(self.data_processor.installations.keys())

        for installation_id in installations:
            # Check for best model (we cache the best performing model)
            if not self.cache_manager.load_cached_model(installation_id, "best_model"):
                logger.info(f"No cached model found for {installation_id}")
                return False

        logger.info("All required ML models found in cache")
        return True

    def _load_models_from_cache(self):
        """Load all ML models from cache."""
        start_time = time.time()
        self.training_start_time = start_time

        try:
            self.models = {}
            self.scalers = {}
            self.model_performance = {}

            installations = list(self.data_processor.installations.keys())
            total_installations = len(installations)

            for i, installation_id in enumerate(installations):
                progress = (i / total_installations) * 100
                self._report_progress(
                    f"Loading model for {installation_id}...", progress
                )

                # Load best model
                best_model = self.cache_manager.load_cached_model(
                    installation_id, "best_model"
                )
                if best_model:
                    # Maintain compatibility with EnhancedEnergyPredictor structure
                    self.models[installation_id] = {
                        "best_model": best_model,
                        "best_model_name": "cached_model",  # Generic name for cached models
                        "all_models": {"cached_model": best_model},
                    }

                # Load scaler
                scaler = self.cache_manager.load_cached_model(installation_id, "scaler")
                if scaler:
                    self.scalers[installation_id] = scaler

                # Load performance metrics (stored as model)
                performance = self.cache_manager.load_cached_model(
                    installation_id, "performance"
                )
                if performance:
                    self.model_performance[installation_id] = performance

            self._report_progress("Model cache loading completed!", 100)

            load_time = time.time() - start_time
            logger.info(
                f"Successfully loaded all ML models from cache in {load_time:.2f} seconds"
            )

        except Exception as e:
            logger.error(f"Error loading models from cache: {e}")
            raise

    def _initialize_without_training(self):
        """Initialize predictor components without training models."""
        # Initialize model configuration (same as parent)
        self.model_types = {
            "random_forest": self._get_random_forest_template(),
            "gradient_boost": self._get_gradient_boost_template(),
            "linear": self._get_linear_template(),
        }

    def _get_random_forest_template(self):
        """Get Random Forest template."""
        from sklearn.ensemble import RandomForestRegressor

        return RandomForestRegressor(
            n_estimators=100,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )

    def _get_gradient_boost_template(self):
        """Get Gradient Boosting template."""
        from sklearn.ensemble import GradientBoostingRegressor

        return GradientBoostingRegressor(
            n_estimators=100,
            max_depth=8,
            learning_rate=0.1,
            min_samples_split=5,
            random_state=42,
        )

    def _get_linear_template(self):
        """Get Linear Regression template."""
        from sklearn.linear_model import LinearRegression

        return LinearRegression()

    def _cache_all_models(self):
        """Cache all trained ML models for future fast loading."""
        if not self.cache_manager:
            return

        try:
            logger.info("Caching trained ML models...")

            for installation_id in self.models:
                # Cache best model
                if "best_model" in self.models[installation_id]:
                    best_model = self.models[installation_id]["best_model"]
                    performance_metrics = self.model_performance.get(
                        installation_id, {}
                    )

                    self.cache_manager.cache_model(
                        best_model,
                        installation_id,
                        "best_model",
                        performance_metrics,
                        f"training_hash_{installation_id}",  # Simplified training data hash
                    )

                # Cache scaler
                if installation_id in self.scalers:
                    self.cache_manager.cache_model(
                        self.scalers[installation_id],
                        installation_id,
                        "scaler",
                        {},
                        f"scaler_hash_{installation_id}",
                    )

                # Cache performance metrics
                if installation_id in self.model_performance:
                    self.cache_manager.cache_model(
                        self.model_performance[installation_id],
                        installation_id,
                        "performance",
                        {"cached_at": time.time()},
                        f"performance_hash_{installation_id}",
                    )

            logger.info("All ML models successfully cached")

        except Exception as e:
            logger.error(f"Error caching models: {e}")

    def _train_all_models(self):
        """Override to add progress reporting."""
        installations = list(self.data_processor.get_installation_list())
        total_installations = len(installations)

        for i, (installation_id, installation_info) in enumerate(installations):
            progress = (i / total_installations) * 100
            self._report_progress(f"Training models for {installation_id}...", progress)

            try:
                self._train_installation_models(installation_id, installation_info)
            except Exception as e:
                logger.error(f"Error training models for {installation_id}: {e}")

        self._report_progress("ML model training completed!", 100)

    def _calculate_training_metrics(self):
        """Calculate and store training performance metrics."""
        if self.training_start_time:
            total_training_time = time.time() - self.training_start_time
        else:
            total_training_time = 0

        # Calculate model statistics
        total_models_trained = len(self.models)
        avg_r2_score = 0
        avg_mae = 0

        if self.model_performance:
            all_r2_scores = []
            all_mae_scores = []

            for installation_metrics in self.model_performance.values():
                for model_metrics in installation_metrics.values():
                    if isinstance(model_metrics, dict):
                        if "r2" in model_metrics:
                            all_r2_scores.append(model_metrics["r2"])
                        if "mae" in model_metrics:
                            all_mae_scores.append(model_metrics["mae"])

            avg_r2_score = np.mean(all_r2_scores) if all_r2_scores else 0
            avg_mae = np.mean(all_mae_scores) if all_mae_scores else 0

        self.model_performance_metrics = {
            "training_time_seconds": total_training_time,
            "total_models_trained": total_models_trained,
            "average_r2_score": avg_r2_score,
            "average_mae": avg_mae,
            "cache_enabled": self.cache_manager is not None,
            "training_method": "cached"
            if self.training_start_time
            and total_training_time < FAST_TRAINING_THRESHOLD_SECONDS
            else "full_training",
        }

    def get_model_performance_report(self) -> dict[str, Any]:
        """Get comprehensive model performance report."""
        report = {
            "training_metrics": self.model_performance_metrics,
            "model_details": {},
            "performance_analysis": self._analyze_model_performance(),
            "optimization_recommendations": self._get_model_optimization_suggestions(),
        }

        # Add detailed model information
        for installation_id, performance in self.model_performance.items():
            if installation_id in self.data_processor.installations:
                location = self.data_processor.installations[installation_id].location
                capacity = self.data_processor.installations[
                    installation_id
                ].installed_power_kwp

                report["model_details"][installation_id] = {
                    "location": location,
                    "capacity_kwp": capacity,
                    "performance_metrics": performance,
                    "model_cached": self.cache_manager.load_cached_model(
                        installation_id, "best_model"
                    )
                    is not None
                    if self.cache_manager
                    else False,
                }

        return report

    def _analyze_model_performance(self) -> dict[str, Any]:
        """Analyze overall model performance across installations."""
        analysis = {
            "performance_distribution": {},
            "location_performance": {},
            "capacity_correlation": {},
        }

        try:
            # Collect performance data
            r2_scores = []
            mae_scores = []
            location_performance = {}
            capacity_performance = []

            for installation_id, performance in self.model_performance.items():
                if not isinstance(performance, dict):
                    continue

                installation_info = self.data_processor.installations.get(
                    installation_id
                )
                if not installation_info:
                    continue

                # Find best model metrics
                best_r2 = 0
                best_mae = float("inf")

                for _model_name, metrics in performance.items():
                    if isinstance(metrics, dict) and "r2" in metrics:
                        if metrics["r2"] > best_r2:
                            best_r2 = metrics["r2"]
                            best_mae = metrics.get("mae", best_mae)

                if best_r2 > 0:
                    r2_scores.append(best_r2)
                    mae_scores.append(best_mae)

                    # Group by location
                    location = installation_info.location
                    if location not in location_performance:
                        location_performance[location] = []
                    location_performance[location].append(best_r2)

                    # Capacity correlation
                    capacity_performance.append(
                        (installation_info.installed_power_kwp, best_r2)
                    )

            # Performance distribution
            if r2_scores:
                analysis["performance_distribution"] = {
                    "r2_mean": np.mean(r2_scores),
                    "r2_std": np.std(r2_scores),
                    "r2_min": np.min(r2_scores),
                    "r2_max": np.max(r2_scores),
                    "mae_mean": np.mean(mae_scores),
                    "mae_std": np.std(mae_scores),
                }

            # Location performance
            for location, scores in location_performance.items():
                analysis["location_performance"][location] = {
                    "mean_r2": np.mean(scores),
                    "installation_count": len(scores),
                }

            # Capacity correlation
            if capacity_performance and len(capacity_performance) > 1:
                capacities, r2s = zip(*capacity_performance, strict=False)
                correlation = np.corrcoef(capacities, r2s)[0, 1]
                analysis["capacity_correlation"] = {
                    "correlation_coefficient": correlation,
                    "interpretation": "Strong positive"
                    if correlation > STRONG_CORRELATION_THRESHOLD
                    else "Moderate"
                    if correlation > MODERATE_CORRELATION_THRESHOLD
                    else "Weak",
                }

        except Exception as e:
            logger.error(f"Error analyzing model performance: {e}")
            analysis["error"] = str(e)

        return analysis

    def _get_model_optimization_suggestions(self) -> list:
        """Generate optimization suggestions based on model performance."""
        suggestions = []

        try:
            metrics = self.model_performance_metrics
            training_time = metrics.get("training_time_seconds", 0)
            avg_r2 = metrics.get("average_r2_score", 0)

            # Training time suggestions
            if training_time < SLOW_TRAINING_THRESHOLD_SECONDS:
                suggestions.append(
                    "✅ Excellent model loading performance (cached models)"
                )
            elif training_time > VERY_SLOW_TRAINING_THRESHOLD_SECONDS:
                suggestions.append(
                    "⚠️ Consider enabling model caching to reduce training time"
                )

            # Model accuracy suggestions
            if avg_r2 > OUTSTANDING_R2_THRESHOLD:
                suggestions.append("✅ Outstanding model accuracy across installations")
            elif avg_r2 > GOOD_R2_THRESHOLD:
                suggestions.append(
                    "✅ Good model accuracy - suitable for production use"
                )
            elif avg_r2 > MODERATE_R2_THRESHOLD:
                suggestions.append(
                    "⚠️ Moderate model accuracy - consider feature engineering"
                )
            else:
                suggestions.append(
                    "❌ Low model accuracy - review data quality and model architecture"
                )

            # Performance analysis suggestions
            analysis = self._analyze_model_performance()
            if "location_performance" in analysis:
                poor_locations = [
                    loc
                    for loc, perf in analysis["location_performance"].items()
                    if perf.get("mean_r2", 0) < MODERATE_R2_THRESHOLD
                ]
                if poor_locations:
                    suggestions.append(
                        f"🔍 Focus improvement on locations: {', '.join(poor_locations)}"
                    )

            # Cache suggestions
            if not self.cache_manager:
                suggestions.append("💡 Enable model caching for instant loading")

        except Exception as e:
            suggestions.append(f"❌ Error generating suggestions: {e}")

        return suggestions

    def add_new_installation_model(self, installation_id: str) -> bool:
        """
        Train and cache model for new installation.

        Args:
            installation_id: ID of the new installation

        Returns:
            Success status
        """
        try:
            logger.info(f"Training model for new installation: {installation_id}")

            # Get installation info
            installation_info = self.data_processor.installations.get(installation_id)
            if not installation_info:
                raise ValueError(f"Installation {installation_id} not found")

            # Train models for this installation
            self._train_installation_models(installation_id, installation_info)

            # Cache the new model
            if self.cache_manager and installation_id in self.models:
                best_model = self.models[installation_id]["best_model"]
                performance_metrics = self.model_performance.get(installation_id, {})

                self.cache_manager.cache_model(
                    best_model,
                    installation_id,
                    "best_model",
                    performance_metrics,
                    f"training_hash_{installation_id}",
                )

                # Cache scaler
                if installation_id in self.scalers:
                    self.cache_manager.cache_model(
                        self.scalers[installation_id],
                        installation_id,
                        "scaler",
                        {},
                        f"scaler_hash_{installation_id}",
                    )

            logger.info(f"Successfully trained and cached model for {installation_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding new installation model: {e}")
            return False

    def get_training_summary(self) -> str:
        """Get human-readable training summary."""
        metrics = self.model_performance_metrics

        if not metrics:
            return "❌ No training metrics available"

        training_method = (
            "✅ Cached Loading"
            if metrics.get("training_method") == "cached"
            else "🔄 Full Training"
        )
        training_time = metrics.get("training_time_seconds", 0)
        avg_r2 = metrics.get("average_r2_score", 0)

        summary = f"""
🤖 **ML Model Training Summary**

⚡ **Method**: {training_method}
⏱️ **Training Time**: {training_time:.2f} seconds
🎯 **Models Trained**: {metrics.get("total_models_trained", 0)}
📊 **Average R² Score**: {avg_r2:.3f}
📉 **Average MAE**: {metrics.get("average_mae", 0):.3f}

🚀 **Optimization Suggestions**:
"""

        suggestions = self._get_model_optimization_suggestions()
        for suggestion in suggestions:
            summary += f"   {suggestion}\n"

        return summary
