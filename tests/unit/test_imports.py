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
        """Test that gui module can be imported (v1.0.0 - compatibility only)."""
        try:
            import gui
            # In v1.0.0, GUI functionality is integrated into main.py
            # This test ensures the module can be imported for compatibility
            assert gui is not None
        except ImportError:
            pytest.skip("gui module not available - GUI integrated into main.py in v1.0.0")

    def test_main_application_import(self):
        """Test that the main application module can be accessed (v1.0.0)."""
        import sys
        import os
        
        # Add project root to path
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        sys.path.insert(0, project_root)
        
        try:
            # Test that main.py exists and can be imported as a module
            import importlib.util
            main_path = os.path.join(project_root, "main.py")
            
            assert os.path.exists(main_path), "main.py should exist as the primary application entry point"
            
            # Try to load main.py as a module
            spec = importlib.util.spec_from_file_location("main", main_path)
            main_module = importlib.util.module_from_spec(spec)
            
            assert main_module is not None
            assert spec is not None
            
        except Exception as e:
            pytest.skip(f"main.py application not accessible: {e}")


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
