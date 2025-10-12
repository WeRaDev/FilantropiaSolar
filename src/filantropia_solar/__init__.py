"""
FilantropiaSolar - Advanced Solar Energy Analysis Application.

A comprehensive solar energy prediction and analysis tool for Portuguese PV installations.
"""

__version__ = "1.0.0"
__author__ = "WeRaDev Team"
__email__ = "contact@weradev.com"
__description__ = (
    "Advanced Solar Energy Analysis Application for Portuguese PV Installations"
)

# Import main modules for easy access
try:
    from . import data_processing, weather_api, prediction, gui, utils

    __all__ = [
        "data_processing",
        "weather_api",
        "prediction",
        "gui",
        "utils",
        "__version__",
    ]
except ImportError:
    # Graceful fallback if modules are not available
    __all__ = ["__version__"]
