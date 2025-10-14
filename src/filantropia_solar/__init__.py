"""
FilantropiaSolar - Advanced Solar Energy Analysis Application.

A comprehensive solar energy prediction and analysis tool for Portuguese PV installations.
Built with modern Python practices, type safety, and clean architecture principles.
"""

from datetime import datetime
import os
from pathlib import Path
import platform
import sys
import warnings

# Package metadata
__version__ = "1.0.0"
__author__ = "WeRaDev Team"
__email__ = "contact@weradev.com"
__description__ = (
    "Advanced Solar Energy Analysis Application for Portuguese PV Installations"
)
__license__ = "MIT"
__url__ = "https://github.com/WeRaDev/FilantropiaSolar"

# Initialize logging as early as possible
try:
    from .core.config import get_environment, get_settings
    from .core.logging import get_logger, log_startup, setup_logging

    # Setup logging with current configuration
    setup_logging()

    # Log application startup
    logger = get_logger("filantropia_solar")
    settings = get_settings()

    log_startup(
        component="FilantropiaSolar",
        version=__version__,
        config_summary={
            "environment": settings.environment.value,
            "debug": settings.debug,
            "log_level": settings.log_level.value,
        },
    )

    logger.info(f"FilantropiaSolar v{__version__} initialized successfully")

except Exception as e:
    # Fallback logging to stderr if core logging fails
    print(
        f"Warning: Failed to initialize FilantropiaSolar logging: {e}", file=sys.stderr
    )

# Import core modules with error handling
try:
    from . import core
    from .core import (
        ConfigurationError,
        FilantropiaSolarError,
        ValidationError,
        get_config,
        get_logger,
        get_settings,
        log_performance,
    )
except ImportError as e:
    warnings.warn(f"Failed to import core modules: {e}", stacklevel=2)
    core = None

# Import main application modules with graceful degradation
try:
    from . import data, models, utils

    _modules_available = ["data", "models", "utils"]
except ImportError as e:
    warnings.warn(f"Some modules failed to import: {e}", stacklevel=2)
    _modules_available = []

# Optional modules (may not be available in all environments)
_optional_modules = []

try:
    from . import gui

    _optional_modules.append("gui")
except ImportError:
    gui = None

try:
    from . import api

    _optional_modules.append("api")
except ImportError:
    api = None

try:
    from . import monitoring

    _optional_modules.append("monitoring")
except ImportError:
    monitoring = None

# Define public API
__all__ = [
    "ConfigurationError",
    "FilantropiaSolarError",
    "ValidationError",
    "__author__",
    "__description__",
    "__license__",
    "__url__",
    "__version__",
    "check_dependencies",
    "core",
    "get_config",
    "get_logger",
    "get_settings",
    "get_system_info",
    "get_version_info",
    "log_performance",
]

# Add available modules to __all__
__all__.extend(_modules_available)
__all__.extend(_optional_modules)

# Clean up temporary variables
del _modules_available, _optional_modules


def get_version_info():
    """
    Get comprehensive version and system information.

    Returns:
        Dict containing version, environment, and system information
    """
    info = {
        "version": __version__,
        "python_version": sys.version,
        "platform": platform.platform(),
        "architecture": platform.architecture(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Add configuration information if available
    try:
        settings = get_settings()
        info.update(
            {
                "environment": settings.environment.value,
                "debug_mode": settings.debug,
                "log_level": settings.log_level.value,
            }
        )
    except Exception:
        pass

    return info


def check_dependencies():
    """
    Check if all required dependencies are available.

    Returns:
        Dict containing dependency status information
    """
    dependencies = {
        "required": {
            "pandas": None,
            "numpy": None,
            "scikit-learn": None,
            "pydantic": None,
            "pyyaml": None,
        },
        "optional": {
            "tkinter": None,
            "matplotlib": None,
            "requests": None,
            "fastapi": None,
            "uvicorn": None,
            "prometheus_client": None,
        },
    }

    for _category, deps in dependencies.items():
        for dep_name in deps:
            try:
                __import__(dep_name)
                deps[dep_name] = "available"
            except ImportError:
                deps[dep_name] = "missing"

    return dependencies


def get_system_info():
    """
    Get system and environment information for debugging.

    Returns:
        Dict containing system information
    """
    return {
        "version_info": get_version_info(),
        "dependencies": check_dependencies(),
        "system": {
            "python_executable": sys.executable,
            "python_path": sys.path[:3],  # First 3 entries
            "platform": platform.platform(),
            "processor": platform.processor(),
            "memory_info": None,  # Could add psutil if available
        },
        "environment": {
            "cwd": str(Path.cwd()),
            "user": os.getenv("USER") or os.getenv("USERNAME"),
            "home": str(Path("~").expanduser()),
        },
    }
