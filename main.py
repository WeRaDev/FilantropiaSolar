#!/usr/bin/env python3
"""
FilantropiaSolar - Advanced Solar Energy Analysis Application

A comprehensive solar energy prediction and analysis tool for Portuguese PV installations
featuring interactive charts, historical analysis, and future simulation capabilities.

Data Source Citation:
Sarmas, Elissaios; Matias, Nuno; Pereira, Catarina; Antunes, Ana Rita (2025),
"Photovoltaic Power Production Dataset", Mendeley Data, V3, doi: 10.17632/dbh93b6vp8.3

Author: FilantropiaSolar Team
Version: 2.0 - Enhanced Edition
"""

import sys
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from pathlib import Path
import threading
import queue
from typing import Dict, Any, Optional
import pandas as pd

# Add src to path for imports
SRC_PATH = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_PATH))

# Configure logger
logger = logging.getLogger(__name__)


class FilantropiaSolarApp:
    """
    Main application class for FilantropiaSolar enhanced solar energy analysis.

    Features:
    - Interactive hourly energy production charts
    - Historical data analysis and future simulation
    - Weather correlation analysis
    - Performance rankings and insights
    - Multi-installation support
    """

    def __init__(self):
        """Initialize the FilantropiaSolar application."""
        self._setup_logging()

        # Core components (loaded progressively)
        self.data_processor = None
        self.weather_simulator = None
        self.energy_predictor = None
        self.weather_ranking_system = None

        # GUI components
        self.root = None
        self.loading_frame = None
        self.main_frame = None
        self.progress_var = None
        self.status_var = None

        # Threading for non-blocking initialization
        self.loading_queue = queue.Queue()
        self.loading_thread = None

        # Application state
        self.is_initialized = False
        self.current_results = None
        self.current_day_index = 7  # Start with center date
        self.available_dates = {}  # Store available dates per installation

        logger.info("FilantropiaSolar Application initialized")

    def _setup_logging(self):
        """Setup logging configuration for the application."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "filantropia_solar.log"),
                logging.StreamHandler(sys.stdout),
            ],
        )

        logger.setLevel(logging.INFO)

    def create_loading_gui(self):
        """Create the initial loading interface."""
        self.root = tk.Tk()
        self.root.title("FilantropiaSolar - Loading...")
        self.root.geometry("520x320")
        self.root.resizable(False, False)

        # Center the window
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 520) // 2
        y = (screen_height - 320) // 2
        self.root.geometry(f"520x320+{x}+{y}")

        # Main loading frame
        self.loading_frame = ttk.Frame(self.root, padding="30")
        self.loading_frame.pack(fill=tk.BOTH, expand=True)

        # Application title and branding
        title_label = ttk.Label(
            self.loading_frame, text="☀️ FilantropiaSolar", font=("Arial", 20, "bold")
        )
        title_label.pack(pady=(20, 5))

        subtitle_label = ttk.Label(
            self.loading_frame,
            text="Advanced Solar Energy Analysis",
            font=("Arial", 12, "italic"),
        )
        subtitle_label.pack(pady=(0, 20))

        # Progress tracking
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            self.loading_frame,
            variable=self.progress_var,
            maximum=100,
            length=350,
            mode="determinate",
        )
        progress_bar.pack(pady=10)

        self.status_var = tk.StringVar(value="Initializing application...")
        status_label = ttk.Label(
            self.loading_frame, textvariable=self.status_var, font=("Arial", 10)
        )
        status_label.pack(pady=10)

        # Feature overview
        info_frame = ttk.Frame(self.loading_frame)
        info_frame.pack(pady=(20, 0), fill=tk.BOTH, expand=True)

        features_text = tk.Text(
            info_frame,
            height=7,
            width=55,
            wrap=tk.WORD,
            font=("Arial", 9),
            state="disabled",
            bg=self.root.cget("bg"),
            relief="flat",
        )
        features_text.pack()

        features_text.config(state="normal")
        features_text.insert(
            tk.END,
            "🔋 Loading comprehensive solar energy system...\n\n"
            "✓ 9 PV installations across Portugal\n"
            "✓ 315,567+ historical energy records\n"
            "✓ Hourly production analysis with weather correlation\n"
            "✓ Historical data exploration & future simulation\n"
            "✓ Interactive charts with performance rankings\n"
            "✓ Advanced machine learning predictions\n",
        )
        features_text.config(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self._on_loading_close)

    def _on_loading_close(self):
        """Handle loading window close event."""
        if messagebox.askyesno(
            "Confirm Exit", "Cancel loading and exit FilantropiaSolar?"
        ):
            self._cleanup_and_exit()

    def _cleanup_and_exit(self):
        """Perform cleanup and exit the application."""
        try:
            if self.loading_thread and self.loading_thread.is_alive():
                # Allow thread to finish naturally
                pass

            if self.root:
                self.root.quit()
                self.root.destroy()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            sys.exit(0)

    def _update_progress(self, value: float, status: str):
        """Update the progress bar and status message."""
        self.progress_var.set(value)
        self.status_var.set(status)
        self.root.update_idletasks()

    def _initialize_components_threaded(self):
        """Initialize all application components in a separate thread."""
        try:
            # Step 1: Load data processing system
            self._update_progress(15, "Loading installation data...")
            from src.data_processing.comprehensive_data_processor import (
                ComprehensiveDataProcessor,
            )

            self.data_processor = ComprehensiveDataProcessor()

            # Step 2: Analyze available data ranges
            self._update_progress(35, "Analyzing available data ranges...")
            self._load_available_dates()

            # Step 3: Initialize weather simulation
            self._update_progress(55, "Initializing weather simulation...")
            from src.weather_simulation.weather_simulator import WeatherSimulator

            self.weather_simulator = WeatherSimulator("weather_files")

            # Step 4: Initialize ML models (try loading existing first)
            self._update_progress(75, "Initializing machine learning models...")
            from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
            from src.prediction.weather_ranking_system import WeatherRankingSystem

            self.energy_predictor = EnhancedEnergyPredictor(
                self.data_processor, self.weather_simulator
            )

            # Initialize weather ranking system
            self.weather_ranking_system = WeatherRankingSystem(
                self.energy_predictor, self.data_processor
            )

            # Try to load existing models first (for weak devices)
            try:
                if self.energy_predictor.load_existing_models():
                    logger.info("Loaded existing ML models successfully")
                    self._update_progress(95, "Using existing ML models...")
                else:
                    logger.info("No existing models found, training new ones")
                    self._update_progress(
                        80, "Training ML models (first-time setup)..."
                    )
                    # Models will be trained automatically during first prediction
            except Exception as e:
                logger.warning(
                    f"Could not load existing models: {e}. Training new ones."
                )
                self._update_progress(80, "Training ML models...")

            # Step 5: Finalize setup
            self._update_progress(98, "Finalizing setup...")

            self._update_progress(100, "Initialization complete!")

            # Signal successful completion
            self.loading_queue.put("COMPLETE")

        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            self.loading_queue.put(f"ERROR: {str(e)}")

    def _load_available_dates(self):
        """Load available date ranges for each installation."""
        try:
            installations = self.data_processor.get_installation_list()

            for inst_id, info in installations:
                try:
                    # Attempt to get installation data
                    data = self.data_processor.get_combined_data(inst_id)
                    if data is not None and not data.empty:
                        min_date = data.index.min().date()
                        max_date = data.index.max().date()
                        self.available_dates[inst_id] = {
                            "min_date": min_date,
                            "max_date": max_date,
                            "location": info.location,
                            "serial": info.serial_number,
                        }
                except Exception as data_error:
                    logger.warning(
                        f"Could not load dates for installation {inst_id}: {data_error}"
                    )
                    # Set reasonable default date range
                    self.available_dates[inst_id] = {
                        "min_date": datetime(2023, 1, 1).date(),
                        "max_date": datetime(2024, 12, 31).date(),
                        "location": info.location,
                        "serial": info.serial_number,
                    }

            logger.info(
                f"Loaded available dates for {len(self.available_dates)} installations"
            )

        except Exception as e:
            logger.error(f"Error loading available dates: {e}")

    def _start_loading(self):
        """Start the loading process in a separate thread."""
        self.loading_thread = threading.Thread(
            target=self._initialize_components_threaded
        )
        self.loading_thread.daemon = True
        self.loading_thread.start()

        self._check_loading_progress()

    def _check_loading_progress(self):
        """Check loading progress and handle completion/errors."""
        try:
            message = self.loading_queue.get_nowait()

            if message == "COMPLETE":
                self._on_loading_complete()
            elif message.startswith("ERROR:"):
                self._on_loading_error(message[6:])  # Remove "ERROR:" prefix

        except queue.Empty:
            # Continue checking
            self.root.after(100, self._check_loading_progress)
        except Exception as e:
            logger.error(f"Error checking loading progress: {e}")
            self._on_loading_error(str(e))

    def _on_loading_complete(self):
        """Handle successful loading completion."""
        try:
            self.is_initialized = True
            logger.info("All components initialized successfully")

            # Brief pause to show completion
            self.root.after(1000, self._transition_to_main_gui)

        except Exception as e:
            logger.error(f"Error handling loading completion: {e}")
            self._on_loading_error(str(e))

    def _on_loading_error(self, error_message: str):
        """Handle loading errors."""
        logger.error(f"Loading failed: {error_message}")

        self.status_var.set("Loading failed!")
        self.progress_var.set(0)

        messagebox.showerror(
            "Loading Failed",
            f"Failed to initialize FilantropiaSolar:\n\n{error_message}\n\n"
            "Please check the logs directory for more details.",
        )

        self._cleanup_and_exit()

    def _transition_to_main_gui(self):
        """Transition from loading screen to main application interface."""
        try:
            # Remove loading interface
            self.loading_frame.destroy()

            # Reconfigure main window
            self.root.title("FilantropiaSolar - Advanced Solar Energy Analysis")
            self.root.geometry("1400x900")
            self.root.resizable(True, True)

            # Create main interface
            self._create_main_gui()
            self._show_welcome_message()

        except Exception as e:
            logger.error(f"Error transitioning to main GUI: {e}")
            messagebox.showerror(
                "Interface Error", f"Failed to create main interface:\n{str(e)}"
            )
            self._cleanup_and_exit()

    def _create_main_gui(self):
        """Create the main application interface with tabs."""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create tabbed interface
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Input & Configuration tab
        input_frame = ttk.Frame(notebook)
        notebook.add(input_frame, text="🎯 Analysis Configuration")
        self._create_input_interface(input_frame)

        # Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="📋 Analysis Results")
        self._create_results_interface(results_frame)

        # Interactive Charts tab
        charts_frame = ttk.Frame(notebook)
        notebook.add(charts_frame, text="📊 Interactive Charts")
        self._create_charts_interface(charts_frame)

        # Configure window close behavior
        self.root.protocol("WM_DELETE_WINDOW", self._on_main_close)

    def _create_input_interface(self, parent):
        """Create the analysis configuration interface."""
        container = ttk.Frame(parent, padding="20")
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        title_label = ttk.Label(
            container,
            text="Solar Energy Analysis Configuration",
            font=("Arial", 16, "bold"),
        )
        title_label.pack(pady=(0, 20))

        # Analysis Mode Selection
        mode_frame = ttk.LabelFrame(container, text="Analysis Mode", padding="15")
        mode_frame.pack(fill=tk.X, pady=(0, 15))

        self.mode_var = tk.StringVar(value="historical")

        ttk.Radiobutton(
            mode_frame,
            text="📈 Historical Analysis (analyze existing data)",
            variable=self.mode_var,
            value="historical",
            command=self._on_mode_change,
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Radiobutton(
            mode_frame,
            text="🔮 Future Simulation (predict any date)",
            variable=self.mode_var,
            value="simulation",
            command=self._on_mode_change,
        ).pack(anchor=tk.W)

        # Installation Selection
        install_frame = ttk.LabelFrame(
            container, text="Installation Selection", padding="15"
        )
        install_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(install_frame, text="Choose Installation:").pack(anchor=tk.W)

        installations = self.data_processor.get_installation_list()
        installation_options = [
            f"{info.location}_{info.serial_number} ({info.installed_power_kwp} kWp)"
            for _, info in installations
        ]

        self.installation_var = tk.StringVar(
            value=installation_options[0] if installation_options else ""
        )
        installation_combo = ttk.Combobox(
            install_frame,
            textvariable=self.installation_var,
            values=installation_options,
            state="readonly",
            width=65,
        )
        installation_combo.pack(fill=tk.X, pady=(5, 0))
        installation_combo.bind("<<ComboboxSelected>>", self._on_installation_change)

        # Date Selection (Dynamic based on mode)
        self.date_frame = ttk.LabelFrame(container, text="Date Selection", padding="15")
        self.date_frame.pack(fill=tk.X, pady=(0, 15))

        # Historical date selection frame
        self.historical_date_frame = ttk.Frame(self.date_frame)
        self.historical_date_frame.pack(fill=tk.X)

        ttk.Label(self.historical_date_frame, text="Available Data Range:").pack(
            anchor=tk.W
        )
        self.date_range_label = ttk.Label(
            self.historical_date_frame,
            text="Select an installation first",
            foreground="gray",
        )
        self.date_range_label.pack(anchor=tk.W, pady=(2, 10))

        ttk.Label(self.historical_date_frame, text="Select Historical Date:").pack(
            anchor=tk.W
        )
        self.historical_date_var = tk.StringVar()
        self.historical_date_combo = ttk.Combobox(
            self.historical_date_frame,
            textvariable=self.historical_date_var,
            state="readonly",
            width=20,
        )
        self.historical_date_combo.pack(anchor=tk.W, pady=(5, 0))

        # Simulation date selection frame
        self.simulation_date_frame = ttk.Frame(self.date_frame)

        ttk.Label(self.simulation_date_frame, text="Enter Date for Simulation:").pack(
            anchor=tk.W
        )
        self.simulation_date_var = tk.StringVar(
            value=datetime.now().strftime("%Y-%m-%d")
        )
        simulation_date_entry = ttk.Entry(
            self.simulation_date_frame, textvariable=self.simulation_date_var, width=20
        )
        simulation_date_entry.pack(anchor=tk.W, pady=(5, 0))

        ttk.Label(
            self.simulation_date_frame,
            text="Format: YYYY-MM-DD (e.g., 2025-06-15)",
            font=("Arial", 9),
            foreground="gray",
        ).pack(anchor=tk.W, pady=(2, 0))

        # Analysis Options
        options_frame = ttk.LabelFrame(container, text="Options", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))

        self.simulation_var = tk.BooleanVar(value=True)
        self.simulation_checkbox = ttk.Checkbutton(
            options_frame,
            text="Enable weather simulation (recommended for complete analysis)",
            variable=self.simulation_var,
        )
        self.simulation_checkbox.pack(anchor=tk.W)

        # Action Buttons Frame
        buttons_frame = ttk.Frame(container)
        buttons_frame.pack(pady=15)

        # Main analysis button
        predict_button = ttk.Button(
            buttons_frame,
            text="🚀 Generate 15-Day Analysis",
            command=self._generate_analysis,
            style="Accent.TButton",
        )
        predict_button.pack(side=tk.LEFT, padx=(0, 10))

        # ML retrain button for advanced users
        retrain_button = ttk.Button(
            buttons_frame,
            text="🔧 Retrain ML Models",
            command=self._retrain_models,
            style="TButton",
        )
        retrain_button.pack(side=tk.LEFT)

        # Status Display
        self.input_status_var = tk.StringVar(value="Ready to generate analysis")
        status_label = ttk.Label(
            container, textvariable=self.input_status_var, foreground="blue"
        )
        status_label.pack(pady=(10, 0))

        # Initialize interface
        self._on_mode_change()
        self._on_installation_change()

    def _on_mode_change(self):
        """Handle analysis mode change."""
        mode = self.mode_var.get()

        if mode == "historical":
            self.historical_date_frame.pack(fill=tk.X)
            self.simulation_date_frame.pack_forget()
            # Enable simulation for historical analysis when weather data is needed
            self.simulation_checkbox.config(state="normal")
            self.simulation_var.set(
                True
            )  # Enable simulation by default for historical analysis
        else:
            self.simulation_date_frame.pack(fill=tk.X)
            self.historical_date_frame.pack_forget()
            self.simulation_checkbox.config(state="normal")
            self.simulation_var.set(True)

    def _on_installation_change(self, event=None):
        """Handle installation selection change."""
        try:
            installation_text = self.installation_var.get()
            if not installation_text:
                return

            # Find corresponding installation ID
            installation_id = None
            for inst_id, info in self.data_processor.get_installation_list():
                if installation_text.startswith(
                    f"{info.location}_{info.serial_number}"
                ):
                    installation_id = inst_id
                    break

            if installation_id and installation_id in self.available_dates:
                date_info = self.available_dates[installation_id]
                min_date = date_info["min_date"]
                max_date = date_info["max_date"]

                # Update date range display
                days_available = (max_date - min_date).days
                self.date_range_label.config(
                    text=f"{min_date} to {max_date} ({days_available:,} days available)",
                    foreground="blue",
                )

                # Populate historical date options (sample to avoid overwhelming dropdown)
                date_list = []
                current = min_date
                step_size = max(1, days_available // 50)  # Limit to ~50 options

                while current <= max_date:
                    date_list.append(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=step_size)

                # Ensure max date is included
                if max_date.strftime("%Y-%m-%d") not in date_list:
                    date_list.append(max_date.strftime("%Y-%m-%d"))

                self.historical_date_combo.config(values=date_list)
                if date_list:
                    self.historical_date_var.set(
                        date_list[-1]
                    )  # Default to most recent

        except Exception as e:
            logger.error(f"Error updating installation dates: {e}")

    def _create_results_interface(self, parent):
        """Create the results display interface."""
        container = ttk.Frame(parent, padding="20")
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        title_label = ttk.Label(
            container, text="Analysis Results", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # Results text area with scrollbar
        text_frame = ttk.Frame(container)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.results_text = tk.Text(
            text_frame, wrap=tk.WORD, font=("Courier", 10), state="disabled"
        )

        scrollbar = ttk.Scrollbar(
            text_frame, orient="vertical", command=self.results_text.yview
        )
        self.results_text.configure(yscrollcommand=scrollbar.set)

        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Initial content
        self._update_results_display(
            "No analysis generated yet.\n\nUse the Analysis Configuration tab to generate detailed analysis."
        )

    def _create_charts_interface(self, parent):
        """Create the interactive charts interface."""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import (
                FigureCanvasTkAgg,
                NavigationToolbar2Tk,
            )
            from matplotlib.figure import Figure

            # Main container
            container = ttk.Frame(parent, padding="10")
            container.pack(fill=tk.BOTH, expand=True)

            # Header with navigation
            header_frame = ttk.Frame(container)
            header_frame.pack(fill=tk.X, pady=(0, 10))

            title_label = ttk.Label(
                header_frame,
                text="📊 Interactive Energy Production Analysis",
                font=("Arial", 16, "bold"),
            )
            title_label.pack(side=tk.LEFT)

            # Day navigation controls
            nav_frame = ttk.Frame(header_frame)
            nav_frame.pack(side=tk.RIGHT)

            ttk.Button(
                nav_frame, text="◄ Previous", command=self._previous_day, width=10
            ).pack(side=tk.LEFT, padx=(0, 3))
            ttk.Button(
                nav_frame, text="Center", command=self._center_day, width=8
            ).pack(side=tk.LEFT, padx=(0, 3))
            ttk.Button(nav_frame, text="Next ►", command=self._next_day, width=10).pack(
                side=tk.LEFT
            )

            # Day information display
            self.day_info_label = ttk.Label(
                container,
                text="Generate analysis to explore interactive charts",
                font=("Arial", 11, "bold"),
                foreground="navy",
            )
            self.day_info_label.pack(pady=(0, 10))

            # Create matplotlib figure for 3-chart design
            self.figure = Figure(figsize=(18, 12), dpi=100, tight_layout=True)

            # Grid layout: 3 rows, 1 column for the three main charts
            gs = self.figure.add_gridspec(
                3,
                1,
                height_ratios=[1, 1, 1],  # Equal height for all 3 charts
                hspace=0.3,
            )

            # Chart 1: Hourly Energy Production (ranked bars)
            self.hourly_energy_ax = self.figure.add_subplot(gs[0])

            # Chart 2: Hourly Weather Conditions (temp line, humidity line, cloud bars, wind line)
            self.hourly_weather_ax = self.figure.add_subplot(gs[1])

            # Chart 3: Daily Energy & Weather Overview with moving red frame
            self.daily_overview_ax = self.figure.add_subplot(gs[2])

            # Create and configure canvas
            self.canvas = FigureCanvasTkAgg(self.figure, container)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Matplotlib navigation toolbar
            toolbar_frame = ttk.Frame(container)
            toolbar_frame.pack(fill=tk.X)
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()

            # Initialize empty plots
            self._clear_plots()

            # Store matplotlib reference
            self.plt = plt

        except ImportError as e:
            # Graceful fallback if matplotlib is not available
            error_frame = ttk.Frame(parent)
            error_frame.pack(expand=True, fill=tk.BOTH)

            error_label = ttk.Label(
                error_frame,
                text=f"📊 Charts Feature Unavailable\n\n"
                f"Missing dependency: {str(e)}\n\n"
                f"To enable interactive charts, please install matplotlib:\n"
                f"pip install matplotlib\n\n"
                f"Then restart FilantropiaSolar.",
                font=("Arial", 12),
                foreground="red",
                justify=tk.CENTER,
            )
            error_label.pack(expand=True)

    def _clear_plots(self):
        """Initialize empty plots with placeholder content."""
        if hasattr(self, "hourly_energy_ax"):
            axes = [
                self.hourly_energy_ax,
                self.hourly_weather_ax,
                self.daily_overview_ax,
            ]
            titles = [
                "1️⃣ Hourly Energy Production (Ranked Bars)",
                "2️⃣ Hourly Weather Conditions (Temperature, Humidity, Cloud Cover, Wind)",
                "3️⃣ Daily Energy & Weather Overview (15-Day Range with Navigation)",
            ]

            # Clear main charts
            for ax, title in zip(axes, titles):
                ax.clear()
                ax.text(
                    0.5,
                    0.5,
                    "Generate analysis\nto view charts",
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=ax.transAxes,
                    fontsize=14,
                    alpha=0.6,
                )
                ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

            self.canvas.draw()

    def _create_color_legend(self):
        """Create color legend for performance rankings."""
        if hasattr(self, "legend_ax"):
            self.legend_ax.clear()
            self.legend_ax.set_xlim(0, 10)  # Much wider to accommodate text
            self.legend_ax.set_ylim(0, 12)  # Much taller for proper spacing

            # Define ranking colors and labels
            rankings = [5, 4, 3, 2, 1]
            colors = ["#2ecc71", "#27ae60", "#f39c12", "#e67e22", "#e74c3c"]
            labels = [
                "Excellent (5)",
                "Good (4)",
                "Average (3)",
                "Below Avg (2)",
                "Poor (1)",
            ]

            # Create properly sized color patches
            for i, (rank, color, label) in enumerate(zip(rankings, colors, labels)):
                y_pos = 10.5 - i * 2.0  # Much better vertical spacing

                # Draw much larger rectangle to properly contain all text
                from matplotlib.patches import Rectangle

                rect = Rectangle(
                    (0.5, y_pos - 0.8),
                    9.0,
                    1.6,
                    facecolor=color,
                    alpha=0.9,
                    edgecolor="black",
                    linewidth=2,
                )
                self.legend_ax.add_patch(rect)

                # Add label with proper positioning and size
                text_color = (
                    "white" if color in ["#2ecc71", "#27ae60", "#e74c3c"] else "black"
                )
                self.legend_ax.text(
                    5.0,
                    y_pos,
                    label,
                    ha="center",
                    va="center",
                    fontsize=14,
                    fontweight="bold",
                    color=text_color,
                )

            # Add title with much better positioning
            self.legend_ax.text(
                5.0,
                11.5,
                "Performance\nRanking",
                ha="center",
                va="center",
                fontsize=16,
                fontweight="bold",
                color="navy",
            )

            # Remove axis elements for cleaner appearance
            self.legend_ax.set_xticks([])
            self.legend_ax.set_yticks([])
            self.legend_ax.spines["top"].set_visible(False)
            self.legend_ax.spines["right"].set_visible(False)
            self.legend_ax.spines["bottom"].set_visible(False)
            self.legend_ax.spines["left"].set_visible(False)
            self.legend_ax.set_facecolor("white")
            self.legend_ax.patch.set_alpha(0.0)

    def _generate_analysis(self):
        """Generate solar energy analysis based on current configuration."""
        try:
            # Validate inputs
            installation_text = self.installation_var.get()
            if not installation_text:
                messagebox.showerror("Input Error", "Please select an installation.")
                return

            # Parse installation ID
            installation_id = None
            for inst_id, info in self.data_processor.get_installation_list():
                if installation_text.startswith(
                    f"{info.location}_{info.serial_number}"
                ):
                    installation_id = inst_id
                    break

            if not installation_id:
                messagebox.showerror("Input Error", "Invalid installation selection.")
                return

            # Get date based on selected mode
            mode = self.mode_var.get()
            try:
                if mode == "historical":
                    date_str = self.historical_date_var.get()
                else:
                    date_str = self.simulation_date_var.get()

                if not date_str:
                    messagebox.showerror(
                        "Input Error", "Please select or enter a date."
                    )
                    return

                center_date = datetime.strptime(date_str.strip(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror(
                    "Input Error", "Invalid date format. Please use YYYY-MM-DD."
                )
                return

            # Update status and begin analysis
            analysis_type = (
                "historical analysis" if mode == "historical" else "future simulation"
            )
            self.input_status_var.set(f"Generating {analysis_type}... Please wait.")
            self.root.update_idletasks()

            # Generate prediction using appropriate settings
            use_simulation = self.simulation_var.get() or mode == "simulation"
            results = self.energy_predictor.predict_15day_period(
                installation_id, center_date, use_simulation
            )

            # Store results and update displays
            self.current_results = results
            self._display_results(results, mode)
            self._update_charts(results)

            # Update status
            self.input_status_var.set(f"Analysis completed for {date_str}")

            # Show completion notification
            installation_info = results["installation_info"]
            period_stats = results["period_statistics"]

            success_msg = (
                f"Analysis completed successfully!\n\n"
                f"📍 Location: {installation_info['location']}\n"
                f"⚡ Capacity: {installation_info['capacity_kwp']} kWp\n"
                f"📊 Total Energy (15 days): {period_stats['total_energy_kwh']:.1f} kWh\n"
                f"📈 Average Daily: {period_stats['total_energy_kwh'] / 15:.1f} kWh/day\n\n"
                f"📊 Explore the Interactive Charts tab for detailed hourly analysis!"
            )

            messagebox.showinfo("Analysis Complete", success_msg)

        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            error_msg = str(e)

            # Provide specific guidance for weather data issues
            if (
                "No weather data available" in error_msg
                and "simulation not enabled" in error_msg
            ):
                self.input_status_var.set("Weather simulation needed for analysis.")
                messagebox.showerror(
                    "Weather Data Required",
                    f"Analysis requires weather simulation for this period.\n\n"
                    f'Solution: Enable "weather simulation" option below and try again.\n\n'
                    f"This allows the system to generate weather data for periods where \n"
                    f"historical weather information may be incomplete.",
                )
            else:
                self.input_status_var.set("Error during analysis. Check logs.")
                messagebox.showerror(
                    "Analysis Error", f"Failed to generate analysis:\n\n{error_msg}"
                )

    def _retrain_models(self):
        """Retrain ML models - for advanced users or weak devices setup."""
        try:
            # Confirm action
            if not messagebox.askyesno(
                "Retrain ML Models",
                "This will retrain all machine learning models which may take several minutes.\n\n"
                "This is recommended for:\n"
                "• First-time setup on weak devices\n"
                "• Improving model performance\n"
                "• After updating data\n\n"
                "Continue?",
            ):
                return

            # Update status
            self.input_status_var.set("Retraining ML models... Please wait.")
            self.root.update_idletasks()

            # Disable buttons during retraining
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.config(state="disabled")

            # Retrain models
            if self.energy_predictor:
                logger.info("Starting ML model retraining...")
                self.energy_predictor.retrain_models()
                self.energy_predictor.save_models()
                logger.info("ML model retraining completed")

                # Success message
                self.input_status_var.set("ML models retrained successfully!")
                messagebox.showinfo(
                    "Retraining Complete",
                    "Machine learning models have been successfully retrained and saved.\n\n"
                    "The application will now use the updated models for all predictions.",
                )
            else:
                messagebox.showerror(
                    "Error",
                    "ML predictor not initialized. Please restart the application.",
                )

        except Exception as e:
            logger.error(f"Error retraining models: {e}")
            self.input_status_var.set("Error during model retraining.")
            messagebox.showerror(
                "Retraining Error",
                f"Failed to retrain ML models:\n\n{str(e)}\n\n"
                f"Please check the logs for details.",
            )
        finally:
            # Re-enable buttons
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.config(state="normal")

    def _display_results(self, results: Dict[str, Any], mode: str):
        """Display comprehensive analysis results."""
        try:
            # Build formatted results text
            text = "FILANTROPIA SOLAR - ANALYSIS RESULTS\n"
            text += "=" * 60 + "\n\n"

            # Analysis type and metadata
            analysis_type = (
                "HISTORICAL ANALYSIS" if mode == "historical" else "FUTURE SIMULATION"
            )
            text += f"Analysis Type: {analysis_type}\n\n"

            # Installation details
            inst_info = results["installation_info"]
            text += f"Installation: {inst_info['location']} (Serial: {inst_info['serial_number']})\n"
            text += f"Capacity: {inst_info['capacity_kwp']} kWp\n\n"

            # Analysis period
            period = results["prediction_period"]
            text += (
                f"Analysis Period: {period['start'].date()} to {period['end'].date()}\n"
            )
            text += f"Center Date: {period['center_date'].date()}\n"
            text += f"Total Hours Analyzed: {period['total_hours']}\n\n"

            # Key performance metrics
            stats = results["period_statistics"]
            text += "KEY PERFORMANCE METRICS (15-day period)\n"
            text += "-" * 50 + "\n"
            text += f"Total Energy Production: {stats['total_energy_kwh']:.1f} kWh\n"
            text += (
                f"Average Daily Energy: {stats['total_energy_kwh'] / 15:.1f} kWh/day\n"
            )
            text += f"Average Specific Energy: {stats['average_specific_energy']:.2f} kWh/kWp\n"
            text += f"Peak Hour Energy: {stats['peak_hour_energy']:.2f} kWh/kWp\n"
            text += (
                f"Average Temperature: {stats.get('average_temperature', 0):.1f}°C\n"
            )
            text += (
                f"Average Cloud Cover: {stats.get('average_cloud_cover', 0):.1f}%\n\n"
            )

            # Daily performance breakdown
            if "daily_summary" in results:
                daily = results["daily_summary"]
                text += "DAILY PERFORMANCE BREAKDOWN\n"
                text += "-" * 50 + "\n"
                text += (
                    f"{'Date':<12} {'Energy(kWh)':<12} {'Rating':<15} {'Note':<10}\n"
                )
                text += "-" * 50 + "\n"

                for i, (date, row) in enumerate(daily.iterrows()):
                    energy = row.get("predicted_total_energy", 0)
                    ranking = row.get("ranking", 3)

                    # Convert ranking to descriptive rating
                    rating_map = {
                        1: "⭐ Poor",
                        2: "⭐⭐ Below Avg",
                        3: "⭐⭐⭐ Average",
                        4: "⭐⭐⭐⭐ Good",
                        5: "⭐⭐⭐⭐⭐ Excellent",
                    }
                    rating = rating_map.get(ranking, "Unknown")

                    # Highlight currently selected day
                    marker = " ← SELECTED" if i == self.current_day_index else ""
                    text += f"{str(date):<12} {energy:<12.1f} {rating:<15} {'Sunny' if ranking >= 4 else 'Cloudy':<10}{marker}\n"

            # Data source and model information
            source = results["data_source"]
            text += "\nDATA SOURCE & MODEL INFORMATION\n"
            text += "-" * 50 + "\n"
            text += (
                f"PV Data: Sarmas et al. (2025) Photovoltaic Power Production Dataset\n"
            )
            text += f"DOI: 10.17632/dbh93b6vp8.3\n"
            text += f"Weather Data: {'🌦️ Simulated' if source['used_simulation'] else '📊 Historical'}\n"
            text += f"ML Model Used: {source['model_used'].replace('_', ' ').title()}\n"

            if (
                "model_performance" in source
                and source["model_used"] in source["model_performance"]
            ):
                perf = source["model_performance"][source["model_used"]]
                text += f"Model Accuracy (R²): {perf.get('r2', 0):.3f}\n"
                text += f"Model Error (MAE): {perf.get('mae', 0):.3f} kWh/kWp\n"

            text += f"\n💡 EXPLORE: Use the Interactive Charts tab to dive deeper into hourly patterns and weather correlations!"

            self._update_results_display(text)

        except Exception as e:
            logger.error(f"Error displaying results: {e}")
            self._update_results_display(f"Error displaying results: {str(e)}")

    def _update_results_display(self, text: str):
        """Update the results text area with new content."""
        self.results_text.config(state="normal")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        self.results_text.config(state="disabled")

    def _update_charts(self, results: Dict[str, Any]):
        """Update all charts with analysis results using weather-based ranking system."""
        if not hasattr(self, "hourly_energy_ax"):
            return

        try:
            # Clear existing plots
            for ax in [
                self.hourly_energy_ax,
                self.hourly_weather_ax,
                self.daily_overview_ax,
            ]:
                ax.clear()

            # Extract data
            daily_summary = results["daily_summary"]
            hourly_data = results["hourly_data"]

            logger.info(
                f"Chart update - Hourly data columns: {list(hourly_data.columns)}"
            )
            logger.info(f"Chart update - Daily summary shape: {daily_summary.shape}")
            logger.info(f"Chart update - Hourly data shape: {hourly_data.shape}")

            # Get data for currently selected day
            current_date = daily_summary.index[self.current_day_index]
            target_date = (
                current_date.date() if hasattr(current_date, "date") else current_date
            )

            # Filter hourly data for the current day
            try:
                current_day_hourly = hourly_data[hourly_data.index.date == target_date]
            except AttributeError:
                current_day_hourly = hourly_data[hourly_data.index == target_date]

            if current_day_hourly.empty:
                logger.warning(f"No hourly data found for {target_date}")
                return

            # ===== WEATHER RANKING SYSTEM INTEGRATION =====

            # Check if weather ranking system is available
            if (
                not hasattr(self, "weather_ranking_system")
                or self.weather_ranking_system is None
            ):
                logger.error("Weather ranking system not initialized")
                # Use fallback ranking
                weather_ranked_hourly = pd.DataFrame()
                daily_weather_rankings = {}
            else:
                try:
                    # Debug: Check available weather columns
                    weather_cols = [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "cloud_cover",
                        "wind_speed_10m",
                        "shortwave_radiation",
                    ]
                    available_weather_cols = [
                        col for col in weather_cols if col in hourly_data.columns
                    ]
                    logger.info(f"Available weather columns: {available_weather_cols}")

                    # Get weather rankings for this day
                    weather_ranked_hourly = (
                        self.weather_ranking_system.rank_hourly_weather_conditions(
                            hourly_data, target_date
                        )
                    )

                    # Get daily weather rankings for all days
                    daily_dates = [
                        d.date() if hasattr(d, "date") else d
                        for d in daily_summary.index
                    ]
                    daily_weather_rankings = (
                        self.weather_ranking_system.rank_daily_weather_conditions(
                            hourly_data, daily_dates
                        )
                    )

                    logger.info(
                        f"Weather ranked hourly data shape: {weather_ranked_hourly.shape}"
                    )
                    logger.info(
                        f"Daily weather rankings count: {len(daily_weather_rankings)}"
                    )

                except Exception as e:
                    logger.error(f"Error in weather ranking system: {e}")
                    import traceback

                    logger.error(f"Weather ranking traceback: {traceback.format_exc()}")
                    # Use fallback ranking
                    weather_ranked_hourly = pd.DataFrame()
                    daily_weather_rankings = {}

            # ===== CREATE THE 3 CHARTS =====
            logger.info(
                f"Creating charts for day {self.current_day_index + 1}: {target_date}"
            )

            # Chart 1: Hourly Energy Production (Ranked Bars)
            self._create_hourly_energy_chart(current_day_hourly, target_date)

            # Chart 2: Hourly Weather Conditions
            self._create_hourly_weather_chart(current_day_hourly, target_date)

            # Chart 3: Daily Overview with Moving Red Frame
            daily_dates = [
                d.date() if hasattr(d, "date") else d for d in daily_summary.index
            ]
            self._create_daily_overview_chart(daily_summary, hourly_data, daily_dates)

            # Refresh canvas
            self.canvas.draw()

            # Update day information display
            current_day_energy = current_day_hourly.get(
                "predicted_total_energy", pd.Series([0])
            )
            if not current_day_energy.empty:
                avg_energy = current_day_energy.mean()
                total_energy = current_day_energy.sum()
                peak_energy = current_day_energy.max()

                info_text = f"📅 Day {self.current_day_index + 1} of 15: {target_date.strftime('%Y-%m-%d')} | Total: {total_energy:.1f} kWh | Peak: {peak_energy:.1f} kWh | Avg: {avg_energy:.1f} kWh"
            else:
                info_text = f"📅 Day {self.current_day_index + 1} of 15: {target_date.strftime('%Y-%m-%d')} | No energy data available"

            if hasattr(self, "day_info_label"):
                self.day_info_label.config(text=info_text)

        except Exception as e:
            logger.error(f"Error updating charts: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Show error message in charts
            error_msg = f"Chart update failed: {str(e)}"
            for ax in [
                self.hourly_energy_ax,
                self.hourly_weather_ax,
                self.daily_overview_ax,
            ]:
                ax.clear()
                ax.text(
                    0.5,
                    0.5,
                    error_msg,
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=ax.transAxes,
                    fontsize=10,
                    color="red",
                    alpha=0.8,
                )

            self._create_weather_color_legend()
            self.canvas.draw()

    def _create_hourly_energy_chart(self, current_day_hourly, target_date):
        """Chart 1: Hourly Energy Production with Ranked Bars."""
        try:
            if current_day_hourly.empty:
                self.hourly_energy_ax.text(
                    0.5,
                    0.5,
                    "No energy data\navailable for this day",
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=self.hourly_energy_ax.transAxes,
                    fontsize=12,
                    alpha=0.6,
                )
                return

            # Get energy data
            energy_col = (
                "predicted_total_energy"
                if "predicted_total_energy" in current_day_hourly.columns
                else "Produced Energy (kWh)"
            )
            hourly_energy = current_day_hourly.get(
                energy_col, pd.Series([0] * len(current_day_hourly))
            )
            hourly_energy = pd.to_numeric(hourly_energy, errors="coerce").fillna(0)

            hours = current_day_hourly.index.hour

            # Create energy-based rankings (1-5 scale)
            if len(hourly_energy) > 1:
                # Calculate percentiles for ranking
                percentiles = [20, 40, 60, 80]
                thresholds = [hourly_energy.quantile(p / 100) for p in percentiles]

                energy_rankings = []
                for energy in hourly_energy:
                    if energy <= thresholds[0]:
                        energy_rankings.append(1)  # Poor
                    elif energy <= thresholds[1]:
                        energy_rankings.append(2)  # Below Average
                    elif energy <= thresholds[2]:
                        energy_rankings.append(3)  # Average
                    elif energy <= thresholds[3]:
                        energy_rankings.append(4)  # Good
                    else:
                        energy_rankings.append(5)  # Excellent
            else:
                energy_rankings = [3] * len(hourly_energy)

            # Color map for energy rankings
            color_map = {
                1: "#DC143C",  # Poor - Dark Red
                2: "#FF8C00",  # Below Average - Dark Orange
                3: "#FFA500",  # Average - Orange
                4: "#32CD32",  # Good - Lime Green
                5: "#FFD700",  # Excellent - Gold
            }

            bar_colors = [color_map.get(r, "#3498db") for r in energy_rankings]

            # Create bar chart
            bars = self.hourly_energy_ax.bar(
                hours,
                hourly_energy,
                color=bar_colors,
                alpha=0.8,
                edgecolor="black",
                linewidth=1,
            )

            # Add value labels on bars
            for bar, energy, ranking in zip(bars, hourly_energy, energy_rankings):
                if energy > 0.1:  # Only show labels for significant values
                    height = bar.get_height()
                    # Show energy value
                    self.hourly_energy_ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        height + height * 0.02,
                        f"{energy:.1f}",
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        fontweight="bold",
                    )
                    # Show ranking as stars
                    stars = "⭐" * ranking
                    self.hourly_energy_ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        height + height * 0.08,
                        stars,
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

            # Chart formatting
            self.hourly_energy_ax.set_title(
                f"1️⃣ Hourly Energy Production - {target_date.strftime('%Y-%m-%d')}",
                fontsize=14,
                fontweight="bold",
                pad=20,
            )
            self.hourly_energy_ax.set_xlabel("Hour of Day", fontsize=12)
            self.hourly_energy_ax.set_ylabel("Energy Production (kWh)", fontsize=12)
            self.hourly_energy_ax.grid(True, alpha=0.3)

            # Set x-axis limits
            self.hourly_energy_ax.set_xlim(-0.5, 23.5)
            self.hourly_energy_ax.set_xticks(range(0, 24, 2))

            # Add top margin for labels
            if hourly_energy.max() > 0:
                self.hourly_energy_ax.set_ylim(0, hourly_energy.max() * 1.2)

            # Add ranking legend
            legend_text = "Ranking: ⭐=Poor, ⭐⭐=Below Avg, ⭐⭐⭐=Average, ⭐⭐⭐⭐=Good, ⭐⭐⭐⭐⭐=Excellent"
            self.hourly_energy_ax.text(
                0.5,
                -0.15,
                legend_text,
                transform=self.hourly_energy_ax.transAxes,
                ha="center",
                va="top",
                fontsize=10,
                style="italic",
            )

        except Exception as e:
            logger.error(f"Error creating hourly energy chart: {e}")
            self.hourly_energy_ax.text(
                0.5,
                0.5,
                f"Error creating chart:\n{str(e)}",
                horizontalalignment="center",
                verticalalignment="center",
                transform=self.hourly_energy_ax.transAxes,
                fontsize=10,
                color="red",
            )

    def _create_hourly_weather_chart(self, current_day_hourly, target_date):
        """Chart 2: Hourly Weather Conditions (Temperature, Humidity, Cloud Cover, Wind)."""
        try:
            # Simple and safe approach: just clear the main axes content
            self.hourly_weather_ax.clear()

            if current_day_hourly.empty:
                self.hourly_weather_ax.text(
                    0.5,
                    0.5,
                    "No weather data\navailable for this day",
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=self.hourly_weather_ax.transAxes,
                    fontsize=12,
                    alpha=0.6,
                )
                return

            hours = current_day_hourly.index.hour

            # Check available weather variables
            weather_vars = [
                "temperature_2m",
                "relative_humidity_2m",
                "cloud_cover",
                "wind_speed_10m",
            ]
            available_vars = [
                var for var in weather_vars if var in current_day_hourly.columns
            ]

            if not available_vars:
                self.hourly_weather_ax.text(
                    0.5,
                    0.5,
                    "No weather variables\nfound in data",
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=self.hourly_weather_ax.transAxes,
                    fontsize=12,
                    alpha=0.6,
                )
                return

            # Create or reuse secondary y-axis to prevent stacking
            if not hasattr(self, "_weather_ax2") or self._weather_ax2 is None:
                self._weather_ax2 = self.hourly_weather_ax.twinx()
            else:
                self._weather_ax2.clear()
            ax2 = self._weather_ax2

            # Plot Temperature (Line, left y-axis)
            if "temperature_2m" in available_vars:
                temp_data = pd.to_numeric(
                    current_day_hourly["temperature_2m"], errors="coerce"
                ).fillna(20)
                self.hourly_weather_ax.plot(
                    hours,
                    temp_data,
                    "ro-",
                    linewidth=3,
                    markersize=6,
                    label="Temperature (°C)",
                    alpha=0.8,
                )
                self.hourly_weather_ax.set_ylabel(
                    "Temperature (°C)", color="red", fontsize=12
                )
                self.hourly_weather_ax.tick_params(axis="y", labelcolor="red")

            # Plot Humidity (Line, right y-axis)
            if "relative_humidity_2m" in available_vars:
                humidity_data = pd.to_numeric(
                    current_day_hourly["relative_humidity_2m"], errors="coerce"
                ).fillna(50)
                ax2.plot(
                    hours,
                    humidity_data,
                    "b^-",
                    linewidth=2,
                    markersize=5,
                    label="Humidity (%)",
                    alpha=0.7,
                )

            # Plot Cloud Cover (Bars, right y-axis)
            if "cloud_cover" in available_vars:
                cloud_data = pd.to_numeric(
                    current_day_hourly["cloud_cover"], errors="coerce"
                ).fillna(50)
                ax2.bar(
                    hours,
                    cloud_data,
                    alpha=0.4,
                    color="lightgray",
                    label="Cloud Cover (%)",
                    width=0.8,
                )

            # Plot Wind Speed (Line, right y-axis)
            if "wind_speed_10m" in available_vars:
                wind_data = pd.to_numeric(
                    current_day_hourly["wind_speed_10m"], errors="coerce"
                ).fillna(5)
                ax2.plot(
                    hours,
                    wind_data,
                    "g*-",
                    linewidth=2,
                    markersize=5,
                    label="Wind Speed (m/s)",
                    alpha=0.7,
                )

            # Formatting
            self.hourly_weather_ax.set_title(
                f"2️⃣ Hourly Weather Conditions - {target_date.strftime('%Y-%m-%d')}",
                fontsize=14,
                fontweight="bold",
                pad=20,
            )
            self.hourly_weather_ax.set_xlabel("Hour of Day", fontsize=12)

            # Right y-axis formatting
            ax2.set_ylabel(
                "Humidity (%) / Cloud Cover (%) / Wind Speed (m/s)",
                color="blue",
                fontsize=12,
            )
            ax2.tick_params(axis="y", labelcolor="blue")
            ax2.set_ylim(0, 100)  # 0-100% scale for humidity and cloud cover

            # Add legends
            lines1, labels1 = self.hourly_weather_ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            self.hourly_weather_ax.legend(
                lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=10
            )

            # Grid and axis limits
            self.hourly_weather_ax.grid(True, alpha=0.3)
            self.hourly_weather_ax.set_xlim(-0.5, 23.5)
            self.hourly_weather_ax.set_xticks(range(0, 24, 2))

        except Exception as e:
            logger.error(f"Error creating hourly weather chart: {e}")
            self.hourly_weather_ax.text(
                0.5,
                0.5,
                f"Error creating chart:\n{str(e)}",
                horizontalalignment="center",
                verticalalignment="center",
                transform=self.hourly_weather_ax.transAxes,
                fontsize=10,
                color="red",
            )

    def _create_daily_overview_chart(self, daily_summary, hourly_data, daily_dates):
        """Chart 3: Daily Energy & Weather Overview with Moving Red Frame."""
        try:
            # Simple and safe approach: just clear the main axes content
            self.daily_overview_ax.clear()

            # Get energy data
            energy_col = (
                "predicted_total_energy"
                if "predicted_total_energy" in daily_summary.columns
                else "total_energy"
            )
            daily_energy = daily_summary.get(
                energy_col, pd.Series([0] * len(daily_summary))
            )
            daily_energy = pd.to_numeric(daily_energy, errors="coerce").fillna(0)

            # Calculate daily weather averages
            daily_temperatures = []
            daily_humidity = []
            daily_clouds = []

            for date in daily_dates:
                try:
                    # Filter hourly data for this date
                    try:
                        day_data = hourly_data[hourly_data.index.date == date]
                    except AttributeError:
                        day_data = hourly_data[hourly_data.index == date]

                    if not day_data.empty:
                        temp = pd.to_numeric(
                            day_data.get("temperature_2m", [20]), errors="coerce"
                        ).mean()
                        humidity = pd.to_numeric(
                            day_data.get("relative_humidity_2m", [50]), errors="coerce"
                        ).mean()
                        clouds = pd.to_numeric(
                            day_data.get("cloud_cover", [50]), errors="coerce"
                        ).mean()
                    else:
                        temp, humidity, clouds = 20, 50, 50

                    daily_temperatures.append(temp)
                    daily_humidity.append(humidity)
                    daily_clouds.append(clouds)

                except Exception as e:
                    logger.warning(f"Error processing weather for {date}: {e}")
                    daily_temperatures.append(20)
                    daily_humidity.append(50)
                    daily_clouds.append(50)

            # Create the main energy bars
            x_positions = range(len(daily_dates))

            # Color bars based on energy levels (green gradient)
            import matplotlib.pyplot as plt

            if len(daily_energy) > 1:
                normalized_energy = (daily_energy - daily_energy.min()) / (
                    daily_energy.max() - daily_energy.min()
                )
                bar_colors = [
                    plt.cm.RdYlGn(0.3 + 0.7 * norm) for norm in normalized_energy
                ]
            else:
                bar_colors = ["orange"] * len(daily_energy)

            bars = self.daily_overview_ax.bar(
                x_positions,
                daily_energy,
                color=bar_colors,
                alpha=0.7,
                edgecolor="black",
                linewidth=1,
                label="Daily Energy (kWh)",
            )

            # Add the MOVING RED FRAME around currently selected day
            if 0 <= self.current_day_index < len(bars):
                selected_bar = bars[self.current_day_index]

                # Highlight selected bar with thick red outline
                selected_bar.set_edgecolor("red")
                selected_bar.set_linewidth(5)

                # Create a prominent red frame around the selected bar
                from matplotlib.patches import Rectangle

                bar_x = selected_bar.get_x()
                bar_width = selected_bar.get_width()
                bar_height = (
                    selected_bar.get_height()
                    if selected_bar.get_height() > 0
                    else daily_energy.max() * 0.1
                )

                # Main red frame
                frame = Rectangle(
                    (bar_x - 0.15, -bar_height * 0.1),
                    bar_width + 0.3,
                    bar_height * 1.3,
                    linewidth=4,
                    edgecolor="red",
                    facecolor="none",
                    alpha=0.9,
                    linestyle="-",
                )
                self.daily_overview_ax.add_patch(frame)

                # Add "VIEWING" label with arrow
                self.daily_overview_ax.annotate(
                    f"◀ VIEWING DAY {self.current_day_index + 1}",
                    xy=(bar_x + bar_width / 2, bar_height),
                    xytext=(0, 30),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=12,
                    fontweight="bold",
                    color="red",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8),
                    arrowprops=dict(arrowstyle="->", color="red", lw=2),
                )

            # Create or reuse secondary y-axis for weather data
            if not hasattr(self, "_daily_ax2") or self._daily_ax2 is None:
                self._daily_ax2 = self.daily_overview_ax.twinx()
            else:
                self._daily_ax2.clear()
            ax2 = self._daily_ax2

            # Plot daily average temperature with bright, visible color
            ax2.plot(
                x_positions,
                daily_temperatures,
                color="darkred",
                marker="o",
                linewidth=2,
                markersize=6,
                label="Avg Temperature (°C)",
                alpha=0.9,
                markerfacecolor="red",
                markeredgecolor="darkred",
            )

            # Plot daily average cloud cover with bright, visible color
            ax2.plot(
                x_positions,
                daily_clouds,
                color="darkblue",
                marker="s",
                linewidth=2,
                markersize=5,
                label="Avg Cloud Cover (%)",
                alpha=0.9,
                markerfacecolor="blue",
                markeredgecolor="darkblue",
            )

            # Chart formatting
            self.daily_overview_ax.set_title(
                f"3️⃣ Daily Energy & Weather Overview (15-Day Analysis Period)",
                fontsize=14,
                fontweight="bold",
                pad=20,
            )
            self.daily_overview_ax.set_xlabel("Day in Analysis Period", fontsize=12)
            self.daily_overview_ax.set_ylabel(
                "Daily Energy Production (kWh)", color="blue", fontsize=12
            )
            ax2.set_ylabel(
                "Temperature (°C) / Cloud Cover (%)", color="red", fontsize=12
            )

            # Set x-axis labels
            date_labels = [
                f"Day {i + 1}\n{d.strftime('%m/%d')}" for i, d in enumerate(daily_dates)
            ]
            self.daily_overview_ax.set_xticks(x_positions)
            self.daily_overview_ax.set_xticklabels(date_labels, rotation=0, ha="center")

            # Axis colors
            self.daily_overview_ax.tick_params(axis="y", labelcolor="blue")
            ax2.tick_params(axis="y", labelcolor="red")

            # Add legends
            lines1, labels1 = self.daily_overview_ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            self.daily_overview_ax.legend(
                lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9
            )

            self.daily_overview_ax.grid(True, alpha=0.3)

            # Add navigation instruction
            instruction_text = "← Previous | → Next | Red frame shows day being analyzed in hourly charts above"
            self.daily_overview_ax.text(
                0.5,
                -0.15,
                instruction_text,
                transform=self.daily_overview_ax.transAxes,
                ha="center",
                va="top",
                fontsize=11,
                style="italic",
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.3),
            )

            # Set y-axis limits with margin
            if daily_energy.max() > 0:
                self.daily_overview_ax.set_ylim(
                    0, daily_energy.max() * 1.4
                )  # Extra space for labels

            # Ensure last day shows data (fix for zero production issue)
            if len(daily_energy) > 0 and daily_energy.iloc[-1] == 0:
                logger.warning(f"Last day has zero production: {daily_dates[-1]}")

        except Exception as e:
            logger.error(f"Error creating daily overview chart: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            self.daily_overview_ax.text(
                0.5,
                0.5,
                f"Error creating chart:\n{str(e)}",
                horizontalalignment="center",
                verticalalignment="center",
                transform=self.daily_overview_ax.transAxes,
                fontsize=10,
                color="red",
            )

    def _previous_day(self):
        """Navigate to the previous day in the analysis period."""
        if self.current_day_index > 0:
            self.current_day_index -= 1
            self._refresh_day_display()

    def _next_day(self):
        """Navigate to the next day in the analysis period."""
        if self.current_day_index < 14:
            self.current_day_index += 1
            self._refresh_day_display()

    def _center_day(self):
        """Navigate to the center day of the analysis period."""
        self.current_day_index = 7
        self._refresh_day_display()

    def _refresh_day_display(self):
        """Refresh charts and displays for the currently selected day."""
        if self.current_results:
            logger.info(
                f"Refreshing day display for day index {self.current_day_index}"
            )
            logger.info(f"Current results keys: {list(self.current_results.keys())}")
            logger.info(
                f"Daily summary shape: {self.current_results['daily_summary'].shape}"
            )
            logger.info(
                f"Hourly data shape: {self.current_results['hourly_data'].shape}"
            )
            self._update_charts(self.current_results)
        else:
            logger.warning("No current results available for refresh")

    def _show_welcome_message(self):
        """Display welcome message with system status."""
        if not self.is_initialized:
            return

        try:
            data_summary = self.data_processor.get_data_summary()

            welcome_msg = (
                f"🎉 Welcome to FilantropiaSolar!\n\n"
                f"🔋 System Status:\n"
                f"• {data_summary['total_installations']} PV installations loaded\n"
                f"• {len(data_summary['locations'])} locations across Portugal\n"
                f"• {data_summary['total_records']:,} historical records available\n"
                f"• Machine learning models trained and ready\n\n"
                f"✨ Available Features:\n"
                f"📊 Detailed hourly energy production analysis\n"
                f"📈 Historical data exploration for existing periods\n"
                f"🔮 Future energy production simulation\n"
                f"🌤️ Weather correlation and impact analysis\n"
                f"⭐ Performance rankings and insights\n"
                f"📱 Interactive day-by-day navigation\n\n"
                f"📚 Data Source:\n"
                f'Sarmas et al. (2025) "Photovoltaic Power Production Dataset"\n'
                f"Mendeley Data, V3, doi: 10.17632/dbh93b6vp8.3\n\n"
                f"🚀 Ready to analyze your solar energy data!"
            )

            messagebox.showinfo("FilantropiaSolar Ready", welcome_msg)

        except Exception as e:
            logger.error(f"Error showing welcome message: {e}")

    def _on_main_close(self):
        """Handle main application window close event."""
        try:
            if messagebox.askyesno(
                "Confirm Exit", "Save current work and exit FilantropiaSolar?"
            ):
                # Save trained models
                if self.energy_predictor:
                    try:
                        self.energy_predictor.save_models()
                    except Exception as e:
                        logger.warning(f"Could not save models: {e}")

                self._cleanup_and_exit()
        except Exception as e:
            logger.error(f"Error during application close: {e}")
            self._cleanup_and_exit()

    def run(self):
        """Start and run the FilantropiaSolar application."""
        try:
            logger.info("Starting FilantropiaSolar Application")

            # Display data citation notice
            print("\n" + "=" * 70)
            print("🌞 FilantropiaSolar - Advanced Solar Energy Analysis Application")
            print("=" * 70)
            print("📚 DATA CITATION REQUIRED:")
            print(
                "   Sarmas, Elissaios; Matias, Nuno; Pereira, Catarina; Antunes, Ana Rita (2025),"
            )
            print(
                '   "Photovoltaic Power Production Dataset", Mendeley Data, V3, doi: 10.17632/dbh93b6vp8.3'
            )
            print("=" * 70)

            # Create and show loading GUI
            self.create_loading_gui()
            self._start_loading()

            # Start main event loop
            self.root.mainloop()

        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in application: {e}")
        finally:
            logger.info("FilantropiaSolar application shutdown")


def main():
    """Main entry point for FilantropiaSolar production application."""
    app = FilantropiaSolarApp()
    app.run()


if __name__ == "__main__":
    main()
