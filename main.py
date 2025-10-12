#!/usr/bin/env python3
"""
FilantropiaSolar - Main Application Entry Point
Solar Energy Prediction System for Lisbon PV Installations
"""

import sys
import logging
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/application.log", mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def setup_directories():
    """Create necessary directories if they don't exist"""
    directories = ["logs", "models", "exports"]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"Directory '{directory}' ready")


def main():
    """Main application entry point"""
    try:
        logger.info("Starting FilantropiaSolar Application")

        # Setup directories
        setup_directories()

        # Import and run GUI application
        from src.gui.main_app import FilantropiaSolarApp

        logger.info("Initializing GUI application")
        app = FilantropiaSolarApp()

        logger.info("Starting GUI main loop")
        app.run()

        logger.info("Application terminated")

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
