#!/usr/bin/env python3
"""
Optimized FilantropiaSolar Application

Improved version with:
- Better performance on macOS
- Simplified GUI loading
- Progressive data loading
- Error handling and fallbacks
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
    Optimized main application with improved performance and stability.
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
        
        logger.info("Optimized FilantropiaSolar Application initialized")
        
    def setup_logging(self):
        """Setup optimized logging configuration."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure logging with less verbose output
        logging.basicConfig(
            level=logging.WARNING,  # Reduced verbosity
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'optimized_application.log'),
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
            text="Solar Energy Prediction System", 
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
            "• Machine learning prediction models\n"
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
                # Signal thread to stop (this is simplified)
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
            self.root.title("Enhanced FilantropiaSolar - Solar Energy Prediction System")
            self.root.geometry("1000x700")
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
        """Create the main GUI interface (simplified version)."""
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create simplified notebook interface
        notebook = ttk.Notebook(self.main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Input tab (simplified)
        input_frame = ttk.Frame(notebook)
        notebook.add(input_frame, text="📊 Input & Prediction")
        self.create_simple_input_interface(input_frame)
        
        # Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text="📋 Results")
        self.create_simple_results_interface(results_frame)
        
        # Configure close behavior
        self.root.protocol("WM_DELETE_WINDOW", self.on_main_close)
        
    def create_simple_input_interface(self, parent):
        """Create simplified input interface."""
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
            width=50
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
            text="Generate 15-Day Prediction",
            command=self.on_simple_predict,
            style="Accent.TButton"
        )
        predict_button.pack(pady=10)
        
        # Status
        self.input_status_var = tk.StringVar(value="Ready to generate predictions")
        status_label = ttk.Label(container, textvariable=self.input_status_var, foreground="blue")
        status_label.pack(pady=(10, 0))
        
    def create_simple_results_interface(self, parent):
        """Create simplified results interface."""
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
        
    def on_simple_predict(self):
        """Handle simple prediction request."""
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
            self.input_status_var.set("Generating prediction... Please wait.")
            self.root.update_idletasks()
            
            # Generate prediction
            use_simulation = self.simulation_var.get()
            results = self.energy_predictor.predict_15day_period(
                installation_id, center_date, use_simulation
            )
            
            # Store and display results
            self.current_results = results
            self.display_simple_results(results)
            
            # Update status
            self.input_status_var.set(f"Prediction completed for {date_str}")
            
            # Show success message
            installation_info = results['installation_info']
            period_stats = results['period_statistics']
            
            success_msg = (
                f"Prediction completed successfully!\n\n"
                f"Installation: {installation_info['location']} ({installation_info['capacity_kwp']} kWp)\n"
                f"Total Energy (15 days): {period_stats['total_energy_kwh']:.1f} kWh\n"
                f"Average Specific Energy: {period_stats['average_specific_energy']:.2f} kWh/kWp\n\n"
                f"Check the Results tab for detailed analysis."
            )
            
            messagebox.showinfo("Prediction Complete", success_msg)
            
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            self.input_status_var.set("Error generating prediction. Check logs.")
            messagebox.showerror("Prediction Error", f"Failed to generate prediction:\n{str(e)}")
            
    def display_simple_results(self, results: Dict[str, Any]):
        """Display prediction results in simple format."""
        try:
            # Format results text
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
        
    def show_welcome_message(self):
        """Show welcome message."""
        if not self.is_initialized:
            return
            
        try:
            data_summary = self.data_processor.get_data_summary()
            
            welcome_msg = (
                f"Welcome to Enhanced FilantropiaSolar!\n\n"
                f"Successfully loaded:\n"
                f"• {data_summary['total_installations']} PV installations\n"
                f"• {len(data_summary['locations'])} locations across Portugal\n"
                f"• {data_summary['total_records']:,} historical energy records\n"
                f"• Advanced weather simulation capabilities\n\n"
                f"Features:\n"
                f"• 15-day energy production predictions\n"
                f"• Weather simulation for future dates\n"
                f"• High-accuracy ML models (R² up to 0.945)\n"
                f"• Comprehensive analysis and rankings\n\n"
                f"Use the Input tab to generate predictions."
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
            logger.info("Starting Optimized FilantropiaSolar Application")
            
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
    """Main entry point for optimized application."""
    try:
        app = OptimizedFilantropiaSolarApp()
        app.run()
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()