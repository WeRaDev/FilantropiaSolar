"""
Main GUI Application for FilantropiaSolar
Provides three-window interface: Input, Output, and Plot windows
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.data_processing.lisbon_data_processor import LisbonDataProcessor
from src.weather_api.weather_client import WeatherClient
from src.prediction.energy_predictor import EnergyPredictor
from src.utils.energy_ranking import get_ranking_description, get_ranking_color


class FilantropiaSolarApp:
    """Main application class for FilantropiaSolar GUI"""

    def __init__(self):
        """Initialize the application"""
        self.root = tk.Tk()
        self.root.title("FilantropiaSolar - Solar Energy Prediction System")
        self.root.geometry("1400x900")

        # Initialize components
        self.data_processor = LisbonDataProcessor()
        self.weather_client = WeatherClient()
        self.predictors = {}  # Dictionary of predictors for each installation

        # Variables
        self.selected_installation = tk.StringVar(value="Lisbon_1")
        self.selected_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.installed_capacity = tk.DoubleVar(value=10.0)

        # Data storage
        self.current_predictions = pd.DataFrame()
        self.current_weather = {}

        # Initialize GUI
        self.setup_gui()
        self.load_data()

    def setup_gui(self):
        """Setup the main GUI layout"""
        # Configure style
        style = ttk.Style()
        style.theme_use("clam")

        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create three main frames
        self.create_input_window(main_container)
        self.create_output_window(main_container)
        self.create_plot_window(main_container)

    def create_input_window(self, parent):
        """Create input window frame"""
        # Input Frame
        input_frame = ttk.LabelFrame(parent, text="Input Parameters", padding=10)
        input_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))

        # Installation selection
        ttk.Label(input_frame, text="PV Installation:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        installation_combo = ttk.Combobox(
            input_frame,
            textvariable=self.selected_installation,
            values=["Lisbon_1", "Lisbon_2", "Lisbon_3", "Lisbon_4"],
            state="readonly",
            width=15,
        )
        installation_combo.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=2)

        # Date selection
        ttk.Label(input_frame, text="Target Date:").grid(
            row=1, column=0, sticky="w", pady=2
        )
        date_entry = ttk.Entry(input_frame, textvariable=self.selected_date, width=15)
        date_entry.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=2)

        # Today button
        today_btn = ttk.Button(
            input_frame,
            text="Today",
            command=lambda: self.selected_date.set(datetime.now().strftime("%Y-%m-%d")),
            width=8,
        )
        today_btn.grid(row=1, column=2, sticky="w", padx=(5, 0), pady=2)

        # Installed capacity
        ttk.Label(input_frame, text="Installed Capacity (kWp):").grid(
            row=2, column=0, sticky="w", pady=2
        )
        capacity_entry = ttk.Entry(
            input_frame, textvariable=self.installed_capacity, width=15
        )
        capacity_entry.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=2)

        # Predict button
        predict_btn = ttk.Button(
            input_frame,
            text="Generate Prediction",
            command=self.generate_prediction,
            width=20,
        )
        predict_btn.grid(row=3, column=0, columnspan=3, pady=10)

        # Status label
        self.status_label = ttk.Label(input_frame, text="Ready", foreground="green")
        self.status_label.grid(row=4, column=0, columnspan=3, pady=5)

    def create_output_window(self, parent):
        """Create output window frame"""
        # Output Frame
        output_frame = ttk.LabelFrame(parent, text="Prediction Results", padding=10)
        output_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=(0, 5))

        # Results text widget with scrollbar
        results_frame = ttk.Frame(output_frame)
        results_frame.grid(row=0, column=0, sticky="nsew")

        self.results_text = tk.Text(
            results_frame, height=15, width=50, wrap=tk.WORD, font=("Courier", 10)
        )

        scrollbar = ttk.Scrollbar(
            results_frame, orient="vertical", command=self.results_text.yview
        )
        self.results_text.configure(yscrollcommand=scrollbar.set)

        self.results_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        # Export button
        export_btn = ttk.Button(
            output_frame, text="Export Results", command=self.export_results, width=15
        )
        export_btn.grid(row=1, column=0, pady=10)

    def create_plot_window(self, parent):
        """Create plot window frame"""
        # Plot Frame
        plot_frame = ttk.LabelFrame(
            parent, text="Energy Production Chart (±7 days)", padding=10
        )
        plot_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

        # Create matplotlib figure
        self.fig = Figure(figsize=(14, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)

        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Initial empty plot
        self.ax.set_title("Energy Production Forecast")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Energy Production (kWh)")
        self.fig.tight_layout()

        # Configure grid weights
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

    def load_data(self):
        """Load historical data and initialize predictors"""
        try:
            self.status_label.config(text="Loading data...", foreground="orange")
            self.root.update()

            # Load PV and weather data
            self.data_processor.load_pv_data()
            self.data_processor.load_weather_data()

            # Initialize predictors for each installation
            for installation in ["Lisbon_1", "Lisbon_2", "Lisbon_3", "Lisbon_4"]:
                self.predictors[installation] = EnergyPredictor(installation)

                # Try to load pre-trained model or train new one
                model_path = f"models/{installation}_model.pkl"
                if Path(model_path).exists():
                    self.predictors[installation].load_model(model_path)
                else:
                    # Train model with historical data
                    merged_data = self.data_processor.merge_pv_weather_data(
                        installation
                    )
                    if not merged_data.empty:
                        self.predictors[installation].train_models(merged_data)

            self.status_label.config(
                text="Data loaded successfully", foreground="green"
            )

        except Exception as e:
            self.status_label.config(
                text=f"Error loading data: {str(e)}", foreground="red"
            )
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")

    def generate_prediction(self):
        """Generate energy production prediction"""
        try:
            self.status_label.config(
                text="Generating prediction...", foreground="orange"
            )
            self.root.update()

            installation = self.selected_installation.get()
            target_date = self.selected_date.get()
            capacity = self.installed_capacity.get()

            # Validate inputs
            try:
                target_datetime = datetime.strptime(target_date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
                return

            if capacity <= 0:
                messagebox.showerror(
                    "Error", "Installed capacity must be greater than 0"
                )
                return

            # Get weather data for ±7 days
            weather_data = self.weather_client.get_weather_for_date_range(
                target_date, days_before=7, days_after=7
            )

            if weather_data.empty:
                messagebox.showerror("Error", "Could not retrieve weather data")
                return

            # Make predictions
            predictor = self.predictors.get(installation)
            if predictor is None or not predictor.is_trained:
                messagebox.showerror(
                    "Error", f"No trained model available for {installation}"
                )
                return

            predictions = predictor.predict_energy(weather_data, capacity)

            if predictions.empty:
                messagebox.showerror("Error", "Failed to generate predictions")
                return

            self.current_predictions = predictions

            # Update displays
            self.update_results_display(target_date, installation, capacity)
            self.update_plot()

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
                pd.to_datetime(self.current_predictions["time"]).dt.date == target_dt
            ]

            # Calculate summary statistics
            if not target_day_data.empty:
                daily_energy = target_day_data["Predicted Energy (kWh)"].sum()
                avg_specific_energy = target_day_data[
                    "Specific Energy (kWh/kWp)"
                ].mean()
                avg_ranking = target_day_data["Ranking"].mean()

                # Weather summary
                avg_temp = (
                    target_day_data["temperature_2m (°C)"].mean()
                    if "temperature_2m (°C)" in target_day_data.columns
                    else 0
                )
                avg_cloud = (
                    target_day_data["cloud_cover (%)"].mean()
                    if "cloud_cover (%)" in target_day_data.columns
                    else 0
                )
                avg_radiation = (
                    target_day_data["shortwave_radiation (W/m²)"].mean()
                    if "shortwave_radiation (W/m²)" in target_day_data.columns
                    else 0
                )

                # Format results
                results_text = f"""ENERGY PRODUCTION FORECAST
{"=" * 40}

Installation: {installation}
Target Date: {target_date}
Installed Capacity: {capacity} kWp

DAILY SUMMARY
{"-" * 20}
Total Energy Production: {daily_energy:.2f} kWh
Average Specific Energy: {avg_specific_energy:.3f} kWh/kWp
Average Ranking: {avg_ranking:.1f}/5 ({get_ranking_description(int(round(avg_ranking)))})

WEATHER CONDITIONS
{"-" * 20}
Average Temperature: {avg_temp:.1f}°C
Average Cloud Cover: {avg_cloud:.1f}%
Average Solar Radiation: {avg_radiation:.1f} W/m²

HOURLY BREAKDOWN
{"-" * 20}
"""

                # Add hourly breakdown
                for _, row in target_day_data.iterrows():
                    hour = pd.to_datetime(row["time"]).hour
                    energy = row["Predicted Energy (kWh)"]
                    ranking = int(row["Ranking"])

                    results_text += (
                        f"Hour {hour:2d}: {energy:5.2f} kWh (Rank {ranking})\n"
                    )

                # Add weekly trend if available
                weekly_summary = self.current_predictions.groupby(
                    pd.to_datetime(self.current_predictions["time"]).dt.date
                )["Predicted Energy (kWh)"].sum()

                results_text += f"\nWEEKLY TREND (±7 days)\n{'-' * 25}\n"
                for date, daily_total in weekly_summary.items():
                    date_str = date.strftime("%Y-%m-%d")
                    marker = " ← TARGET" if date == target_dt else ""
                    results_text += f"{date_str}: {daily_total:6.2f} kWh{marker}\n"

            else:
                results_text = f"No data available for {target_date}"

            self.results_text.insert(tk.END, results_text)

        except Exception as e:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Error displaying results: {str(e)}")

    def update_plot(self):
        """Update the energy production plot"""
        try:
            # Clear previous plot
            self.ax.clear()

            if self.current_predictions.empty:
                self.ax.text(
                    0.5,
                    0.5,
                    "No data to plot",
                    transform=self.ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=12,
                )
                self.canvas.draw()
                return

            # Prepare data for plotting
            df = self.current_predictions.copy()
            df["datetime"] = pd.to_datetime(df["time"])
            df["date"] = df["datetime"].dt.date

            # Daily aggregation
            daily_data = (
                df.groupby("date")
                .agg(
                    {
                        "Predicted Energy (kWh)": "sum",
                        "Ranking": "mean",
                        "temperature_2m (°C)": "mean"
                        if "temperature_2m (°C)" in df.columns
                        else lambda x: 0,
                    }
                )
                .reset_index()
            )

            # Create main energy production plot
            ax1 = self.ax
            bars = ax1.bar(
                daily_data["date"],
                daily_data["Predicted Energy (kWh)"],
                color="skyblue",
                alpha=0.7,
                label="Energy Production",
            )

            ax1.set_xlabel("Date")
            ax1.set_ylabel("Daily Energy Production (kWh)", color="blue")
            ax1.tick_params(axis="y", labelcolor="blue")
            ax1.set_title("Solar Energy Production Forecast (±7 days)")

            # Add ranking colors to bars
            for i, (bar, ranking) in enumerate(zip(bars, daily_data["Ranking"])):
                color = get_ranking_color(int(round(ranking)))
                bar.set_edgecolor(color)
                bar.set_linewidth(2)

            # Secondary axis for temperature
            if "temperature_2m (°C)" in df.columns:
                ax2 = ax1.twinx()
                ax2.plot(
                    daily_data["date"],
                    daily_data["temperature_2m (°C)"],
                    color="red",
                    marker="o",
                    linewidth=2,
                    markersize=4,
                    label="Temperature",
                )
                ax2.set_ylabel("Temperature (°C)", color="red")
                ax2.tick_params(axis="y", labelcolor="red")

            # Highlight target date
            target_date = datetime.strptime(self.selected_date.get(), "%Y-%m-%d").date()
            if target_date in daily_data["date"].values:
                target_idx = daily_data[daily_data["date"] == target_date].index[0]
                ax1.axvline(
                    x=target_date, color="green", linestyle="--", linewidth=2, alpha=0.7
                )
                ax1.text(
                    target_date,
                    daily_data.iloc[target_idx]["Predicted Energy (kWh)"] * 1.1,
                    "TARGET",
                    ha="center",
                    va="bottom",
                    fontweight="bold",
                    color="green",
                )

            # Format x-axis
            plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

            # Add legend
            lines1, labels1 = ax1.get_legend_handles_labels()
            if "temperature_2m (°C)" in df.columns:
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
            else:
                ax1.legend(loc="upper left")

            # Add ranking legend
            ranking_text = "Ranking Colors:\n"
            for rank in range(1, 6):
                color = get_ranking_color(rank)
                description = get_ranking_description(rank)
                ranking_text += f"■ Rank {rank}: {description}\n"

            ax1.text(
                0.02,
                0.98,
                ranking_text,
                transform=ax1.transAxes,
                va="top",
                ha="left",
                fontsize=8,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
            )

            self.fig.tight_layout()
            self.canvas.draw()

        except Exception as e:
            self.ax.clear()
            self.ax.text(
                0.5,
                0.5,
                f"Error creating plot: {str(e)}",
                transform=self.ax.transAxes,
                ha="center",
                va="center",
            )
            self.canvas.draw()

    def export_results(self):
        """Export prediction results to CSV"""
        try:
            if self.current_predictions.empty:
                messagebox.showwarning("Warning", "No data to export")
                return

            # Create filename
            installation = self.selected_installation.get()
            target_date = self.selected_date.get()
            filename = f"predictions_{installation}_{target_date}.csv"

            # Export to CSV
            self.current_predictions.to_csv(filename, index=False)
            messagebox.showinfo("Success", f"Results exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export results: {str(e)}")

    def run(self):
        """Run the application"""
        self.root.mainloop()


def main():
    """Main function to run the application"""
    app = FilantropiaSolarApp()
    app.run()


if __name__ == "__main__":
    main()
