#!/usr/bin/env python3
"""
FilantropiaSolar - Simple GUI Application (Without Weather API)
Uses historical data for reliable testing and demonstration
"""

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.data_processing.lisbon_data_processor import LisbonDataProcessor
from src.prediction.energy_predictor import EnergyPredictor
from src.utils.energy_ranking import get_ranking_description, get_ranking_color, calculate_average_ranking


class SimpleFTSolarApp:
    """Simplified FilantropiaSolar GUI application"""
    
    def __init__(self):
        """Initialize the application"""
        self.root = tk.Tk()
        self.root.title("FilantropiaSolar - Solar Energy Prediction System")
        self.root.geometry("1200x800")
        
        # Initialize components
        self.data_processor = LisbonDataProcessor()
        self.predictors = {}
        
        # Variables
        self.selected_installation = tk.StringVar(value="Lisbon_1")
        self.selected_date = tk.StringVar(value="2022-06-15")  # Use valid historical date (2019-2022 range)
        self.installed_capacity = tk.DoubleVar(value=10.0)
        
        # Data storage
        self.current_predictions = pd.DataFrame()
        self.available_dates = []
        
        # Setup GUI and load data
        self.setup_gui()
        self.load_data_async()
        
    def setup_gui(self):
        """Setup the GUI layout"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create frames
        self.create_input_frame(main_container)
        self.create_output_frame(main_container)
        self.create_plot_frame(main_container)
        
    def create_input_frame(self, parent):
        """Create input controls frame"""
        # Input Frame
        input_frame = ttk.LabelFrame(parent, text="Input Parameters", padding=10)
        input_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))
        
        # Installation selection
        ttk.Label(input_frame, text="PV Installation:").grid(row=0, column=0, sticky="w", pady=2)
        installation_combo = ttk.Combobox(
            input_frame, 
            textvariable=self.selected_installation,
            values=["Lisbon_1", "Lisbon_2", "Lisbon_3", "Lisbon_4"],
            state="readonly",
            width=15
        )
        installation_combo.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=2)
        
        # Date selection (using historical data)
        ttk.Label(input_frame, text="Historical Date:").grid(row=1, column=0, sticky="w", pady=2)
        self.date_entry = ttk.Entry(input_frame, textvariable=self.selected_date, width=15)
        self.date_entry.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=2)
        
        # Data range info
        range_label = ttk.Label(input_frame, text="(2019-2022 data available)", font=('TkDefaultFont', 8), foreground="gray")
        range_label.grid(row=1, column=3, sticky="w", padx=(5, 0), pady=2)
        
        # Example dates button
        example_btn = ttk.Button(
            input_frame, 
            text="Example Dates", 
            command=self.show_example_dates,
            width=12
        )
        example_btn.grid(row=1, column=2, sticky="w", padx=(5, 0), pady=2)
        
        # Installed capacity
        ttk.Label(input_frame, text="Installed Capacity (kWp):").grid(row=2, column=0, sticky="w", pady=2)
        capacity_entry = ttk.Entry(input_frame, textvariable=self.installed_capacity, width=15)
        capacity_entry.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=2)
        
        # Predict button
        self.predict_btn = ttk.Button(
            input_frame, 
            text="Generate Prediction", 
            command=self.generate_prediction,
            width=20
        )
        self.predict_btn.grid(row=3, column=0, columnspan=3, pady=10)
        
        # Status label
        self.status_label = ttk.Label(input_frame, text="Loading data...", foreground="orange")
        self.status_label.grid(row=4, column=0, columnspan=3, pady=5)
        
    def create_output_frame(self, parent):
        """Create output display frame"""
        # Output Frame
        output_frame = ttk.LabelFrame(parent, text="Prediction Results", padding=10)
        output_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=(0, 5))
        
        # Results text with scrollbar
        results_container = ttk.Frame(output_frame)
        results_container.grid(row=0, column=0, sticky="nsew")
        
        self.results_text = tk.Text(
            results_container, 
            height=15, 
            width=50, 
            wrap=tk.WORD,
            font=("Courier", 10)
        )
        
        scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        results_container.columnconfigure(0, weight=1)
        results_container.rowconfigure(0, weight=1)
        
        # Export button
        export_btn = ttk.Button(
            output_frame, 
            text="Export Results", 
            command=self.export_results,
            width=15
        )
        export_btn.grid(row=1, column=0, pady=10)
        
        # Configure weights
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
    def create_plot_frame(self, parent):
        """Create plot display frame"""
        # Plot Frame
        plot_frame = ttk.LabelFrame(parent, text="Energy Production Chart (Historical Analysis)", padding=10)
        plot_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(12, 5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initial empty plot
        self.ax.set_title("Historical Energy Production Analysis")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Energy Production (kWh)")
        self.fig.tight_layout()
        
        # Configure weights
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)
        
    def load_data_async(self):
        """Load data in background"""
        def load_data():
            try:
                # Load PV and weather data
                self.data_processor.load_pv_data()
                self.data_processor.load_weather_data()
                
                # Train models for all installations
                for installation in ["Lisbon_1", "Lisbon_2", "Lisbon_3", "Lisbon_4"]:
                    self.predictors[installation] = EnergyPredictor(installation)
                    merged_data = self.data_processor.merge_pv_weather_data(installation)
                    if not merged_data.empty:
                        self.predictors[installation].train_models(merged_data)
                
                # Get available dates from historical data
                if not self.data_processor.weather_data.empty:
                    dates = pd.to_datetime(self.data_processor.weather_data['time']).dt.date.unique()
                    self.available_dates = sorted([d.strftime('%Y-%m-%d') for d in dates])
                
                self.status_label.config(text="Ready - Historical data loaded", foreground="green")
                
            except Exception as e:
                self.status_label.config(text=f"Error: {str(e)}", foreground="red")
        
        # Run in background (simplified - in a real app, use threading)
        self.root.after(100, load_data)
        
    def show_example_dates(self):
        """Show example historical dates"""
        if self.available_dates:
            # Show examples from different seasons and years
            examples = [
                "2019-06-21",  # Summer solstice 2019
                "2019-12-21",  # Winter solstice 2019
                "2020-03-20",  # Spring equinox 2020
                "2020-09-22",  # Autumn equinox 2020
                "2021-07-15",  # Summer 2021
                "2021-01-15",  # Winter 2021
                "2022-06-15",  # Summer 2022 (default)
                "2022-08-30",  # Late summer 2022
                "2022-11-15"   # Autumn 2022
            ]
            
            # Filter to only show dates that exist in our dataset
            valid_examples = [date for date in examples if date in self.available_dates]
            
            example_text = f"Historical data range: 2019-01-01 to 2022-12-31\n\n"
            example_text += "Example dates to try:\n" + "\n".join(valid_examples[:8])
            example_text += "\n\nNote: Use YYYY-MM-DD format"
            messagebox.showinfo("Example Dates", example_text)
        else:
            messagebox.showinfo("Example Dates", "Historical data not loaded yet")
            
    def generate_prediction(self):
        """Generate prediction using historical data"""
        try:
            self.status_label.config(text="Generating prediction...", foreground="orange")
            self.root.update()
            
            installation = self.selected_installation.get()
            target_date = self.selected_date.get()
            capacity = self.installed_capacity.get()
            
            # Validate inputs
            try:
                target_datetime = datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
                self.status_label.config(text="Ready", foreground="green")
                return
            
            if capacity <= 0:
                messagebox.showerror("Error", "Installed capacity must be greater than 0")
                self.status_label.config(text="Ready", foreground="green")
                return
            
            # Get historical weather data around the target date
            target_date_obj = pd.to_datetime(target_date).date()
            
            # Find data for ±7 days around target date
            start_date = target_date_obj - timedelta(days=7)
            end_date = target_date_obj + timedelta(days=7)
            
            weather_subset = self.data_processor.weather_data.copy()
            weather_subset['date'] = pd.to_datetime(weather_subset['time']).dt.date
            
            # Filter for the date range
            mask = (weather_subset['date'] >= start_date) & (weather_subset['date'] <= end_date)
            weather_data = weather_subset[mask].copy()
            
            if weather_data.empty:
                messagebox.showerror("Error", f"No historical data available for {target_date}")
                self.status_label.config(text="Ready", foreground="green")
                return
            
            # Make predictions
            predictor = self.predictors.get(installation)
            if predictor is None or not predictor.is_trained:
                messagebox.showerror("Error", f"Model not trained for {installation}")
                self.status_label.config(text="Ready", foreground="green")
                return
            
            # Drop the temporary 'date' column
            weather_data = weather_data.drop('date', axis=1)
            
            predictions = predictor.predict_energy(weather_data, capacity)
            
            if predictions.empty:
                messagebox.showerror("Error", "Failed to generate predictions")
                self.status_label.config(text="Ready", foreground="green")
                return
            
            self.current_predictions = predictions
            
            # Update displays
            self.update_results_display(target_date, installation, capacity)
            self.update_plot(target_date)
            
            self.status_label.config(text="Prediction completed", foreground="green")
            
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", foreground="red")
            messagebox.showerror("Error", f"Failed to generate prediction: {str(e)}")
            
    def update_results_display(self, target_date, installation, capacity):
        """Update the results text display"""
        try:
            # Clear previous results
            self.results_text.delete(1.0, tk.END)
            
            if self.current_predictions.empty:
                self.results_text.insert(tk.END, "No prediction data available")
                return
            
            # Filter data for target date
            target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            target_day_data = self.current_predictions[
                pd.to_datetime(self.current_predictions['time']).dt.date == target_dt
            ]
            
            if not target_day_data.empty:
                daily_energy = target_day_data['Predicted Energy (kWh)'].sum()
                avg_specific_energy = target_day_data['Specific Energy (kWh/kWp)'].mean()
                avg_ranking = target_day_data['Ranking'].mean()
                
                # Weather summary
                avg_temp = target_day_data['temperature_2m (°C)'].mean() if 'temperature_2m (°C)' in target_day_data.columns else 0
                avg_cloud = target_day_data['cloud_cover (%)'].mean() if 'cloud_cover (%)' in target_day_data.columns else 0
                avg_radiation = target_day_data['shortwave_radiation (W/m²)'].mean() if 'shortwave_radiation (W/m²)' in target_day_data.columns else 0
                
                # Format results
                results_text = f"""HISTORICAL ENERGY ANALYSIS
{'='*40}

Installation: {installation}
Target Date: {target_date}
Installed Capacity: {capacity} kWp

DAILY SUMMARY
{'-'*20}
Total Energy Production: {daily_energy:.2f} kWh
Average Specific Energy: {avg_specific_energy:.3f} kWh/kWp
Average Ranking: {avg_ranking:.1f}/5 ({get_ranking_description(int(round(avg_ranking)))})

HISTORICAL WEATHER CONDITIONS
{'-'*30}
Average Temperature: {avg_temp:.1f}°C
Average Cloud Cover: {avg_cloud:.1f}%
Average Solar Radiation: {avg_radiation:.1f} W/m²

HOURLY BREAKDOWN
{'-'*20}
"""
                
                # Add hourly breakdown
                for _, row in target_day_data.iterrows():
                    hour = pd.to_datetime(row['time']).hour
                    energy = row['Predicted Energy (kWh)']
                    ranking = int(row['Ranking'])
                    
                    results_text += f"Hour {hour:2d}: {energy:5.2f} kWh (Rank {ranking})\n"
                
                # Add weekly trend
                weekly_summary = self.current_predictions.groupby(
                    pd.to_datetime(self.current_predictions['time']).dt.date
                )['Predicted Energy (kWh)'].sum()
                
                results_text += f"\nWEEKLY ANALYSIS (±7 days)\n{'-'*28}\n"
                for date, daily_total in weekly_summary.items():
                    date_str = date.strftime('%Y-%m-%d')
                    marker = " ← TARGET" if date == target_dt else ""
                    results_text += f"{date_str}: {daily_total:6.2f} kWh{marker}\n"
                
            else:
                results_text = f"No historical data available for {target_date}"
            
            self.results_text.insert(tk.END, results_text)
            
        except Exception as e:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Error displaying results: {str(e)}")
            
    def update_plot(self, target_date):
        """Update the energy production plot"""
        try:
            # Clear previous plot
            self.ax.clear()
            
            if self.current_predictions.empty:
                self.ax.text(0.5, 0.5, 'No data to plot', transform=self.ax.transAxes, 
                            ha='center', va='center', fontsize=12)
                self.canvas.draw()
                return
            
            # Prepare data for plotting
            df = self.current_predictions.copy()
            df['datetime'] = pd.to_datetime(df['time'])
            df['date'] = df['datetime'].dt.date
            
            # Daily aggregation
            daily_data = df.groupby('date').agg({
                'Predicted Energy (kWh)': 'sum',
                'Ranking': 'mean',
                'temperature_2m (°C)': 'mean' if 'temperature_2m (°C)' in df.columns else lambda x: 0
            }).reset_index()
            
            # Create main energy production plot
            ax1 = self.ax
            bars = ax1.bar(daily_data['date'], daily_data['Predicted Energy (kWh)'], 
                          color='skyblue', alpha=0.7, label='Energy Production')
            
            ax1.set_xlabel('Date')
            ax1.set_ylabel('Daily Energy Production (kWh)', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            ax1.set_title('Historical Solar Energy Production Analysis')
            
            # Add ranking colors to bars
            for i, (bar, ranking) in enumerate(zip(bars, daily_data['Ranking'])):
                color = get_ranking_color(int(round(ranking)))
                bar.set_edgecolor(color)
                bar.set_linewidth(2)
            
            # Secondary axis for temperature
            if 'temperature_2m (°C)' in df.columns:
                ax2 = ax1.twinx()
                ax2.plot(daily_data['date'], daily_data['temperature_2m (°C)'], 
                        color='red', marker='o', linewidth=2, markersize=4, 
                        label='Temperature')
                ax2.set_ylabel('Temperature (°C)', color='red')
                ax2.tick_params(axis='y', labelcolor='red')
            
            # Highlight target date
            target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
            if target_date_obj in daily_data['date'].values:
                ax1.axvline(x=target_date_obj, color='green', linestyle='--', linewidth=2, alpha=0.7)
                ax1.text(target_date_obj, ax1.get_ylim()[1] * 0.9, 
                        'TARGET', ha='center', va='center', fontweight='bold', color='green')
            
            # Format x-axis
            import matplotlib.dates as mdates
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax1.xaxis.set_major_locator(mdates.DayLocator(interval=2))
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            # Add ranking legend
            ranking_text = "Ranking Colors:\n"
            for rank in range(1, 6):
                color = get_ranking_color(rank)
                description = get_ranking_description(rank).split('(')[0].strip()
                ranking_text += f"■ Rank {rank}: {description}\n"
            
            ax1.text(0.02, 0.98, ranking_text, transform=ax1.transAxes, 
                    va='top', ha='left', fontsize=8, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
            
            self.fig.tight_layout()
            self.canvas.draw()
            
        except Exception as e:
            self.ax.clear()
            self.ax.text(0.5, 0.5, f'Error creating plot: {str(e)}', 
                        transform=self.ax.transAxes, ha='center', va='center')
            self.canvas.draw()
            
    def export_results(self):
        """Export prediction results to CSV"""
        try:
            if self.current_predictions.empty:
                messagebox.showwarning("Warning", "No data to export")
                return
            
            installation = self.selected_installation.get()
            target_date = self.selected_date.get()
            filename = f"historical_analysis_{installation}_{target_date}.csv"
            
            self.current_predictions.to_csv(filename, index=False)
            messagebox.showinfo("Success", f"Results exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export results: {str(e)}")
            
    def run(self):
        """Run the application"""
        self.root.mainloop()


def main():
    """Main function"""
    app = SimpleFTSolarApp()
    app.run()


if __name__ == "__main__":
    main()