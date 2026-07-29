#!/usr/bin/env python3
"""
Optimized FilantropiaSolar Application with Plotting

Enhanced version that includes plotting capabilities with optimized performance.
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
from typing import Dict, Any, Optional

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

logger = logging.getLogger(__name__)


class OptimizedFilantropiaSolarApp:
    """
    Optimized main application with plotting capabilities restored.
    """
    
    def __init__(self):
        """Initialize the optimized application."""
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
        
        logger.info("Optimized FilantropiaSolar Application with Plots initialized")
        
    def setup_logging(self):
        """Setup optimized logging configuration."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure logging with less verbose output
        logging.basicConfig(
            level=logging.WARNING,  # Reduced verbosity
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'optimized_plots_application.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Set our logger to INFO level
        logger.setLevel(logging.INFO)
        
    def create_loading_gui(self):
        """Create initial loading GUI."""
        self.root = tk.Tk()
        self.root.title("FilantropiaSolar - Loading...")
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
            text="☀️ FilantropiaSolar", 
            font=('Arial', 20, 'bold')
        )
        title_label.pack(pady=(20, 10))
        
        subtitle_label = ttk.Label(
            self.loading_frame, 
            text="Solar Energy Prediction System with Charts", 
            font=('Arial', 12)
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
            "Loading comprehensive solar energy data...\n\n"
            "• 9 PV installations across Portugal\n"
            "• 315,567 historical energy records\n"
            "• Advanced weather simulation\n"
            "• Interactive plotting capabilities\n"
        )
        info_text.config(state='disabled')
        
        # Protocol for window closing
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
            
            self.update_progress(40, "Loaded 9 installations successfully")
            
            # Step 2: Initialize weather simulator
            self.update_progress(50, "Initializing weather simulation...")
            from src.weather_simulation.weather_simulator import WeatherSimulator
            self.weather_simulator = WeatherSimulator("weather_files")
            
            self.update_progress(70, "Weather simulation ready")
            
            # Step 3: Initialize energy predictor (this takes the longest)
            self.update_progress(75, "Training ML models... (this may take a moment)")
            from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
            self.energy_predictor = EnhancedEnergyPredictor(
                self.data_processor, 
                self.weather_simulator
            )
            
            self.update_progress(95, "Saving trained models...")
            self.energy_predictor.save_models()
            
            self.update_progress(100, "Initialization complete!")
            
            # Signal completion
            self.loading_queue.put("COMPLETE")
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            self.loading_queue.put(f"ERROR: {str(e)}")
            
    def start_loading(self):
        """Start the loading process."""
        # Start initialization thread
        self.loading_thread = threading.Thread(target=self.initialize_components_threaded)
        self.loading_thread.daemon = True
        self.loading_thread.start()
        
        # Start checking for completion
        self.check_loading_progress()
        
    def check_loading_progress(self):
        """Check loading progress and handle completion."""
        try:
            # Check if thread has sent a message
            message = self.loading_queue.get_nowait()
            
            if message == "COMPLETE":
                self.on_loading_complete()
            elif message.startswith("ERROR:"):
                self.on_loading_error(message[6:])  # Remove "ERROR:" prefix
            else:
                # Schedule next check
                self.root.after(100, self.check_loading_progress)
                
        except queue.Empty:
            # No message yet, check again soon
            self.root.after(100, self.check_loading_progress)
        except Exception as e:
            logger.error(f"Error checking loading progress: {e}")
            self.on_loading_error(str(e))
            
    def on_loading_complete(self):
        """Handle successful loading completion."""
        try:
            self.is_initialized = True
            logger.info("All components initialized successfully")
            
            # Wait a moment to show completion
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
            # Destroy loading frame
            self.loading_frame.destroy()
            
            # Reconfigure window
            self.root.title("Enhanced FilantropiaSolar - Solar Energy Prediction with Charts")
            self.root.geometry("1200x800")
            self.root.resizable(True, True)
            
            # Create main interface
            self.create_main_gui()
            
            # Show welcome message
            self.show_welcome_message()
            
        except Exception as e:
            logger.error(f"Error transitioning to main GUI: {e}")
            messagebox.showerror("GUI Error", f"Failed to create main interface: {str(e)}")
            self.cleanup_and_exit()
            
    def create_main_gui(self):
        """Create the main GUI interface with plotting."""
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook interface with 3 tabs
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Input tab
        input_frame = ttk.Frame(notebook)
        notebook.add(input_frame, text="📊 Input & Prediction")
        self.create_input_interface(input_frame)
        
        # Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="📋 Results")
        self.create_results_interface(results_frame)
        
        # Charts tab - NEW
        charts_frame = ttk.Frame(notebook)
        notebook.add(charts_frame, text="📈 Charts & Analysis")
        self.create_charts_interface(charts_frame)
        
        # Configure close behavior
        self.root.protocol("WM_DELETE_WINDOW", self.on_main_close)
        
    def create_input_interface(self, parent):
        """Create input interface."""
        # Main container
        container = ttk.Frame(parent, padding="20")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            container, 
            text="Solar Energy Prediction", 
            font=('Arial', 16, 'bold')
        )
        title_label.pack(pady=(0, 20))
        
        # Installation selection
        install_frame = ttk.LabelFrame(container, text="Installation Selection", padding="10")
        install_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(install_frame, text="Choose Installation:").pack(anchor=tk.W)
        
        # Get installation list
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
        
        # Date selection
        date_frame = ttk.LabelFrame(container, text="Date Selection", padding="10")
        date_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(date_frame, text="Select Date:").pack(anchor=tk.W)
        
        # Simple date entry
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = ttk.Entry(date_frame, textvariable=self.date_var, width=20)
        date_entry.pack(anchor=tk.W, pady=(5, 0))
        
        ttk.Label(
            date_frame, 
            text="Format: YYYY-MM-DD (e.g., 2024-06-15)", 
            font=('Arial', 9),
            foreground="gray"
        ).pack(anchor=tk.W, pady=(2, 0))
        
        # Options
        options_frame = ttk.LabelFrame(container, text="Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.simulation_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Use weather simulation for missing data",
            variable=self.simulation_var
        ).pack(anchor=tk.W)
        
        # Predict button
        predict_button = ttk.Button(
            container,
            text="Generate 15-Day Prediction with Charts",
            command=self.on_predict_with_charts,
            style="Accent.TButton"
        )
        predict_button.pack(pady=10)
        
        # Status
        self.input_status_var = tk.StringVar(value="Ready to generate predictions")
        status_label = ttk.Label(container, textvariable=self.input_status_var, foreground="blue")
        status_label.pack(pady=(10, 0))
        
    def create_results_interface(self, parent):
        """Create results interface."""
        container = ttk.Frame(parent, padding="20")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            container,
            text="Prediction Results",
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
        
        # Initial message
        self.update_results_display("No predictions generated yet.\n\nUse the Input tab to generate predictions.")
        
    def create_charts_interface(self, parent):
        """Create charts interface with matplotlib."""
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
            from matplotlib.figure import Figure
            
            # Main container
            container = ttk.Frame(parent, padding="10")
            container.pack(fill=tk.BOTH, expand=True)
            
            # Title
            title_label = ttk.Label(
                container,
                text="Energy Production Charts & Analysis",
                font=('Arial', 16, 'bold')
            )
            title_label.pack(pady=(0, 10))
            
            # Control frame for day navigation
            control_frame = ttk.Frame(container)
            control_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Day selection controls
            ttk.Label(control_frame, text="Navigate Days:").pack(side=tk.LEFT, padx=(0, 10))
            
            self.day_var = tk.IntVar(value=7)  # Start with center date
            
            ttk.Button(control_frame, text="← Prev Day", 
                      command=self.previous_day).pack(side=tk.LEFT, padx=(0, 5))
            
            ttk.Button(control_frame, text="Center", 
                      command=self.center_day).pack(side=tk.LEFT, padx=(0, 5))
            
            ttk.Button(control_frame, text="Next Day →", 
                      command=self.next_day).pack(side=tk.LEFT, padx=(0, 5))
            
            self.day_info_label = ttk.Label(control_frame, text="Day 8 of 15 (Center Date)")
            self.day_info_label.pack(side=tk.LEFT, padx=(20, 0))
            
            # Create matplotlib figure
            self.figure = Figure(figsize=(12, 8), dpi=100, tight_layout=True)
            
            # Create subplots
            gs = self.figure.add_gridspec(2, 2, height_ratios=[2, 1], hspace=0.3, wspace=0.3)
            
            # Energy production plot (top row, spans both columns)
            self.energy_ax = self.figure.add_subplot(gs[0, :])
            
            # Weather plots (bottom row)
            self.temp_ax = self.figure.add_subplot(gs[1, 0])
            self.ranking_ax = self.figure.add_subplot(gs[1, 1])
            
            # Create canvas
            self.canvas = FigureCanvasTkAgg(self.figure, container)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Create navigation toolbar
            toolbar_frame = ttk.Frame(container)
            toolbar_frame.pack(fill=tk.X)
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()
            
            # Initialize empty plots
            self.clear_plots()
            
            # Store reference to matplotlib modules
            self.plt = plt
            
        except ImportError as e:
            # Fallback if matplotlib is not available
            error_label = ttk.Label(
                parent,
                text=f"Charts unavailable: {str(e)}\n\nTo enable charts, install matplotlib:\npip install matplotlib",
                font=('Arial', 12),
                foreground="red",
                justify=tk.CENTER
            )
            error_label.pack(expand=True)
            
    def clear_plots(self):
        """Clear all plots and show placeholder text."""
        if hasattr(self, 'energy_ax'):
            for ax in [self.energy_ax, self.temp_ax, self.ranking_ax]:
                ax.clear()
                ax.text(0.5, 0.5, 'Generate a prediction\nto see charts', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=12, alpha=0.5)
                
            self.energy_ax.set_title('Daily Energy Production')
            self.temp_ax.set_title('Temperature')
            self.ranking_ax.set_title('Rankings')
            
            self.canvas.draw()
            
    def on_predict_with_charts(self):
        """Handle prediction request with charts."""
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
                
            # Parse date
            try:
                date_str = self.date_var.get().strip()
                center_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return
                
            # Update status
            self.input_status_var.set("Generating prediction with charts... Please wait.")
            self.root.update_idletasks()
            
            # Generate prediction
            use_simulation = self.simulation_var.get()
            results = self.energy_predictor.predict_15day_period(
                installation_id, center_date, use_simulation
            )
            
            # Store and display results
            self.current_results = results
            self.display_results(results)
            self.update_charts(results)
            
            # Update status
            self.input_status_var.set(f"Prediction with charts completed for {date_str}")
            
            # Show success message
            installation_info = results['installation_info']
            period_stats = results['period_statistics']
            
            success_msg = (
                f"Prediction completed successfully!\n\n"
                f"Installation: {installation_info['location']} ({installation_info['capacity_kwp']} kWp)\n"
                f"Total Energy (15 days): {period_stats['total_energy_kwh']:.1f} kWh\n"
                f"Average Specific Energy: {period_stats['average_specific_energy']:.2f} kWh/kWp\n\n"
                f"Check the Results and Charts tabs for detailed analysis."
            )
            
            messagebox.showinfo("Prediction Complete", success_msg)
            
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            self.input_status_var.set("Error generating prediction. Check logs.")
            messagebox.showerror("Prediction Error", f"Failed to generate prediction:\n{str(e)}")
            
    def display_results(self, results: Dict[str, Any]):
        """Display prediction results in simple format."""
        try:
            # Format results text (same as before)
            text = "FILANTROPIA SOLAR - PREDICTION RESULTS\n"
            text += "=" * 50 + "\n\n"
            
            # Installation info
            inst_info = results['installation_info']
            text += f"Installation: {inst_info['location']} (Serial: {inst_info['serial_number']})\n"
            text += f"Capacity: {inst_info['capacity_kwp']} kWp\n\n"
            
            # Prediction period
            period = results['prediction_period']
            text += f"Prediction Period: {period['start'].date()} to {period['end'].date()}\n"
            text += f"Center Date: {period['center_date'].date()}\n"
            text += f"Total Hours: {period['total_hours']}\n\n"
            
            # Key statistics
            stats = results['period_statistics']
            text += "KEY STATISTICS (15-day period)\n"
            text += "-" * 40 + "\n"
            text += f"Total Energy: {stats['total_energy_kwh']:.1f} kWh\n"
            text += f"Average Specific Energy: {stats['average_specific_energy']:.2f} kWh/kWp\n"
            text += f"Peak Hour Energy: {stats['peak_hour_energy']:.2f} kWh/kWp\n"
            text += f"Average Temperature: {stats.get('average_temperature', 0):.1f}°C\n"
            text += f"Average Cloud Cover: {stats.get('average_cloud_cover', 0):.1f}%\n\n"
            
            # Daily summary (top 5 days)
            if 'daily_summary' in results:
                daily = results['daily_summary']
                text += "DAILY SUMMARY (Top 5 days)\n"
                text += "-" * 40 + "\n"
                text += f"{'Date':<12} {'Energy(kWh)':<12} {'Ranking':<8}\n"
                text += "-" * 32 + "\n"
                
                # Sort by energy production and show top 5
                daily_sorted = daily.sort_values('predicted_total_energy', ascending=False)
                for i, (date, row) in enumerate(daily_sorted.head(5).iterrows()):
                    energy = row.get('predicted_total_energy', 0)
                    ranking = row.get('ranking', 3)
                    rank_text = {1: 'Poor', 2: 'Below', 3: 'Avg', 4: 'Good', 5: 'Excellent'}.get(ranking, 'Avg')
                    text += f"{str(date):<12} {energy:<12.1f} {rank_text:<8}\n"
            
            # Data source info
            source = results['data_source']
            text += "\nDATA SOURCE\n"
            text += "-" * 40 + "\n"
            text += f"Weather Data: {'Simulated' if source['used_simulation'] else 'Historical'}\n"
            text += f"ML Model: {source['model_used'].replace('_', ' ').title()}\n"
            
            if 'model_performance' in source and source['model_used'] in source['model_performance']:
                perf = source['model_performance'][source['model_used']]
                text += f"Model R²: {perf.get('r2', 0):.3f}\n"
                text += f"Model MAE: {perf.get('mae', 0):.3f} kWh/kWp\n"
                
            # Update display
            self.update_results_display(text)
            
        except Exception as e:
            logger.error(f"Error displaying results: {e}")
            self.update_results_display(f"Error displaying results: {str(e)}")
            
    def update_results_display(self, text: str):
        """Update the results text display."""
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, text)
        self.results_text.config(state='disabled')
        
    def update_charts(self, results: Dict[str, Any]):
        """Update charts with prediction results."""
        if not hasattr(self, 'energy_ax'):
            return
            
        try:
            # Clear existing plots
            for ax in [self.energy_ax, self.temp_ax, self.ranking_ax]:
                ax.clear()
            
            # Get data
            daily_summary = results['daily_summary']
            hourly_data = results['hourly_data']
            
            # Plot 1: Daily Energy Production
            dates = daily_summary.index
            daily_energy = daily_summary['predicted_total_energy']
            
            # Color bars based on ranking
            colors = []
            ranking_colors = {
                1: '#e74c3c', 2: '#e67e22', 3: '#f1c40f', 4: '#2ecc71', 5: '#27ae60'
            }
            
            if 'ranking' in daily_summary.columns:
                colors = [ranking_colors.get(r, '#95a5a6') for r in daily_summary['ranking']]
            else:
                colors = ['#3498db'] * len(dates)
            
            bars = self.energy_ax.bar(dates, daily_energy, color=colors, alpha=0.8)
            
            # Highlight current day
            current_day_index = getattr(self, 'current_day_index', 7)
            if current_day_index < len(bars):
                bars[current_day_index].set_edgecolor('red')
                bars[current_day_index].set_linewidth(3)
            
            self.energy_ax.set_title('Daily Energy Production (kWh)', fontsize=12, fontweight='bold')
            self.energy_ax.set_ylabel('Energy (kWh)')
            self.energy_ax.tick_params(axis='x', rotation=45)
            self.energy_ax.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    self.energy_ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                                       f'{height:.1f}', ha='center', va='bottom', fontsize=8)
            
            # Plot 2: Temperature
            if 'temperature_2m' in hourly_data.columns:
                daily_temps = hourly_data.groupby(hourly_data.index.date)['temperature_2m'].agg(['mean', 'min', 'max'])
                
                self.temp_ax.plot(daily_temps.index, daily_temps['mean'], 'b-', marker='o', linewidth=2)
                self.temp_ax.fill_between(daily_temps.index, daily_temps['min'], daily_temps['max'], 
                                         alpha=0.3, color='blue')
                
                self.temp_ax.set_title('Temperature (°C)', fontsize=10, fontweight='bold')
                self.temp_ax.set_ylabel('Temperature (°C)')
                self.temp_ax.tick_params(axis='x', rotation=45)
                self.temp_ax.grid(True, alpha=0.3)
            
            # Plot 3: Rankings
            if 'ranking' in daily_summary.columns:
                rankings = daily_summary['ranking']
                
                bars = self.ranking_ax.bar(dates, rankings, color=colors, alpha=0.8)
                
                # Highlight current day
                if current_day_index < len(bars):
                    bars[current_day_index].set_edgecolor('red')
                    bars[current_day_index].set_linewidth(3)
                
                self.ranking_ax.set_title('Energy Production Rankings', fontsize=10, fontweight='bold')
                self.ranking_ax.set_ylabel('Ranking (1-5)')
                self.ranking_ax.set_ylim(0, 6)
                self.ranking_ax.set_yticks([1, 2, 3, 4, 5])
                self.ranking_ax.tick_params(axis='x', rotation=45)
                self.ranking_ax.grid(True, alpha=0.3)
            
            # Update canvas
            self.canvas.draw()
            
            # Update day info
            self.update_day_info()
            
        except Exception as e:
            logger.error(f"Error updating charts: {e}")
            
    def previous_day(self):
        """Navigate to previous day."""
        if hasattr(self, 'current_day_index'):
            if self.current_day_index > 0:
                self.current_day_index -= 1
                self.day_var.set(self.current_day_index)
                self.update_day_highlight()
                
    def next_day(self):
        """Navigate to next day."""
        if hasattr(self, 'current_day_index'):
            if self.current_day_index < 14:
                self.current_day_index += 1
                self.day_var.set(self.current_day_index)
                self.update_day_highlight()
                
    def center_day(self):
        """Go to center day."""
        self.current_day_index = 7
        self.day_var.set(7)
        self.update_day_highlight()
        
    def update_day_highlight(self):
        """Update the day highlight in charts."""
        if self.current_results:
            self.update_charts(self.current_results)
            
    def update_day_info(self):
        """Update day information label."""
        if hasattr(self, 'current_day_index'):
            day_num = self.current_day_index + 1
            if self.current_day_index == 7:
                day_text = f"Day {day_num} of 15 (Center Date)"
            elif self.current_day_index < 7:
                days_before = 7 - self.current_day_index
                day_text = f"Day {day_num} of 15 ({days_before} days before center)"
            else:
                days_after = self.current_day_index - 7
                day_text = f"Day {day_num} of 15 ({days_after} days after center)"
            
            if hasattr(self, 'day_info_label'):
                self.day_info_label.config(text=day_text)
        
    def show_welcome_message(self):
        """Show welcome message."""
        if not self.is_initialized:
            return
            
        try:
            data_summary = self.data_processor.get_data_summary()
            
            welcome_msg = (
                f"Welcome to Enhanced FilantropiaSolar with Charts!\n\n"
                f"Successfully loaded:\n"
                f"• {data_summary['total_installations']} PV installations\n"
                f"• {len(data_summary['locations'])} locations across Portugal\n"
                f"• {data_summary['total_records']:,} historical energy records\n"
                f"• Advanced weather simulation capabilities\n"
                f"• Interactive plotting and analysis\n\n"
                f"Features:\n"
                f"• 15-day energy production predictions\n"
                f"• Weather simulation for future dates\n"
                f"• High-accuracy ML models (R² up to 0.945)\n"
                f"• Interactive charts with day navigation\n"
                f"• Comprehensive analysis and rankings\n\n"
                f"Use the Input tab to generate predictions with charts."
            )
            
            messagebox.showinfo("Enhanced FilantropiaSolar", welcome_msg)
            
        except Exception as e:
            logger.error(f"Error showing welcome message: {e}")
            
    def on_main_close(self):
        """Handle main window close."""
        try:
            if messagebox.askyesno("Confirm Exit", "Are you sure you want to exit?"):
                # Save models if needed
                if self.energy_predictor:
                    self.energy_predictor.save_models()
                    
                self.cleanup_and_exit()
        except Exception as e:
            logger.error(f"Error during close: {e}")
            self.cleanup_and_exit()
            
    def run(self):
        """Run the optimized application."""
        try:
            logger.info("Starting Optimized FilantropiaSolar Application with Plots")
            
            # Check prerequisites
            if not Path("data").exists() or not Path("weather_files").exists():
                messagebox.showerror(
                    "Missing Data",
                    "Required directories 'data' and 'weather_files' not found.\n"
                    "Please run the application from the project root directory."
                )
                return
                
            # Create loading GUI
            self.create_loading_gui()
            
            # Start loading process
            self.start_loading()
            
            # Start main loop
            logger.info("Starting GUI main loop")
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
            self.cleanup_and_exit()
        except Exception as e:
            logger.error(f"Fatal error in application: {e}")
            if self.root:
                messagebox.showerror(
                    "Fatal Error",
                    f"A fatal error occurred:\n{str(e)}\n\nThe application will close."
                )
            self.cleanup_and_exit()


def main():
    """Main entry point for optimized application with plots."""
    try:
        app = OptimizedFilantropiaSolarApp()
        app.run()
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()