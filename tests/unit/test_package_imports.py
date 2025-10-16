"""
Minimal package import tests.
"""

import importlib


def test_import_package_root():
    mod = importlib.import_module("filantropia_solar")
    assert mod is not None


def test_import_core_logging():
    mod = importlib.import_module("filantropia_solar.core.logging")
    assert hasattr(mod, "setup_logging")
