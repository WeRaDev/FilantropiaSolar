"""
Advanced ML model validation and testing.
"""

import pytest
import numpy as np
import sys
import os
from sklearn.metrics import mean_absolute_error, r2_score
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


@pytest.mark.ml
def test_model_performance_validation():
    """Test ML model performance meets minimum requirements."""
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split

    # Generate synthetic solar energy data
    np.random.seed(42)  # For reproducible tests
    n_samples = 1000

    # Features: solar_radiation, temperature, humidity, cloud_cover, hour
    X = np.column_stack(
        [
            np.random.uniform(0, 1200, n_samples),  # solar_radiation
            np.random.uniform(10, 40, n_samples),  # temperature
            np.random.uniform(30, 90, n_samples),  # humidity
            np.random.uniform(0, 100, n_samples),  # cloud_cover
            np.random.randint(0, 24, n_samples),  # hour
        ]
    )

    # Target: energy production with realistic relationship to features
    y = (
        X[:, 0] * 0.01  # solar radiation impact
        + X[:, 1] * 0.02  # temperature impact
        + (100 - X[:, 3]) * 0.01  # inverse cloud cover impact
        + np.random.normal(0, 0.5, n_samples)  # noise
    )
    y = np.clip(y, 0, None)  # Energy can't be negative

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Train model
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)

    # Make predictions
    y_pred = model.predict(X_test)

    # Validate performance
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # Performance requirements
    assert mae < 2.0, f"MAE too high: {mae:.3f}"
    assert r2 > 0.5, f"R² too low: {r2:.3f}"

    # Validate predictions are reasonable
    assert np.all(y_pred >= 0), "Predictions should be non-negative"
    assert np.all(y_pred < 50), "Predictions should be realistic for solar energy"


@pytest.mark.ml
def test_model_feature_importance():
    """Test that ML models identify important features correctly."""
    from sklearn.ensemble import RandomForestRegressor

    np.random.seed(42)
    n_samples = 500

    # Create features where first feature is most important
    X = np.random.randn(n_samples, 5)
    y = (
        2 * X[:, 0]
        + 0.5 * X[:, 1]
        + 0.1 * np.sum(X[:, 2:], axis=1)
        + np.random.randn(n_samples) * 0.1
    )

    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)

    # Get feature importances
    importances = model.feature_importances_

    # Most important feature should be first
    most_important_idx = np.argmax(importances)
    assert most_important_idx == 0, "Model should identify most important feature"

    # Check importances sum to 1
    assert abs(np.sum(importances) - 1.0) < 1e-6, "Feature importances should sum to 1"


@pytest.mark.ml
def test_model_robustness():
    """Test model robustness to different data conditions."""
    from sklearn.ensemble import RandomForestRegressor

    # Test with different data scenarios
    scenarios = [
        {"name": "normal", "noise": 0.1, "outliers": 0},
        {"name": "noisy", "noise": 0.5, "outliers": 0},
        {"name": "with_outliers", "noise": 0.1, "outliers": 10},
    ]

    for scenario in scenarios:
        np.random.seed(42)
        n_samples = 300

        # Generate base data
        X = np.random.randn(n_samples, 3)
        y = X[:, 0] + 0.5 * X[:, 1] + np.random.randn(n_samples) * scenario["noise"]

        # Add outliers if specified
        if scenario["outliers"] > 0:
            outlier_indices = np.random.choice(
                n_samples, scenario["outliers"], replace=False
            )
            y[outlier_indices] += np.random.choice([-10, 10], scenario["outliers"])

        # Train model
        model = RandomForestRegressor(n_estimators=30, random_state=42)
        model.fit(X, y)

        # Test prediction
        X_test = np.random.randn(50, 3)
        y_pred = model.predict(X_test)

        # Validate predictions are finite and reasonable
        assert np.all(np.isfinite(y_pred)), (
            f"Predictions should be finite for {scenario['name']} data"
        )
        assert np.std(y_pred) > 0, (
            f"Model should produce varied predictions for {scenario['name']} data"
        )


@pytest.mark.ml
def test_cross_validation_stability():
    """Test model stability across different train/test splits."""
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score

    np.random.seed(42)
    n_samples = 400

    # Generate consistent dataset
    X = np.random.randn(n_samples, 4)
    y = X[:, 0] + 0.3 * X[:, 1] + 0.2 * X[:, 2] + np.random.randn(n_samples) * 0.2

    model = RandomForestRegressor(n_estimators=30, random_state=42)

    # Perform cross-validation
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2")

    # Check stability
    mean_score = np.mean(cv_scores)
    std_score = np.std(cv_scores)

    assert mean_score > 0.6, f"Mean CV score too low: {mean_score:.3f}"
    assert std_score < 0.2, f"CV scores too variable: std={std_score:.3f}"
    assert len(cv_scores) == 5, "Should have 5 CV folds"


@pytest.mark.ml
@pytest.mark.slow
def test_model_scalability():
    """Test model performance with larger datasets."""
    from sklearn.ensemble import RandomForestRegressor
    import time

    # Test different dataset sizes
    sizes = [100, 500, 1000, 2000]
    training_times = []

    for size in sizes:
        np.random.seed(42)
        X = np.random.randn(size, 5)
        y = np.sum(X, axis=1) + np.random.randn(size) * 0.1

        model = RandomForestRegressor(n_estimators=20, random_state=42)

        start_time = time.time()
        model.fit(X, y)
        training_time = time.time() - start_time
        training_times.append(training_time)

        # Validate model trained successfully
        assert hasattr(model, "feature_importances_"), (
            f"Model should be trained for size {size}"
        )

        # Test prediction
        y_pred = model.predict(X[:10])
        assert len(y_pred) == 10, f"Should predict for all samples at size {size}"

    # Check that training time doesn't grow exponentially
    # (This is a rough check - RandomForest should scale reasonably)
    assert all(t < 10.0 for t in training_times), "Training times should be reasonable"


@pytest.mark.ml
def test_model_data_validation():
    """Test model handles various data validation scenarios."""
    from sklearn.ensemble import RandomForestRegressor

    model = RandomForestRegressor(n_estimators=10, random_state=42)

    # Valid training data
    X_valid = np.random.randn(100, 3)
    y_valid = np.random.randn(100)
    model.fit(X_valid, y_valid)

    # Test various prediction scenarios
    test_cases = [
        {"name": "normal", "X": np.random.randn(10, 3), "should_work": True},
        {"name": "single_sample", "X": np.random.randn(1, 3), "should_work": True},
        {"name": "wrong_features", "X": np.random.randn(10, 2), "should_work": False},
    ]

    for case in test_cases:
        try:
            y_pred = model.predict(case["X"])
            if case["should_work"]:
                assert len(y_pred) == len(case["X"]), (
                    f"Prediction length mismatch for {case['name']}"
                )
                assert np.all(np.isfinite(y_pred)), (
                    f"Predictions should be finite for {case['name']}"
                )
            else:
                pytest.fail(f"Should have failed for {case['name']}")
        except Exception as e:
            if case["should_work"]:
                pytest.fail(f"Should have worked for {case['name']}: {str(e)}")
            # Expected to fail, test passes


@pytest.mark.ml
def test_energy_ranking_validation():
    """Test energy ranking system validation."""
    try:
        from utils.energy_ranking import get_energy_rank, get_rank_color

        # Test ranking function
        test_energies = [0.05, 0.15, 0.3, 0.5, 0.7, 0.9]
        expected_ranks = [1, 1, 2, 3, 4, 5]  # Based on kWh/kWp thresholds

        for energy, expected_rank in zip(test_energies, expected_ranks):
            rank = get_energy_rank(energy)
            assert rank == expected_rank, (
                f"Energy {energy} should have rank {expected_rank}, got {rank}"
            )

        # Test color function
        for rank in range(1, 6):
            color = get_rank_color(rank)
            assert color is not None, f"Should have color for rank {rank}"
            assert isinstance(color, str), f"Color should be string for rank {rank}"

    except ImportError:
        pytest.skip("Energy ranking utilities not available")
