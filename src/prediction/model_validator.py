#!/usr/bin/env python3
"""
ML Model Cross-Validation System
Implements location-based cross-validation by excluding one installation from training
and using it for model validation against real historical data.
"""

from datetime import datetime, timedelta
import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ..data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
from ..weather_simulation.weather_simulator import WeatherSimulator
from .enhanced_energy_predictor import EnhancedEnergyPredictor

logger = logging.getLogger(__name__)

# Validation thresholds
MIN_TEST_DATA_POINTS = 100  # Minimum data points needed for testing
MIN_DAILY_DATA_HOURS = 24  # Minimum hours of data needed (one day)
EXCELLENT_SUCCESS_RATE = 90  # Success rate threshold for excellent performance
GOOD_SUCCESS_RATE = 70  # Success rate threshold for good performance
HIGH_ACCURACY_R2 = 0.8  # R² threshold for high accuracy
MODERATE_ACCURACY_R2 = 0.6  # R² threshold for moderate accuracy
LOW_ERROR_MAPE = 15  # MAPE threshold for low errors
MODERATE_ERROR_MAPE = 25  # MAPE threshold for moderate errors
POOR_PERFORMANCE_R2 = 0.5  # R² threshold for poor performance


class ModelValidator:
    """
    Cross-validation system for solar energy prediction models.

    Features:
    - Leave-one-installation-out cross-validation
    - Performance comparison against real historical data
    - Weather simulation accuracy testing
    - Comprehensive validation metrics
    """

    def __init__(
        self,
        data_processor: ComprehensiveDataProcessor,
        weather_simulator: WeatherSimulator,
    ):
        """Initialize the model validator."""
        self.data_processor = data_processor
        self.weather_simulator = weather_simulator
        self.validation_results = {}

        logger.info("Model validator initialized")

    def run_cross_validation(
        self, exclude_location: str | None = None
    ) -> dict[str, Any]:
        """
        Run comprehensive cross-validation testing.

        Args:
            exclude_location: Specific location to exclude, or None for all locations

        Returns:
            Comprehensive validation results
        """
        logger.info("Starting cross-validation testing...")

        installations = list(self.data_processor.installations.keys())
        locations = list(
            {info.location for info in self.data_processor.installations.values()}
        )

        if exclude_location:
            test_locations = [exclude_location] if exclude_location in locations else []
        else:
            test_locations = locations

        validation_results = {
            "summary": {
                "total_installations": len(installations),
                "total_locations": len(locations),
                "tested_locations": len(test_locations),
                "validation_date": datetime.now().isoformat(),
            },
            "location_results": {},
            "overall_metrics": {},
            "recommendations": [],
        }

        for test_location in test_locations:
            logger.info(f"Testing location: {test_location}")

            # Get installations for this location
            test_installations = [
                inst_id
                for inst_id, info in self.data_processor.installations.items()
                if info.location == test_location
            ]

            if not test_installations:
                logger.warning(f"No installations found for location: {test_location}")
                continue

            # Run validation for this location
            location_result = self._validate_location(test_location, test_installations)
            validation_results["location_results"][test_location] = location_result

        # Calculate overall metrics
        validation_results["overall_metrics"] = self._calculate_overall_metrics(
            validation_results["location_results"]
        )
        validation_results["recommendations"] = self._generate_recommendations(
            validation_results
        )

        self.validation_results = validation_results
        logger.info("Cross-validation testing completed")

        return validation_results

    def _validate_location(
        self, test_location: str, test_installations: list[str]
    ) -> dict[str, Any]:
        """Validate models by excluding one location from training."""
        try:
            # Create training dataset excluding test location
            training_installations = [
                inst_id
                for inst_id, info in self.data_processor.installations.items()
                if info.location != test_location
            ]

            logger.info(
                f"Training with {len(training_installations)} installations, testing with {len(test_installations)}"
            )

            # Train models on remaining installations
            excluded_predictor = self._train_excluded_models(training_installations)

            # Test on excluded installation
            location_results = {
                "test_location": test_location,
                "training_installations": len(training_installations),
                "test_installations": test_installations,
                "installation_results": {},
                "location_metrics": {},
            }

            all_predictions = []
            all_actual = []

            for test_installation in test_installations:
                installation_result = self._test_installation(
                    excluded_predictor, test_installation, test_location
                )
                location_results["installation_results"][test_installation] = (
                    installation_result
                )

                if installation_result["predictions"] is not None:
                    all_predictions.extend(installation_result["predictions"])
                    all_actual.extend(installation_result["actual"])

            # Calculate location-wide metrics
            if all_predictions and all_actual:
                location_results["location_metrics"] = self._calculate_metrics(
                    all_actual, all_predictions
                )

            return location_results

        except Exception as e:
            logger.error(f"Error validating location {test_location}: {e}")
            return {"error": str(e)}

    def _train_excluded_models(
        self, training_installations: list[str]
    ) -> EnhancedEnergyPredictor:
        """Train models excluding specific installations."""
        # Create temporary data processor with only training installations
        excluded_installations = {}
        excluded_energy_data = {}
        excluded_combined_data = {}

        for inst_id in training_installations:
            if inst_id in self.data_processor.installations:
                excluded_installations[inst_id] = self.data_processor.installations[
                    inst_id
                ]
                excluded_energy_data[inst_id] = self.data_processor.energy_data[inst_id]
                excluded_combined_data[inst_id] = self.data_processor.combined_data[
                    inst_id
                ]

        # Create temporary data processor
        temp_processor = ComprehensiveDataProcessor.__new__(ComprehensiveDataProcessor)
        temp_processor.installations = excluded_installations
        temp_processor.energy_data = excluded_energy_data
        temp_processor.combined_data = excluded_combined_data
        temp_processor.weather_data = self.data_processor.weather_data

        # Train predictor on reduced dataset
        excluded_predictor = EnhancedEnergyPredictor(
            temp_processor, self.weather_simulator
        )

        return excluded_predictor

    def _test_installation(
        self, predictor: EnhancedEnergyPredictor, installation_id: str, location: str
    ) -> dict[str, Any]:
        """Test model performance on excluded installation."""
        try:
            # Get test data
            test_data = self.data_processor.get_combined_data(installation_id)
            if test_data is None or len(test_data) < MIN_TEST_DATA_POINTS:
                return {
                    "error": "Insufficient test data",
                    "predictions": None,
                    "actual": None,
                }

            # Select test period (last 30 days of available data)
            test_start = test_data.index.max() - timedelta(days=30)
            test_period = test_data[test_data.index >= test_start]

            if len(test_period) < MIN_DAILY_DATA_HOURS:  # Need at least one day
                return {
                    "error": "Insufficient test period data",
                    "predictions": None,
                    "actual": None,
                }

            # Get actual values
            actual_energy = test_period["Produced Energy (kWh)"].values

            # Generate predictions using trained model
            predictions = []

            for date in pd.date_range(
                start=test_start.date(), end=test_data.index.max().date(), freq="D"
            ):
                try:
                    # Predict using historical weather data
                    prediction_result = predictor.predict_15_day_period(
                        installation_id="temp_test",  # Use temporary ID
                        center_date=date,
                        use_historical_weather=True,
                        weather_location=location,
                    )

                    if prediction_result and "hourly_data" in prediction_result:
                        day_predictions = prediction_result["hourly_data"][
                            "predicted_total_energy"
                        ]
                        predictions.extend(day_predictions.tolist())

                except Exception as e:
                    logger.warning(f"Failed to predict for {date}: {e}")
                    continue

            # Align predictions with actual data
            min_length = min(len(actual_energy), len(predictions))
            if min_length == 0:
                return {
                    "error": "No valid predictions generated",
                    "predictions": None,
                    "actual": None,
                }

            actual_aligned = actual_energy[:min_length]
            predictions_aligned = predictions[:min_length]

            # Calculate metrics
            metrics = self._calculate_metrics(actual_aligned, predictions_aligned)

            return {
                "installation_id": installation_id,
                "test_period_days": (test_data.index.max() - test_start).days,
                "data_points": min_length,
                "predictions": predictions_aligned,
                "actual": actual_aligned,
                "metrics": metrics,
                "weather_coverage": self._calculate_weather_coverage(test_period),
            }

        except Exception as e:
            logger.error(f"Error testing installation {installation_id}: {e}")
            return {"error": str(e), "predictions": None, "actual": None}

    def _calculate_metrics(
        self, actual: list[float], predictions: list[float]
    ) -> dict[str, float]:
        """Calculate comprehensive performance metrics."""
        try:
            actual_arr = np.array(actual)
            pred_arr = np.array(predictions)

            # Remove any NaN or infinite values
            mask = np.isfinite(actual_arr) & np.isfinite(pred_arr)
            actual_clean = actual_arr[mask]
            pred_clean = pred_arr[mask]

            if len(actual_clean) == 0:
                return {"error": "No valid data points after cleaning"}

            metrics = {
                "mae": float(mean_absolute_error(actual_clean, pred_clean)),
                "mse": float(mean_squared_error(actual_clean, pred_clean)),
                "rmse": float(np.sqrt(mean_squared_error(actual_clean, pred_clean))),
                "r2": float(r2_score(actual_clean, pred_clean)),
                "mape": float(
                    np.mean(np.abs((actual_clean - pred_clean) / (actual_clean + 1e-8)))
                    * 100
                ),
                "data_points": len(actual_clean),
                "actual_mean": float(np.mean(actual_clean)),
                "predicted_mean": float(np.mean(pred_clean)),
                "actual_std": float(np.std(actual_clean)),
                "predicted_std": float(np.std(pred_clean)),
            }

            return metrics

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return {"error": str(e)}

    def _calculate_weather_coverage(self, data: pd.DataFrame) -> dict[str, float]:
        """Calculate weather data coverage and quality."""
        weather_cols = [
            "temperature_2m",
            "cloud_cover",
            "shortwave_radiation",
            "relative_humidity_2m",
        ]
        coverage = {}

        for col in weather_cols:
            if col in data.columns:
                valid_count = data[col].notna().sum()
                total_count = len(data)
                coverage[col] = (valid_count / total_count) * 100
            else:
                coverage[col] = 0.0

        coverage["overall"] = np.mean(list(coverage.values()))
        return coverage

    def _calculate_overall_metrics(self, location_results: dict) -> dict[str, Any]:
        """Calculate overall validation metrics across all locations."""
        try:
            all_metrics = []
            successful_tests = 0
            total_tests = 0

            for _location, result in location_results.items():
                if "error" not in result and "location_metrics" in result:
                    metrics = result["location_metrics"]
                    if "error" not in metrics:
                        all_metrics.append(metrics)
                        successful_tests += 1
                total_tests += 1

            if not all_metrics:
                return {"error": "No successful validation tests"}

            # Aggregate metrics
            overall = {
                "success_rate": (successful_tests / total_tests) * 100,
                "total_locations_tested": total_tests,
                "successful_locations": successful_tests,
                "avg_mae": np.mean([m["mae"] for m in all_metrics]),
                "avg_r2": np.mean([m["r2"] for m in all_metrics]),
                "avg_mape": np.mean([m["mape"] for m in all_metrics]),
                "best_r2": max([m["r2"] for m in all_metrics]),
                "worst_r2": min([m["r2"] for m in all_metrics]),
                "total_data_points": sum([m["data_points"] for m in all_metrics]),
            }

            return overall

        except Exception as e:
            logger.error(f"Error calculating overall metrics: {e}")
            return {"error": str(e)}

    def _generate_recommendations(self, validation_results: dict) -> list[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        try:
            overall = validation_results.get("overall_metrics", {})

            if "error" in overall:
                recommendations.append(
                    "❌ Validation failed - check data quality and model training"
                )
                return recommendations

            success_rate = overall.get("success_rate", 0)
            avg_r2 = overall.get("avg_r2", 0)
            avg_mape = overall.get("avg_mape", 100)

            # Success rate recommendations
            if success_rate >= EXCELLENT_SUCCESS_RATE:
                recommendations.append(
                    "✅ Excellent validation success rate - models are robust"
                )
            elif success_rate >= GOOD_SUCCESS_RATE:
                recommendations.append(
                    "⚠️ Good validation success rate - minor improvements possible"
                )
            else:
                recommendations.append(
                    "❌ Low validation success rate - review data quality and model architecture"
                )

            # Accuracy recommendations
            if avg_r2 >= HIGH_ACCURACY_R2:
                recommendations.append(
                    "✅ High prediction accuracy - models perform well across locations"
                )
            elif avg_r2 >= MODERATE_ACCURACY_R2:
                recommendations.append(
                    "⚠️ Moderate prediction accuracy - consider feature engineering improvements"
                )
            else:
                recommendations.append(
                    "❌ Low prediction accuracy - models need significant improvement"
                )

            # Error rate recommendations
            if avg_mape <= LOW_ERROR_MAPE:
                recommendations.append(
                    "✅ Low prediction errors - suitable for production use"
                )
            elif avg_mape <= MODERATE_ERROR_MAPE:
                recommendations.append(
                    "⚠️ Moderate prediction errors - acceptable for most use cases"
                )
            else:
                recommendations.append(
                    "❌ High prediction errors - not recommended for critical applications"
                )

            # Specific improvements
            location_results = validation_results.get("location_results", {})
            poor_locations = [
                loc
                for loc, result in location_results.items()
                if "location_metrics" in result
                and result["location_metrics"].get("r2", 0) < POOR_PERFORMANCE_R2
            ]

            if poor_locations:
                recommendations.append(
                    f"🔍 Focus improvement efforts on: {', '.join(poor_locations)}"
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return [f"❌ Error generating recommendations: {e}"]

    def get_validation_summary(self) -> str:
        """Get a human-readable validation summary."""
        if not self.validation_results:
            return "❌ No validation results available. Run cross-validation first."

        try:
            summary = self.validation_results.get("summary", {})
            overall = self.validation_results.get("overall_metrics", {})
            recommendations = self.validation_results.get("recommendations", [])

            report = f"""
# 📊 ML Model Cross-Validation Report

## Summary
- **Total Installations:** {summary.get("total_installations", "N/A")}
- **Locations Tested:** {summary.get("tested_locations", "N/A")}
- **Validation Date:** {summary.get("validation_date", "N/A")[:10]}

## Performance Metrics
- **Success Rate:** {overall.get("success_rate", 0):.1f}%
- **Average R² Score:** {overall.get("avg_r2", 0):.3f}
- **Average MAPE:** {overall.get("avg_mape", 0):.1f}%
- **Best R² Score:** {overall.get("best_r2", 0):.3f}
- **Total Data Points:** {overall.get("total_data_points", 0):,}

## Recommendations
"""
            for rec in recommendations:
                report += f"- {rec}\n"

            return report

        except Exception as e:
            logger.error(f"Error creating validation summary: {e}")
            return f"❌ Error creating summary: {e}"
