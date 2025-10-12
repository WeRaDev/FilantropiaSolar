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
SRC_PATH = Path(__file__).parent / 'src'
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
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'filantropia_solar.log'),
                logging.StreamHandler(sys.stdout)
            ]
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
            self.loading_frame, 
            text="☀️ FilantropiaSolar", 
            font=('Arial', 20, 'bold')
        )
        title_label.pack(pady=(20, 5))
        
        subtitle_label = ttk.Label(
            self.loading_frame, 
            text="Advanced Solar Energy Analysis", 
            font=('Arial', 12, 'italic')
        )
        subtitle_label.pack(pady=(0, 20))
        
        # Progress tracking
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            self.loading_frame,
            variable=self.progress_var,
            maximum=100,
            length=350,
            mode='determinate'
        )
        progress_bar.pack(pady=10)
        
        self.status_var = tk.StringVar(value="Initializing application...")
        status_label = ttk.Label(
            self.loading_frame,
            textvariable=self.status_var,
            font=('Arial', 10)
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
            font=('Arial', 9),
            state='disabled',
            bg=self.root.cget('bg'),
            relief='flat'
        )
        features_text.pack()
        
        features_text.config(state='normal')
        features_text.insert(tk.END, 
            "🔋 Loading comprehensive solar energy system...\n\n"
            "✓ 9 PV installations across Portugal\n"
            "✓ 315,567+ historical energy records\n"
            "✓ Hourly production analysis with weather correlation\n"
            "✓ Historical data exploration & future simulation\n"
            "✓ Interactive charts with performance rankings\n"
            "✓ Advanced machine learning predictions\n"
        )
        features_text.config(state='disabled')
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_loading_close)
        
    def _on_loading_close(self):
        """Handle loading window close event."""
        if messagebox.askyesno("Confirm Exit", "Cancel loading and exit FilantropiaSolar?"):
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
            from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
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
            self.energy_predictor = EnhancedEnergyPredictor(
                self.data_processor, 
                self.weather_simulator
            )
            
            # Try to load existing models first (for weak devices)
            try:
                if self.energy_predictor.load_existing_models():
                    logger.info("Loaded existing ML models successfully")
                    self._update_progress(95, "Using existing ML models...")
                else:
                    logger.info("No existing models found, training new ones")
                    self._update_progress(80, "Training ML models (first-time setup)...")
                    # Models will be trained automatically during first prediction
            except Exception as e:
                logger.warning(f"Could not load existing models: {e}. Training new ones.")
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
                            'min_date': min_date,
                            'max_date': max_date,
                            'location': info.location,
                            'serial': info.serial_number
                        }
                except Exception as data_error:
                    logger.warning(f"Could not load dates for installation {inst_id}: {data_error}")
                    # Set reasonable default date range
                    self.available_dates[inst_id] = {
                        'min_date': datetime(2023, 1, 1).date(),
                        'max_date': datetime(2024, 12, 31).date(),
                        'location': info.location,
                        'serial': info.serial_number
                    }
            
            logger.info(f"Loaded available dates for {len(self.available_dates)} installations")
            
        except Exception as e:
            logger.error(f"Error loading available dates: {e}")
            
    def _start_loading(self):
        """Start the loading process in a separate thread."""
        self.loading_thread = threading.Thread(target=self._initialize_components_threaded)
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
            "Please check the logs directory for more details."
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
            messagebox.showerror("Interface Error", f"Failed to create main interface:\n{str(e)}")
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
            font=('Arial', 16, 'bold')
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
            command=self._on_mode_change
        ).pack(anchor=tk.W, pady=(0, 5))
        
        ttk.Radiobutton(
            mode_frame,
            text="🔮 Future Simulation (predict any date)",
            variable=self.mode_var,
            value="simulation",
            command=self._on_mode_change
        ).pack(anchor=tk.W)
        
        # Installation Selection
        install_frame = ttk.LabelFrame(container, text="Installation Selection", padding="15")
        install_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(install_frame, text="Choose Installation:").pack(anchor=tk.W)
        
        installations = self.data_processor.get_installation_list()
        installation_options = [
            f"{info.location}_{info.serial_number} ({info.installed_power_kwp} kWp)"
            for _, info in installations
        ]
        
        self.installation_var = tk.StringVar(value=installation_options[0] if installation_options else "")
        installation_combo = ttk.Combobox(
            install_frame, 
            textvariable=self.installation_var,
            values=installation_options,
            state="readonly",
            width=65
        )
        installation_combo.pack(fill=tk.X, pady=(5, 0))
        installation_combo.bind('<<ComboboxSelected>>', self._on_installation_change)
        
        # Date Selection (Dynamic based on mode)
        self.date_frame = ttk.LabelFrame(container, text="Date Selection", padding="15")
        self.date_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Historical date selection frame
        self.historical_date_frame = ttk.Frame(self.date_frame)
        self.historical_date_frame.pack(fill=tk.X)
        
        ttk.Label(self.historical_date_frame, text="Available Data Range:").pack(anchor=tk.W)
        self.date_range_label = ttk.Label(
            self.historical_date_frame, 
            text="Select an installation first", 
            foreground="gray"
        )
        self.date_range_label.pack(anchor=tk.W, pady=(2, 10))
        
        ttk.Label(self.historical_date_frame, text="Select Historical Date:").pack(anchor=tk.W)
        self.historical_date_var = tk.StringVar()
        self.historical_date_combo = ttk.Combobox(
            self.historical_date_frame,
            textvariable=self.historical_date_var,
            state="readonly",
            width=20
        )
        self.historical_date_combo.pack(anchor=tk.W, pady=(5, 0))
        
        # Simulation date selection frame
        self.simulation_date_frame = ttk.Frame(self.date_frame)
        
        ttk.Label(self.simulation_date_frame, text="Enter Date for Simulation:").pack(anchor=tk.W)
        self.simulation_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        simulation_date_entry = ttk.Entry(
            self.simulation_date_frame, 
            textvariable=self.simulation_date_var, 
            width=20
        )
        simulation_date_entry.pack(anchor=tk.W, pady=(5, 0))
        
        ttk.Label(
            self.simulation_date_frame, 
            text="Format: YYYY-MM-DD (e.g., 2025-06-15)", 
            font=('Arial', 9),
            foreground="gray"
        ).pack(anchor=tk.W, pady=(2, 0))
        
        # Analysis Options
        options_frame = ttk.LabelFrame(container, text="Options", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.simulation_var = tk.BooleanVar(value=True)
        self.simulation_checkbox = ttk.Checkbutton(
            options_frame,
            text="Enable weather simulation (recommended for complete analysis)",
            variable=self.simulation_var
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
            style="Accent.TButton"
        )
        predict_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # ML retrain button for advanced users
        retrain_button = ttk.Button(
            buttons_frame,
            text="🔧 Retrain ML Models",
            command=self._retrain_models,
            style="TButton"
        )
        retrain_button.pack(side=tk.LEFT)
        
        # Status Display
        self.input_status_var = tk.StringVar(value="Ready to generate analysis")
        status_label = ttk.Label(container, textvariable=self.input_status_var, foreground="blue")
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
            self.simulation_checkbox.config(state='normal')
            self.simulation_var.set(True)  # Enable simulation by default for historical analysis
        else:
            self.simulation_date_frame.pack(fill=tk.X)
            self.historical_date_frame.pack_forget()
            self.simulation_checkbox.config(state='normal')
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
                if installation_text.startswith(f"{info.location}_{info.serial_number}"):
                    installation_id = inst_id
                    break
                    
            if installation_id and installation_id in self.available_dates:
                date_info = self.available_dates[installation_id]
                min_date = date_info['min_date']
                max_date = date_info['max_date']
                
                # Update date range display
                days_available = (max_date - min_date).days
                self.date_range_label.config(
                    text=f"{min_date} to {max_date} ({days_available:,} days available)",
                    foreground="blue"
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
                    self.historical_date_var.set(date_list[-1])  # Default to most recent
                    
        except Exception as e:
            logger.error(f"Error updating installation dates: {e}")
            
    def _create_results_interface(self, parent):
        """Create the results display interface."""
        container = ttk.Frame(parent, padding="20")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Header
        title_label = ttk.Label(
            container,
            text="Analysis Results",
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 20))
        
        # Results text area with scrollbar
        text_frame = ttk.Frame(container)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=('Courier', 10),
            state='disabled'
        )
        
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Initial content
        self._update_results_display("No analysis generated yet.\n\nUse the Analysis Configuration tab to generate detailed analysis.")
        
    def _create_charts_interface(self, parent):
        """Create the interactive charts interface."""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
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
                font=('Arial', 16, 'bold')
            )
            title_label.pack(side=tk.LEFT)
            
            # Day navigation controls
            nav_frame = ttk.Frame(header_frame)
            nav_frame.pack(side=tk.RIGHT)
            
            ttk.Button(nav_frame, text="◄ Previous", 
                      command=self._previous_day, width=10).pack(side=tk.LEFT, padx=(0, 3))
            ttk.Button(nav_frame, text="Center", 
                      command=self._center_day, width=8).pack(side=tk.LEFT, padx=(0, 3))
            ttk.Button(nav_frame, text="Next ►", 
                      command=self._next_day, width=10).pack(side=tk.LEFT)
            
            # Day information display
            self.day_info_label = ttk.Label(
                container, 
                text="Generate analysis to explore interactive charts",
                font=('Arial', 11, 'bold'),
                foreground="navy"
            )
            self.day_info_label.pack(pady=(0, 10))
            
            # Create matplotlib figure with optimized layout and legend space
            self.figure = Figure(figsize=(16, 10), dpi=100, tight_layout=True)
            
            # Grid layout: 3 rows, 3 columns (added column for legend)
            gs = self.figure.add_gridspec(3, 3, height_ratios=[2, 1, 1], width_ratios=[4, 4, 1], 
                                         hspace=0.4, wspace=0.3)
            
            # Main hourly energy production chart (top row, spans first two columns)
            self.hourly_ax = self.figure.add_subplot(gs[0, :2])
            
            # Weather analysis charts (middle row)
            self.temp_ax = self.figure.add_subplot(gs[1, 0])
            self.cloud_ax = self.figure.add_subplot(gs[1, 1])
            
            # 15-day summary chart (bottom row, spans first two columns)
            self.daily_ax = self.figure.add_subplot(gs[2, :2])
            
            # Color legend (spans right column)
            self.legend_ax = self.figure.add_subplot(gs[:, 2])
            
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
                font=('Arial', 12),
                foreground="red",
                justify=tk.CENTER
            )
            error_label.pack(expand=True)
            
    def _clear_plots(self):
        """Initialize empty plots with placeholder content."""
        if hasattr(self, 'hourly_ax'):
            axes = [self.hourly_ax, self.temp_ax, self.cloud_ax, self.daily_ax]
            titles = [
                'Hourly Energy Production', 
                'Temperature Profile', 
                'Cloud Cover', 
                '15-Day Energy Summary'
            ]
            
            # Clear main charts
            for ax, title in zip(axes, titles):
                ax.clear()
                ax.text(0.5, 0.5, 'Generate analysis\nto view charts', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=12, alpha=0.6)
                ax.set_title(title, fontsize=12, fontweight='bold')
            
            # Initialize color legend
            self._create_color_legend()
            self.canvas.draw()
            
    def _create_color_legend(self):
        """Create color legend for performance rankings."""
        if hasattr(self, 'legend_ax'):
            self.legend_ax.clear()
            self.legend_ax.set_xlim(0, 10)  # Much wider to accommodate text
            self.legend_ax.set_ylim(0, 12)  # Much taller for proper spacing
            
            # Define ranking colors and labels
            rankings = [5, 4, 3, 2, 1]
            colors = ['#2ecc71', '#27ae60', '#f39c12', '#e67e22', '#e74c3c']
            labels = ['Excellent (5)', 'Good (4)', 'Average (3)', 'Below Avg (2)', 'Poor (1)']
            
            # Create properly sized color patches
            for i, (rank, color, label) in enumerate(zip(rankings, colors, labels)):
                y_pos = 10.5 - i * 2.0  # Much better vertical spacing
                
                # Draw much larger rectangle to properly contain all text
                from matplotlib.patches import Rectangle
                rect = Rectangle((0.5, y_pos-0.8), 9.0, 1.6, facecolor=color, alpha=0.9, 
                               edgecolor='black', linewidth=2)
                self.legend_ax.add_patch(rect)
                
                # Add label with proper positioning and size
                text_color = 'white' if color in ['#2ecc71', '#27ae60', '#e74c3c'] else 'black'
                self.legend_ax.text(5.0, y_pos, label, ha='center', va='center', 
                                   fontsize=14, fontweight='bold', color=text_color)
            
            # Add title with much better positioning
            self.legend_ax.text(5.0, 11.5, 'Performance\nRanking', ha='center', va='center',
                              fontsize=16, fontweight='bold', color='navy')
            
            # Remove axis elements for cleaner appearance
            self.legend_ax.set_xticks([])
            self.legend_ax.set_yticks([])
            self.legend_ax.spines['top'].set_visible(False)
            self.legend_ax.spines['right'].set_visible(False)
            self.legend_ax.spines['bottom'].set_visible(False)
            self.legend_ax.spines['left'].set_visible(False)
            self.legend_ax.set_facecolor('white')
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
                if installation_text.startswith(f"{info.location}_{info.serial_number}"):
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
                    messagebox.showerror("Input Error", "Please select or enter a date.")
                    return
                    
                center_date = datetime.strptime(date_str.strip(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Input Error", "Invalid date format. Please use YYYY-MM-DD.")
                return
                
            # Update status and begin analysis
            analysis_type = "historical analysis" if mode == "historical" else "future simulation"
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
            installation_info = results['installation_info']
            period_stats = results['period_statistics']
            
            success_msg = (
                f"Analysis completed successfully!\n\n"
                f"📍 Location: {installation_info['location']}\n"
                f"⚡ Capacity: {installation_info['capacity_kwp']} kWp\n"
                f"📊 Total Energy (15 days): {period_stats['total_energy_kwh']:.1f} kWh\n"
                f"📈 Average Daily: {period_stats['total_energy_kwh']/15:.1f} kWh/day\n\n"
                f"📊 Explore the Interactive Charts tab for detailed hourly analysis!"
            )
            
            messagebox.showinfo("Analysis Complete", success_msg)
            
        except Exception as e:
            logger.error(f"Error generating analysis: {e}")
            error_msg = str(e)
            
            # Provide specific guidance for weather data issues
            if "No weather data available" in error_msg and "simulation not enabled" in error_msg:
                self.input_status_var.set("Weather simulation needed for analysis.")
                messagebox.showerror(
                    "Weather Data Required", 
                    f"Analysis requires weather simulation for this period.\n\n"
                    f"Solution: Enable \"weather simulation\" option below and try again.\n\n"
                    f"This allows the system to generate weather data for periods where \n"
                    f"historical weather information may be incomplete."
                )
            else:
                self.input_status_var.set("Error during analysis. Check logs.")
                messagebox.showerror("Analysis Error", f"Failed to generate analysis:\n\n{error_msg}")
                
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
                "Continue?"
            ):
                return
                
            # Update status
            self.input_status_var.set("Retraining ML models... Please wait.")
            self.root.update_idletasks()
            
            # Disable buttons during retraining
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.config(state='disabled')
            
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
                    "The application will now use the updated models for all predictions."
                )
            else:
                messagebox.showerror("Error", "ML predictor not initialized. Please restart the application.")
                
        except Exception as e:
            logger.error(f"Error retraining models: {e}")
            self.input_status_var.set("Error during model retraining.")
            messagebox.showerror(
                "Retraining Error", 
                f"Failed to retrain ML models:\n\n{str(e)}\n\n"
                f"Please check the logs for details."
            )
        finally:
            # Re-enable buttons
            for widget in self.root.winfo_children():
                if isinstance(widget, ttk.Button):
                    widget.config(state='normal')
            
    def _display_results(self, results: Dict[str, Any], mode: str):
        """Display comprehensive analysis results."""
        try:
            # Build formatted results text
            text = "FILANTROPIA SOLAR - ANALYSIS RESULTS\n"
            text += "=" * 60 + "\n\n"
            
            # Analysis type and metadata
            analysis_type = "HISTORICAL ANALYSIS" if mode == "historical" else "FUTURE SIMULATION"
            text += f"Analysis Type: {analysis_type}\n\n"
            
            # Installation details
            inst_info = results['installation_info']
            text += f"Installation: {inst_info['location']} (Serial: {inst_info['serial_number']})\n"
            text += f"Capacity: {inst_info['capacity_kwp']} kWp\n\n"
            
            # Analysis period
            period = results['prediction_period']
            text += f"Analysis Period: {period['start'].date()} to {period['end'].date()}\n"
            text += f"Center Date: {period['center_date'].date()}\n"
            text += f"Total Hours Analyzed: {period['total_hours']}\n\n"
            
            # Key performance metrics
            stats = results['period_statistics']
            text += "KEY PERFORMANCE METRICS (15-day period)\n"
            text += "-" * 50 + "\n"
            text += f"Total Energy Production: {stats['total_energy_kwh']:.1f} kWh\n"
            text += f"Average Daily Energy: {stats['total_energy_kwh']/15:.1f} kWh/day\n"
            text += f"Average Specific Energy: {stats['average_specific_energy']:.2f} kWh/kWp\n"
            text += f"Peak Hour Energy: {stats['peak_hour_energy']:.2f} kWh/kWp\n"
            text += f"Average Temperature: {stats.get('average_temperature', 0):.1f}°C\n"
            text += f"Average Cloud Cover: {stats.get('average_cloud_cover', 0):.1f}%\n\n"
            
            # Daily performance breakdown
            if 'daily_summary' in results:
                daily = results['daily_summary']
                text += "DAILY PERFORMANCE BREAKDOWN\n"
                text += "-" * 50 + "\n"
                text += f"{'Date':<12} {'Energy(kWh)':<12} {'Rating':<15} {'Note':<10}\n"
                text += "-" * 50 + "\n"
                
                for i, (date, row) in enumerate(daily.iterrows()):
                    energy = row.get('predicted_total_energy', 0)
                    ranking = row.get('ranking', 3)
                    
                    # Convert ranking to descriptive rating
                    rating_map = {
                        1: '⭐ Poor', 
                        2: '⭐⭐ Below Avg', 
                        3: '⭐⭐⭐ Average', 
                        4: '⭐⭐⭐⭐ Good', 
                        5: '⭐⭐⭐⭐⭐ Excellent'
                    }
                    rating = rating_map.get(ranking, 'Unknown')
                    
                    # Highlight currently selected day
                    marker = " ← SELECTED" if i == self.current_day_index else ""
                    text += f"{str(date):<12} {energy:<12.1f} {rating:<15} {'Sunny' if ranking >= 4 else 'Cloudy':<10}{marker}\n"
            
            # Data source and model information
            source = results['data_source']
            text += "\nDATA SOURCE & MODEL INFORMATION\n"
            text += "-" * 50 + "\n"
            text += f"PV Data: Sarmas et al. (2025) Photovoltaic Power Production Dataset\n"
            text += f"DOI: 10.17632/dbh93b6vp8.3\n"
            text += f"Weather Data: {'🌦️ Simulated' if source['used_simulation'] else '📊 Historical'}\n"
            text += f"ML Model Used: {source['model_used'].replace('_', ' ').title()}\n"
            
            if 'model_performance' in source and source['model_used'] in source['model_performance']:
                perf = source['model_performance'][source['model_used']]
                text += f"Model Accuracy (R²): {perf.get('r2', 0):.3f}\n"
                text += f"Model Error (MAE): {perf.get('mae', 0):.3f} kWh/kWp\n"
                
            text += f"\n💡 EXPLORE: Use the Interactive Charts tab to dive deeper into hourly patterns and weather correlations!"
                
            self._update_results_display(text)
            
        except Exception as e:
            logger.error(f"Error displaying results: {e}")
            self._update_results_display(f"Error displaying results: {str(e)}")
            
    def _update_results_display(self, text: str):
        """Update the results text area with new content."""
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        self.results_text.config(state='disabled')
        
    def _update_charts(self, results: Dict[str, Any]):
        """Update all charts with analysis results."""
        if not hasattr(self, 'hourly_ax'):
            return
            
        try:
            # Clear existing plots
            for ax in [self.hourly_ax, self.temp_ax, self.cloud_ax, self.daily_ax]:
                ax.clear()
            
            # Extract data
            daily_summary = results['daily_summary']
            hourly_data = results['hourly_data']
            
            # Debug: Print available columns and data info
            logger.info(f"Chart update - Hourly data columns: {list(hourly_data.columns)}")
            logger.info(f"Chart update - Daily summary shape: {daily_summary.shape}")
            logger.info(f"Chart update - Hourly data shape: {hourly_data.shape}")
            
            # Get data for currently selected day
            current_date = daily_summary.index[self.current_day_index]
            # Handle both datetime and date objects
            if hasattr(current_date, 'date'):
                target_date = current_date.date()
            else:
                target_date = current_date
            
            # Filter hourly data for the current day, handling both date and datetime indices
            try:
                # Try filtering with .date attribute (for datetime index)
                current_day_hourly = hourly_data[hourly_data.index.date == target_date]
            except AttributeError:
                # If index is already date objects, filter directly
                current_day_hourly = hourly_data[hourly_data.index == target_date]
            
            # 1. HOURLY ENERGY PRODUCTION CHART
            if not current_day_hourly.empty:
                # Get total energy data for display (kWh)
                hourly_total_energy = current_day_hourly.get('predicted_total_energy', 
                                                           current_day_hourly.get('Produced Energy (kWh)', 
                                                           pd.Series([0]*len(current_day_hourly))))
                
                # Get specific energy for filtering and ranking (kWh/kWp)
                hourly_specific_energy = current_day_hourly.get('predicted_specific_energy', 
                                                              current_day_hourly.get('Specific Energy (kWh/kWp)', 
                                                              pd.Series([0]*len(current_day_hourly))))
                
                # Ensure both energy datasets are numeric
                hourly_total_energy = pd.to_numeric(hourly_total_energy, errors='coerce').fillna(0)
                hourly_specific_energy = pd.to_numeric(hourly_specific_energy, errors='coerce').fillna(0)
                logger.info(f"Total energy type: {hourly_total_energy.dtype}, sample values: {hourly_total_energy.head(3).tolist()}")
                logger.info(f"Specific energy type: {hourly_specific_energy.dtype}, sample values: {hourly_specific_energy.head(3).tolist()}")
                
                # Filter for daylight hours based on specific energy (hours with meaningful production > 0.01 kWh/kWp)
                daylight_mask = hourly_specific_energy > 0.01
                if daylight_mask.any():
                    daylight_data = current_day_hourly[daylight_mask]
                    daylight_hours = daylight_data.index.hour
                    # Use total energy for display
                    daylight_total_energy = hourly_total_energy[daylight_mask]
                    daylight_specific_energy = hourly_specific_energy[daylight_mask]
                    
                    # Create hourly ranking system for optimal energy usage planning
                    # Rank hours from 1 (worst) to 5 (best) based on specific energy
                    if len(daylight_specific_energy) > 0:
                        # Calculate percentiles for ranking
                        percentiles = [20, 40, 60, 80]
                        thresholds = [daylight_specific_energy.quantile(p/100) for p in percentiles]
                        
                        # Assign hourly rankings (1=worst, 5=best)
                        hourly_rankings = []
                        for energy in daylight_specific_energy:
                            if energy <= thresholds[0]:
                                hourly_rankings.append(1)  # Poor (bottom 20%)
                            elif energy <= thresholds[1]:
                                hourly_rankings.append(2)  # Below average (20-40%)
                            elif energy <= thresholds[2]:
                                hourly_rankings.append(3)  # Average (40-60%)
                            elif energy <= thresholds[3]:
                                hourly_rankings.append(4)  # Good (60-80%)
                            else:
                                hourly_rankings.append(5)  # Excellent (top 20%)
                    else:
                        hourly_rankings = [3] * len(daylight_specific_energy)
                    
                    # Color coding based on hourly performance ranking
                    color_map = {1: '#e74c3c', 2: '#e67e22', 3: '#f39c12', 4: '#27ae60', 5: '#2ecc71'}
                    bar_colors = [color_map.get(rank, '#3498db') for rank in hourly_rankings]
                    
                    # Plot total energy (kWh) with hourly ranking colors
                    bars = self.hourly_ax.bar(daylight_hours, daylight_total_energy, color=bar_colors, alpha=0.8, 
                                             edgecolor='navy', linewidth=0.5)
                    
                    # Highlight peak production hour (best time for energy usage)
                    if len(daylight_total_energy) > 0 and daylight_total_energy.max() > 0:
                        try:
                            peak_idx = daylight_total_energy.idxmax()
                            if hasattr(peak_idx, 'hour'):
                                peak_hour = peak_idx.hour
                            else:
                                peak_hour = peak_idx
                            
                            # Find the peak hour bar and add special highlighting
                            for i, bar in enumerate(bars):
                                bar_hour = int(round(bar.get_x()))
                                if bar_hour == peak_hour:
                                    # Add golden outline for peak hour
                                    bar.set_edgecolor('#d35400')
                                    bar.set_linewidth(3)
                                    
                                    # Add "PEAK" label
                                    bar_height = bar.get_height()
                                    self.hourly_ax.text(bar.get_x() + bar.get_width()/2., 
                                                       bar_height + bar_height*0.05,
                                                       'PEAK', ha='center', va='bottom', 
                                                       fontsize=8, fontweight='bold', color='#d35400')
                        except Exception as e:
                            logger.warning(f"Could not highlight peak hour: {e}")
                    
                    # Chart formatting - adjust x-axis to focus on daylight hours
                    # Calculate day's overall rating from hourly rankings
                    avg_hourly_rating = sum(hourly_rankings) / len(hourly_rankings) if hourly_rankings else 3
                    daily_rating_stars = "⭐" * int(round(avg_hourly_rating))
                    
                    self.hourly_ax.set_title(
                        f'Hourly Energy Production & Usage Optimization - {current_date.strftime("%Y-%m-%d")}', 
                        fontsize=13, fontweight='bold'
                    )
                    self.hourly_ax.set_xlabel('Hour of Day')
                    self.hourly_ax.set_ylabel('Total Energy (kWh)')
                    
                    # Add subtitle explaining the hourly ranking system for load planning
                    best_hours = [h for h, r in zip(daylight_hours, hourly_rankings) if r >= 4]
                    if best_hours:
                        best_hours_str = ', '.join([f'{h:02d}:00' for h in sorted(best_hours)])
                        subtitle_text = f'Best hours for appliances: {best_hours_str}'
                    else:
                        subtitle_text = 'Limited optimal hours for appliances'
                    
                    # Position subtitle below the title to avoid overlap with chart data
                    self.hourly_ax.text(0.5, 0.92, subtitle_text, transform=self.hourly_ax.transAxes, 
                                       ha='center', va='top', fontsize=9, style='italic', alpha=0.8, 
                                       bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.3))
                    
                    # Set x-axis limits to show only productive hours with some padding
                    min_hour = max(0, daylight_hours.min() - 1)
                    max_hour = min(23, daylight_hours.max() + 1)
                    self.hourly_ax.set_xlim(min_hour - 0.5, max_hour + 0.5)
                    
                    # Add top margin for value labels and stars
                    max_energy = daylight_total_energy.max()
                    self.hourly_ax.set_ylim(0, max_energy * 1.15)  # 15% top margin
                    
                    self.hourly_ax.grid(True, alpha=0.3)
                    self.hourly_ax.set_xticks(range(min_hour, max_hour + 1))
                else:
                    # No daylight production - show all hours for diagnostic purposes
                    hours = current_day_hourly.index.hour
                    bars = self.hourly_ax.bar(hours, hourly_total_energy, color='#95a5a6', alpha=0.5)
                    self.hourly_ax.set_title(
                        f'Energy Production - {current_date.strftime("%Y-%m-%d")} (No significant production detected)', 
                        fontsize=13, fontweight='bold'
                    )
                    self.hourly_ax.set_xlabel('Hour of Day')
                    self.hourly_ax.set_ylabel('Total Energy (kWh)')
                    self.hourly_ax.set_xlim(-0.5, 23.5)
                    self.hourly_ax.grid(True, alpha=0.3)
                    self.hourly_ax.set_xticks(range(0, 24, 2))
                
                # Add value labels with hourly ranking information
                for i, bar in enumerate(bars):
                    height = bar.get_height()
                    try:
                        # Ensure height is numeric
                        height_value = float(height) if height is not None else 0.0
                        # Show labels for values > 0.05 kWh (50 Wh) to avoid clutter
                        if height_value > 0.05 and i < len(hourly_rankings):
                            # Format energy value based on magnitude
                            if height_value < 1.0:
                                energy_text = f'{height_value:.2f}'
                            elif height_value < 10.0:
                                energy_text = f'{height_value:.1f}'
                            else:
                                energy_text = f'{height_value:.0f}'
                            
                            # Get ranking star representation
                            ranking = hourly_rankings[i]
                            ranking_stars = '⭐' * ranking
                            
                            # Show energy value
                            self.hourly_ax.text(bar.get_x() + bar.get_width()/2., height_value + height_value*0.02,
                                               energy_text, ha='center', va='bottom', fontsize=8, fontweight='bold')
                            
                            # Note: Numerical rankings removed - using color legend instead
                                                   
                    except (TypeError, ValueError, IndexError):
                        # Skip if height is not convertible to float or index issues
                        continue
            
            # 2. TEMPERATURE PROFILE CHART
            temp_columns = ['temperature_2m', 'Temperature', 'temp', 'air_temperature']
            temp_col = None
            for col in temp_columns:
                if col in current_day_hourly.columns:
                    temp_col = col
                    break
                    
            if not current_day_hourly.empty and temp_col:
                temp_data = current_day_hourly[temp_col]
                hours = current_day_hourly.index.hour
                
                # Filter to same hours as energy production for consistency
                if 'daylight_mask' in locals() and daylight_mask.any():
                    temp_daylight = temp_data[daylight_mask]
                    temp_hours = hours[daylight_mask]
                else:
                    temp_daylight = temp_data
                    temp_hours = hours
                
                if len(temp_daylight) > 0:
                    self.temp_ax.plot(temp_hours, temp_daylight, 'ro-', linewidth=2, markersize=4, alpha=0.8)
                    self.temp_ax.fill_between(temp_hours, temp_daylight, alpha=0.3, color='red')
                    
                    self.temp_ax.set_title(f'Temperature - {current_date.strftime("%m-%d")}', 
                                          fontsize=11, fontweight='bold')
                    self.temp_ax.set_xlabel('Hour')
                    self.temp_ax.set_ylabel('Temperature (°C)')
                    self.temp_ax.grid(True, alpha=0.3)
                    
                    # Match x-axis with energy production chart
                    if 'min_hour' in locals() and 'max_hour' in locals():
                        self.temp_ax.set_xlim(min_hour - 0.5, max_hour + 0.5)
                    else:
                        self.temp_ax.set_xlim(temp_hours.min() - 0.5, temp_hours.max() + 0.5)
            else:
                # No temperature data - show placeholder
                self.temp_ax.text(0.5, 0.5, 'Temperature data\nnot available', 
                                 horizontalalignment='center', verticalalignment='center',
                                 transform=self.temp_ax.transAxes, fontsize=10, alpha=0.6)
                self.temp_ax.set_title(f'Temperature - {current_date.strftime("%m-%d")}', 
                                      fontsize=11, fontweight='bold')
            
            # 3. CLOUD COVER CHART
            cloud_columns = ['cloud_cover', 'cloudiness', 'cloud_fraction', 'total_cloud_cover']
            cloud_col = None
            for col in cloud_columns:
                if col in current_day_hourly.columns:
                    cloud_col = col
                    break
                    
            if not current_day_hourly.empty and cloud_col:
                cloud_data = current_day_hourly[cloud_col]
                hours = current_day_hourly.index.hour
                
                # Filter to same hours as energy production for consistency
                if 'daylight_mask' in locals() and daylight_mask.any():
                    cloud_daylight = cloud_data[daylight_mask]
                    cloud_hours = hours[daylight_mask]
                else:
                    cloud_daylight = cloud_data
                    cloud_hours = hours
                
                if len(cloud_daylight) > 0:
                    self.cloud_ax.bar(cloud_hours, cloud_daylight, color='lightblue', alpha=0.7, 
                                     edgecolor='steelblue')
                    
                    self.cloud_ax.set_title(f'Cloud Cover - {current_date.strftime("%m-%d")}', 
                                           fontsize=11, fontweight='bold')
                    self.cloud_ax.set_xlabel('Hour')
                    self.cloud_ax.set_ylabel('Cloud Cover (%)')
                    self.cloud_ax.set_ylim(0, 100)
                    self.cloud_ax.grid(True, alpha=0.3)
                    
                    # Match x-axis with energy production chart
                    if 'min_hour' in locals() and 'max_hour' in locals():
                        self.cloud_ax.set_xlim(min_hour - 0.5, max_hour + 0.5)
                    else:
                        self.cloud_ax.set_xlim(cloud_hours.min() - 0.5, cloud_hours.max() + 0.5)
            else:
                # No cloud cover data - show placeholder
                self.cloud_ax.text(0.5, 0.5, 'Cloud cover data\nnot available', 
                                  horizontalalignment='center', verticalalignment='center',
                                  transform=self.cloud_ax.transAxes, fontsize=10, alpha=0.6)
                self.cloud_ax.set_title(f'Cloud Cover - {current_date.strftime("%m-%d")}', 
                                       fontsize=11, fontweight='bold')
            
            # 4. 15-DAY SUMMARY CHART
            dates = daily_summary.index
            daily_energy = daily_summary['predicted_total_energy']
            
            # Calculate daily rankings based on actual energy production
            colors = []
            ranking_values = []
            color_map = {1: '#e74c3c', 2: '#e67e22', 3: '#f39c12', 4: '#27ae60', 5: '#2ecc71'}
            
            # Filter out days with zero production for fair ranking
            non_zero_energy = daily_energy[daily_energy > 0]
            
            if len(non_zero_energy) > 1:
                # Calculate percentiles for ranking based on actual energy production
                percentiles = [20, 40, 60, 80]
                energy_thresholds = [non_zero_energy.quantile(p/100) for p in percentiles]
                
                # Assign rankings based on energy production levels
                for energy in daily_energy:
                    if energy <= 0:
                        ranking_values.append(1)  # No production = poor
                    elif energy <= energy_thresholds[0]:
                        ranking_values.append(1)  # Poor (bottom 20%)
                    elif energy <= energy_thresholds[1]:
                        ranking_values.append(2)  # Below average (20-40%)
                    elif energy <= energy_thresholds[2]:
                        ranking_values.append(3)  # Average (40-60%)
                    elif energy <= energy_thresholds[3]:
                        ranking_values.append(4)  # Good (60-80%)
                    else:
                        ranking_values.append(5)  # Excellent (top 20%)
            else:
                # Fallback if insufficient data
                ranking_values = [3] * len(dates)
            
            colors = [color_map.get(r, '#95a5a6') for r in ranking_values]
            
            # Debug: Log the ranking calculations
            logger.info(f"Daily rankings - Energy values: {daily_energy.tolist()[:5]} (first 5)")
            logger.info(f"Daily rankings - Ranking values: {ranking_values[:5]} (first 5)")
            if len(non_zero_energy) > 1:
                logger.info(f"Energy thresholds: {energy_thresholds}")
            
            bars = self.daily_ax.bar(dates, daily_energy, color=colors, alpha=0.8)
            
            # Note: Numerical ranking badges removed - using color legend instead
            
            # Highlight currently selected day
            if self.current_day_index < len(bars):
                bars[self.current_day_index].set_edgecolor('black')
                bars[self.current_day_index].set_linewidth(3)
                
                # Add selection indicator
                selected_bar = bars[self.current_day_index]
                try:
                    arrow_y = float(selected_bar.get_height()) * 1.1
                except (TypeError, ValueError):
                    arrow_y = 1.0  # Default height if conversion fails
                self.daily_ax.annotate('SELECTED', 
                                      xy=(selected_bar.get_x() + selected_bar.get_width()/2, arrow_y),
                                      xytext=(0, 15), textcoords='offset points',
                                      ha='center', va='bottom',
                                      arrowprops=dict(arrowstyle='->', color='red'),
                                      fontsize=9, fontweight='bold', color='red')
            
            self.daily_ax.set_title('15-Day Energy Production Overview', fontsize=12, fontweight='bold')
            self.daily_ax.set_ylabel('Daily Energy (kWh)')
            self.daily_ax.tick_params(axis='x', rotation=45)
            self.daily_ax.grid(True, alpha=0.3)
            
            # Add top margin for star indicators
            if len(daily_energy) > 0 and daily_energy.max() > 0:
                max_daily_energy = daily_energy.max()
                self.daily_ax.set_ylim(0, max_daily_energy * 1.15)  # 15% top margin
            
            # Add subtitle explaining the color coding
            subtitle_text = 'Colors and numbers show daily performance ranking (1=Poor, 5=Excellent)'
            self.daily_ax.text(0.5, 0.90, subtitle_text, transform=self.daily_ax.transAxes, 
                              ha='center', va='top', fontsize=9, style='italic', alpha=0.8,
                              bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.3))
            
            # Update color legend
            self._create_color_legend()
            
            # Refresh canvas
            self.canvas.draw()
            
            # Update day information display with hourly insights
            if 'hourly_rankings' in locals() and hourly_rankings:
                self._update_day_info(current_date, hourly_rankings, daylight_hours)
            else:
                # Fallback to daily ranking if hourly rankings not available
                daily_ranking = daily_summary.iloc[self.current_day_index].get('ranking', 3)
                try:
                    daily_ranking = int(float(daily_ranking)) if daily_ranking is not None else 3
                except (ValueError, TypeError):
                    daily_ranking = 3
                self._update_day_info(current_date, [daily_ranking], [])
            
        except Exception as e:
            logger.error(f"Error updating charts: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Show error message in charts
            error_msg = f"Chart update failed: {str(e)}"
            for ax in [self.hourly_ax, self.temp_ax, self.cloud_ax, self.daily_ax]:
                ax.clear()
                ax.text(0.5, 0.5, error_msg, 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=10, color='red', alpha=0.8)
            
            # Keep legend visible even on error
            self._create_color_legend()
            
            self.canvas.draw()
            
    def _update_day_info(self, current_date, rankings, hours=[]):
        """Update the day information display with hourly optimization insights."""
        day_num = self.current_day_index + 1
        
        # Position description
        if self.current_day_index == 7:
            position = "(Center Date)"
        elif self.current_day_index < 7:
            days_before = 7 - self.current_day_index
            position = f"({days_before} days before center)"
        else:
            days_after = self.current_day_index - 7
            position = f"({days_after} days after center)"
        
        if len(rankings) > 1 and len(hours) > 0:  # Hourly rankings available
            # Calculate overall day rating
            avg_rating = sum(rankings) / len(rankings)
            overall_rating = {
                1: 'Poor (R1/5)', 
                2: 'Below Average (R2/5)', 
                3: 'Average (R3/5)', 
                4: 'Good (R4/5)', 
                5: 'Excellent (R5/5)'
            }.get(int(round(avg_rating)), 'Unknown')
            
            # Find optimal hours for appliance usage
            excellent_hours = [f"{h:02d}:00" for h, r in zip(hours, rankings) if r == 5]
            good_hours = [f"{h:02d}:00" for h, r in zip(hours, rankings) if r == 4]
            
            if excellent_hours:
                optimal_text = f"Prime time for appliances: {', '.join(excellent_hours[:3])}"
            elif good_hours:
                optimal_text = f"Good time for appliances: {', '.join(good_hours[:3])}"
            else:
                optimal_text = "Limited optimal hours - plan lighter loads"
            
            info_text = f"📅 Day {day_num} of 15: {current_date.strftime('%Y-%m-%d')} {position} - {overall_rating} • {optimal_text}"
        else:  # Fallback to single daily ranking
            rating = rankings[0] if rankings else 3
            rating_text = {
                1: 'Poor (R1/5)', 
                2: 'Below Average (R2/5)', 
                3: 'Average (R3/5)', 
                4: 'Good (R4/5)', 
                5: 'Excellent (R5/5)'
            }.get(rating, 'Unknown')
            
            info_text = f"📅 Day {day_num} of 15: {current_date.strftime('%Y-%m-%d')} {position} - Performance: {rating_text}"
        
        if hasattr(self, 'day_info_label'):
            self.day_info_label.config(text=info_text)
            
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
            self._update_charts(self.current_results)
            
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
                f"Sarmas et al. (2025) \"Photovoltaic Power Production Dataset\"\n"
                f"Mendeley Data, V3, doi: 10.17632/dbh93b6vp8.3\n\n"
                f"🚀 Ready to analyze your solar energy data!"
            )
            
            messagebox.showinfo("FilantropiaSolar Ready", welcome_msg)
            
        except Exception as e:
            logger.error(f"Error showing welcome message: {e}")
            
    def _on_main_close(self):
        """Handle main application window close event."""
        try:
            if messagebox.askyesno("Confirm Exit", "Save current work and exit FilantropiaSolar?"):
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
            print("\n" + "="*70)
            print("🌞 FilantropiaSolar - Advanced Solar Energy Analysis Application")
            print("="*70)
            print("📚 DATA CITATION REQUIRED:")
            print("   Sarmas, Elissaios; Matias, Nuno; Pereira, Catarina; Antunes, Ana Rita (2025),")
            print("   \"Photovoltaic Power Production Dataset\", Mendeley Data, V3,")
            print("   doi: 10.17632/dbh93b6vp8.3")
            print("="*70 + "\n")
            
            # Verify required directories exist
            required_dirs = ["data", "weather_files"]
            missing_dirs = [d for d in required_dirs if not Path(d).exists()]
            
            if missing_dirs:
                messagebox.showerror(
                    "Missing Required Directories",
                    f"The following required directories were not found:\n"
                    f"{', '.join(missing_dirs)}\n\n"
                    f"Please ensure you are running FilantropiaSolar from the project root directory."
                )
                return
                
            # Create and start loading interface
            self.create_loading_gui()
            self._start_loading()
            
            logger.info("Starting main application loop")
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
            self._cleanup_and_exit()
        except Exception as e:
            logger.error(f"Fatal error in application: {e}")
            if self.root:
                messagebox.showerror(
                    "Fatal Error",
                    f"A fatal error occurred in FilantropiaSolar:\n\n{str(e)}\n\n"
                    f"The application will now close. Please check the logs for details."
                )
            self._cleanup_and_exit()


def main():
    """Main entry point for FilantropiaSolar application."""
    try:
        app = FilantropiaSolarApp()
        app.run()
    except Exception as e:
        print(f"Failed to start FilantropiaSolar: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()