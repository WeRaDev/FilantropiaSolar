#!/usr/bin/env python3
"""
Enhanced FilantropiaSolar Application

Upgraded version with comprehensive features:
- Loads all PV installations from metadata
- Weather simulation for future dates
- Enhanced GUI with 15-day predictions
- Interactive plot window with day slider
- Rankings and detailed analysis
"""

import sys
import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Import our modules
try:
    from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
    from src.weather_simulation.weather_simulator import WeatherSimulator
    from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
    from src.gui.enhanced_input_window import EnhancedInputWindow
    from src.gui.enhanced_plot_window import EnhancedPlotWindow
    from src.gui.output_window import OutputWindow
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all required modules are installed and paths are correct.")
    sys.exit(1)


class EnhancedFilantropiaSolarApp:
    """
    Enhanced main application for FilantropiaSolar.
    
    Integrates all components for comprehensive solar energy prediction
    with weather simulation and advanced visualization.
    """
    
    def __init__(self):
        """Initialize the enhanced application."""
        self.setup_logging()
        self.setup_directories()
        
        # Core components
        self.data_processor = None
        self.weather_simulator = None
        self.energy_predictor = None
        
        # GUI components
        self.root = None
        self.input_window = None
        self.output_window = None
        self.plot_window = None
        
        # Current prediction results
        self.current_results = None
        
        logger.info("Enhanced FilantropiaSolar Application initialized")
        
    def setup_logging(self):
        """Setup logging configuration."""
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'enhanced_application.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        global logger
        logger = logging.getLogger(__name__)
        
    def setup_directories(self):
        """Setup necessary directories."""
        directories = ['logs', 'models', 'exports', 'cache']
        for dir_name in directories:
            Path(dir_name).mkdir(exist_ok=True)
            logger.info(f"Directory '{dir_name}' ready")
            
    def initialize_components(self):
        """Initialize core application components."""
        try:
            logger.info("Initializing application components...")
            
            # Initialize data processor
            logger.info("Loading data processor...")
            self.data_processor = ComprehensiveDataProcessor()
            
            # Print data summary
            data_summary = self.data_processor.get_data_summary()
            logger.info(f"Data Summary: {data_summary}")
            
            # Initialize weather simulator
            logger.info("Initializing weather simulator...")
            self.weather_simulator = WeatherSimulator("weather_files")
            
            # Initialize energy predictor
            logger.info("Training energy prediction models...")
            self.energy_predictor = EnhancedEnergyPredictor(
                self.data_processor, 
                self.weather_simulator
            )
            
            # Save trained models
            self.energy_predictor.save_models()
            
            logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            messagebox.showerror(
                "Initialization Error", 
                f"Failed to initialize application components:\n{str(e)}"
            )
            return False
            
    def create_gui(self):
        """Create the main GUI interface."""
        try:
            logger.info("Creating GUI interface...")
            
            # Create main window
            self.root = tk.Tk()
            self.root.title("Enhanced FilantropiaSolar - Solar Energy Prediction System")
            self.root.geometry("1400x900")
            self.root.minsize(1200, 800)
            
            # Configure styles
            style = ttk.Style()
            style.theme_use('clam')
            
            # Create main notebook for different windows
            main_notebook = ttk.Notebook(self.root, padding="10")
            main_notebook.pack(fill=tk.BOTH, expand=True)
            
            # Input window tab
            input_frame = ttk.Frame(main_notebook)
            main_notebook.add(input_frame, text="📊 Input & Prediction")
            
            self.input_window = EnhancedInputWindow(
                input_frame, 
                self.data_processor, 
                self.on_predict_requested
            )
            
            # Output window tab
            output_frame = ttk.Frame(main_notebook)
            main_notebook.add(output_frame, text="📋 Results & Analysis")
            
            self.output_window = OutputWindow(output_frame)
            
            # Plot window tab
            plot_frame = ttk.Frame(main_notebook)
            main_notebook.add(plot_frame, text="📈 Interactive Plots")
            
            self.plot_window = EnhancedPlotWindow(plot_frame)
            
            # Configure window close behavior
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            # Center window on screen
            self.center_window()
            
            logger.info("GUI interface created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create GUI: {e}")
            messagebox.showerror("GUI Error", f"Failed to create GUI interface:\n{str(e)}")
            raise
            
    def center_window(self):
        """Center the main window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
    def on_predict_requested(self, installation_id: str, center_date: datetime, use_simulation: bool):
        """Handle prediction request from input window."""
        try:
            logger.info(f"Prediction requested for {installation_id} on {center_date.date()} "
                       f"(simulation: {use_simulation})")
            
            # Show progress
            self.root.config(cursor="wait")
            self.root.update()
            
            # Generate prediction
            results = self.energy_predictor.predict_15day_period(
                installation_id, center_date, use_simulation
            )
            
            # Store results
            self.current_results = results
            
            # Update output window
            self.output_window.display_results(results)
            
            # Update plot window
            self.plot_window.update_prediction_data(results)
            
            # Show success message
            installation_info = results['installation_info']
            period_stats = results['period_statistics']
            
            success_msg = (
                f"Prediction completed successfully!\n\n"
                f"Installation: {installation_info['location']} ({installation_info['capacity_kwp']} kWp)\n"
                f"Period: {results['prediction_period']['start'].strftime('%Y-%m-%d')} to "
                f"{results['prediction_period']['end'].strftime('%Y-%m-%d')}\n"
                f"Total Energy (15 days): {period_stats['total_energy_kwh']:.1f} kWh\n"
                f"Average Specific Energy: {period_stats['average_specific_energy']:.2f} kWh/kWp\n\n"
                f"Check the Results and Interactive Plots tabs for detailed analysis."
            )
            
            messagebox.showinfo("Prediction Complete", success_msg)
            
            logger.info("Prediction completed and results displayed")
            
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            messagebox.showerror(
                "Prediction Error", 
                f"Failed to generate prediction:\n{str(e)}"
            )
        finally:
            self.root.config(cursor="")
            
    def export_results(self):
        """Export current results to files."""
        if not self.current_results:
            messagebox.showwarning("No Results", "No prediction results to export.")
            return
            
        try:
            from tkinter import filedialog
            
            # Get export directory
            export_dir = filedialog.askdirectory(
                title="Select Export Directory",
                initialdir="exports"
            )
            
            if not export_dir:
                return
                
            export_path = Path(export_dir)
            
            # Generate filename base
            installation_id = self.current_results['installation_id']
            center_date = self.current_results['prediction_period']['center_date']
            filename_base = f"{installation_id}_{center_date.strftime('%Y%m%d')}"
            
            # Export hourly data
            hourly_file = export_path / f"{filename_base}_hourly.csv"
            self.current_results['hourly_data'].to_csv(hourly_file)
            
            # Export daily summary
            daily_file = export_path / f"{filename_base}_daily.csv"
            self.current_results['daily_summary'].to_csv(daily_file)
            
            # Export summary statistics
            summary_file = export_path / f"{filename_base}_summary.txt"
            with open(summary_file, 'w') as f:
                f.write(f"FilantropiaSolar Prediction Results\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"\nInstallation: {self.current_results['installation_info']}\n")
                f.write(f"\nPrediction Period: {self.current_results['prediction_period']}\n")
                f.write(f"\nStatistics: {self.current_results['period_statistics']}\n")
                f.write(f"\nData Source: {self.current_results['data_source']}\n")
                
            messagebox.showinfo(
                "Export Complete", 
                f"Results exported to:\n{export_path}\n\nFiles exported:\n"
                f"- {hourly_file.name}\n- {daily_file.name}\n- {summary_file.name}"
            )
            
            logger.info(f"Results exported to {export_path}")
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            messagebox.showerror("Export Error", f"Failed to export results:\n{str(e)}")
            
    def on_closing(self):
        """Handle application closing."""
        try:
            logger.info("Application closing...")
            
            # Save any unsaved data or models if needed
            if self.energy_predictor:
                self.energy_predictor.save_models()
                
            # Clean up resources
            if self.root:
                self.root.quit()
                self.root.destroy()
                
            logger.info("Application closed successfully")
            
        except Exception as e:
            logger.error(f"Error during application closing: {e}")
        finally:
            sys.exit(0)
            
    def run(self):
        """Run the enhanced application."""
        try:
            logger.info("Starting Enhanced FilantropiaSolar Application")
            
            # Initialize components
            if not self.initialize_components():
                return
                
            # Create GUI
            self.create_gui()
            
            # Show welcome message
            welcome_msg = (
                f"Welcome to Enhanced FilantropiaSolar!\n\n"
                f"Loaded {self.data_processor.get_data_summary()['total_installations']} installations "
                f"across {len(self.data_processor.get_locations())} locations.\n\n"
                f"Features:\n"
                f"• All Portuguese PV installations\n"
                f"• Weather simulation for future dates\n"
                f"• 15-day energy production predictions\n"
                f"• Interactive plots with day slider\n"
                f"• Comprehensive rankings and analysis\n\n"
                f"Select an installation and date in the Input tab to begin."
            )
            
            messagebox.showinfo("Enhanced FilantropiaSolar", welcome_msg)
            
            # Start GUI main loop
            logger.info("Starting GUI main loop")
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
            self.on_closing()
        except Exception as e:
            logger.error(f"Fatal error in application: {e}")
            if self.root:
                messagebox.showerror(
                    "Fatal Error", 
                    f"A fatal error occurred:\n{str(e)}\n\nThe application will close."
                )
            self.on_closing()


def main():
    """Main entry point."""
    try:
        # Check if we're in the right directory
        if not Path("data").exists() or not Path("weather_files").exists():
            print("Error: Required directories 'data' and 'weather_files' not found.")
            print("Please run the application from the project root directory.")
            sys.exit(1)
            
        # Create and run the application
        app = EnhancedFilantropiaSolarApp()
        app.run()
        
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()