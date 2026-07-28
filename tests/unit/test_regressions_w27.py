"""Regression tests for latent bugs fixed during the quality-debt paydown.

Covers (see tasks/revisor-quality-debt.md, "Latent issues found during the paydown"):
1. CircuitBreaker.call returned None on OPEN -> HALF_OPEN transition
2. LoggingManager.set_context crashed on first call (_local unset)
3. OptimizedDataProcessor._combine_installation_weather called nonexistent method
4. ModelValidator._test_installation could not produce predictions for excluded
   installations (now routes via predict_period_for_custom reference models)
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from src.core.exceptions import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerState,
)
from src.filantropia_solar.core.logging import LogContext, LoggingManager
from src.filantropia_solar.data_processing.comprehensive_data_processor import (
    InstallationInfo,
)
from src.filantropia_solar.data_processing.optimized_data_processor import (
    OptimizedDataProcessor,
)
from src.filantropia_solar.prediction.model_validator import ModelValidator


def test_circuit_breaker_half_open_transition_executes_function():
    """OPEN -> HALF_OPEN transition must execute the function, not return None."""
    breaker = CircuitBreaker(
        CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.0),
    )
    calls = []

    def protected() -> str:
        calls.append(1)
        return "ok"

    # Force OPEN with the recovery timeout already elapsed
    breaker.state = CircuitBreakerState.OPEN
    breaker.last_failure_time = 0.0

    result = breaker.call(protected)

    assert result == "ok"
    assert calls, "protected function was not executed after transition"
    assert breaker.state == CircuitBreakerState.CLOSED


def test_logging_manager_set_context_first_call():
    """set_context must work on first call without AttributeError."""
    manager = LoggingManager()
    context = LogContext()

    manager.set_context(context)

    assert manager.get_context() is context


def test_combine_installation_weather_adds_computed_features():
    """Incremental combine must apply parent computed features, not crash."""
    processor = OptimizedDataProcessor.__new__(OptimizedDataProcessor)

    timestamps = pd.date_range("2024-06-01", periods=4, freq="h")
    energy_df = pd.DataFrame(
        {"Produced Energy (kWh)": [1.0, 2.0, 3.0, 4.0]},
        index=timestamps,
    )
    weather_df = pd.DataFrame(
        {"shortwave_radiation": [100.0, 200.0, 300.0, 400.0]},
        index=timestamps,
    )
    processor.weather_data = {"Lisbon": weather_df}
    processor.installations = {
        "Lisbon_9999": InstallationInfo(
            serial_number="9999",
            location="Lisbon",
            latitude=38.7223,
            longitude=-9.1393,
            installed_power_kwp=10.0,
            connection_power_kwn=10.0,
            from_date=datetime(2024, 1, 1),
            to_date=datetime(2024, 12, 31),
        ),
    }

    combined = processor._combine_installation_weather(
        energy_df,
        "Lisbon",
        "Lisbon_9999",
    )

    assert not combined.empty
    assert "shortwave_radiation" in combined.columns
    # Computed features from the parent's _add_computed_features
    assert "solar_elevation" in combined.columns
    assert "theoretical_power" in combined.columns


def test_model_validator_tests_via_reference_model_prediction():
    """_test_installation must route through predict_period_for_custom."""
    validator = ModelValidator.__new__(ModelValidator)
    validator.weather_simulator = MagicMock()

    timestamps = pd.date_range("2024-06-01", periods=200, freq="h")
    test_data = pd.DataFrame(
        {"Produced Energy (kWh)": [1.0] * 200},
        index=timestamps,
    )
    validator.data_processor = MagicMock()
    validator.data_processor.get_combined_data.return_value = test_data
    validator.data_processor.installations = {
        "Lisbon_9999": SimpleNamespace(installed_power_kwp=10.0),
    }

    predictor = MagicMock()
    predictor.predict_period_for_custom.return_value = {
        "hourly_data": pd.DataFrame({"predicted_total_energy": [1.0] * 24}),
    }

    result = validator._test_installation(predictor, "Lisbon_9999", "Lisbon")

    predictor.predict_period_for_custom.assert_called()
    first_call_args = predictor.predict_period_for_custom.call_args_list[0].args
    assert first_call_args[0] == "Lisbon"
    assert first_call_args[1] == 10.0
    assert result["predictions"] is not None
    assert result["metrics"]["data_points"] > 0
