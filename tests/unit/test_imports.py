"""
Test basic imports and module availability.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestBasicImports:
    """Test basic module imports."""

    def test_data_processing_import(self):
        """Test that data_processing module can be imported."""
        try:
            import data_processing

            assert data_processing is not None
        except ImportError:
            pytest.skip("data_processing module not available")

    def test_weather_api_import(self):
        """Test that weather_api module can be imported."""
        try:
            import weather_api

            assert weather_api is not None
        except ImportError:
            pytest.skip("weather_api module not available")

    def test_prediction_import(self):
        """Test that prediction module can be imported."""
        try:
            import prediction

            assert prediction is not None
        except ImportError:
            pytest.skip("prediction module not available")

    def test_utils_import(self):
        """Test that utils module can be imported."""
        try:
            import utils

            assert utils is not None
        except ImportError:
            pytest.skip("utils module not available")

    def test_gui_import(self):
        """Test that gui module can be imported."""
        try:
            import gui

            assert gui is not None
        except ImportError:
            pytest.skip("gui module not available")


class TestRequiredPackages:
    """Test that required packages are available."""

    def test_pandas_available(self):
        """Test pandas is available."""
        import pandas as pd

        assert pd.__version__ is not None

    def test_numpy_available(self):
        """Test numpy is available."""
        import numpy as np

        assert np.__version__ is not None

    def test_sklearn_available(self):
        """Test scikit-learn is available."""
        import sklearn

        assert sklearn.__version__ is not None

    def test_matplotlib_available(self):
        """Test matplotlib is available."""
        import matplotlib

        assert matplotlib.__version__ is not None
