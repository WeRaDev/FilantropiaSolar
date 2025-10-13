"""
Enhanced Main Application for FilantropiaSolar

Provides the proper 3-tab interface: Input, Charts, Output windows
with full functionality for historical data analysis and ML predictions.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
from src.weather_simulation.weather_simulator import WeatherSimulator
from src.gui.enhanced_input_window import EnhancedInputWindow
from src.gui.enhanced_plot_window import EnhancedPlotWindow
from src.gui.output_window import OutputWindow

logger = logging.getLogger(__name__)


class EnhancedFilantropiaSolarApp:
    """
    Enhanced main application for FilantropiaSolar.

    Features:
    - Proper 3-tab interface (Input, Charts, Output)
    - Historical data analysis and future simulation
    - Machine learning predictions
    - Interactive visualizations
    - Export capabilities
    """

    def __init__(self):
        """Initialize the enhanced application."""
        self.root = tk.Tk()
        self.root.title("FilantropiaSolar v2.0 - Enhanced Solar Energy Analysis")
        self.root.geometry("1600x1000")
        self.root.state("zoomed")  # Maximize window on Windows

        # Try to maximize on other platforms
        try:
            self.root.attributes("-zoomed", True)  # Linux
        except tk.TclError:
            try:
                self.root.state("zoomed")  # Windows
            except tk.TclError:
                pass  # macOS doesn't support maximize attribute

        # Configure style
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass  # Fallback to default theme

        # Initialize core components
        self._initialize_components()

        # Create GUI
        self._create_gui()

        # Set up callbacks
        self._setup_callbacks()

        logger.info("Enhanced FilantropiaSolar application initialized")

    def _initialize_components(self):
        """Initialize data processor and prediction components."""
        try:
            # Initialize data processor
            logger.info("Initializing data processor...")
            self.data_processor = ComprehensiveDataProcessor()

            # Initialize weather simulator
            logger.info("Initializing weather simulator...")
            weather_data_dir = project_root / "weather_files"
            self.weather_simulator = WeatherSimulator(str(weather_data_dir))

            # Initialize predictor
            logger.info("Initializing enhanced predictor...")
            self.predictor = EnhancedEnergyPredictor(
                self.data_processor, self.weather_simulator
            )

            # Current prediction results
            self.current_results = None

            logger.info("All components initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            messagebox.showerror(
                "Initialization Error",
                f"Failed to initialize application components:\n{e}\n\n"
                "Please check that all data files are present and accessible.",
            )
            raise

    def _create_gui(self):
        """Create the main GUI with tabs."""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tab frames
        input_tab = ttk.Frame(self.notebook, padding="10")
        charts_tab = ttk.Frame(self.notebook, padding="10")
        output_tab = ttk.Frame(self.notebook, padding="10")

        # Add tabs to notebook
        self.notebook.add(input_tab, text="🏠 Input & Configuration")
        self.notebook.add(charts_tab, text="📊 Charts & Analysis")
        self.notebook.add(output_tab, text="📋 Results & Output")

        # Initialize tab components
        self.input_window = EnhancedInputWindow(
            input_tab, self.data_processor, self._on_predict_callback
        )

        self.plot_window = EnhancedPlotWindow(charts_tab)
        self.output_window = OutputWindow(output_tab)

        # Status bar
        self._create_status_bar(main_container)

        logger.info("GUI created with 3-tab interface")

    def _create_status_bar(self, parent):
        """Create status bar."""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))

        # Status label
        self.status_var = tk.StringVar(
            value="Ready - Select installation and date for prediction"
        )
        self.status_label = ttk.Label(
            self.status_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            padding="5",
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            self.status_frame, mode="indeterminate", length=200
        )
        self.progress_bar.pack(side=tk.RIGHT, padx=(5, 0))

    def _setup_callbacks(self):
        """Set up event callbacks."""
        # Tab selection callback
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Window close callback
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_tab_changed(self, event):
        """Handle tab change event."""
        tab_index = self.notebook.index(self.notebook.select())
        tab_names = ["Input", "Charts", "Output"]

        if tab_index < len(tab_names):
            logger.info(f"Switched to {tab_names[tab_index]} tab")
            self.status_var.set(f"Active tab: {tab_names[tab_index]}")

    def _on_predict_callback(
        self, installation_id: str, target_date: datetime, use_simulation: bool
    ):
        """Handle prediction request from input window."""
        try:
            self.status_var.set("Generating predictions...")
            self.progress_bar.start()
            self.root.update_idletasks()

            logger.info(
                f"Starting prediction for {installation_id} on {target_date.date()}"
            )

            # Generate 15-day prediction centered on target date
            start_date = target_date - timedelta(days=7)
            end_date = target_date + timedelta(days=7)

            # Generate predictions
            results = self.predictor.predict_energy_for_period(
                installation_id=installation_id,
                start_date=start_date,
                end_date=end_date,
                center_date=target_date,
                use_simulation=use_simulation,
            )

            if results and not results.get("predictions", pd.DataFrame()).empty:
                self.current_results = results

                # Update all windows with results
                self.plot_window.update_prediction_data(results)
                self.output_window.display_results(results)

                # Switch to charts tab to show results
                self.notebook.select(1)  # Charts tab

                self.status_var.set(
                    f"Prediction completed for {installation_id} - "
                    f"15-day period centered on {target_date.strftime('%Y-%m-%d')}"
                )

                logger.info("Prediction completed successfully")

                # Show success message
                messagebox.showinfo(
                    "Prediction Complete",
                    f"Successfully generated 15-day energy production forecast for {installation_id}\n"
                    f"Center date: {target_date.strftime('%Y-%m-%d')}\n"
                    f"Data source: {'Weather simulation' if use_simulation else 'Historical data'}\n\n"
                    "View the Charts tab for detailed analysis.",
                )

            else:
                self.status_var.set("Prediction failed - No results generated")
                messagebox.showerror(
                    "Prediction Error",
                    "Failed to generate predictions. Please check:\n"
                    "• Installation data availability\n"
                    "• Date range validity\n"
                    "• Weather data access",
                )

        except Exception as e:
            logger.error(f"Error during prediction: {e}")
            self.status_var.set(f"Error: {str(e)}")
            messagebox.showerror(
                "Prediction Error",
                f"An error occurred during prediction:\n{e}\n\n"
                "Please check the application logs for more details.",
            )

        finally:
            self.progress_bar.stop()

    def _on_closing(self):
        """Handle application closing."""
        try:
            logger.info("Application closing...")

            # Save any necessary data or models
            # (Future enhancement)

            self.root.quit()
            self.root.destroy()

        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            self.root.quit()
            self.root.destroy()

    def run(self):
        """Run the application main loop."""
        try:
            logger.info("Starting FilantropiaSolar application main loop")
            self.root.mainloop()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise

    def get_installation_info(self):
        """Get information about available installations."""
        return self.data_processor.get_installation_list()

    def get_data_summary(self):
        """Get summary of available data."""
        return self.data_processor.get_data_summary()


def main():
    """Main application entry point."""
    try:
        # Create and run the enhanced application
        app = EnhancedFilantropiaSolarApp()
        app.run()

    except Exception as e:
        logger.error(f"Fatal error starting application: {e}")
        if tk._default_root:
            messagebox.showerror(
                "Fatal Error",
                f"Failed to start FilantropiaSolar:\n{e}\n\n"
                "Please check the logs for more information.",
            )
        raise


if __name__ == "__main__":
    main()
