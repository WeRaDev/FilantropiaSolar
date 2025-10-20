"""
Machine Learning integration tests.
"""

import numpy as np
import pytest
import sklearn
from sklearn.ensemble import RandomForestRegressor

# Use proper package imports - no sys.path manipulation needed


@pytest.mark.ml
def test_sklearn_available():
    """Test that scikit-learn is available for ML operations."""
    try:
        assert sklearn.__version__ is not None
    except ImportError:
        pytest.skip("scikit-learn not available")


@pytest.mark.ml
def test_prediction_module_structure():
    """Test that prediction module has expected structure."""
    try:
        from src import prediction  # noqa: PLC0415

        # Basic structural tests
        assert prediction is not None
    except ImportError:
        pytest.skip("prediction module not available")


@pytest.mark.ml
@pytest.mark.slow
def test_basic_ml_workflow():
    """Test basic ML workflow components."""
    try:
        # Create simple synthetic data
        X = np.random.rand(100, 5)
        y = np.random.rand(100)

        # Test model creation
        model = RandomForestRegressor(n_estimators=10, random_state=42)
        model.fit(X, y)

        # Test prediction
        predictions = model.predict(X[:5])
        assert len(predictions) == 5

    except ImportError:
        pytest.skip("Required ML libraries not available")
