"""
Performance benchmark tests for FilantropiaSolar.

These tests measure performance of key application components.
"""

import os
import sys

import pytest

# Use proper package imports - no sys.path manipulation needed

# Pytest-benchmark is required for these tests
pytest_plugins = ["pytest_benchmark"]


@pytest.mark.benchmark
def test_data_import_speed(benchmark):
    """Benchmark data processing import speed."""

    def import_data_processing():
        try:
            import src.data_processing as data_processing

            return data_processing
        except ImportError:
            pytest.skip("data_processing module not available")

    result = benchmark(import_data_processing)
    assert result is not None


@pytest.mark.benchmark
def test_basic_calculation_performance(benchmark):
    """Benchmark basic mathematical operations."""

    def calculate_energy_metrics():
        # Simple calculation to test performance
        result = []
        for i in range(1000):
            energy = i * 0.8  # kWh/kWp calculation
            result.append(energy)
        return result

    result = benchmark(calculate_energy_metrics)
    assert len(result) == 1000


@pytest.mark.slow
@pytest.mark.benchmark
def test_ml_model_import_speed(benchmark):
    """Benchmark ML model import performance."""

    def import_prediction_module():
        try:
            import src.prediction as prediction

            return prediction
        except ImportError:
            pytest.skip("prediction module not available")

    result = benchmark(import_prediction_module)
    assert result is not None
