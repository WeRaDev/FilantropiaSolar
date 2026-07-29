#!/usr/bin/env python3
"""
Enhanced FilantropiaSolar Application with Advanced Charts and Input Controls

Version with hourly production charts and historical/simulation mode selection.
"""

import sys
import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from pathlib import Path
import threading
import queue
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

logger = logging.getLogger(__name__)


class EnhancedFilantropiaSolarApp:
    """
    Enhanced FilantropiaSolar application with improved charts and input controls.
    """
    
    def __init__(self):
        """Initialize the enhanced application."""
        self.setup_logging()
        
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
        
        # Threading
        self.loading_queue = queue.Queue()
        self.loading_thread = None
        
        # Application state
        self.is_initialized = False
        self.current_results = None
        self.current_day_index = 7  # Start with center date
        self.available_dates = {}  # Store available dates per installation
        
        logger.info("Enhanced FilantropiaSolar Application initialized")
        
    def setup_logging(self):
        """Setup optimized logging configuration."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure logging with minimal output
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'enhanced_optimized_application.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        logger.setLevel(logging.INFO)
        
    def create_loading_gui(self):
        """Create initial loading GUI."""
        self.root = tk.Tk()
        self.root.title("Enhanced FilantropiaSolar - Loading...")
        self.root.geometry("500x300")
        self.root.resizable(False, False)
        
        # Center the window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.root.winfo_screenheight() // 2) - (300 // 2)
        self.root.geometry(f"500x300+{x}+{y}")
        
        # Loading frame
        self.loading_frame = ttk.Frame(self.root, padding="30")
        self.loading_frame.pack(fill=tk.BOTH, expand=True)
        
        # Logo/Title
        title_label = ttk.Label(
            self.loading_frame, 
            text="☀️ Enhanced FilantropiaSolar", 
            font=('Arial', 18, 'bold')
        )
        title_label.pack(pady=(20, 10))
        
        subtitle_label = ttk.Label(
            self.loading_frame, 
            text="Advanced Solar Energy Analysis with Interactive Charts", 
            font=('Arial', 11)
        )
        subtitle_label.pack(pady=(0, 30))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(
            self.loading_frame,
            variable=self.progress_var,
            maximum=100,
            length=300,
            mode='determinate'
        )
        progress_bar.pack(pady=10)
        
        # Status label
        self.status_var = tk.StringVar(value="Initializing...")
        status_label = ttk.Label(
            self.loading_frame,
            textvariable=self.status_var,
            font=('Arial', 10)
        )
        status_label.pack(pady=10)
        
        # Info text
        info_text = tk.Text(
            self.loading_frame,
            height=6,
            width=50,
            wrap=tk.WORD,
            font=('Arial', 9),
            state='disabled',
            bg=self.root.cget('bg')
        )
        info_text.pack(pady=(20, 0))
        
        info_text.config(state='normal')
        info_text.insert(tk.END, 
            "Loading enhanced solar energy system...\n\n"
            "• 9 PV installations across Portugal\n"
            "• 315,567+ historical records\n"
            "• Hourly production analysis\n"
            "• Historical & simulation modes\n"
        )
        info_text.config(state='disabled')
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_loading_close)
        
    def on_loading_close(self):
        """Handle loading window close."""
        if messagebox.askyesno("Confirm", "Cancel loading and exit application?"):
            self.cleanup_and_exit()
            
    def cleanup_and_exit(self):
        """Clean up and exit."""
        try:
            if self.loading_thread and self.loading_thread.is_alive():
                pass
            
            if self.root:
                self.root.quit()
                self.root.destroy()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            sys.exit(0)
            
    def update_progress(self, value: float, status: str):
        """Update progress bar and status."""
        self.progress_var.set(value)
        self.status_var.set(status)
        self.root.update_idletasks()
        
    def initialize_components_threaded(self):
        """Initialize components in a separate thread."""
        try:
            # Step 1: Load data processor
            self.update_progress(10, "Loading installation data...")
            from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
            self.data_processor = ComprehensiveDataProcessor()
            
            self.update_progress(30, "Analyzing available data ranges...")
            self.load_available_dates()
            
            self.update_progress(50, "Initializing weather simulation...")
            from src.weather_simulation.weather_simulator import WeatherSimulator
            self.weather_simulator = WeatherSimulator("weather_files")
            
            self.update_progress(70, "Training ML models...")
            from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
            self.energy_predictor = EnhancedEnergyPredictor(
                self.data_processor, 
                self.weather_simulator
            )
            
            self.update_progress(95, "Finalizing setup...")
            self.energy_predictor.save_models()
            
            self.update_progress(100, "Initialization complete!")
            
            # Signal completion
            self.loading_queue.put("COMPLETE")
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            self.loading_queue.put(f"ERROR: {str(e)}")
            
    def load_available_dates(self):
        """Load available date ranges for each installation."""
        try:
            installations = self.data_processor.get_installation_list()
            
            for inst_id, info in installations:
                try:
                    # Get data for this installation using the correct method
                    data = self.data_processor.get_installation_data(inst_id)
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
                    # Set default date range if data unavailable
                    self.available_dates[inst_id] = {
                        'min_date': datetime(2023, 1, 1).date(),
                        'max_date': datetime(2024, 12, 31).date(),
                        'location': info.location,
                        'serial': info.serial_number
                    }
            
            logger.info(f"Loaded available dates for {len(self.available_dates)} installations")
            
        except Exception as e:
            logger.error(f"Error loading available dates: {e}")
            
    def start_loading(self):
        """Start the loading process."""
        self.loading_thread = threading.Thread(target=self.initialize_components_threaded)
        self.loading_thread.daemon = True
        self.loading_thread.start()
        
        self.check_loading_progress()
        
    def check_loading_progress(self):
        """Check loading progress and handle completion."""
        try:
            message = self.loading_queue.get_nowait()
            
            if message == "COMPLETE":
                self.on_loading_complete()
            elif message.startswith("ERROR:"):
                self.on_loading_error(message[6:])
            else:
                self.root.after(100, self.check_loading_progress)
                
        except queue.Empty:
            self.root.after(100, self.check_loading_progress)
        except Exception as e:
            logger.error(f"Error checking loading progress: {e}")
            self.on_loading_error(str(e))
            
    def on_loading_complete(self):
        """Handle successful loading completion."""
        try:
            self.is_initialized = True
            logger.info("All components initialized successfully")
            
            self.root.after(1000, self.transition_to_main_gui)
            
        except Exception as e:
            logger.error(f"Error handling loading completion: {e}")
            self.on_loading_error(str(e))
            
    def on_loading_error(self, error_message: str):
        """Handle loading error."""
        logger.error(f"Loading failed: {error_message}")
        
        self.status_var.set("Loading failed!")
        self.progress_var.set(0)
        
        messagebox.showerror(
            "Loading Failed",
            f"Failed to initialize application:\n\n{error_message}\n\n"
            "Please check the logs for more details."
        )
        
        self.cleanup_and_exit()
        
    def transition_to_main_gui(self):
        """Transition from loading to main GUI."""
        try:
            self.loading_frame.destroy()
            
            self.root.title("Enhanced FilantropiaSolar - Advanced Solar Energy Analysis")
            self.root.geometry("1400x900")
            self.root.resizable(True, True)
            
            self.create_main_gui()
            self.show_welcome_message()
            
        except Exception as e:
            logger.error(f"Error transitioning to main GUI: {e}")
            messagebox.showerror("GUI Error", f"Failed to create main interface: {str(e)}")
            self.cleanup_and_exit()
            
    def create_main_gui(self):
        """Create the main GUI interface."""
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook interface
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Input tab - ENHANCED
        input_frame = ttk.Frame(notebook)
        notebook.add(input_frame, text="🎯 Input & Configuration")
        self.create_enhanced_input_interface(input_frame)
        
        # Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="📋 Results")
        self.create_results_interface(results_frame)
        
        # Charts tab - REDESIGNED
        charts_frame = ttk.Frame(notebook)
        notebook.add(charts_frame, text="📊 Interactive Charts")
        self.create_enhanced_charts_interface(charts_frame)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_main_close)
        
    def create_enhanced_input_interface(self, parent):
        """Create enhanced input interface with historical/simulation modes."""
        # Main container
        container = ttk.Frame(parent, padding="20")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            container, 
            text="Solar Energy Prediction Configuration", 
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 20))
        
        # Mode selection - NEW
        mode_frame = ttk.LabelFrame(container, text="Analysis Mode", padding="15")
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.mode_var = tk.StringVar(value="historical")
        
        historical_radio = ttk.Radiobutton(
            mode_frame,
            text="📈 Historical Analysis (use existing data)",
            variable=self.mode_var,
            value="historical",
            command=self.on_mode_change
        )
        historical_radio.pack(anchor=tk.W, pady=(0, 5))
        
        simulation_radio = ttk.Radiobutton(
            mode_frame,
            text="🔮 Future Simulation (predict any date)",
            variable=self.mode_var,
            value="simulation",
            command=self.on_mode_change
        )
        simulation_radio.pack(anchor=tk.W)
        
        # Installation selection
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
            width=60
        )
        installation_combo.pack(fill=tk.X, pady=(5, 0))
        installation_combo.bind('<<ComboboxSelected>>', self.on_installation_change)
        
        # Date selection - ENHANCED
        self.date_frame = ttk.LabelFrame(container, text="Date Selection", padding="15")
        self.date_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Historical date selection
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
        
        # Simulation date selection
        self.simulation_date_frame = ttk.Frame(self.date_frame)
        
        ttk.Label(self.simulation_date_frame, text="Enter Any Date for Simulation:").pack(anchor=tk.W)
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
        
        # Options
        options_frame = ttk.LabelFrame(container, text="Options", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.simulation_var = tk.BooleanVar(value=True)
        self.simulation_checkbox = ttk.Checkbutton(
            options_frame,
            text="Use weather simulation for missing data",
            variable=self.simulation_var
        )
        self.simulation_checkbox.pack(anchor=tk.W)
        
        # Predict button
        predict_button = ttk.Button(
            container,
            text="🚀 Generate Enhanced 15-Day Analysis",
            command=self.on_predict_enhanced,
            style="Accent.TButton"
        )
        predict_button.pack(pady=15)
        
        # Status
        self.input_status_var = tk.StringVar(value="Ready to generate enhanced analysis")
        status_label = ttk.Label(container, textvariable=self.input_status_var, foreground="blue")
        status_label.pack(pady=(10, 0))
        
        # Initialize mode
        self.on_mode_change()
        self.on_installation_change()
        
    def on_mode_change(self):
        """Handle mode change between historical and simulation."""
        mode = self.mode_var.get()
        
        if mode == "historical":
            self.historical_date_frame.pack(fill=tk.X)
            self.simulation_date_frame.pack_forget()
            self.simulation_checkbox.config(state='disabled')
            self.simulation_var.set(False)
        else:
            self.simulation_date_frame.pack(fill=tk.X)
            self.historical_date_frame.pack_forget()
            self.simulation_checkbox.config(state='normal')
            self.simulation_var.set(True)
            
    def on_installation_change(self, event=None):
        """Handle installation selection change."""
        try:
            installation_text = self.installation_var.get()
            if not installation_text:
                return
                
            # Find installation ID
            installation_id = None
            for inst_id, info in self.data_processor.get_installation_list():
                if installation_text.startswith(f"{info.location}_{info.serial_number}"):
                    installation_id = inst_id
                    break
                    
            if installation_id and installation_id in self.available_dates:
                date_info = self.available_dates[installation_id]
                min_date = date_info['min_date']
                max_date = date_info['max_date']
                
                # Update date range label
                self.date_range_label.config(
                    text=f"{min_date} to {max_date} ({(max_date - min_date).days} days)",
                    foreground="blue"
                )
                
                # Populate historical dates (sample some dates to avoid too many)
                date_list = []
                current = min_date
                while current <= max_date:
                    date_list.append(current.strftime("%Y-%m-%d"))
                    current += timedelta(days=30)  # Sample every 30 days
                
                # Add max date if not already included
                if max_date.strftime("%Y-%m-%d") not in date_list:
                    date_list.append(max_date.strftime("%Y-%m-%d"))
                
                self.historical_date_combo.config(values=date_list)
                if date_list:
                    self.historical_date_var.set(date_list[-1])  # Default to most recent
                    
        except Exception as e:
            logger.error(f"Error updating installation dates: {e}")
            
    def create_results_interface(self, parent):
        """Create results interface."""
        container = ttk.Frame(parent, padding="20")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Title
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
        
        self.update_results_display("No analysis generated yet.\n\nUse the Input tab to generate enhanced analysis.")
        
    def create_enhanced_charts_interface(self, parent):
        """Create enhanced charts interface with hourly focus."""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure
            
            # Main container
            container = ttk.Frame(parent, padding="10")
            container.pack(fill=tk.BOTH, expand=True)
            
            # Title and controls
            header_frame = ttk.Frame(container)
            header_frame.pack(fill=tk.X, pady=(0, 10))
            
            title_label = ttk.Label(
                header_frame,
                text="📊 Interactive Energy Production Analysis",
                font=('Arial', 16, 'bold')
            )
            title_label.pack(side=tk.LEFT)
            
            # Day navigation controls - RIGHT SIDE
            nav_frame = ttk.Frame(header_frame)
            nav_frame.pack(side=tk.RIGHT)
            
            ttk.Button(nav_frame, text="◄ Prev", 
                      command=self.previous_day, width=8).pack(side=tk.LEFT, padx=(0, 2))
            ttk.Button(nav_frame, text="Center", 
                      command=self.center_day, width=8).pack(side=tk.LEFT, padx=(0, 2))
            ttk.Button(nav_frame, text="Next ►", 
                      command=self.next_day, width=8).pack(side=tk.LEFT)
            
            # Day info
            self.day_info_label = ttk.Label(
                container, 
                text="Select a day to see hourly analysis",
                font=('Arial', 11, 'bold'),
                foreground="navy"
            )
            self.day_info_label.pack(pady=(0, 10))
            
            # Create matplotlib figure with new layout
            self.figure = Figure(figsize=(14, 10), dpi=100, tight_layout=True)
            
            # Create grid layout: 2 rows, 2 columns
            # Top row: Hourly energy (spans 2 columns)
            # Bottom left: Weather data, Bottom right: 15-day summary
            gs = self.figure.add_gridspec(3, 2, height_ratios=[2, 1, 1], hspace=0.4, wspace=0.3)
            
            # Main hourly chart (top row, full width)
            self.hourly_ax = self.figure.add_subplot(gs[0, :])
            
            # Weather charts (middle row)
            self.temp_ax = self.figure.add_subplot(gs[1, 0])
            self.cloud_ax = self.figure.add_subplot(gs[1, 1])
            
            # Daily summary chart (bottom row, full width)
            self.daily_ax = self.figure.add_subplot(gs[2, :])
            
            # Create canvas
            self.canvas = FigureCanvasTkAgg(self.figure, container)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Navigation toolbar
            toolbar_frame = ttk.Frame(container)
            toolbar_frame.pack(fill=tk.X)
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()
            
            # Initialize empty plots
            self.clear_enhanced_plots()
            
            self.plt = plt
            
        except ImportError as e:
            error_label = ttk.Label(
                parent,
                text=f"Charts unavailable: {str(e)}\n\nTo enable charts, install matplotlib:\npip install matplotlib",
                font=('Arial', 12),
                foreground="red",
                justify=tk.CENTER
            )
            error_label.pack(expand=True)
            
    def clear_enhanced_plots(self):
        """Clear all plots and show placeholder text."""
        if hasattr(self, 'hourly_ax'):
            axes = [self.hourly_ax, self.temp_ax, self.cloud_ax, self.daily_ax]
            titles = ['Hourly Energy Production', 'Temperature', 'Cloud Cover', '15-Day Summary']
            
            for ax, title in zip(axes, titles):
                ax.clear()
                ax.text(0.5, 0.5, 'Generate analysis\nto see charts', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=12, alpha=0.5)
                ax.set_title(title, fontsize=12, fontweight='bold')
                
            self.canvas.draw()
            
    def on_predict_enhanced(self):
        """Handle enhanced prediction request."""
        try:
            # Validate inputs
            installation_text = self.installation_var.get()
            if not installation_text:
                messagebox.showerror("Error", "Please select an installation.")
                return
                
            # Parse installation ID
            installation_id = None
            for inst_id, info in self.data_processor.get_installation_list():
                if installation_text.startswith(f"{info.location}_{info.serial_number}"):
                    installation_id = inst_id
                    break
                    
            if not installation_id:
                messagebox.showerror("Error", "Invalid installation selection.")
                return
                
            # Get date based on mode
            mode = self.mode_var.get()
            try:
                if mode == "historical":
                    date_str = self.historical_date_var.get()
                else:
                    date_str = self.simulation_date_var.get()
                    
                if not date_str:
                    messagebox.showerror("Error", "Please select a date.")
                    return
                    
                center_date = datetime.strptime(date_str.strip(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return
                
            # Update status
            analysis_type = "historical analysis" if mode == "historical" else "future simulation"
            self.input_status_var.set(f"Generating enhanced {analysis_type}... Please wait.")
            self.root.update_idletasks()
            
            # Generate prediction
            use_simulation = self.simulation_var.get() or mode == "simulation"
            results = self.energy_predictor.predict_15day_period(
                installation_id, center_date, use_simulation
            )
            
            # Store and display results
            self.current_results = results
            self.display_enhanced_results(results, mode)
            self.update_enhanced_charts(results)
            
            # Update status
            self.input_status_var.set(f"Enhanced {analysis_type} completed for {date_str}")
            
            # Show success message
            installation_info = results['installation_info']
            period_stats = results['period_statistics']
            
            success_msg = (
                f"Enhanced {analysis_type} completed!\n\n"
                f"📍 {installation_info['location']} ({installation_info['capacity_kwp']} kWp)\n"
                f"⚡ Total Energy (15 days): {period_stats['total_energy_kwh']:.1f} kWh\n"
                f"📊 Average Specific Energy: {period_stats['average_specific_energy']:.2f} kWh/kWp\n\n"
                f"📈 Check the Interactive Charts tab for detailed hourly analysis!"
            )
            
            messagebox.showinfo("Analysis Complete", success_msg)
            
        except Exception as e:
            logger.error(f"Error in enhanced prediction: {e}")
            self.input_status_var.set("Error generating analysis. Check logs.")
            messagebox.showerror("Analysis Error", f"Failed to generate analysis:\n{str(e)}")
            
    def display_enhanced_results(self, results: Dict[str, Any], mode: str):
        """Display enhanced prediction results."""
        try:
            text = "ENHANCED FILANTROPIA SOLAR - ANALYSIS RESULTS\n"
            text += "=" * 55 + "\n\n"
            
            # Mode info
            analysis_type = "HISTORICAL ANALYSIS" if mode == "historical" else "FUTURE SIMULATION"
            text += f"Analysis Type: {analysis_type}\n\n"
            
            # Installation info
            inst_info = results['installation_info']
            text += f"Installation: {inst_info['location']} (Serial: {inst_info['serial_number']})\n"
            text += f"Capacity: {inst_info['capacity_kwp']} kWp\n\n"
            
            # Prediction period
            period = results['prediction_period']
            text += f"Analysis Period: {period['start'].date()} to {period['end'].date()}\n"
            text += f"Center Date: {period['center_date'].date()}\n"
            text += f"Total Hours: {period['total_hours']}\n\n"
            
            # Enhanced statistics
            stats = results['period_statistics']
            text += "ENHANCED STATISTICS (15-day period)\n"
            text += "-" * 45 + "\n"
            text += f"Total Energy: {stats['total_energy_kwh']:.1f} kWh\n"
            text += f"Average Daily Energy: {stats['total_energy_kwh']/15:.1f} kWh/day\n"
            text += f"Average Specific Energy: {stats['average_specific_energy']:.2f} kWh/kWp\n"
            text += f"Peak Hour Energy: {stats['peak_hour_energy']:.2f} kWh/kWp\n"
            text += f"Average Temperature: {stats.get('average_temperature', 0):.1f}°C\n"
            text += f"Average Cloud Cover: {stats.get('average_cloud_cover', 0):.1f}%\n\n"
            
            # Daily rankings
            if 'daily_summary' in results:
                daily = results['daily_summary']
                text += "DAILY PERFORMANCE RANKING\n"
                text += "-" * 45 + "\n"
                text += f"{'Date':<12} {'Energy':<10} {'Ranking':<10} {'Weather':<10}\n"
                text += "-" * 45 + "\n"
                
                for i, (date, row) in enumerate(daily.iterrows()):
                    energy = row.get('predicted_total_energy', 0)
                    ranking = row.get('ranking', 3)
                    rank_text = {1: '⭐Poor', 2: '⭐⭐Below', 3: '⭐⭐⭐Avg', 4: '⭐⭐⭐⭐Good', 5: '⭐⭐⭐⭐⭐Exc'}.get(ranking, 'Avg')
                    
                    # Highlight current day
                    marker = " ◄ SELECTED" if i == self.current_day_index else ""
                    text += f"{str(date):<12} {energy:<10.1f} {rank_text:<10} {'Sunny' if ranking >= 4 else 'Cloudy':<10}{marker}\n"
            
            # Data source info
            source = results['data_source']
            text += "\nDATA SOURCE & MODEL INFO\n"
            text += "-" * 45 + "\n"
            text += f"Weather Data: {'🌦️ Simulated' if source['used_simulation'] else '📊 Historical'}\n"
            text += f"ML Model: {source['model_used'].replace('_', ' ').title()}\n"
            
            if 'model_performance' in source and source['model_used'] in source['model_performance']:
                perf = source['model_performance'][source['model_used']]
                text += f"Model Accuracy (R²): {perf.get('r2', 0):.3f}\n"
                text += f"Model Error (MAE): {perf.get('mae', 0):.3f} kWh/kWp\n"
                
            text += f"\n💡 TIP: Use the Interactive Charts tab to explore hourly patterns!"
                
            self.update_results_display(text)
            
        except Exception as e:
            logger.error(f"Error displaying enhanced results: {e}")
            self.update_results_display(f"Error displaying results: {str(e)}")
            
    def update_results_display(self, text: str):
        """Update the results text display."""
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        self.results_text.config(state='disabled')
        
    def update_enhanced_charts(self, results: Dict[str, Any]):
        """Update enhanced charts with hourly focus."""
        if not hasattr(self, 'hourly_ax'):
            return
            
        try:
            # Clear existing plots
            for ax in [self.hourly_ax, self.temp_ax, self.cloud_ax, self.daily_ax]:
                ax.clear()
            
            # Get data
            daily_summary = results['daily_summary']
            hourly_data = results['hourly_data']
            
            # Get current day data
            current_date = daily_summary.index[self.current_day_index]
            current_day_hourly = hourly_data[hourly_data.index.date == current_date.date()]
            
            # 1. MAIN CHART: Hourly Energy Production for Selected Day
            if not current_day_hourly.empty:
                hours = current_day_hourly.index.hour
                hourly_energy = current_day_hourly.get('predicted_specific_energy', pd.Series([0]*len(current_day_hourly)))
                
                # Color bars based on daily ranking
                daily_ranking = daily_summary.iloc[self.current_day_index].get('ranking', 3)
                ranking_colors = {1: '#e74c3c', 2: '#e67e22', 3: '#f39c12', 4: '#27ae60', 5: '#2ecc71'}
                bar_color = ranking_colors.get(daily_ranking, '#3498db')
                
                bars = self.hourly_ax.bar(hours, hourly_energy, color=bar_color, alpha=0.8, edgecolor='navy', linewidth=0.5)
                
                # Highlight peak hours
                if len(hourly_energy) > 0:
                    max_idx = hourly_energy.idxmax()
                    max_hour = max_idx.hour
                    for bar in bars:
                        if bar.get_x() == max_hour:
                            bar.set_color('#f1c40f')
                            bar.set_edgecolor('#d35400')
                            bar.set_linewidth(2)
                
                self.hourly_ax.set_title(f'Hourly Energy Production - {current_date.strftime("%Y-%m-%d")} (Ranking: {"⭐"*daily_ranking})', 
                                        fontsize=13, fontweight='bold')
                self.hourly_ax.set_xlabel('Hour of Day')
                self.hourly_ax.set_ylabel('Specific Energy (kWh/kWp)')
                self.hourly_ax.set_xlim(-0.5, 23.5)
                self.hourly_ax.grid(True, alpha=0.3)
                self.hourly_ax.set_xticks(range(0, 24, 2))
                
                # Add value labels on significant bars
                for bar in bars:
                    height = bar.get_height()
                    if height > 0.1:  # Only label significant values
                        self.hourly_ax.text(bar.get_x() + bar.get_width()/2., height + height*0.02,
                                           f'{height:.2f}', ha='center', va='bottom', fontsize=8)
            
            # 2. TEMPERATURE CHART for Selected Day
            if not current_day_hourly.empty and 'temperature_2m' in current_day_hourly.columns:
                temp_data = current_day_hourly['temperature_2m']
                hours = current_day_hourly.index.hour
                
                self.temp_ax.plot(hours, temp_data, 'ro-', linewidth=2, markersize=4, alpha=0.8)
                self.temp_ax.fill_between(hours, temp_data, alpha=0.3, color='red')
                
                self.temp_ax.set_title(f'Temperature Profile - {current_date.strftime("%m-%d")}', fontsize=11, fontweight='bold')
                self.temp_ax.set_xlabel('Hour')
                self.temp_ax.set_ylabel('Temperature (°C)')
                self.temp_ax.grid(True, alpha=0.3)
                self.temp_ax.set_xlim(-0.5, 23.5)
            
            # 3. CLOUD COVER CHART for Selected Day
            if not current_day_hourly.empty and 'cloud_cover' in current_day_hourly.columns:
                cloud_data = current_day_hourly['cloud_cover']
                hours = current_day_hourly.index.hour
                
                self.cloud_ax.bar(hours, cloud_data, color='lightblue', alpha=0.7, edgecolor='steelblue')
                
                self.cloud_ax.set_title(f'Cloud Cover - {current_date.strftime("%m-%d")}', fontsize=11, fontweight='bold')
                self.cloud_ax.set_xlabel('Hour')
                self.cloud_ax.set_ylabel('Cloud Cover (%)')
                self.cloud_ax.set_ylim(0, 100)
                self.cloud_ax.grid(True, alpha=0.3)
                self.cloud_ax.set_xlim(-0.5, 23.5)
            
            # 4. DAILY SUMMARY CHART (15 days)
            dates = daily_summary.index
            daily_energy = daily_summary['predicted_total_energy']
            
            # Color bars based on ranking
            colors = []
            ranking_colors = {1: '#e74c3c', 2: '#e67e22', 3: '#f39c12', 4: '#27ae60', 5: '#2ecc71'}
            
            if 'ranking' in daily_summary.columns:
                colors = [ranking_colors.get(r, '#95a5a6') for r in daily_summary['ranking']]
            else:
                colors = ['#3498db'] * len(dates)
            
            bars = self.daily_ax.bar(dates, daily_energy, color=colors, alpha=0.8)
            
            # Highlight selected day
            if self.current_day_index < len(bars):
                bars[self.current_day_index].set_edgecolor('black')
                bars[self.current_day_index].set_linewidth(3)
                
                # Add arrow pointing to selected day
                selected_bar = bars[self.current_day_index]
                arrow_y = selected_bar.get_height() + selected_bar.get_height() * 0.1
                self.daily_ax.annotate('SELECTED DAY', 
                                      xy=(selected_bar.get_x() + selected_bar.get_width()/2, arrow_y),
                                      xytext=(0, 20), textcoords='offset points',
                                      ha='center', va='bottom',
                                      arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'),
                                      fontsize=9, fontweight='bold', color='red')
            
            self.daily_ax.set_title('15-Day Energy Production Summary', fontsize=12, fontweight='bold')
            self.daily_ax.set_ylabel('Daily Energy (kWh)')
            self.daily_ax.tick_params(axis='x', rotation=45)
            self.daily_ax.grid(True, alpha=0.3)
            
            # Update canvas
            self.canvas.draw()
            
            # Update day info
            self.update_enhanced_day_info(current_date, daily_ranking)
            
        except Exception as e:
            logger.error(f"Error updating enhanced charts: {e}")
            
    def update_enhanced_day_info(self, current_date, ranking):
        """Update enhanced day information label."""
        day_num = self.current_day_index + 1
        rank_text = {1: 'Poor ⭐', 2: 'Below Average ⭐⭐', 3: 'Average ⭐⭐⭐', 4: 'Good ⭐⭐⭐⭐', 5: 'Excellent ⭐⭐⭐⭐⭐'}.get(ranking, 'Unknown')
        
        if self.current_day_index == 7:
            position_text = "(Center Date)"
        elif self.current_day_index < 7:
            days_before = 7 - self.current_day_index
            position_text = f"({days_before} days before center)"
        else:
            days_after = self.current_day_index - 7
            position_text = f"({days_after} days after center)"
        
        day_text = f"📅 Day {day_num} of 15: {current_date.strftime('%Y-%m-%d')} {position_text} - Performance: {rank_text}"
        
        if hasattr(self, 'day_info_label'):
            self.day_info_label.config(text=day_text)
            
    def previous_day(self):
        """Navigate to previous day."""
        if self.current_day_index > 0:
            self.current_day_index -= 1
            self.update_day_highlight()
                
    def next_day(self):
        """Navigate to next day."""
        if self.current_day_index < 14:
            self.current_day_index += 1
            self.update_day_highlight()
                
    def center_day(self):
        """Go to center day."""
        self.current_day_index = 7
        self.update_day_highlight()
        
    def update_day_highlight(self):
        """Update the day highlight in charts."""
        if self.current_results:
            self.update_enhanced_charts(self.current_results)
            
    def show_welcome_message(self):
        """Show enhanced welcome message."""
        if not self.is_initialized:
            return
            
        try:
            data_summary = self.data_processor.get_data_summary()
            
            welcome_msg = (
                f"🎉 Welcome to Enhanced FilantropiaSolar!\n\n"
                f"🔋 System Status:\n"
                f"• {data_summary['total_installations']} PV installations loaded\n"
                f"• {len(data_summary['locations'])} locations across Portugal\n"
                f"• {data_summary['total_records']:,} historical records available\n"
                f"• Advanced ML models trained and ready\n\n"
                f"✨ Enhanced Features:\n"
                f"📊 Hourly production analysis with weather correlation\n"
                f"📈 Historical data mode for existing periods\n"
                f"🔮 Future simulation for any date\n"
                f"🎯 Interactive day-by-day navigation\n"
                f"⭐ Performance rankings and insights\n\n"
                f"🚀 Ready to explore your solar energy data!"
            )
            
            messagebox.showinfo("Enhanced FilantropiaSolar Ready", welcome_msg)
            
        except Exception as e:
            logger.error(f"Error showing welcome message: {e}")
            
    def on_main_close(self):
        """Handle main window close."""
        try:
            if messagebox.askyesno("Confirm Exit", "Save models and exit Enhanced FilantropiaSolar?"):
                if self.energy_predictor:
                    self.energy_predictor.save_models()
                    
                self.cleanup_and_exit()
        except Exception as e:
            logger.error(f"Error during close: {e}")
            self.cleanup_and_exit()
            
    def run(self):
        """Run the enhanced application."""
        try:
            logger.info("Starting Enhanced FilantropiaSolar Application")
            
            # Check prerequisites
            if not Path("data").exists() or not Path("weather_files").exists():
                messagebox.showerror(
                    "Missing Data",
                    "Required directories 'data' and 'weather_files' not found.\n"
                    "Please run the application from the project root directory."
                )
                return
                
            self.create_loading_gui()
            self.start_loading()
            
            logger.info("Starting enhanced GUI main loop")
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
            self.cleanup_and_exit()
        except Exception as e:
            logger.error(f"Fatal error in enhanced application: {e}")
            if self.root:
                messagebox.showerror(
                    "Fatal Error",
                    f"A fatal error occurred:\n{str(e)}\n\nThe application will close."
                )
            self.cleanup_and_exit()


def main():
    """Main entry point for enhanced application."""
    try:
        app = EnhancedFilantropiaSolarApp()
        app.run()
    except Exception as e:
        print(f"Failed to start enhanced application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()