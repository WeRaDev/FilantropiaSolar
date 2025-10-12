"""
Enhanced Plot Window

Displays energy production, weather data, and rankings for 15-day periods.
Includes a day slider for navigating through the prediction period.
"""

import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging

# Local imports
# from ..utils.ranking_system import EnergyRank  # Not needed for basic functionality

logger = logging.getLogger(__name__)


class EnhancedPlotWindow:
    """
    Enhanced plot window for displaying 15-day energy production predictions
    with weather data and rankings.
    
    Features:
    - Day slider for navigating through 15-day period
    - Multiple plot types (energy, weather, rankings)
    - Interactive visualization with hover information
    - Export capabilities
    """
    
    def __init__(self, parent):
        """Initialize the enhanced plot window."""
        self.parent = parent
        
        # Data storage
        self.prediction_results = None
        self.current_day_index = 7  # Start with center date (day 7 of 15)
        
        # GUI components
        self.figure = None
        self.canvas = None
        self.toolbar = None
        
        # Create GUI
        self._create_widgets()
        
    def _create_widgets(self):
        """Create the GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)
        
        # Day selection controls
        self._create_day_controls(control_frame)
        
        # Plot frame
        plot_frame = ttk.Frame(main_frame)
        plot_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        
        # Create matplotlib figure
        self._create_plot_area(plot_frame)
        
        # Info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Create info display
        self._create_info_display(info_frame)
        
    def _create_day_controls(self, parent):
        """Create day selection controls."""
        # Title
        title_label = ttk.Label(parent, text="15-Day Energy Production Analysis", 
                               font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 10))
        
        # Day navigation
        ttk.Label(parent, text="Select Day:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        
        # Day slider
        self.day_var = tk.IntVar(value=7)
        self.day_slider = ttk.Scale(
            parent, 
            from_=0, to=14, 
            orient=tk.HORIZONTAL,
            command=self._on_day_changed,
            length=300
        )
        self.day_slider.set(7)  # Set initial value
        self.day_slider.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        # Day info label
        self.day_info_label = ttk.Label(parent, text="Day 8 of 15 (Center Date)", 
                                       font=('Arial', 10, 'bold'))
        self.day_info_label.grid(row=1, column=2, sticky=tk.W, padx=(10, 0))
        
        # Navigation buttons
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, columnspan=4, pady=(10, 0))
        
        ttk.Button(button_frame, text="← Previous Day", 
                  command=self._previous_day).grid(row=0, column=0, padx=(0, 5))
        
        ttk.Button(button_frame, text="Center Date", 
                  command=self._go_to_center).grid(row=0, column=1, padx=5)
        
        ttk.Button(button_frame, text="Next Day →", 
                  command=self._next_day).grid(row=0, column=2, padx=(5, 0))
        
    def _create_plot_area(self, parent):
        """Create the matplotlib plot area."""
        # Create figure with subplots
        self.figure = Figure(figsize=(14, 10), dpi=100)
        
        # Create subplots
        gs = self.figure.add_gridspec(3, 2, height_ratios=[2, 1.5, 1], hspace=0.3, wspace=0.3)
        
        # Energy production plot (top, spans both columns)
        self.energy_ax = self.figure.add_subplot(gs[0, :])
        
        # Weather plots (middle row)
        self.temp_ax = self.figure.add_subplot(gs[1, 0])
        self.radiation_ax = self.figure.add_subplot(gs[1, 1])
        
        # Ranking plot (bottom, spans both columns)
        self.ranking_ax = self.figure.add_subplot(gs[2, :])
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.figure, parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create toolbar
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
        
    def _create_info_display(self, parent):
        """Create information display area."""
        # Info frame with notebook for different tabs
        self.info_notebook = ttk.Notebook(parent)
        self.info_notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Day summary tab
        day_frame = ttk.Frame(self.info_notebook, padding="10")
        self.info_notebook.add(day_frame, text="Day Summary")
        self._create_day_summary(day_frame)
        
        # Period statistics tab
        period_frame = ttk.Frame(self.info_notebook, padding="10")
        self.info_notebook.add(period_frame, text="Period Statistics")
        self._create_period_stats(period_frame)
        
        # Data source tab
        source_frame = ttk.Frame(self.info_notebook, padding="10")
        self.info_notebook.add(source_frame, text="Data Source")
        self._create_source_info(source_frame)
        
    def _create_day_summary(self, parent):
        """Create day summary information."""
        # Create a grid of labels for day information
        labels = [
            ("Date:", "day_date_label"),
            ("Total Energy:", "day_energy_label"),
            ("Avg Specific Energy:", "day_specific_label"),
            ("Peak Hour:", "day_peak_label"),
            ("Average Temperature:", "day_temp_label"),
            ("Average Cloud Cover:", "day_cloud_label"),
            ("Total Solar Radiation:", "day_radiation_label"),
            ("Energy Ranking:", "day_ranking_label")
        ]
        
        self.day_labels = {}
        for i, (label_text, var_name) in enumerate(labels):
            ttk.Label(parent, text=label_text).grid(row=i//2, column=(i%2)*2, sticky=tk.W, padx=(0, 10), pady=2)
            value_label = ttk.Label(parent, text="-", font=('Arial', 9, 'bold'))
            value_label.grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, padx=(0, 20), pady=2)
            self.day_labels[var_name] = value_label
            
    def _create_period_stats(self, parent):
        """Create period statistics information."""
        labels = [
            ("Period:", "period_range_label"),
            ("Total Energy (15 days):", "period_total_label"),
            ("Average Daily Energy:", "period_avg_label"),
            ("Best Day:", "period_best_label"),
            ("Worst Day:", "period_worst_label"),
            ("Weather Conditions:", "period_weather_label")
        ]
        
        self.period_labels = {}
        for i, (label_text, var_name) in enumerate(labels):
            ttk.Label(parent, text=label_text).grid(row=i, column=0, sticky=tk.W, padx=(0, 10), pady=2)
            value_label = ttk.Label(parent, text="-", font=('Arial', 9, 'bold'))
            value_label.grid(row=i, column=1, sticky=tk.W, pady=2)
            self.period_labels[var_name] = value_label
            
    def _create_source_info(self, parent):
        """Create data source information."""
        labels = [
            ("Installation:", "source_installation_label"),
            ("Model Used:", "source_model_label"),
            ("Data Source:", "source_data_label"),
            ("Model Performance (R²):", "source_r2_label"),
            ("Prediction Accuracy (MAE):", "source_mae_label")
        ]
        
        self.source_labels = {}
        for i, (label_text, var_name) in enumerate(labels):
            ttk.Label(parent, text=label_text).grid(row=i, column=0, sticky=tk.W, padx=(0, 10), pady=2)
            value_label = ttk.Label(parent, text="-", font=('Arial', 9, 'bold'))
            value_label.grid(row=i, column=1, sticky=tk.W, pady=2)
            self.source_labels[var_name] = value_label
            
    def update_prediction_data(self, prediction_results: Dict[str, Any]):
        """Update the plot with new prediction results."""
        try:
            self.prediction_results = prediction_results
            
            # Reset to center day
            self.current_day_index = 7
            self.day_var.set(7)
            
            # Update plots
            self._update_all_plots()
            self._update_info_displays()
            
            logger.info(f"Updated plot data for installation: {prediction_results.get('installation_id')}")
            
        except Exception as e:
            logger.error(f"Error updating prediction data: {e}")
            
    def _update_all_plots(self):
        """Update all plot displays."""
        if not self.prediction_results:
            return
            
        try:
            # Clear existing plots
            for ax in [self.energy_ax, self.temp_ax, self.radiation_ax, self.ranking_ax]:
                ax.clear()
            
            # Get data
            hourly_data = self.prediction_results['hourly_data']
            daily_summary = self.prediction_results['daily_summary']
            
            # Plot energy production
            self._plot_energy_production(hourly_data, daily_summary)
            
            # Plot weather data
            self._plot_weather_data(hourly_data)
            
            # Plot rankings
            self._plot_rankings(daily_summary)
            
            # Highlight current day
            self._highlight_current_day()
            
            # Update canvas
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"Error updating plots: {e}")
            
    def _plot_energy_production(self, hourly_data: pd.DataFrame, daily_summary: pd.DataFrame):
        """Plot energy production data."""
        # Daily energy production
        dates = daily_summary.index
        daily_energy = daily_summary['predicted_total_energy']
        
        bars = self.energy_ax.bar(dates, daily_energy, alpha=0.7, color='orange', label='Daily Energy')
        
        # Color bars based on ranking
        if 'ranking' in daily_summary.columns:
            ranking_colors = {
                1: '#e74c3c',   # Red - Poor
                2: '#e67e22',   # Orange - Below Average  
                3: '#f1c40f',   # Yellow - Average
                4: '#2ecc71',   # Green - Good
                5: '#27ae60'    # Dark Green - Excellent
            }
            
            for i, (bar, ranking) in enumerate(zip(bars, daily_summary['ranking'])):
                if ranking in ranking_colors:
                    bar.set_color(ranking_colors[ranking])
        
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
        
    def _plot_weather_data(self, hourly_data: pd.DataFrame):
        """Plot weather data."""
        # Temperature plot
        if 'temperature_2m' in hourly_data.columns:
            daily_temps = hourly_data.groupby(hourly_data.index.date)['temperature_2m'].agg(['mean', 'min', 'max'])
            
            dates = daily_temps.index
            self.temp_ax.plot(dates, daily_temps['mean'], 'b-', marker='o', label='Avg Temp', linewidth=2)
            self.temp_ax.fill_between(dates, daily_temps['min'], daily_temps['max'], 
                                     alpha=0.3, color='blue', label='Min-Max Range')
            
            self.temp_ax.set_title('Temperature (°C)', fontsize=10, fontweight='bold')
            self.temp_ax.set_ylabel('Temperature (°C)')
            self.temp_ax.tick_params(axis='x', rotation=45)
            self.temp_ax.grid(True, alpha=0.3)
            self.temp_ax.legend(fontsize=8)
        
        # Solar radiation plot
        if 'shortwave_radiation' in hourly_data.columns:
            daily_radiation = hourly_data.groupby(hourly_data.index.date)['shortwave_radiation'].sum()
            
            dates = daily_radiation.index
            self.radiation_ax.bar(dates, daily_radiation, alpha=0.7, color='gold', 
                                 label='Daily Solar Radiation')
            
            self.radiation_ax.set_title('Solar Radiation (Wh/m²)', fontsize=10, fontweight='bold')
            self.radiation_ax.set_ylabel('Radiation (Wh/m²)')
            self.radiation_ax.tick_params(axis='x', rotation=45)
            self.radiation_ax.grid(True, alpha=0.3)
            
    def _plot_rankings(self, daily_summary: pd.DataFrame):
        """Plot energy rankings."""
        if 'ranking' not in daily_summary.columns:
            return
            
        dates = daily_summary.index
        rankings = daily_summary['ranking']
        
        # Color map for rankings
        colors = []
        ranking_colors = {
            1: '#e74c3c',   # Red - Poor
            2: '#e67e22',   # Orange - Below Average  
            3: '#f1c40f',   # Yellow - Average
            4: '#2ecc71',   # Green - Good
            5: '#27ae60'    # Dark Green - Excellent
        }
        
        for ranking in rankings:
            colors.append(ranking_colors.get(ranking, '#95a5a6'))
        
        bars = self.ranking_ax.bar(dates, rankings, color=colors, alpha=0.8)
        
        # Add ranking descriptions
        ranking_labels = {1: 'Poor', 2: 'Below Avg', 3: 'Average', 4: 'Good', 5: 'Excellent'}
        for bar, ranking in zip(bars, rankings):
            label = ranking_labels.get(ranking, 'Unknown')
            self.ranking_ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.05,
                               label, ha='center', va='bottom', fontsize=8)
        
        self.ranking_ax.set_title('Energy Production Rankings', fontsize=10, fontweight='bold')
        self.ranking_ax.set_ylabel('Ranking (1-5)')
        self.ranking_ax.set_ylim(0, 6)
        self.ranking_ax.set_yticks([1, 2, 3, 4, 5])
        self.ranking_ax.tick_params(axis='x', rotation=45)
        self.ranking_ax.grid(True, alpha=0.3)
        
    def _highlight_current_day(self):
        """Highlight the currently selected day."""
        if not self.prediction_results:
            return
            
        try:
            daily_summary = self.prediction_results['daily_summary']
            if len(daily_summary) > self.current_day_index:
                current_date = daily_summary.index[self.current_day_index]
                
                # Add vertical lines to highlight current day
                for ax in [self.energy_ax, self.temp_ax, self.radiation_ax, self.ranking_ax]:
                    ax.axvline(x=current_date, color='red', linestyle='--', linewidth=2, alpha=0.7)
                    
        except Exception as e:
            logger.error(f"Error highlighting current day: {e}")
            
    def _update_info_displays(self):
        """Update information display panels."""
        if not self.prediction_results:
            return
            
        try:
            # Update day summary
            self._update_day_summary()
            
            # Update period statistics
            self._update_period_statistics()
            
            # Update source information
            self._update_source_information()
            
        except Exception as e:
            logger.error(f"Error updating info displays: {e}")
            
    def _update_day_summary(self):
        """Update day summary information."""
        try:
            daily_summary = self.prediction_results['daily_summary']
            hourly_data = self.prediction_results['hourly_data']
            
            if len(daily_summary) > self.current_day_index:
                current_date = daily_summary.index[self.current_day_index]
                day_data = daily_summary.iloc[self.current_day_index]
                
                # Get hourly data for the current day
                day_hourly = hourly_data[hourly_data.index.date == current_date]
                
                # Update labels
                self.day_labels['day_date_label'].config(text=str(current_date))
                self.day_labels['day_energy_label'].config(text=f"{day_data['predicted_total_energy']:.1f} kWh")
                self.day_labels['day_specific_label'].config(text=f"{day_data['predicted_specific_energy']:.2f} kWh/kWp")
                
                # Find peak hour
                if len(day_hourly) > 0:
                    peak_hour = day_hourly['predicted_specific_energy'].idxmax()
                    peak_value = day_hourly['predicted_specific_energy'].max()
                    self.day_labels['day_peak_label'].config(text=f"{peak_hour.strftime('%H:%M')} ({peak_value:.2f} kWh/kWp)")
                
                # Weather info
                self.day_labels['day_temp_label'].config(text=f"{day_data.get('temperature_2m', 0):.1f}°C")
                self.day_labels['day_cloud_label'].config(text=f"{day_data.get('cloud_cover', 0):.1f}%")
                self.day_labels['day_radiation_label'].config(text=f"{day_data.get('shortwave_radiation', 0):.0f} Wh/m²")
                
                # Ranking
                ranking = int(day_data.get('ranking', 3))
                ranking_labels = {1: 'Poor', 2: 'Below Average', 3: 'Average', 4: 'Good', 5: 'Excellent'}
                ranking_text = ranking_labels.get(ranking, 'Unknown')
                self.day_labels['day_ranking_label'].config(text=f"{ranking}/5 - {ranking_text}")
                
        except Exception as e:
            logger.error(f"Error updating day summary: {e}")
            
    def _update_period_statistics(self):
        """Update period statistics."""
        try:
            period_stats = self.prediction_results['period_statistics']
            daily_summary = self.prediction_results['daily_summary']
            
            # Period range
            start_date = daily_summary.index.min()
            end_date = daily_summary.index.max()
            self.period_labels['period_range_label'].config(text=f"{start_date} to {end_date}")
            
            # Energy statistics
            total_energy = period_stats['total_energy_kwh']
            avg_daily = total_energy / len(daily_summary)
            self.period_labels['period_total_label'].config(text=f"{total_energy:.1f} kWh")
            self.period_labels['period_avg_label'].config(text=f"{avg_daily:.1f} kWh/day")
            
            # Best and worst days
            best_day = daily_summary['predicted_total_energy'].idxmax()
            worst_day = daily_summary['predicted_total_energy'].idxmin()
            best_energy = daily_summary.loc[best_day, 'predicted_total_energy']
            worst_energy = daily_summary.loc[worst_day, 'predicted_total_energy']
            
            self.period_labels['period_best_label'].config(text=f"{best_day} ({best_energy:.1f} kWh)")
            self.period_labels['period_worst_label'].config(text=f"{worst_day} ({worst_energy:.1f} kWh)")
            
            # Weather summary
            avg_temp = period_stats.get('average_temperature', 0)
            avg_cloud = period_stats.get('average_cloud_cover', 0)
            weather_summary = f"Avg: {avg_temp:.1f}°C, {avg_cloud:.1f}% clouds"
            self.period_labels['period_weather_label'].config(text=weather_summary)
            
        except Exception as e:
            logger.error(f"Error updating period statistics: {e}")
            
    def _update_source_information(self):
        """Update data source information."""
        try:
            installation_info = self.prediction_results['installation_info']
            data_source = self.prediction_results['data_source']
            
            # Installation info
            inst_text = f"{installation_info['location']} ({installation_info['capacity_kwp']} kWp)"
            self.source_labels['source_installation_label'].config(text=inst_text)
            
            # Model info
            model_name = data_source.get('model_used', 'Unknown')
            self.source_labels['source_model_label'].config(text=model_name.replace('_', ' ').title())
            
            # Data source
            data_type = "Simulated" if data_source.get('used_simulation', False) else "Historical"
            self.source_labels['source_data_label'].config(text=data_type)
            
            # Model performance
            performance = data_source.get('model_performance', {})
            if model_name in performance:
                model_perf = performance[model_name]
                r2_score = model_perf.get('r2', 0)
                mae_score = model_perf.get('mae', 0)
                
                self.source_labels['source_r2_label'].config(text=f"{r2_score:.3f}")
                self.source_labels['source_mae_label'].config(text=f"{mae_score:.3f} kWh/kWp")
            
        except Exception as e:
            logger.error(f"Error updating source information: {e}")
            
    def _on_day_changed(self, value=None):
        """Handle day slider change."""
        try:
            if value is not None:
                new_day = int(float(value))
            else:
                new_day = int(float(self.day_slider.get()))
                
            if new_day != self.current_day_index:
                self.current_day_index = new_day
                self.day_var.set(new_day)
                self._update_day_info_label()
                self._update_all_plots()
                self._update_day_summary()
                
        except Exception as e:
            logger.error(f"Error handling day change: {e}")
            
    def _update_day_info_label(self):
        """Update the day information label."""
        try:
            day_num = self.current_day_index + 1
            
            if self.current_day_index == 7:
                day_text = f"Day {day_num} of 15 (Center Date)"
            elif self.current_day_index < 7:
                days_before = 7 - self.current_day_index
                day_text = f"Day {day_num} of 15 ({days_before} days before center)"
            else:
                days_after = self.current_day_index - 7
                day_text = f"Day {day_num} of 15 ({days_after} days after center)"
                
            self.day_info_label.config(text=day_text)
            
        except Exception as e:
            logger.error(f"Error updating day info label: {e}")
            
    def _previous_day(self):
        """Go to previous day."""
        if self.current_day_index > 0:
            self.current_day_index -= 1
            self.day_var.set(self.current_day_index)
            self._update_day_info_label()
            self._update_all_plots()
            self._update_day_summary()
            
    def _next_day(self):
        """Go to next day."""
        if self.current_day_index < 14:
            self.current_day_index += 1
            self.day_var.set(self.current_day_index)
            self._update_day_info_label()
            self._update_all_plots()
            self._update_day_summary()
            
    def _go_to_center(self):
        """Go to center date."""
        self.current_day_index = 7
        self.day_var.set(7)
        self._update_day_info_label()
        self._update_all_plots()
        self._update_day_summary()
        
    def clear_plots(self):
        """Clear all plots."""
        if self.figure:
            for ax in [self.energy_ax, self.temp_ax, self.radiation_ax, self.ranking_ax]:
                ax.clear()
                ax.text(0.5, 0.5, 'No data to display', 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=12, alpha=0.5)
            self.canvas.draw()