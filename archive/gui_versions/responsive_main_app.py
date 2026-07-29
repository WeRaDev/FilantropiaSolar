"""
Responsive Main Application for FilantropiaSolar

Loads data in background threads with progress feedback to keep GUI responsive.
Shows immediate feedback about available data and loading progress.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from pathlib import Path
import sys
import threading
import time
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
from src.weather_simulation.weather_simulator import WeatherSimulator
from src.gui.simple_input_window import SimpleInputWindow
from src.gui.enhanced_plot_window import EnhancedPlotWindow
from src.gui.output_window import OutputWindow

logger = logging.getLogger(__name__)


class ResponsiveFilantropiaSolarApp:
    """
    Responsive main application for FilantropiaSolar.

    Features:
    - Fast GUI startup with background data loading
    - Progress feedback for all long operations
    - Responsive interface during data processing
    - Immediate display of available data ranges
    """

    def __init__(self):
        """Initialize the responsive application."""
        self.root = tk.Tk()
        self.root.title("FilantropiaSolar v2.0 - Loading...")

        # Set minimum size and responsive geometry
        self.root.minsize(1200, 800)

        # Get screen dimensions for better sizing
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Use 90% of screen size but with maximum limits
        width = min(int(screen_width * 0.9), 1600)
        height = min(int(screen_height * 0.9), 1000)

        # Center the window
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Initialize components as None - will be loaded in background
        self.data_processor = None
        self.weather_simulator = None
        self.predictor = None
        self.current_results = None

        # Loading state
        self.loading_complete = False
        self.loading_progress = 0
        self.loading_status = "Initializing..."

        # Create immediate GUI
        self._create_loading_gui()

        # Start background loading
        self._start_background_loading()

        logger.info("Responsive FilantropiaSolar application initialized")

    def _create_loading_gui(self):
        """Create the initial loading GUI."""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Loading screen frame
        self.loading_frame = ttk.Frame(main_container)
        self.loading_frame.pack(expand=True)

        # App title
        title_label = ttk.Label(
            self.loading_frame, text="FilantropiaSolar v2.0", font=("Arial", 24, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Loading progress
        progress_frame = ttk.Frame(self.loading_frame)
        progress_frame.pack(pady=20)

        ttk.Label(progress_frame, text="Loading Application...").pack()

        self.progress_bar = ttk.Progressbar(
            progress_frame, mode="determinate", length=400
        )
        self.progress_bar.pack(pady=10)

        # Status label
        self.loading_status_var = tk.StringVar(value="Initializing...")
        self.loading_status_label = ttk.Label(
            progress_frame, textvariable=self.loading_status_var, foreground="blue"
        )
        self.loading_status_label.pack()

        # Data preview (will be populated as data loads)
        preview_frame = ttk.LabelFrame(
            self.loading_frame, text="Available Data", padding="10"
        )
        preview_frame.pack(pady=20, fill=tk.X)

        self.data_preview_text = tk.Text(
            preview_frame, height=8, width=80, state=tk.DISABLED, font=("Courier", 10)
        )
        self.data_preview_text.pack(fill=tk.X)

        # Initially show basic info
        self._update_data_preview("Scanning data directory...")

        # Quick data scan (lightweight)
        self._scan_available_data()

    def _scan_available_data(self):
        """Quick scan to show what data files are available."""
        try:
            data_dir = project_root / "data"
            weather_dir = project_root / "weather_files"

            preview_text = "📁 Data Directory Scan:\n\n"

            # Check PV data files
            if data_dir.exists():
                pv_files = list(data_dir.glob("*.xlsx"))
                preview_text += (
                    f"🔋 PV Data Files: {len(pv_files)} installations found\n"
                )
                for i, file in enumerate(pv_files[:5]):  # Show first 5
                    preview_text += f"   • {file.stem}\n"
                if len(pv_files) > 5:
                    preview_text += f"   • ... and {len(pv_files) - 5} more\n"
            else:
                preview_text += "🔋 PV Data Files: Directory not found\n"

            preview_text += "\n"

            # Check weather data files
            if weather_dir.exists():
                weather_files = list(weather_dir.glob("*.csv"))
                preview_text += (
                    f"🌤️  Weather Data Files: {len(weather_files)} locations found\n"
                )
                for i, file in enumerate(weather_files[:6]):  # Show first 6
                    preview_text += f"   • {file.stem.replace('_weather', '')}\n"
                if len(weather_files) > 6:
                    preview_text += f"   • ... and {len(weather_files) - 6} more\n"
            else:
                preview_text += "🌤️  Weather Data Files: Directory not found\n"

            preview_text += f"\n📊 Full data loading in progress...\n"
            preview_text += f"⏱️  This may take 1-2 minutes for complete initialization."

            self._update_data_preview(preview_text)

        except Exception as e:
            logger.error(f"Error scanning available data: {e}")
            self._update_data_preview(f"Error scanning data: {e}")

    def _update_data_preview(self, text: str):
        """Update the data preview text."""
        self.data_preview_text.config(state=tk.NORMAL)
        self.data_preview_text.delete(1.0, tk.END)
        self.data_preview_text.insert(1.0, text)
        self.data_preview_text.config(state=tk.DISABLED)

    def _start_background_loading(self):
        """Start background loading of data."""

        def load_data():
            try:
                # Step 1: Load data processor
                self.loading_status_var.set("Loading installation metadata...")
                self.progress_bar["value"] = 10
                self.root.update_idletasks()

                self.data_processor = ComprehensiveDataProcessor()

                # Update preview with loaded installations
                installations = self.data_processor.get_installation_list()
                date_range = self.data_processor.get_date_range()

                preview_text = f"✅ Successfully Loaded Data:\n\n"
                preview_text += f"🏠 Solar Installations: {len(installations)}\n"

                for inst_id, info in installations:
                    preview_text += f"   • {info.location}_{info.serial_number}: {info.installed_power_kwp} kWp\n"

                if date_range[0] and date_range[1]:
                    preview_text += f"\n📅 Historical Data Range:\n"
                    preview_text += f"   From: {date_range[0].date()}\n"
                    preview_text += f"   To: {date_range[1].date()}\n"
                    days = (date_range[1] - date_range[0]).days
                    preview_text += f"   Duration: {days} days\n"

                preview_text += f"\n🤖 Training ML models..."

                self._update_data_preview(preview_text)

                # Step 2: Load weather simulator
                self.loading_status_var.set("Initializing weather simulation...")
                self.progress_bar["value"] = 30
                self.root.update_idletasks()

                weather_data_dir = project_root / "weather_files"
                self.weather_simulator = WeatherSimulator(str(weather_data_dir))

                # Step 3: Initialize predictor (this takes the longest)
                self.loading_status_var.set(
                    "Training ML models (this may take 1-2 minutes)..."
                )
                self.progress_bar["value"] = 50
                self.root.update_idletasks()

                self.predictor = EnhancedEnergyPredictor(
                    self.data_processor, self.weather_simulator
                )

                # Completion
                self.loading_status_var.set("Loading complete!")
                self.progress_bar["value"] = 100
                self.root.update_idletasks()

                # Update final preview
                preview_text = preview_text.replace(
                    "🤖 Training ML models...", "🤖 ML Models: Trained and ready"
                )
                preview_text += f"\n\n🎉 Application ready for predictions!"
                self._update_data_preview(preview_text)

                self.loading_complete = True

                # Switch to main GUI after short delay
                self.root.after(2000, self._switch_to_main_gui)

            except Exception as e:
                logger.error(f"Error during background loading: {e}")
                self.loading_status_var.set(f"Error: {e}")
                self.progress_bar["value"] = 0
                messagebox.showerror(
                    "Loading Error",
                    f"Failed to initialize application components:\n{e}\n\n"
                    "Please check that all data files are present and accessible.",
                )

        # Start loading in background thread
        loading_thread = threading.Thread(target=load_data, daemon=True)
        loading_thread.start()

    def _switch_to_main_gui(self):
        """Switch from loading screen to main application GUI."""
        try:
            # Clear loading screen
            self.loading_frame.destroy()

            # Update window title
            self.root.title("FilantropiaSolar v2.0 - Solar Energy Analysis")

            # Ensure window is properly sized (don't force maximize on macOS)
            # Window was already properly sized in __init__

            # Configure style
            self.style = ttk.Style()
            try:
                self.style.theme_use("clam")
            except Exception:
                pass  # Fallback to default theme

            # Create main GUI
            self._create_main_gui()

            # Set up callbacks
            self._setup_callbacks()

            logger.info("Switched to main GUI interface")

        except Exception as e:
            logger.error(f"Error switching to main GUI: {e}")
            messagebox.showerror("GUI Error", f"Failed to create main interface: {e}")

    def _create_main_gui(self):
        """Create the main GUI with tabs."""
        # Main container - use all available space
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Configure main container to expand
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

        # Create notebook for tabs - maximize space usage
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Create tab frames with proper configuration
        input_tab = ttk.Frame(self.notebook)
        charts_tab = ttk.Frame(self.notebook)
        output_tab = ttk.Frame(self.notebook)

        # Configure tab frames to expand
        for tab in [input_tab, charts_tab, output_tab]:
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        # Add tabs to notebook
        self.notebook.add(input_tab, text="🏠 Input & Configuration")
        self.notebook.add(charts_tab, text="📊 Charts & Analysis")
        self.notebook.add(output_tab, text="📋 Results & Output")

        # Initialize tab components
        self.input_window = SimpleInputWindow(
            input_tab, self.data_processor, self._on_predict_callback
        )

        self.plot_window = EnhancedPlotWindow(charts_tab)
        self.output_window = OutputWindow(output_tab)

        # Status bar
        self._create_status_bar(main_container)

        logger.info("Main GUI created with 3-tab interface")

    def _create_status_bar(self, parent):
        """Create status bar."""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=0)

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

        # Progress bar (hidden initially)
        self.main_progress_bar = ttk.Progressbar(
            self.status_frame, mode="indeterminate", length=200
        )
        self.main_progress_bar.pack(side=tk.RIGHT, padx=(5, 0))
        self.main_progress_bar.pack_forget()  # Hide initially

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

        def run_prediction():
            try:
                self.status_var.set("Generating predictions...")
                self.main_progress_bar.pack(side=tk.RIGHT, padx=(5, 0))
                self.main_progress_bar.start()
                self.root.update_idletasks()

                logger.info(
                    f"Starting prediction for {installation_id} on {target_date.date()}"
                )

                # Generate 15-day prediction centered on target date
                start_date = target_date - timedelta(days=7)
                end_date = target_date + timedelta(days=7)

                # Generate predictions
                results = self.predictor.predict_15day_period(
                    installation_id=installation_id,
                    center_date=target_date,
                    use_simulation=use_simulation,
                )

                self.current_results = results

                # Update plot window
                self.plot_window.update_prediction_data(results)

                # Update output window
                self.output_window.display_results(results)

                # Switch to charts tab to show results
                self.notebook.select(1)  # Charts tab

                self.status_var.set(f"Prediction complete for {installation_id}")

                logger.info(f"Prediction completed successfully")

            except Exception as e:
                logger.error(f"Error during prediction: {e}")
                self.status_var.set(f"Prediction failed: {e}")
                messagebox.showerror(
                    "Prediction Error", f"Failed to generate prediction:\n{e}"
                )

            finally:
                self.main_progress_bar.stop()
                self.main_progress_bar.pack_forget()

        # Run prediction in background thread
        prediction_thread = threading.Thread(target=run_prediction, daemon=True)
        prediction_thread.start()

    def _on_closing(self):
        """Handle application closing."""
        logger.info("Application closing...")
        self.root.destroy()

    def run(self):
        """Start the application main loop."""
        logger.info("Starting FilantropiaSolar application main loop")
        self.root.mainloop()
        logger.info("Application terminated")


if __name__ == "__main__":
    app = ResponsiveFilantropiaSolarApp()
    app.run()
