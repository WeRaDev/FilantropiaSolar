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
from typing import Any, Dict
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
        self.cache_manager = None  # Will be set after initialization
        self.current_analysis_mode = None  # Store current analysis mode

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

    def _create_cache_status_display(self, parent):
        """Create cache status display with management options."""
        try:
            if not self.cache_manager:
                ttk.Label(parent, text="⚠️ Caching disabled", foreground="orange").pack(anchor=tk.W)
                return
            
            status = self.cache_manager.get_cache_status()
            
            # Status information frame
            info_frame = ttk.Frame(parent)
            info_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Cache statistics
            ttk.Label(info_frame, text="📊 Cache Status:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
            
            status_text = f"""• Data Cache: {status.get('data_cache', {}).get('cached_items', 0)} items ({status.get('data_cache', {}).get('size_mb', 0):.1f} MB)
• Model Cache: {status.get('model_cache', {}).get('cached_models', 0)} models ({status.get('model_cache', {}).get('size_mb', 0):.1f} MB)
• Total Size: {status.get('total_size_mb', 0):.1f} MB"""
            
            ttk.Label(info_frame, text=status_text, font=("Arial", 9)).pack(anchor=tk.W, pady=(2, 0))
            
            # Cache management buttons
            buttons_frame = ttk.Frame(parent)
            buttons_frame.pack(fill=tk.X)
            
            ttk.Button(
                buttons_frame, 
                text="🔄 Refresh Status", 
                command=self._refresh_cache_status,
                width=15
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            ttk.Button(
                buttons_frame, 
                text="🧹 Clear Cache", 
                command=self._clear_cache_dialog,
                width=15
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            ttk.Button(
                buttons_frame, 
                text="🔍 Validate Cache", 
                command=self._validate_cache,
                width=15
            ).pack(side=tk.LEFT)
            
        except Exception as e:
            logger.error(f"Error creating cache status display: {e}")
            ttk.Label(parent, text=f"Error loading cache status: {e}", foreground="red").pack(anchor=tk.W)
    
    def _refresh_cache_status(self):
        """Refresh the cache status display."""
        try:
            # Find and update the cache frame
            for child in self.main_frame.winfo_children():
                if isinstance(child, ttk.Notebook):
                    for tab_id in child.tabs():
                        tab_frame = child.nametowidget(tab_id)
                        if "Configuration" in child.tab(tab_id, "text"):
                            # Find the cache frame and refresh it
                            self.input_status_var.set("Cache status refreshed")
                            self.root.after(2000, lambda: self.input_status_var.set("Ready to generate analysis"))
                            break
        except Exception as e:
            logger.error(f"Error refreshing cache status: {e}")
    
    def _clear_cache_dialog(self):
        """Show cache clearing dialog."""
        try:
            if not self.cache_manager:
                messagebox.showwarning("Cache Management", "Cache is not enabled.")
                return
                
            result = messagebox.askyesnocancel(
                "Clear Cache",
                "Choose cache clearing option:\n\n"
                "• Yes: Clear all cache (data + models)\n"
                "• No: Clear only data cache\n"
                "• Cancel: Keep cache unchanged"
            )
            
            if result is True:  # Clear all
                if self.cache_manager.clear_cache("all"):
                    messagebox.showinfo("Success", "All cache cleared successfully")
                    self.input_status_var.set("All cache cleared - next run will rebuild")
                else:
                    messagebox.showerror("Error", "Failed to clear cache")
                    
            elif result is False:  # Clear data only
                if self.cache_manager.clear_cache("data"):
                    messagebox.showinfo("Success", "Data cache cleared successfully")
                    self.input_status_var.set("Data cache cleared - models preserved")
                else:
                    messagebox.showerror("Error", "Failed to clear data cache")
                    
        except Exception as e:
            logger.error(f"Error in cache clear dialog: {e}")
            messagebox.showerror("Error", f"Cache operation failed: {e}")
    
    def _validate_cache(self):
        """Validate cache integrity."""
        try:
            if not self.cache_manager:
                messagebox.showwarning("Cache Management", "Cache is not enabled.")
                return
                
            self.input_status_var.set("Validating cache integrity...")
            self.root.update_idletasks()
            
            results = self.cache_manager.validate_cache()
            
            if results.get("issues"):
                issues_text = "\n".join(results["issues"][:5])  # Show first 5 issues
                if len(results["issues"]) > 5:
                    issues_text += f"\n... and {len(results['issues']) - 5} more issues"
                    
                messagebox.showwarning(
                    "Cache Validation",
                    f"Found {len(results['issues'])} issues:\n\n{issues_text}"
                )
            else:
                messagebox.showinfo(
                    "Cache Validation",
                    f"Cache validation successful!\n\n"
                    f"Valid entries: {results.get('valid_entries', 0)}\n"
                    f"No issues found."
                )
                
            self.input_status_var.set("Cache validation completed")
            self.root.after(3000, lambda: self.input_status_var.set("Ready to generate analysis"))
            
        except Exception as e:
            logger.error(f"Error validating cache: {e}")
            messagebox.showerror("Error", f"Cache validation failed: {e}")
            self.input_status_var.set("Cache validation failed")

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
            # Store cache manager reference
            self.cache_manager = getattr(self.data_processor, 'cache_manager', None)

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

        # Cache Status Display
        cache_frame = ttk.LabelFrame(container, text="System Status", padding="15")
        cache_frame.pack(fill=tk.X, pady=(15, 0))
        
        self._create_cache_status_display(cache_frame)
        
        # Status Display
        self.input_status_var = tk.StringVar(value="Ready to generate analysis")
        status_label = ttk.Label(
            container, textvariable=self.input_status_var, foreground="goldenrod"
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
                    foreground="goldenrod",
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
        """Create the results display interface with split layout."""
        container = ttk.Frame(parent, padding="10")
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        title_label = ttk.Label(
            container, text="Analysis Results", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Main split container
        main_split = ttk.PanedWindow(container, orient=tk.HORIZONTAL)
        main_split.pack(fill=tk.BOTH, expand=True)

        # Left panel: Overall info and daily values
        left_frame = ttk.LabelFrame(main_split, text="Overall Information & Daily Summary", padding="10")
        main_split.add(left_frame, weight=1)

        # Left panel text area with scrollbar
        left_text_frame = ttk.Frame(left_frame)
        left_text_frame.pack(fill=tk.BOTH, expand=True)

        self.results_overview_text = tk.Text(
            left_text_frame, wrap=tk.WORD, font=("Courier", 9), state="disabled"
        )

        left_scrollbar = ttk.Scrollbar(
            left_text_frame, orient="vertical", command=self.results_overview_text.yview
        )
        self.results_overview_text.configure(yscrollcommand=left_scrollbar.set)

        self.results_overview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right panel: Hourly values for entire range
        right_frame = ttk.LabelFrame(main_split, text="Hourly Breakdown (All Days)", padding="10")
        main_split.add(right_frame, weight=1)

        # Right panel text area with scrollbar
        right_text_frame = ttk.Frame(right_frame)
        right_text_frame.pack(fill=tk.BOTH, expand=True)

        self.results_hourly_text = tk.Text(
            right_text_frame, wrap=tk.WORD, font=("Courier", 8), state="disabled"
        )

        right_scrollbar = ttk.Scrollbar(
            right_text_frame, orient="vertical", command=self.results_hourly_text.yview
        )
        self.results_hourly_text.configure(yscrollcommand=right_scrollbar.set)

        self.results_hourly_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Initial content
        self._update_results_display(
            "No analysis generated yet.\n\nUse the Analysis Configuration tab to generate detailed analysis.", 
            "Hourly data will appear here after analysis is generated."
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
                text="Interactive Energy Production Analysis",
                font=("Arial", 16, "bold"),
            )
            title_label.pack(side=tk.LEFT)

            # Day navigation controls and help
            nav_frame = ttk.Frame(header_frame)
            nav_frame.pack(side=tk.RIGHT)

            # Help button (question mark)
            ttk.Button(
                nav_frame, text="?", command=self._show_charts_help, width=3
            ).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Button(
                nav_frame, text="Previous", command=self._previous_day, width=10
            ).pack(side=tk.LEFT, padx=(0, 3))
            ttk.Button(
                nav_frame, text="Center", command=self._center_day, width=8
            ).pack(side=tk.LEFT, padx=(0, 3))
            ttk.Button(nav_frame, text="Next", command=self._next_day, width=10).pack(
                side=tk.LEFT
            )

            # Day information display
            self.day_info_label = ttk.Label(
                container,
                text="Generate analysis to explore interactive charts",
                font=("Arial", 11, "bold"),
                foreground="white",
            )
            self.day_info_label.pack(pady=(0, 10))

            # Create matplotlib figure with adjusted layout for legends
            self.figure = Figure(figsize=(20, 10), dpi=100)  # Wider for legends, shorter for charts
            
            # Adjust layout to leave space for right-aligned legends
            self.figure.subplots_adjust(
                left=0.05,    # Charts aligned to left
                right=0.75,   # Leave space on right for legends
                top=0.95,     # Small top margin
                bottom=0.1,   # Bottom margin
                hspace=0.9    # Much more vertical spacing between charts
            )

            # Grid layout: 3 rows, 1 column for shorter charts
            gs = self.figure.add_gridspec(
                3,
                1,
                height_ratios=[0.8, 0.8, 0.8],  # Shorter charts
                hspace=0.7,  # More spacing between charts
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
                text=f"Charts Feature Unavailable\n\n"
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
                "Chart 1: Hourly Energy Production (Ranked Bars)",
                "Chart 2: Hourly Weather Conditions (Temperature, Humidity, Cloud Cover, Wind)",
                "Chart 3: Daily Energy & Weather Overview (15-Day Range with Navigation)",
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

            # Store results and analysis mode for consistent navigation
            self.current_results = results
            self.current_analysis_mode = mode  # Store the mode for day navigation
            self._display_results(results, mode)
            self._update_charts(results, mode)

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
        """Display comprehensive analysis results in split layout."""
        try:
            # ===== LEFT PANEL: OVERVIEW =====
            overview_text = "FILANTROPIA SOLAR - ANALYSIS RESULTS\n"
            overview_text += "=" * 60 + "\n\n"

            # Analysis type and metadata
            analysis_type = (
                "HISTORICAL ANALYSIS" if mode == "historical" else "FUTURE SIMULATION"
            )
            overview_text += f"Analysis Type: {analysis_type}\n\n"

            # Installation details
            inst_info = results["installation_info"]
            overview_text += f"Installation: {inst_info['location']} (Serial: {inst_info['serial_number']})\n"
            overview_text += f"Capacity: {inst_info['capacity_kwp']} kWp\n\n"

            # Analysis period
            period = results["prediction_period"]
            overview_text += (
                f"Analysis Period: {period['start'].date()} to {period['end'].date()}\n"
            )
            overview_text += f"Center Date: {period['center_date'].date()}\n"
            overview_text += f"Total Hours Analyzed: {period['total_hours']}\n\n"

            # Key performance metrics
            stats = results["period_statistics"]
            overview_text += "KEY PERFORMANCE METRICS (15-day period)\n"
            overview_text += "-" * 50 + "\n"
            overview_text += f"Total Energy Production: {stats['total_energy_kwh']:.2f} kWh\n"
            overview_text += (
                f"Average Daily Energy: {stats['total_energy_kwh'] / 15:.2f} kWh/day\n"
            )
            overview_text += f"Average Specific Energy: {stats['average_specific_energy']:.2f} kWh/kWp\n"
            overview_text += f"Peak Hour Energy: {stats['peak_hour_energy']:.2f} kWh/kWp\n"
            overview_text += (
                f"Average Temperature: {stats.get('average_temperature', 0):.1f}°C\n"
            )
            overview_text += (
                f"Average Cloud Cover: {stats.get('average_cloud_cover', 0):.1f}%\n\n"
            )

            # ===== DAILY SUMMARY (LEFT PANEL) =====
            # Determine energy column based on mode and available data
            hourly_text = ""
            if "daily_summary" in results and "hourly_data" in results:
                daily = results["daily_summary"]
                hourly_data = results["hourly_data"]
                
                if mode == "historical" and "Produced Energy (kWh)" in hourly_data.columns:
                    energy_column = "Produced Energy (kWh)"
                    data_type_label = "HISTORICAL" 
                    logger.info("Using historical original energy data for display")
                else:
                    energy_column = "predicted_total_energy"
                    data_type_label = "PREDICTED"
                    logger.info("Using predicted energy data for display")
                
                overview_text += f"\nDAILY SUMMARY ({data_type_label} DATA)\n"
                overview_text += "=" * 50 + "\n"
                overview_text += f"{'Day':<4} {'Date':<12} {'Energy(kWh)':<12} {'Peak':<8} {'Temp':<6} {'Cloud':<6} {'Rating':<12}\n"
                overview_text += "-" * 50 + "\n"

                # ===== HOURLY DATA (RIGHT PANEL) =====
                hourly_text = f"HOURLY BREAKDOWN - ALL 15 DAYS ({data_type_label} DATA)\n"
                hourly_text += "=" * 70 + "\n\n"

                for i, (date, row) in enumerate(daily.iterrows()):
                    day_num = i + 1
                    # Use appropriate energy column based on mode
                    if mode == "historical" and energy_column in hourly_data.columns:
                        # Calculate daily total from historical hourly data
                        try:
                            day_hourly = hourly_data[hourly_data.index.date == (date.date() if hasattr(date, 'date') else date)]
                            energy = day_hourly[energy_column].sum() if not day_hourly.empty else 0
                        except Exception:
                            energy = row.get("predicted_total_energy", 0)  # Fallback
                    else:
                        energy = row.get("predicted_total_energy", 0)
                    
                    ranking = row.get("ranking", 3)
                    temp = row.get("temperature_2m", 0)
                    cloud = row.get("cloud_cover", 0)

                    # Get peak hourly energy for this day using appropriate column
                    try:
                        day_hourly = hourly_data[hourly_data.index.date == (date.date() if hasattr(date, 'date') else date)]
                        if mode == "historical" and energy_column in day_hourly.columns:
                            peak_energy = day_hourly[energy_column].max() if not day_hourly.empty else 0
                        else:
                            peak_energy = day_hourly["predicted_total_energy"].max() if not day_hourly.empty else 0
                    except Exception:
                        peak_energy = 0

                    # Convert ranking to descriptive rating
                    rating_map = {
                        1: "(1) Poor",
                        2: "(2) Below", 
                        3: "(3) Avg",
                        4: "(4) Good",
                        5: "(5) Excell",
                    }
                    rating = rating_map.get(ranking, "Unknown")

                    # Add to daily summary (left panel)
                    marker = " <-" if i == self.current_day_index else ""
                    overview_text += f"{day_num:<4} {str(date)[:10]:<12} {energy:<12.2f} {peak_energy:<8.2f} {temp:<6.1f} {cloud:<6.0f} {rating:<12}{marker}\n"
                    
                    # Add hourly breakdown to right panel
                    hourly_text += f"DAY {day_num}: {date.strftime('%Y-%m-%d')} ({date.strftime('%A')})\n"
                    hourly_text += "-" * 60 + "\n"
                    hourly_text += f"{'Hour':<6} {'Energy':<10} {'Temp°C':<8} {'Cloud%':<8} {'Wind':<8} {'Solar':<10} {'Humid%':<8}\n"
                    hourly_text += "-" * 60 + "\n"
                    
                    try:
                        day_hourly = hourly_data[hourly_data.index.date == (date.date() if hasattr(date, 'date') else date)]
                        # Show ALL hours with data, not just productive ones
                        if not day_hourly.empty:
                            for _, hour_row in day_hourly.iterrows():
                                hour = hour_row.name.hour
                                h_energy = hour_row.get(energy_column, 0)
                                h_temp = hour_row.get("temperature_2m", 0)
                                h_cloud = hour_row.get("cloud_cover", 0) 
                                h_wind = hour_row.get("wind_speed_10m", 0)
                                h_solar = hour_row.get("shortwave_radiation", 0)
                                h_humidity = hour_row.get("relative_humidity_2m", 0)
                                
                                hourly_text += f"{hour:02d}:00 {h_energy:<10.2f} {h_temp:<8.1f} {h_cloud:<8.0f} {h_wind:<8.1f} {h_solar:<10.0f} {h_humidity:<8.0f}\n"
                        else:
                            hourly_text += "No hourly data available for this day\n"
                    except Exception as e:
                        hourly_text += f"Error loading hourly data: {str(e)}\n"
                    
                    hourly_text += "\n"

            # Data source and model information (left panel)
            source = results["data_source"]
            overview_text += "\nDATA SOURCE & MODEL INFO\n"
            overview_text += "-" * 30 + "\n"
            overview_text += (
                f"PV Data: Sarmas et al. (2025)\nPhotovoltaic Power Production Dataset\n"
            )
            overview_text += f"DOI: 10.17632/dbh93b6vp8.3\n"
            overview_text += f"Weather: {'Simulated' if source['used_simulation'] else 'Historical'}\n"
            overview_text += f"ML Model: {source['model_used'].replace('_', ' ').title()}\n"

            if (
                "model_performance" in source
                and source["model_used"] in source["model_performance"]
            ):
                perf = source["model_performance"][source["model_used"]]
                overview_text += f"Model R²: {perf.get('r2', 0):.3f}\n"
                overview_text += f"Model MAE: {perf.get('mae', 0):.3f} kWh/kWp\n"

            overview_text += f"\nEXPLORE: Use Interactive Charts tab for detailed analysis!"

            self._update_results_display(overview_text, hourly_text)

        except Exception as e:
            logger.error(f"Error displaying results: {e}")
            self._update_results_display(f"Error displaying results: {str(e)}", "Error loading hourly data")

    def _update_results_display(self, overview_text: str, hourly_text: str = ""):
        """Update the results text areas with new content."""
        # Update left panel (overview)
        self.results_overview_text.config(state="normal")
        self.results_overview_text.delete(1.0, tk.END)
        self.results_overview_text.insert(tk.END, overview_text)
        self.results_overview_text.config(state="disabled")
        
        # Update right panel (hourly) if provided
        if hasattr(self, 'results_hourly_text'):
            self.results_hourly_text.config(state="normal")
            self.results_hourly_text.delete(1.0, tk.END)
            self.results_hourly_text.insert(tk.END, hourly_text)
            self.results_hourly_text.config(state="disabled")

    def _update_charts(self, results: Dict[str, Any], mode: str = "simulation"):
        """Update all charts with analysis results using weather-based ranking system."""
        if not hasattr(self, "hourly_energy_ax"):
            return

        try:
            # Determine correct energy column based on mode and available data
            hourly_data_preview = results.get("hourly_data", pd.DataFrame())
            data_source = results.get('data_source', {})
            
            # Priority: 
            # 1. If explicitly in simulation mode, use predicted data
            # 2. If historical mode and historical data available, use historical data
            # 3. Otherwise, use best available data
            if mode == "simulation" or data_source.get('used_simulation', False):
                if "predicted_total_energy" in hourly_data_preview.columns:
                    energy_column_for_charts = "predicted_total_energy"
                    logger.info("Using predicted energy data for charts (simulation mode)")
                elif "Produced Energy (kWh)" in hourly_data_preview.columns:
                    energy_column_for_charts = "Produced Energy (kWh)"
                    logger.info("Using historical energy data for charts (predicted not available)")
                else:
                    energy_column_for_charts = "predicted_total_energy"  # fallback
                    logger.warning("No energy columns found, using predicted_total_energy as fallback")
            elif mode == "historical" and "Produced Energy (kWh)" in hourly_data_preview.columns:
                energy_column_for_charts = "Produced Energy (kWh)"
                logger.info("Using historical energy data for charts (historical mode)")
            else:
                # Fallback: use whatever is available
                if "predicted_total_energy" in hourly_data_preview.columns:
                    energy_column_for_charts = "predicted_total_energy"
                    logger.info("Using predicted energy data for charts (fallback)")
                else:
                    energy_column_for_charts = "Produced Energy (kWh)"
                    logger.info("Using historical energy data for charts (fallback)")
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

            # ===== CALCULATE DYNAMIC PRODUCTIVE HOURS RANGE =====
            # Determine the productive hours range across all 15 days using the correct energy column
            productive_hour_min, productive_hour_max = self._calculate_dynamic_productive_hours(hourly_data, energy_column_for_charts)
            logger.info(f"Dynamic productive hours range: {productive_hour_min}:00 - {productive_hour_max}:00")

            # ===== CREATE THE 3 CHARTS =====
            logger.info(
                f"Creating charts for day {self.current_day_index + 1}: {target_date}"
            )

            # Chart 1: Hourly Energy Production (Ranked Bars)
            self._create_hourly_energy_chart(current_day_hourly, target_date, productive_hour_min, productive_hour_max, energy_column_for_charts)

            # Chart 2: Hourly Weather Conditions
            self._create_hourly_weather_chart(current_day_hourly, target_date, productive_hour_min, productive_hour_max)

            # Chart 3: Daily Overview with Moving Red Frame
            daily_dates = [
                d.date() if hasattr(d, "date") else d for d in daily_summary.index
            ]
            self._create_daily_overview_chart(daily_summary, hourly_data, daily_dates)

            # Refresh canvas
            self.canvas.draw()

            # Update day information display using correct energy column
            current_day_energy = current_day_hourly.get(
                energy_column_for_charts, pd.Series([0])
            )
            if not current_day_energy.empty:
                avg_energy = current_day_energy.mean()
                total_energy = current_day_energy.sum()
                peak_energy = current_day_energy.max()

                data_type = "Historical" if energy_column_for_charts == "Produced Energy (kWh)" else "Predicted"
                info_text = f"📅 Day {self.current_day_index + 1} of 15: {target_date.strftime('%Y-%m-%d')} | {data_type} - Total: {total_energy:.2f} kWh | Peak: {peak_energy:.2f} kWh | Avg: {avg_energy:.2f} kWh"
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

            self.canvas.draw()

    def _calculate_dynamic_productive_hours(self, hourly_data, energy_col=None):
        """Calculate the dynamic productive hours range based on energy production across all days."""
        try:
            # Use provided energy column or determine automatically
            if energy_col is None:
                energy_col = (
                    "predicted_total_energy"
                    if "predicted_total_energy" in hourly_data.columns
                    else "Produced Energy (kWh)"
                )
            
            logger.info(f"Calculating productive hours using energy column: {energy_col}")
            
            if energy_col not in hourly_data.columns:
                # Fallback to hardcoded range if no energy data
                logger.warning("No energy column found, using default 6-20 hour range")
                return 6, 20
            
            # Get energy data and convert to numeric
            energy_data = pd.to_numeric(hourly_data[energy_col], errors="coerce").fillna(0)
            
            # Define a minimal threshold (e.g., 0.1 kWh) for productive hours
            min_threshold = 0.1
            
            # Find hours where energy production is above threshold
            productive_mask = energy_data > min_threshold
            productive_hourly_data = hourly_data[productive_mask]
            
            if productive_hourly_data.empty:
                # Fallback to hardcoded range if no productive hours found
                logger.warning("No productive hours found above threshold, using default 6-20 hour range")
                return 6, 20
            
            # Get the hour range where production occurs
            productive_hours = productive_hourly_data.index.hour
            hour_min = productive_hours.min()
            hour_max = productive_hours.max()
            
            # Ensure we have a reasonable range (at least 1 hour difference)
            if hour_max - hour_min < 1:
                logger.warning("Very narrow productive hour range detected, using default 6-20 hour range")
                return 6, 20
            
            # Add some padding to ensure we capture edge hours
            hour_min = max(0, hour_min - 1)  # Don't go below 0
            hour_max = min(23, hour_max + 1)  # Don't go above 23
            
            logger.info(f"Calculated dynamic productive hours: {hour_min} to {hour_max}")
            return hour_min, hour_max
            
        except Exception as e:
            logger.error(f"Error calculating dynamic productive hours: {e}")
            # Fallback to hardcoded range on error
            return 6, 20

    def _create_hourly_energy_chart(self, current_day_hourly, target_date, productive_hour_min=6, productive_hour_max=20, energy_column="predicted_total_energy"):
        """Chart 1: Hourly Energy Production with Ranked Bars (Dynamic Productive Hours)."""
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

            # Filter to dynamic productive hours range
            productive_hours = current_day_hourly[
                (current_day_hourly.index.hour >= productive_hour_min) & 
                (current_day_hourly.index.hour <= productive_hour_max)
            ]
            
            if productive_hours.empty:
                self.hourly_energy_ax.text(
                    0.5,
                    0.5,
                    "No productive hours\ndata available",
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=self.hourly_energy_ax.transAxes,
                    fontsize=12,
                    alpha=0.6,
                )
                return

            # Use the specified energy column 
            energy_data_type = "HISTORICAL" if energy_column == "Produced Energy (kWh)" else "PREDICTED"
            logger.info(f"Using {energy_data_type} data ({energy_column}) for hourly energy chart")
            
            # Ensure the column exists in the data
            if energy_column not in productive_hours.columns:
                energy_column = "predicted_total_energy" if "predicted_total_energy" in productive_hours.columns else "Produced Energy (kWh)"
                logger.warning(f"Specified energy column not found, falling back to {energy_column}")
                
            hourly_energy = productive_hours.get(
                energy_column, pd.Series([0] * len(productive_hours))
            )
            hourly_energy = pd.to_numeric(hourly_energy, errors="coerce").fillna(0)

            hours = productive_hours.index.hour

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
                    
                    # Show energy value INSIDE the bar (middle of bar height)
                    self.hourly_energy_ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        height / 2.0,  # Middle of bar
                        f"{energy:.2f}",
                        ha="center",
                        va="center",
                        fontsize=8,
                        fontweight="bold",
                        color="black",  # Black text for visibility inside colored bars
                    )
                    
                    # Show ranking ON TOP of bars
                    ranking_text = f"({ranking}/5)"
                    self.hourly_energy_ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        height + height * 0.02,  # Above the bar
                        ranking_text,
                        ha="center",
                        va="bottom",
                        fontsize=8,
                        fontweight="bold",
                        color="black",
                    )

            # Chart formatting with dynamic hour range and data type indication
            hour_range_str = f"{productive_hour_min}:00-{productive_hour_max}:00"
            title_suffix = f"({energy_data_type} DATA)"
            self.hourly_energy_ax.set_title(
                f"Chart 1: {title_suffix} Hourly Energy Production ({hour_range_str}) - {target_date.strftime('%Y-%m-%d')}",
                fontsize=11,  # Reduced font size
                fontweight="bold",
                pad=15,
            )
            self.hourly_energy_ax.set_xlabel(f"Hour of Day (Productive Hours {hour_range_str})", fontsize=12)
            self.hourly_energy_ax.set_ylabel("Energy Production (kWh)", fontsize=12)
            self.hourly_energy_ax.grid(True, alpha=0.3)

            # Set x-axis limits for dynamic productive hours with padding
            self.hourly_energy_ax.set_xlim(productive_hour_min - 0.5, productive_hour_max + 0.5)
            # Set x-axis ticks dynamically
            tick_range = productive_hour_max - productive_hour_min + 1
            tick_step = max(1, tick_range // 8)  # Aim for ~8 ticks max
            self.hourly_energy_ax.set_xticks(range(productive_hour_min, productive_hour_max + 1, tick_step))

            # Add top margin for labels
            if hourly_energy.max() > 0:
                self.hourly_energy_ax.set_ylim(0, hourly_energy.max() * 1.2)

            # Create performance ranking legend
            from matplotlib.patches import Patch
            legend_elements = [
                Patch(facecolor='#FFD700', label='Excellent (5)'),
                Patch(facecolor='#32CD32', label='Good (4)'),
                Patch(facecolor='#FFA500', label='Average (3)'),
                Patch(facecolor='#FF8C00', label='Below Avg (2)'),
                Patch(facecolor='#DC143C', label='Poor (1)')
            ]
            
            # Add legend to the right side
            self.hourly_energy_ax.legend(
                handles=legend_elements,
                loc="center left",
                fontsize=8,
                ncol=1,
                frameon=True,
                fancybox=False,
                shadow=False,
                framealpha=0.9,
                bbox_to_anchor=(1.08, 0.5),  # Moved further right
                handlelength=0.8,
                handletextpad=0.3,
                borderaxespad=0.2
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

    def _create_hourly_weather_chart(self, current_day_hourly, target_date, productive_hour_min=6, productive_hour_max=20):
        """Chart 2: Hourly Weather Conditions (Temperature, Humidity, Cloud Cover, Wind) - Dynamic Productive Hours."""
        try:
            # Clear the main axes content and properly handle secondary axis
            self.hourly_weather_ax.clear()
            
            # Remove existing secondary axis if it exists
            if hasattr(self, '_weather_ax2') and self._weather_ax2 is not None:
                self._weather_ax2.remove()
                self._weather_ax2 = None

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

            # Filter to dynamic productive hours range
            productive_hours = current_day_hourly[
                (current_day_hourly.index.hour >= productive_hour_min) & 
                (current_day_hourly.index.hour <= productive_hour_max)
            ]
            
            if productive_hours.empty:
                self.hourly_weather_ax.text(
                    0.5,
                    0.5,
                    "No productive hours\nweather data available",
                    horizontalalignment="center",
                    verticalalignment="center",
                    transform=self.hourly_weather_ax.transAxes,
                    fontsize=12,
                    alpha=0.6,
                )
                return

            hours = productive_hours.index.hour

            # Check available weather variables
            weather_vars = [
                "temperature_2m",
                "relative_humidity_2m",
                "cloud_cover",
                "wind_speed_10m",
                "shortwave_radiation",
            ]
            available_vars = [
                var for var in weather_vars if var in productive_hours.columns
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

            # Create new secondary y-axis and store reference
            self._weather_ax2 = self.hourly_weather_ax.twinx()
            ax2 = self._weather_ax2

            # Plot Temperature (Line, left y-axis)
            if "temperature_2m" in available_vars:
                temp_data = pd.to_numeric(
                    productive_hours["temperature_2m"], errors="coerce"
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
                    productive_hours["relative_humidity_2m"], errors="coerce"
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
                    productive_hours["cloud_cover"], errors="coerce"
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
                    productive_hours["wind_speed_10m"], errors="coerce"
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

            # Plot Solar Radiation (Line, right y-axis)
            if "shortwave_radiation" in available_vars:
                radiation_data = pd.to_numeric(
                    productive_hours["shortwave_radiation"], errors="coerce"
                ).fillna(200)
                ax2.plot(
                    hours,
                    radiation_data / 10,  # Scale down for better visualization
                    "md-",
                    linewidth=2,
                    markersize=4,
                    label="Solar Radiation (W/m²/10)",
                    alpha=0.7,
                    color="orange",
                )

            # Formatting with dynamic hour range
            hour_range_str = f"{productive_hour_min}:00-{productive_hour_max}:00"
            self.hourly_weather_ax.set_title(
                f"Chart 2: Hourly Weather Conditions ({hour_range_str}) - {target_date.strftime('%Y-%m-%d')}",
                fontsize=11,  # Reduced font size
                fontweight="bold",
                pad=15,
            )
            self.hourly_weather_ax.set_xlabel(f"Hour of Day (Productive Hours {hour_range_str})", fontsize=12)

            # Right y-axis formatting
            ax2.set_ylabel(
                "Humidity (%) / Cloud Cover (%) / Wind (m/s) / Solar (W/m²/10)",
                color="blue",
                fontsize=11,  # Slightly smaller to fit longer text
            )
            ax2.tick_params(axis="y", labelcolor="blue")
            ax2.set_ylim(0, 100)  # 0-100% scale for humidity and cloud cover

            # Add compact legend to avoid overlap
            lines1, labels1 = self.hourly_weather_ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            
            # Only show legend if we have data to display (moved outside)
            if lines1 or lines2:
                self.hourly_weather_ax.legend(
                    lines1 + lines2, 
                    labels1 + labels2, 
                    loc="center left", 
                    fontsize=8,  # Smaller font
                    ncol=1,  # Single column outside chart
                    frameon=True,
                    fancybox=False,  # Simpler frame
                    shadow=False,  # No shadow
                    framealpha=0.9,
                    bbox_to_anchor=(1.08, 0.5),  # Moved further right
                    handlelength=0.8,
                    handletextpad=0.3,
                    borderaxespad=0.2
                )

            # Grid and axis limits for dynamic productive hours with padding
            self.hourly_weather_ax.grid(True, alpha=0.3)
            self.hourly_weather_ax.set_xlim(productive_hour_min - 0.5, productive_hour_max + 0.5)
            # Set x-axis ticks dynamically
            tick_range = productive_hour_max - productive_hour_min + 1
            tick_step = max(1, tick_range // 8)  # Aim for ~8 ticks max
            self.hourly_weather_ax.set_xticks(range(productive_hour_min, productive_hour_max + 1, tick_step))

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
            # Clear the main axes content and properly handle secondary axis
            self.daily_overview_ax.clear()
            
            # Remove existing secondary axis if it exists
            if hasattr(self, '_daily_ax2') and self._daily_ax2 is not None:
                self._daily_ax2.remove()
                self._daily_ax2 = None

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
                    f"VIEWING DAY {self.current_day_index + 1}",
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

            # Create new secondary y-axis and store reference
            self._daily_ax2 = self.daily_overview_ax.twinx()
            ax2 = self._daily_ax2

            # Plot daily average humidity with bright, visible color
            ax2.plot(
                x_positions,
                daily_humidity,
                color="darkgreen",
                marker="o",
                linewidth=2,
                markersize=6,
                label="Avg Humidity (%)",
                alpha=0.9,
                markerfacecolor="green",
                markeredgecolor="darkgreen",
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
                f"Chart 3: Daily Energy & Weather Overview (15-Day Analysis Period)",
                fontsize=11,  # Reduced font size
                fontweight="bold",
                pad=15,
            )
            self.daily_overview_ax.set_xlabel("Day in Analysis Period", fontsize=12)
            self.daily_overview_ax.set_ylabel(
                "Daily Energy Production (kWh)", color="blue", fontsize=12
            )
            ax2.set_ylabel(
                "Humidity (%) / Cloud Cover (%)", color="darkgreen", fontsize=12
            )

            # Set x-axis labels
            date_labels = [
                f"Day {i + 1}\n{d.strftime('%m/%d')}" for i, d in enumerate(daily_dates)
            ]
            self.daily_overview_ax.set_xticks(x_positions)
            self.daily_overview_ax.set_xticklabels(date_labels, rotation=0, ha="center")

            # Axis colors
            self.daily_overview_ax.tick_params(axis="y", labelcolor="blue")
            ax2.tick_params(axis="y", labelcolor="darkgreen")

            # Add compact legend with better positioning
            lines1, labels1 = self.daily_overview_ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            
            # Only show legend if we have data (moved outside)
            if lines1 or lines2:
                self.daily_overview_ax.legend(
                    lines1 + lines2, 
                    labels1 + labels2, 
                    loc="center left", 
                    fontsize=8,  # Smaller font
                    ncol=1,  # Single column outside chart
                    frameon=True,
                    fancybox=False,  # Simpler frame
                    shadow=False,  # No shadow
                    framealpha=0.9,
                    bbox_to_anchor=(1.08, 0.5),  # Moved further right
                    handlelength=0.8,
                    handletextpad=0.3,
                    borderaxespad=0.2
                )

            self.daily_overview_ax.grid(True, alpha=0.3)

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
            
            # Determine mode based on stored analysis mode, then data source information
            if self.current_analysis_mode:
                mode = self.current_analysis_mode
                logger.info(f"Using stored analysis mode for chart refresh: {mode}")
            else:
                data_source = self.current_results.get('data_source', {})
                if data_source.get('used_simulation', False):
                    mode = "simulation" 
                    logger.info("Using simulation mode for chart refresh (data source indicates simulation)")
                elif "Produced Energy (kWh)" in self.current_results.get('hourly_data', pd.DataFrame()).columns:
                    mode = "historical"
                    logger.info("Using historical mode for chart refresh (historical data detected)")
                else:
                    mode = "simulation"
                    logger.info("Defaulting to simulation mode for chart refresh")
                
            self._update_charts(self.current_results, mode)
        else:
            logger.warning("No current results available for refresh")

    def _show_charts_help(self):
        """Display comprehensive help for Interactive Charts tab."""
        help_text = (
            "INTERACTIVE CHARTS - USER GUIDE\n"
            "===================================\n\n"
            "This tab displays three interactive charts for detailed solar energy analysis:\n\n"
            
            "CHART 1: HOURLY ENERGY PRODUCTION\n"
            "• Shows energy production for each hour of the selected day\n"
            "• Energy values are displayed INSIDE the bars (white text)\n"
            "• Performance rankings (1-5) are shown ABOVE the bars\n"
            "• Bar colors represent performance: Red=Poor, Orange=Below Avg, Yellow=Average, Green=Good, Gold=Excellent\n"
            "• Shows productive hours of the range\n\n"
            
            "CHART 2: HOURLY WEATHER CONDITIONS\n"
            "• Temperature (red line with circles) - Left axis\n"
            "• Humidity (blue line with triangles) - Right axis\n"
            "• Cloud Cover (gray bars) - Right axis\n"
            "• Wind Speed (green line with stars) - Right axis\n"
            "• Shows weather conditions for the same productive hours\n\n"
            
            "CHART 3: DAILY OVERVIEW (15-DAY PERIOD)\n"
            "• Energy bars for all 15 days in the analysis period\n"
            "• Temperature and Cloud Cover trend lines\n"
            "• RED FRAME highlights the currently selected day\n"
            "• 'VIEWING DAY X' label shows which day is displayed in hourly charts above\n\n"
            
            "NAVIGATION:\n"
            "• Previous/Next: Navigate between days in the 15-day period\n"
            "• Center: Jump to the middle day (day 8) of the analysis period\n\n"
            
            "DATA TYPES:\n"
            "• HISTORICAL: Shows actual recorded solar production data\n"
            "• PREDICTED: Shows ML model predictions for future dates\n"
            "• Chart titles indicate which data type is being displayed\n\n"
            
            
            "TIP: Use this tab after generating analysis in the 'Analysis Configuration' tab."
        )
        
        messagebox.showinfo("Interactive Charts Help", help_text)

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
