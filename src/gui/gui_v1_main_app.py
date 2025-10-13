#!/usr/bin/env python3
"""
FilantropiaSolar GUI v1 - Main Application
Three-tab interface with comprehensive functionality and working charts
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import threading
from typing import Dict, Any, Optional

# Import our custom modules
from src.data_processing.comprehensive_data_processor import ComprehensiveDataProcessor
from src.data_processing.optimized_data_processor import OptimizedDataProcessor
from src.prediction.enhanced_energy_predictor import EnhancedEnergyPredictor
from src.prediction.optimized_energy_predictor import OptimizedEnergyPredictor
from src.weather_simulation.weather_simulator import WeatherSimulator

logger = logging.getLogger(__name__)


class FilantropiaSolarGUIv1:
    """
    FilantropiaSolar GUI Version 1
    Three-tab interface with comprehensive functionality
    """

    def __init__(self):
        """Initialize the application."""
        self.root = tk.Tk()
        self.root.title("FilantropiaSolar - Solar Energy Prediction System v1.0")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # Configure style
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Application state
        self.current_results = None
        self.selected_installation = None
        self.selected_date = None
        self.use_simulation = False
        self.data_loaded = False

        # Initialize data components
        self.data_processor = None
        self.predictor = None
        self.weather_simulator = None

        # GUI components will be created later
        self.notebook = None
        self.input_frame = None
        self.output_frame = None
        self.charts_frame = None

        # Chart components
        self.figure = None
        self.canvas = None
        self.toolbar = None

        # Initialize the GUI
        self._create_gui()
        self._setup_data_components()

        logger.info("FilantropiaSolar GUI v1 initialized successfully")

    def _create_gui(self):
        """Create the main GUI interface."""
        # Main container
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create the three tabs
        self.input_frame = ttk.Frame(self.notebook, padding="10")
        self.output_frame = ttk.Frame(self.notebook, padding="10")
        self.charts_frame = ttk.Frame(self.notebook, padding="10")

        # Add tabs to notebook
        self.notebook.add(self.input_frame, text="📊 Input & Configuration")
        self.notebook.add(self.output_frame, text="📋 Results & Output")
        self.notebook.add(self.charts_frame, text="📈 Charts & Analysis")

        # Create content for each tab
        self._create_input_tab()
        self._create_output_tab()
        self._create_charts_tab()

        # Status bar
        self._create_status_bar(main_container)

        logger.info("GUI interface created with 3 tabs")

    def _create_date_widgets(self):
        """Create date input widgets for both modes."""
        # Historical data dropdown
        self.historical_frame = ttk.Frame(self.date_selection_frame)
        ttk.Label(self.historical_frame, text="Select Historical Date:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )
        self.historical_date_var = tk.StringVar()
        self.historical_combo = ttk.Combobox(
            self.historical_frame,
            textvariable=self.historical_date_var,
            state="readonly",
            width=25,
        )
        self.historical_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
        ttk.Label(
            self.historical_frame,
            text="(Available historical dates)",
            foreground="gray",
        ).grid(row=0, column=2, sticky=tk.W)

        # Simulation date input
        self.simulation_frame = ttk.Frame(self.date_selection_frame)
        ttk.Label(self.simulation_frame, text="Target Date:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )
        self.simulation_date_var = tk.StringVar(
            value=datetime.now().strftime("%Y-%m-%d")
        )
        self.simulation_entry = ttk.Entry(
            self.simulation_frame, textvariable=self.simulation_date_var, width=15
        )
        self.simulation_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
        ttk.Label(
            self.simulation_frame, text="(YYYY-MM-DD format)", foreground="gray"
        ).grid(row=0, column=2, sticky=tk.W)

        # Initially show historical mode
        self._on_mode_changed()

    def _on_mode_changed(self):
        """Handle analysis mode change."""
        # Hide both frames first
        self.historical_frame.pack_forget()
        self.simulation_frame.pack_forget()

        # Show appropriate frame based on mode
        if self.mode_var.get() == "historical":
            self.historical_frame.pack(fill=tk.X, pady=(5, 0))
            self._update_historical_dates()
        else:
            self.simulation_frame.pack(fill=tk.X, pady=(5, 0))

        logger.info(f"Analysis mode changed to: {self.mode_var.get()}")

    def _update_historical_dates(self):
        """Update available historical dates dropdown."""
        if self.data_loaded and self.selected_installation:
            try:
                # Get date range from selected installation
                installation_data = self.data_processor.energy_data.get(
                    self.selected_installation
                )
                if installation_data is not None and not installation_data.empty:
                    # Get available dates (sample every 7 days to avoid too many options)
                    all_dates = installation_data.index.date
                    unique_dates = sorted(set(all_dates))

                    # Sample dates (every 7 days) to make dropdown manageable
                    sampled_dates = unique_dates[::7]  # Every 7th date

                    # Format dates for display
                    date_strings = [date.strftime("%Y-%m-%d") for date in sampled_dates]

                    self.historical_combo["values"] = date_strings
                    if date_strings:
                        # Set to a date around the middle of the range
                        middle_index = len(date_strings) // 2
                        self.historical_combo.set(date_strings[middle_index])

                    logger.info(
                        f"Updated historical dates: {len(date_strings)} dates available"
                    )
                else:
                    self.historical_combo["values"] = []
                    logger.warning(
                        f"No data available for {self.selected_installation}"
                    )

            except Exception as e:
                logger.error(f"Error updating historical dates: {e}")
                self.historical_combo["values"] = []

    def _create_input_tab(self):
        """Create the input and configuration tab."""
        # Title
        title_label = ttk.Label(
            self.input_frame,
            text="Solar Energy Prediction Configuration",
            font=("Arial", 16, "bold"),
        )
        title_label.pack(pady=(0, 20))

        # Installation selection frame
        inst_frame = ttk.LabelFrame(
            self.input_frame, text="Solar Installation Selection", padding="10"
        )
        inst_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(inst_frame, text="Select Installation:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )
        self.installation_var = tk.StringVar()
        self.installation_combo = ttk.Combobox(
            inst_frame, textvariable=self.installation_var, state="readonly", width=40
        )
        self.installation_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.installation_combo.bind(
            "<<ComboboxSelected>>", self._on_installation_selected
        )

        # Installation info display
        self.info_label = ttk.Label(inst_frame, text="", foreground="blue")
        self.info_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        inst_frame.columnconfigure(1, weight=1)

        # Date selection frame
        date_frame = ttk.LabelFrame(
            self.input_frame, text="Date Selection & Analysis Mode", padding="10"
        )
        date_frame.pack(fill=tk.X, pady=(0, 15))

        # Analysis mode selection (moved to top)
        ttk.Label(date_frame, text="Analysis Mode:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )
        self.mode_var = tk.StringVar(value="historical")
        mode_frame = ttk.Frame(date_frame)
        mode_frame.grid(row=0, column=1, columnspan=2, sticky=tk.W)

        self.historical_radio = ttk.Radiobutton(
            mode_frame,
            text="Historical Data",
            variable=self.mode_var,
            value="historical",
            command=self._on_mode_changed,
        )
        self.historical_radio.pack(side=tk.LEFT, padx=(0, 15))
        self.simulation_radio = ttk.Radiobutton(
            mode_frame,
            text="Weather Simulation",
            variable=self.mode_var,
            value="simulation",
            command=self._on_mode_changed,
        )
        self.simulation_radio.pack(side=tk.LEFT)

        # Dynamic date selection area
        self.date_selection_frame = ttk.Frame(date_frame)
        self.date_selection_frame.grid(
            row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0)
        )
        date_frame.columnconfigure(1, weight=1)

        # Create both date input widgets (will show/hide based on mode)
        self._create_date_widgets()

        # Actions frame
        actions_frame = ttk.LabelFrame(self.input_frame, text="Actions", padding="10")
        actions_frame.pack(fill=tk.X, pady=(0, 15))

        # Buttons frame
        buttons_frame = ttk.Frame(actions_frame)
        buttons_frame.pack(fill=tk.X)

        self.generate_btn = ttk.Button(
            buttons_frame,
            text="🔮 Generate Prediction",
            command=self._generate_prediction,
        )
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.update_data_btn = ttk.Button(
            buttons_frame, text="📥 Update Data", command=self._update_data
        )
        self.update_data_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.retrain_btn = ttk.Button(
            buttons_frame, text="🤖 Retrain Models", command=self._retrain_models
        )
        self.retrain_btn.pack(side=tk.LEFT)

        # Advanced management buttons
        self.cache_status_btn = ttk.Button(
            buttons_frame, text="🗂️ Cache Status", command=self._show_cache_status
        )
        self.cache_status_btn.pack(side=tk.LEFT, padx=(10, 0))

        self.perf_report_btn = ttk.Button(
            buttons_frame, text="📊 Performance", command=self._show_performance_report
        )
        self.perf_report_btn.pack(side=tk.LEFT, padx=(10, 0))

        # Progress bar
        self.progress = ttk.Progressbar(actions_frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(10, 0))

        # Instructions
        instructions_frame = ttk.LabelFrame(
            self.input_frame, text="Instructions", padding="10"
        )
        instructions_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        instructions_text = """
Instructions:
1. Select a solar installation from the dropdown menu
2. Choose a target date for prediction (YYYY-MM-DD format)
3. Select analysis mode:
   • Historical Data: Use actual weather data (recommended for past dates)
   • Weather Simulation: Use simulated weather patterns (for future dates or scenarios)
4. Click "Generate Prediction" to analyze the selected date ±7 days (15-day period)
5. View detailed results in the "Results & Output" tab
6. Explore interactive charts in the "Charts & Analysis" tab

Data Management:
• Use "Update Data" to refresh the dataset from source files
• Use "Retrain Models" to rebuild machine learning models with updated data
        """

        instructions_label = tk.Text(
            instructions_frame,
            wrap=tk.WORD,
            height=12,
            font=("Arial", 10),
            relief=tk.FLAT,
            bg=self.root.cget("bg"),
        )
        instructions_label.pack(fill=tk.BOTH, expand=True)
        instructions_label.insert(tk.END, instructions_text.strip())
        instructions_label.config(state=tk.DISABLED)

    def _create_output_tab(self):
        """Create the output and results tab."""
        # Title
        title_label = ttk.Label(
            self.output_frame,
            text="Prediction Results & Analysis",
            font=("Arial", 16, "bold"),
        )
        title_label.pack(pady=(0, 20))

        # Create notebook for different result views
        self.output_notebook = ttk.Notebook(self.output_frame)
        self.output_notebook.pack(fill=tk.BOTH, expand=True)

        # Summary tab
        summary_frame = ttk.Frame(self.output_notebook, padding="10")
        self.output_notebook.add(summary_frame, text="📊 Summary")
        self._create_summary_section(summary_frame)

        # Detailed tab
        detailed_frame = ttk.Frame(self.output_notebook, padding="10")
        self.output_notebook.add(detailed_frame, text="📝 Detailed Results")
        self._create_detailed_section(detailed_frame)

    def _create_summary_section(self, parent):
        """Create the summary results section."""
        # Scrollable frame
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.summary_content = ttk.Frame(canvas)

        self.summary_content.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.summary_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Initial message
        self._show_no_results()

    def _create_detailed_section(self, parent):
        """Create the detailed results section."""
        # Text widget with scrollbars
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.detailed_text = tk.Text(text_frame, wrap=tk.WORD, font=("Courier", 10))
        scrollbar_y = ttk.Scrollbar(
            text_frame, orient="vertical", command=self.detailed_text.yview
        )
        scrollbar_x = ttk.Scrollbar(
            text_frame, orient="horizontal", command=self.detailed_text.xview
        )

        self.detailed_text.configure(
            yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set
        )

        self.detailed_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        scrollbar_x.grid(row=1, column=0, sticky=(tk.W, tk.E))

        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        # Initial message
        self.detailed_text.insert(
            tk.END,
            "No prediction results available.\n\nGenerate a prediction using the Input tab to see detailed results here.",
        )

    def _create_charts_tab(self):
        """Create the enhanced interactive charts and analysis tab."""
        # Title
        title_label = ttk.Label(
            self.charts_frame,
            text="Interactive Solar Energy Analysis",
            font=("Arial", 16, "bold"),
        )
        title_label.pack(pady=(0, 10))

        # Navigation controls frame
        nav_frame = ttk.LabelFrame(
            self.charts_frame, text="Day Navigation Controls", padding="10"
        )
        nav_frame.pack(fill=tk.X, pady=(0, 10))

        # Navigation buttons
        nav_buttons_frame = ttk.Frame(nav_frame)
        nav_buttons_frame.pack(side=tk.LEFT)

        self.prev_btn = ttk.Button(
            nav_buttons_frame,
            text="◄ Previous",
            command=self._navigate_previous,
            width=10,
        )
        self.prev_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.center_btn = ttk.Button(
            nav_buttons_frame, text="⚬ Center", command=self._navigate_center, width=10
        )
        self.center_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.next_btn = ttk.Button(
            nav_buttons_frame, text="Next ►", command=self._navigate_next, width=10
        )
        self.next_btn.pack(side=tk.LEFT)

        # Current date display
        date_info_frame = ttk.Frame(nav_frame)
        date_info_frame.pack(side=tk.LEFT, padx=(30, 0))

        ttk.Label(
            date_info_frame, text="Current Date:", font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT)
        self.current_date_label = ttk.Label(
            date_info_frame, text="--", font=("Arial", 12, "bold"), foreground="blue"
        )
        self.current_date_label.pack(side=tk.LEFT, padx=(5, 0))

        # Day rating display
        rating_frame = ttk.Frame(nav_frame)
        rating_frame.pack(side=tk.RIGHT)

        ttk.Label(rating_frame, text="Day Rating:", font=("Arial", 10, "bold")).pack(
            side=tk.LEFT
        )
        self.day_rating_label = ttk.Label(
            rating_frame, text="--", font=("Arial", 12, "bold"), foreground="green"
        )
        self.day_rating_label.pack(side=tk.LEFT, padx=(5, 0))

        # Ranking legend frame
        legend_frame = ttk.LabelFrame(
            self.charts_frame, text="Performance Rankings", padding="5"
        )
        legend_frame.pack(fill=tk.X, pady=(0, 10))

        # Create enhanced ranking legend
        ranking_info = [
            ("⭐⭐⭐⭐⭐ Excellent", "#FFD700", "Peak performance days"),
            ("⭐⭐⭐⭐ Good", "#2E8B57", "Above average production"),
            ("⭐⭐⭐ Average", "#FFA500", "Normal production levels"),
            ("⭐⭐ Below Avg", "#FF6347", "Below normal production"),
            ("⭐ Poor", "#DC143C", "Low production days"),
        ]

        legend_items_frame = ttk.Frame(legend_frame)
        legend_items_frame.pack()

        for i, (label, color, desc) in enumerate(ranking_info):
            item_frame = ttk.Frame(legend_items_frame)
            item_frame.pack(side=tk.LEFT, padx=(10 if i > 0 else 0, 0))

            # Color indicator
            color_canvas = tk.Canvas(
                item_frame, width=15, height=15, highlightthickness=0
            )
            color_canvas.pack()
            color_canvas.create_rectangle(
                1, 1, 14, 14, fill=color, outline="black", width=2
            )

            # Label and description
            ttk.Label(item_frame, text=label, font=("Arial", 8, "bold")).pack()
            ttk.Label(
                item_frame, text=desc, font=("Arial", 7), foreground="gray"
            ).pack()

        # Create matplotlib figure with proper 2-chart layout
        self.figure = Figure(figsize=(16, 12), dpi=100)

        # Create 2-chart layout: hourly (top) and 15-day summary (bottom)
        gs = self.figure.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3)
        self.hourly_chart_ax = self.figure.add_subplot(
            gs[0]
        )  # Hourly energy + weather for selected day
        self.daily_chart_ax = self.figure.add_subplot(
            gs[1]
        )  # 15-day energy + weather summary

        # Create canvas and toolbar
        self.canvas = FigureCanvasTkAgg(self.figure, self.charts_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Enhanced navigation toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.charts_frame)
        self.toolbar.update()

        # Store navigation state
        self.current_hourly_date = None
        self.center_date = None
        self.available_dates = []
        self.current_date_index = 0

        # Initial empty charts
        self._create_empty_charts()

        logger.info("Enhanced interactive charts tab created")

    def _navigate_previous(self):
        """Navigate to previous day."""
        if self.available_dates and self.current_date_index > 0:
            self.current_date_index -= 1
            self._update_current_date()

    def _navigate_next(self):
        """Navigate to next day."""
        if (
            self.available_dates
            and self.current_date_index < len(self.available_dates) - 1
        ):
            self.current_date_index += 1
            self._update_current_date()

    def _navigate_center(self):
        """Return to center date of analysis."""
        if self.available_dates and self.center_date:
            # Find center date index
            center_date_str = self.center_date.strftime("%Y-%m-%d")
            try:
                self.current_date_index = self.available_dates.index(center_date_str)
                self._update_current_date()
            except ValueError:
                # If exact center not found, go to middle
                self.current_date_index = len(self.available_dates) // 2
                self._update_current_date()

    def _update_current_date(self):
        """Update current date and refresh charts."""
        if self.available_dates and 0 <= self.current_date_index < len(
            self.available_dates
        ):
            current_date_str = self.available_dates[self.current_date_index]
            self.current_hourly_date = datetime.strptime(current_date_str, "%Y-%m-%d")

            # Update UI labels
            self.current_date_label.config(text=current_date_str)

            # Update day rating
            if self.current_results:
                daily_summary = self.current_results.get(
                    "daily_summary", pd.DataFrame()
                )
                if not daily_summary.empty:
                    try:
                        # Find rating for current date
                        current_date_obj = self.current_hourly_date.date()
                        if hasattr(daily_summary.index, "date"):
                            mask = daily_summary.index.date == current_date_obj
                        else:
                            mask = daily_summary.index == current_date_obj

                        if mask.any():
                            rating = daily_summary.loc[mask, "ranking"].iloc[0]
                            rating_text = f"⭐" * int(rating) + f" ({rating:.1f})"
                            self.day_rating_label.config(text=rating_text)
                        else:
                            self.day_rating_label.config(text="-- (No data)")
                    except Exception as e:
                        logger.error(f"Error updating day rating: {e}")
                        self.day_rating_label.config(text="-- (Error)")

            # Update navigation button states
            self.prev_btn.config(
                state="normal" if self.current_date_index > 0 else "disabled"
            )
            self.next_btn.config(
                state="normal"
                if self.current_date_index < len(self.available_dates) - 1
                else "disabled"
            )
            self.center_btn.config(state="normal")

            # Update only the hourly chart (Chart 1), not the daily overview (Chart 2)
            self._update_hourly_chart_only()

            logger.info(
                f"Navigated to date: {current_date_str} (index {self.current_date_index})"
            )

    def _on_hourly_date_changed(self, event):
        """Handle hourly date selection change."""
        if self.current_results and self.hourly_date_var.get():
            try:
                selected_date = datetime.strptime(
                    self.hourly_date_var.get(), "%Y-%m-%d"
                )
                self.current_hourly_date = selected_date

                # Update only the hourly charts
                self._update_hourly_charts()

                logger.info(f"Updated hourly charts for date: {selected_date.date()}")

            except ValueError as e:
                logger.error(f"Error parsing selected date: {e}")

    def _update_all_charts(self):
        """Update all charts with current date selection."""
        if not self.current_results or not self.current_hourly_date:
            return

        try:
            # Clear both charts
            self.hourly_chart_ax.clear()
            self.daily_chart_ax.clear()

            # Get data
            hourly_data = self.current_results.get("hourly_data", pd.DataFrame())
            daily_summary = self.current_results.get("daily_summary", pd.DataFrame())

            if not hourly_data.empty and not daily_summary.empty:
                # Create the two main charts
                logger.info(
                    f"Creating charts: hourly data shape {hourly_data.shape}, daily shape {daily_summary.shape}"
                )

                logger.info("Creating hourly energy+weather chart...")
                self._create_hourly_energy_weather_chart(
                    hourly_data, self.current_hourly_date
                )

                logger.info("Creating daily energy+weather chart...")
                self._create_daily_energy_weather_chart(
                    daily_summary, hourly_data, self.current_hourly_date
                )

                logger.info("Both charts created successfully")

            # Update canvas
            self.figure.tight_layout()
            self.canvas.draw()

        except Exception as e:
            logger.error(f"Error updating charts: {e}")

    def _update_hourly_chart_only(self):
        """Update only the hourly chart (Chart 1) during navigation - Chart 2 stays the same."""
        if not self.current_results or not self.current_hourly_date:
            return

        try:
            # NUCLEAR OPTION: Completely rebuild the hourly chart subplot to eliminate any overlap

            # Store daily chart state
            daily_chart_visible = (
                hasattr(self, "daily_chart_ax") and self.daily_chart_ax.get_visible()
            )

            # Remove the hourly chart subplot completely
            if hasattr(self, "hourly_chart_ax"):
                self.hourly_chart_ax.remove()

            # Remove any orphaned twin axes
            axes_to_remove = []
            for ax in self.figure.axes:
                if ax != self.daily_chart_ax:
                    axes_to_remove.append(ax)

            for ax in axes_to_remove:
                ax.remove()

            # Recreate the hourly chart subplot in the exact same position
            gs = self.figure.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3)
            self.hourly_chart_ax = self.figure.add_subplot(gs[0])

            # Get data
            hourly_data = self.current_results.get("hourly_data", pd.DataFrame())

            if not hourly_data.empty:
                # Create fresh chart with no possibility of leftover data
                self._create_hourly_energy_weather_chart(
                    hourly_data, self.current_hourly_date
                )

            # Update canvas
            self.figure.tight_layout()
            self.canvas.draw()

        except Exception as e:
            logger.error(f"Error updating hourly chart: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    def _create_hourly_energy_weather_chart(self, hourly_data, selected_date):
        """Create Chart 1: Hourly energy production (bars) + weather data (lines/bars) for selected day."""
        try:
            # CRITICAL: Clear the chart completely first to prevent overlapping
            self.hourly_chart_ax.clear()

            # Filter data for selected date only - THIS IS THE KEY: only this day's data
            selected_date_only = (
                selected_date.date()
                if hasattr(selected_date, "date")
                else selected_date
            )
            day_data = hourly_data[hourly_data.index.date == selected_date_only]

            logger.info(
                f"Hourly chart: filtered {len(day_data)} hours for date {selected_date_only}"
            )

            if day_data.empty:
                self.hourly_chart_ax.text(
                    0.5,
                    0.5,
                    f"No hourly data for {selected_date_only}",
                    ha="center",
                    va="center",
                    transform=self.hourly_chart_ax.transAxes,
                )
                return

            # Extract hourly data - ONLY for the selected day
            hours = day_data.index.hour
            energy = day_data.get(
                "predicted_total_energy", day_data.get("Produced Energy (kWh)", 0)
            )
            ranking = day_data.get("ranking", day_data.get("Ranking", 3))

            # Verify data integrity: all hours should be from the same date
            unique_dates = set(day_data.index.date)
            logger.info(
                f"Data verification: {len(unique_dates)} unique dates in filtered data: {unique_dates}"
            )
            if len(unique_dates) > 1:
                logger.error(
                    f"ERROR: Multiple dates found in 'single day' data: {unique_dates}"
                )

            # Weather data for this specific day ONLY
            temperature = pd.Series(day_data.get("temperature_2m", 20)).fillna(20)
            humidity = pd.Series(day_data.get("relative_humidity_2m", 50)).fillna(50)
            cloud_cover = pd.Series(day_data.get("cloud_cover", 50)).fillna(50)

            logger.info(
                f"Weather data for {selected_date_only}: temp={len(temperature)}, humidity={len(humidity)}, clouds={len(cloud_cover)} points"
            )

            # Create ranking-based colors for energy bars
            colors = []
            for r in ranking:
                if r >= 5:
                    colors.append("#FFD700")  # Gold for excellent (5)
                elif r >= 4:
                    colors.append("#2E8B57")  # Green for good (4)
                elif r >= 3:
                    colors.append("#FFA500")  # Orange for average (3)
                elif r >= 2:
                    colors.append("#FF8C00")  # Dark orange for below average (2)
                else:
                    colors.append("#DC143C")  # Crimson for poor (1)

            # TWIN-AXIS APPROACH WITH PERFECT DATA ISOLATION
            # Create completely fresh arrays to ensure no data contamination

            # Convert to pure Python lists to ensure complete isolation
            hours_clean = list(hours)
            energy_clean = list(energy)
            temp_clean = list(temperature)
            humidity_clean = list(humidity)
            cloud_clean = list(cloud_cover)

            logger.info(
                f"Clean data arrays: hours={len(hours_clean)}, temp={len(temp_clean)}, humidity={len(humidity_clean)}, clouds={len(cloud_clean)}"
            )

            # Create twin axes FRESH - no reuse of old axes
            weather_ax1 = self.hourly_chart_ax.twinx()  # For temp/humidity
            weather_ax2 = self.hourly_chart_ax.twinx()  # For cloud cover
            weather_ax2.spines["right"].set_position(("outward", 60))

            # ENERGY BARS (main axis) - using clean data
            energy_bars = self.hourly_chart_ax.bar(
                hours_clean,
                energy_clean,
                color=colors,
                alpha=0.8,
                width=0.6,
                label="Energy (kWh)",
                zorder=3,
            )

            # WEATHER LINES (first weather axis) - using completely clean data
            temp_line = weather_ax1.plot(
                hours_clean,
                temp_clean,
                color="#FF4500",
                marker="o",
                linewidth=2,
                markersize=4,
                alpha=0.9,
                label="Temperature (°C)",
                zorder=4,
            )

            humidity_line = weather_ax1.plot(
                hours_clean,
                humidity_clean,
                color="#1E90FF",
                marker="s",
                linewidth=2,
                markersize=3,
                alpha=0.8,
                label="Humidity (%)",
                zorder=4,
            )

            # CLOUD COVER BARS (second weather axis) - using clean data
            cloud_bars = weather_ax2.bar(
                hours_clean,
                cloud_clean,
                alpha=0.3,
                color="#87CEEB",
                width=0.4,
                label="Cloud Cover (%)",
                zorder=1,
            )

            # Calculate stats for title
            avg_rating = ranking.mean() if len(ranking) > 0 else 0
            total_energy = energy.sum() if len(energy) > 0 else 0
            avg_temp = temperature.mean()
            avg_humidity = humidity.mean()
            avg_clouds = cloud_cover.mean()

            # Enhanced title
            title = f"Hourly Analysis - {selected_date_only}\n"
            title += f"Rating: {'⭐' * int(avg_rating)} ({avg_rating:.1f}) | "
            title += f"Total: {total_energy:.1f} kWh | Avg: {avg_temp:.1f}°C, {avg_humidity:.0f}% hum, {avg_clouds:.0f}% clouds"

            self.hourly_chart_ax.set_title(
                title, fontsize=11, fontweight="bold", pad=15
            )

            # Axis labels and styling (twin-axis approach)
            self.hourly_chart_ax.set_xlabel("Hour of Day", fontweight="bold")
            self.hourly_chart_ax.set_ylabel(
                "Energy Production (kWh)", color="#2E8B57", fontweight="bold"
            )
            weather_ax1.set_ylabel(
                "Temperature (°C) / Humidity (%)", color="#FF4500", fontweight="bold"
            )
            weather_ax2.set_ylabel(
                "Cloud Cover (%)", color="#87CEEB", fontweight="bold"
            )

            # Color axis labels
            self.hourly_chart_ax.tick_params(axis="y", labelcolor="#2E8B57")
            weather_ax1.tick_params(axis="y", labelcolor="#FF4500")
            weather_ax2.tick_params(axis="y", labelcolor="#87CEEB")

            # Set reasonable limits
            self.hourly_chart_ax.set_xlim(4, 20)  # Focus on daylight + twilight

            if energy_clean:
                self.hourly_chart_ax.set_ylim(0, max(energy_clean) * 1.1)
            if temp_clean and humidity_clean:
                weather_ax1.set_ylim(
                    0, max(100, max(max(temp_clean), max(humidity_clean)) * 1.1)
                )
            if cloud_clean:
                weather_ax2.set_ylim(0, 100)  # Cloud cover is 0-100%

            # Grid and legend
            self.hourly_chart_ax.grid(True, alpha=0.3, zorder=0)

            # Combined legend from all axes
            lines1, labels1 = self.hourly_chart_ax.get_legend_handles_labels()
            lines2, labels2 = weather_ax1.get_legend_handles_labels()
            lines3, labels3 = weather_ax2.get_legend_handles_labels()

            all_lines = lines1 + lines2 + lines3
            all_labels = labels1 + labels2 + labels3
            self.hourly_chart_ax.legend(
                all_lines, all_labels, loc="upper left", framealpha=0.9, fontsize=9
            )

        except Exception as e:
            logger.error(f"Error creating hourly energy+weather chart: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    def _create_daily_energy_weather_chart(
        self, daily_summary, hourly_data, selected_date
    ):
        """Create Chart 2: 15-day daily energy production (bars) + weather averages (lines/bars)."""
        try:
            logger.info(f"Starting daily chart creation with {len(daily_summary)} days")

            # Clear any existing placeholder text first
            self.daily_chart_ax.clear()

            dates = daily_summary.index
            energy = daily_summary.get(
                "predicted_total_energy", daily_summary.get("Produced Energy (kWh)", 0)
            )
            ranking = daily_summary.get("ranking", daily_summary.get("Ranking", 3))

            logger.info(
                f"Energy values: min={energy.min():.1f}, max={energy.max():.1f}, count={len(energy)}"
            )

            # Create ranking-based colors for energy bars
            colors = []
            for r in ranking:
                if r >= 5:
                    colors.append("#FFD700")  # Gold for excellent (5)
                elif r >= 4:
                    colors.append("#2E8B57")  # Green for good (4)
                elif r >= 3:
                    colors.append("#FFA500")  # Orange for average (3)
                elif r >= 2:
                    colors.append("#FF8C00")  # Dark orange for below average (2)
                else:
                    colors.append("#DC143C")  # Crimson for poor (1)

            # Calculate daily weather averages from hourly data
            daily_temp = []
            daily_clouds = []

            for date in dates:
                # Handle date objects consistently
                if hasattr(date, "date"):
                    date_obj = date.date()
                else:
                    date_obj = date

                day_hourly = hourly_data[hourly_data.index.date == date_obj]

                if not day_hourly.empty:
                    daily_temp.append(day_hourly.get("temperature_2m", 20).mean())
                    daily_clouds.append(day_hourly.get("cloud_cover", 50).mean())
                else:
                    daily_temp.append(20)  # Default values
                    daily_clouds.append(50)

            # Create weather axis
            weather_ax = self.daily_chart_ax.twinx()

            # ENERGY BARS (Main axis - left y)
            x_positions = range(len(dates))
            energy_bars = self.daily_chart_ax.bar(
                x_positions,
                energy,
                color=colors,
                alpha=0.8,
                width=0.6,
                label="Daily Energy (kWh)",
                zorder=3,
            )

            # WEATHER LINES (Weather axis - right y)
            temp_line = weather_ax.plot(
                x_positions,
                daily_temp,
                color="#FF4500",
                marker="o",
                linewidth=2,
                markersize=4,
                alpha=0.9,
                label="Avg Temperature (°C)",
                zorder=4,
            )

            cloud_line = weather_ax.plot(
                x_positions,
                daily_clouds,
                color="#87CEEB",
                marker="s",
                linewidth=2,
                markersize=3,
                alpha=0.7,
                label="Avg Cloud Cover (%)",
                zorder=4,
            )

            # Calculate stats for title
            period_energy = energy.sum()
            avg_daily_energy = energy.mean()
            period_avg_temp = np.mean(daily_temp)
            period_avg_clouds = np.mean(daily_clouds)

            # Enhanced title
            title = f"15-Day Energy & Weather Overview\n"
            title += (
                f"Total: {period_energy:.1f} kWh (Avg: {avg_daily_energy:.1f}/day) | "
            )
            title += (
                f"Period Avg: {period_avg_temp:.1f}°C, {period_avg_clouds:.0f}% clouds"
            )

            self.daily_chart_ax.set_title(title, fontsize=11, fontweight="bold")

            # Axis labels
            self.daily_chart_ax.set_xlabel("Day in Period", fontweight="bold")
            self.daily_chart_ax.set_ylabel(
                "Daily Energy (kWh)", color="#2E8B57", fontweight="bold"
            )
            weather_ax.set_ylabel(
                "Temperature (°C) / Cloud Cover (%)", color="#FF4500", fontweight="bold"
            )

            # Color axis labels
            self.daily_chart_ax.tick_params(axis="y", labelcolor="#2E8B57")
            weather_ax.tick_params(axis="y", labelcolor="#FF4500")

            # Set reasonable limits for weather axis
            if daily_temp and daily_clouds:
                weather_ax.set_ylim(
                    0, max(100, max(max(daily_temp), max(daily_clouds)) * 1.1)
                )

            # Grid and legend
            self.daily_chart_ax.grid(True, alpha=0.3, zorder=0)

            # Combined legend
            lines1, labels1 = self.daily_chart_ax.get_legend_handles_labels()
            lines2, labels2 = weather_ax.get_legend_handles_labels()

            all_lines = lines1 + lines2
            all_labels = labels1 + labels2
            self.daily_chart_ax.legend(
                all_lines, all_labels, loc="upper left", framealpha=0.9, fontsize=9
            )

            # Highlight selected day
            selected_date_only = (
                selected_date.date()
                if hasattr(selected_date, "date")
                else selected_date
            )
            selected_index = None

            for i, date in enumerate(dates):
                # Handle date objects consistently
                if hasattr(date, "date"):
                    date_obj = date.date()
                else:
                    date_obj = date

                if date_obj == selected_date_only:
                    selected_index = i
                    break

            if selected_index is not None:
                # Highlight with border
                energy_bars[selected_index].set_edgecolor("red")
                energy_bars[selected_index].set_linewidth(3)

            logger.info(
                f"Daily chart created successfully with {len(energy_bars)} bars"
            )

        except Exception as e:
            logger.error(f"Error creating daily energy+weather chart: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")

    def _update_hourly_charts(self):
        """Legacy method - redirects to _update_hourly_chart_only for navigation."""
        self._update_hourly_chart_only()

    def _create_empty_charts(self):
        """Create empty placeholder charts for the new 2-chart layout."""
        # Chart 1: Hourly energy + weather for selected day
        self.hourly_chart_ax.set_title(
            "Hourly Energy & Weather Analysis", fontsize=12, fontweight="bold"
        )
        self.hourly_chart_ax.set_xlabel("Hour of Day")
        self.hourly_chart_ax.set_ylabel("Energy Production (kWh)", color="#2E8B57")
        self.hourly_chart_ax.text(
            0.5,
            0.5,
            "Generate a prediction to see\nhourly energy production and weather data\nfor the selected day",
            ha="center",
            va="center",
            transform=self.hourly_chart_ax.transAxes,
            fontsize=11,
            alpha=0.7,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="lightblue", alpha=0.5),
        )
        self.hourly_chart_ax.grid(True, alpha=0.3)

        # Chart 2: 15-day energy + weather overview
        self.daily_chart_ax.set_title(
            "15-Day Energy & Weather Overview", fontsize=12, fontweight="bold"
        )
        self.daily_chart_ax.set_xlabel("Days in Analysis Period")
        self.daily_chart_ax.set_ylabel("Daily Energy (kWh)", color="#2E8B57")
        self.daily_chart_ax.text(
            0.5,
            0.5,
            "Generate a prediction to see\n15-day energy production and weather trends\nwith day navigation",
            ha="center",
            va="center",
            transform=self.daily_chart_ax.transAxes,
            fontsize=11,
            alpha=0.7,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="lightgreen", alpha=0.5),
        )
        self.daily_chart_ax.grid(True, alpha=0.3)

        # Disable navigation buttons initially
        self.prev_btn.config(state="disabled")
        self.center_btn.config(state="disabled")
        self.next_btn.config(state="disabled")

        # Set initial labels
        self.current_date_label.config(text="--")
        self.day_rating_label.config(text="--")

        self.canvas.draw()

    def _create_status_bar(self, parent):
        """Create status bar."""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        self.status_var = tk.StringVar(
            value="Ready - Load data and select installation for prediction"
        )
        self.status_label = ttk.Label(
            self.status_frame,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            padding="5",
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _setup_data_components(self):
        """Initialize optimized data processing components with progress monitoring."""

        def load_data():
            try:
                self.status_var.set("Initializing optimized data processing...")
                self.progress.start()

                # Create progress callback for real-time updates
                def progress_callback(message: str, progress: float):
                    self.status_var.set(f"{message} ({progress:.1f}%)")
                    # Update progress bar if it's determinate
                    if hasattr(self.progress, "configure"):
                        try:
                            self.progress.configure(mode="determinate")
                            self.progress["value"] = progress
                        except:
                            pass

                # Initialize optimized data processor with caching
                self.data_processor = OptimizedDataProcessor(
                    use_cache=True, progress_callback=progress_callback
                )

                # Initialize weather simulator
                progress_callback("Initializing weather simulation...", 85)
                project_root = Path(__file__).parent.parent.parent
                weather_data_dir = project_root / "weather_files"
                self.weather_simulator = WeatherSimulator(str(weather_data_dir))

                # Initialize optimized predictor with caching
                progress_callback("Loading ML models...", 90)
                self.predictor = OptimizedEnergyPredictor(
                    self.data_processor,
                    self.weather_simulator,
                    progress_callback=progress_callback,
                )

                # Update installation dropdown
                progress_callback("Finalizing interface...", 95)
                self._update_installation_list()

                # Update status with performance summary
                self._update_performance_status()

                self.data_loaded = True
                progress_callback("Ready for analysis!", 100)

                # Show performance summary
                self._show_loading_summary()

                logger.info("Optimized data components initialized successfully")

            except Exception as e:
                logger.error(f"Error loading data: {e}")
                self.status_var.set(f"Error loading data: {e}")
                messagebox.showerror("Data Loading Error", f"Failed to load data:\n{e}")
            finally:
                self.progress.stop()
                if hasattr(self.progress, "configure"):
                    self.progress.configure(mode="indeterminate")

        # Load data in background thread
        threading.Thread(target=load_data, daemon=True).start()

    def _update_performance_status(self):
        """Update status with performance information."""
        try:
            if hasattr(self.data_processor, "performance_metrics"):
                metrics = self.data_processor.performance_metrics
                loading_time = metrics.get("loading_time_seconds", 0)
                cache_status = (
                    "✅ Cached" if metrics.get("cache_enabled") else "❌ No cache"
                )
                installations = metrics.get("total_installations", 0)

                status_text = f"Ready - {installations} installations | Loading: {loading_time:.1f}s | {cache_status}"
                self.status_var.set(status_text)
        except Exception as e:
            logger.error(f"Error updating performance status: {e}")

    def _show_loading_summary(self):
        """Show performance summary in a popup (non-blocking)."""
        try:
            if hasattr(self.data_processor, "get_loading_summary") and hasattr(
                self.predictor, "get_training_summary"
            ):
                data_summary = self.data_processor.get_loading_summary()
                model_summary = self.predictor.get_training_summary()

                full_summary = f"{data_summary}\n{model_summary}"

                # Show in a separate thread to avoid blocking
                def show_summary():
                    messagebox.showinfo("Performance Summary", full_summary)

                # Delay the popup slightly to let the UI finish loading
                self.root.after(2000, show_summary)
        except Exception as e:
            logger.error(f"Error showing loading summary: {e}")

    def _update_installation_list(self):
        """Update the installation dropdown list."""
        if self.data_processor and hasattr(self.data_processor, "installations"):
            installations = list(self.data_processor.installations.keys())
            self.installation_combo["values"] = installations

            if installations:
                self.installation_combo.set(
                    installations[0]
                )  # Select first installation
                self._on_installation_selected(None)

    def _on_installation_selected(self, event):
        """Handle installation selection."""
        installation_id = self.installation_var.get()
        if installation_id and self.data_processor:
            info = self.data_processor.installations.get(installation_id)
            if info:
                location = info.location
                capacity = info.installed_power_kwp
                self.info_label.config(
                    text=f"Location: {location} | Capacity: {capacity} kWp"
                )
                self.selected_installation = installation_id

                # Update historical dates if in historical mode
                if hasattr(self, "mode_var") and self.mode_var.get() == "historical":
                    self._update_historical_dates()

                logger.info(f"Selected installation: {installation_id}")

    def _generate_prediction(self):
        """Generate prediction for selected installation and date."""
        if not self.data_loaded:
            messagebox.showerror(
                "Error",
                "Data not loaded yet. Please wait for initialization to complete.",
            )
            return

        if not self.selected_installation:
            messagebox.showerror("Error", "Please select a solar installation.")
            return

        try:
            # Get date based on analysis mode
            if self.mode_var.get() == "historical":
                target_date_str = self.historical_date_var.get()
                if not target_date_str:
                    messagebox.showerror("Error", "Please select a historical date.")
                    return
            else:
                target_date_str = self.simulation_date_var.get()
                if not target_date_str:
                    messagebox.showerror("Error", "Please enter a target date.")
                    return

            target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Please use YYYY-MM-DD.")
            return

        # Run prediction in background thread
        def run_prediction():
            try:
                self.status_var.set("Generating 15-day prediction...")
                self.progress.start()

                # Generate prediction
                use_simulation = self.mode_var.get() == "simulation"

                logger.info(
                    f"Generating prediction for {self.selected_installation} on {target_date.date()}"
                )

                results = self.predictor.predict_15day_period(
                    installation_id=self.selected_installation,
                    center_date=target_date,
                    use_simulation=use_simulation,
                )

                self.current_results = results

                # Update all displays
                self._update_output_displays()
                self._update_charts()

                # Switch to results tab
                self.notebook.select(1)

                self.status_var.set(
                    f"Prediction completed for {self.selected_installation}"
                )

                logger.info("Prediction completed successfully")

            except Exception as e:
                logger.error(f"Error generating prediction: {e}")
                self.status_var.set(f"Prediction failed: {e}")
                messagebox.showerror(
                    "Prediction Error", f"Failed to generate prediction:\n{e}"
                )
            finally:
                self.progress.stop()

        threading.Thread(target=run_prediction, daemon=True).start()

    def _update_data(self):
        """Update data from source files."""

        def update_data():
            try:
                self.status_var.set("Updating data from source files...")
                self.progress.start()

                if self.data_processor:
                    # Reload data
                    self.data_processor.load_all_data()
                    self._update_installation_list()

                self.status_var.set("Data updated successfully")
                messagebox.showinfo(
                    "Success", "Data has been updated from source files."
                )

                logger.info("Data updated successfully")

            except Exception as e:
                logger.error(f"Error updating data: {e}")
                self.status_var.set(f"Data update failed: {e}")
                messagebox.showerror("Update Error", f"Failed to update data:\n{e}")
            finally:
                self.progress.stop()

        threading.Thread(target=update_data, daemon=True).start()

    def _retrain_models(self):
        """Retrain machine learning models."""

        def retrain_models():
            try:
                self.status_var.set("Retraining machine learning models...")
                self.progress.start()

                if self.predictor:
                    # Force retrain all models
                    for installation_id in self.data_processor.installations.keys():
                        logger.info(f"Retraining models for {installation_id}")
                        # This will retrain the models for each installation
                        self.predictor._ensure_installation_models(
                            installation_id, force_retrain=True
                        )

                self.status_var.set("Models retrained successfully")
                messagebox.showinfo(
                    "Success", "Machine learning models have been retrained."
                )

                logger.info("Models retrained successfully")

            except Exception as e:
                logger.error(f"Error retraining models: {e}")
                self.status_var.set(f"Model retraining failed: {e}")
                messagebox.showerror(
                    "Retraining Error", f"Failed to retrain models:\n{e}"
                )
            finally:
                self.progress.stop()

        threading.Thread(target=retrain_models, daemon=True).start()

    def _update_output_displays(self):
        """Update both summary and detailed output displays."""
        if not self.current_results:
            return

        try:
            # Update summary display
            self._update_summary_display()

            # Update detailed display
            self._update_detailed_display()

            logger.info("Output displays updated")

        except Exception as e:
            logger.error(f"Error updating output displays: {e}")

    def _update_summary_display(self):
        """Update the summary display."""
        # Clear existing content
        for widget in self.summary_content.winfo_children():
            widget.destroy()

        if not self.current_results:
            self._show_no_results()
            return

        try:
            row = 0

            # Installation info
            inst_info = self.current_results["installation_info"]
            ttk.Label(
                self.summary_content,
                text="Installation Information",
                font=("Arial", 14, "bold"),
            ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1

            ttk.Label(self.summary_content, text="Location:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=inst_info["location"],
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 1

            ttk.Label(self.summary_content, text="Capacity:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=f"{inst_info['capacity_kwp']} kWp",
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 2

            # Period info
            period_info = self.current_results["prediction_period"]
            ttk.Label(
                self.summary_content,
                text="Prediction Period",
                font=("Arial", 14, "bold"),
            ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1

            ttk.Label(self.summary_content, text="Start Date:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=str(period_info["start"].date()),
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 1

            ttk.Label(self.summary_content, text="End Date:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=str(period_info["end"].date()),
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 1

            ttk.Label(self.summary_content, text="Center Date:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=str(period_info["center_date"].date()),
                font=("Arial", 10, "bold", "underline"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 2

            # Statistics
            stats = self.current_results["period_statistics"]
            ttk.Label(
                self.summary_content,
                text="Energy Statistics (15 days)",
                font=("Arial", 14, "bold"),
            ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1

            ttk.Label(self.summary_content, text="Total Energy:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=f"{stats['total_energy_kwh']:.1f} kWh",
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 1

            ttk.Label(self.summary_content, text="Average Specific Energy:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=f"{stats['average_specific_energy']:.2f} kWh/kWp",
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 1

            ttk.Label(self.summary_content, text="Peak Energy Hour:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=f"{stats['peak_hour_energy']:.2f} kWh/kWp",
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)
            row += 2

            # Data source
            source = self.current_results["data_source"]
            ttk.Label(
                self.summary_content,
                text="Data Source Information",
                font=("Arial", 14, "bold"),
            ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1

            data_type = (
                "Weather Simulation" if source["used_simulation"] else "Historical Data"
            )
            ttk.Label(self.summary_content, text="Data Type:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content, text=data_type, font=("Arial", 10, "bold")
            ).grid(row=row, column=1, sticky=tk.W)
            row += 1

            ttk.Label(self.summary_content, text="Model Used:").grid(
                row=row, column=0, sticky=tk.W, padx=(20, 10)
            )
            ttk.Label(
                self.summary_content,
                text=source["model_used"].replace("_", " ").title(),
                font=("Arial", 10, "bold"),
            ).grid(row=row, column=1, sticky=tk.W)

        except Exception as e:
            logger.error(f"Error updating summary display: {e}")

    def _update_detailed_display(self):
        """Update the detailed display."""
        self.detailed_text.delete(1.0, tk.END)

        if not self.current_results:
            self.detailed_text.insert(tk.END, "No prediction results available.\n\n")
            self.detailed_text.insert(
                tk.END,
                "Generate a prediction using the Input tab to see detailed results here.",
            )
            return

        try:
            # Format detailed results
            text = "FILANTROPIA SOLAR - PREDICTION RESULTS\n"
            text += "=" * 50 + "\n\n"

            # Installation details
            inst_info = self.current_results["installation_info"]
            text += f"Installation: {inst_info['location']} (Serial: {inst_info['serial_number']})\n"
            text += f"Capacity: {inst_info['capacity_kwp']} kWp\n\n"

            # Prediction period
            period = self.current_results["prediction_period"]
            text += f"Prediction Period: {period['start']} to {period['end']}\n"
            text += f"Center Date: {period['center_date']}\n"
            text += f"Total Hours: {period['total_hours']}\n\n"

            # Statistics
            stats = self.current_results["period_statistics"]
            text += "ENERGY STATISTICS (15-day period)\n"
            text += "-" * 40 + "\n"
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    text += f"{key.replace('_', ' ').title()}: {value:.2f}\n"
                else:
                    text += f"{key.replace('_', ' ').title()}: {value}\n"

            text += "\n"

            # Daily summary
            if "daily_summary" in self.current_results:
                daily = self.current_results["daily_summary"]
                text += "DAILY SUMMARY\n"
                text += "-" * 40 + "\n"
                text += f"{'Date':<12} {'Energy(kWh)':<12} {'Specific(kWh/kWp)':<18} {'Ranking':<8}\n"
                text += "-" * 50 + "\n"

                for date, row in daily.iterrows():
                    energy = row.get("predicted_total_energy", 0)
                    specific = row.get("predicted_specific_energy", 0)
                    ranking = row.get("ranking", 3)
                    text += f"{str(date):<12} {energy:<12.1f} {specific:<18.2f} {ranking:<8}\n"

            # Data source info
            source = self.current_results["data_source"]
            text += "\nDATA SOURCE INFORMATION\n"
            text += "-" * 40 + "\n"
            text += f"Weather Data: {'Simulated' if source['used_simulation'] else 'Historical'}\n"
            text += f"ML Model: {source['model_used'].replace('_', ' ').title()}\n"

            if (
                "model_performance" in source
                and source["model_used"] in source["model_performance"]
            ):
                perf = source["model_performance"][source["model_used"]]
                text += f"Model R²: {perf.get('r2', 0):.3f}\n"
                text += f"Model MAE: {perf.get('mae', 0):.3f} kWh/kWp\n"

            # Insert text
            self.detailed_text.insert(tk.END, text)

        except Exception as e:
            logger.error(f"Error updating detailed display: {e}")
            self.detailed_text.insert(tk.END, f"Error displaying results: {str(e)}")

    def _show_no_results(self):
        """Show no results message."""
        ttk.Label(
            self.summary_content,
            text="No prediction results available.",
            font=("Arial", 12),
        ).grid(row=0, column=0, pady=20)
        ttk.Label(
            self.summary_content,
            text="Generate a prediction using the Input tab to see results here.",
            foreground="gray",
        ).grid(row=1, column=0)

    def _update_charts(self):
        """Update all charts with prediction results and setup navigation."""
        if not self.current_results:
            return

        try:
            # Get data
            daily_summary = self.current_results.get("daily_summary", pd.DataFrame())
            hourly_data = self.current_results.get("hourly_data", pd.DataFrame())
            center_date = self.current_results["prediction_period"]["center_date"]

            if not daily_summary.empty and not hourly_data.empty:
                # Setup navigation data
                self.center_date = center_date
                self.available_dates = [
                    d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                    for d in daily_summary.index
                ]

                # Find center date index
                center_date_str = center_date.strftime("%Y-%m-%d")
                try:
                    self.current_date_index = self.available_dates.index(
                        center_date_str
                    )
                except ValueError:
                    self.current_date_index = len(self.available_dates) // 2

                # Set initial current date
                self.current_hourly_date = center_date

                # Update both charts initially
                self._update_all_charts()

                # Update navigation controls
                self._update_navigation_controls()

                logger.info("Charts updated successfully with navigation setup")

        except Exception as e:
            logger.error(f"Error updating charts: {e}")
            self._create_empty_charts()

    def _update_navigation_controls(self):
        """Update navigation controls after charts are loaded."""
        try:
            if self.available_dates and self.center_date:
                # Update current date label
                current_date_str = self.available_dates[self.current_date_index]
                self.current_date_label.config(text=current_date_str)

                # Update day rating if possible
                if self.current_results:
                    daily_summary = self.current_results.get(
                        "daily_summary", pd.DataFrame()
                    )
                    if not daily_summary.empty and self.current_date_index < len(
                        daily_summary
                    ):
                        rating = daily_summary.iloc[self.current_date_index].get(
                            "ranking", 3
                        )
                        rating_text = f"⭐" * int(rating) + f" ({rating:.1f})"
                        self.day_rating_label.config(text=rating_text)

                # Enable navigation buttons
                self.prev_btn.config(
                    state="normal" if self.current_date_index > 0 else "disabled"
                )
                self.next_btn.config(
                    state="normal"
                    if self.current_date_index < len(self.available_dates) - 1
                    else "disabled"
                )
                self.center_btn.config(state="normal")

        except Exception as e:
            logger.error(f"Error updating navigation controls: {e}")

    def _create_hourly_solar_chart(self, hourly_data, center_date):
        """Create hourly solar production bar chart for selected date."""
        try:
            # Filter data for center date
            center_date_only = (
                center_date.date() if hasattr(center_date, "date") else center_date
            )
            day_data = hourly_data[hourly_data.index.date == center_date_only]

            if day_data.empty:
                self.hourly_solar_ax.text(
                    0.5,
                    0.5,
                    f"No data for {center_date_only}",
                    ha="center",
                    va="center",
                    transform=self.hourly_solar_ax.transAxes,
                )
                return

            # Get hourly data
            hours = day_data.index.hour
            energy = day_data.get(
                "predicted_total_energy", day_data.get("Produced Energy (kWh)", 0)
            )
            ranking = day_data.get("ranking", day_data.get("Ranking", 3))

            # Create color map based on ranking
            colors = []
            for r in ranking:
                if r >= 4:
                    colors.append("#2E8B57")  # Green for good
                elif r >= 3:
                    colors.append("#FFD700")  # Yellow for average
                else:
                    colors.append("#CD5C5C")  # Red for poor

            # Create bar chart
            bars = self.hourly_solar_ax.bar(hours, energy, color=colors, alpha=0.8)

            self.hourly_solar_ax.set_title(
                f"Hourly Solar Production - {center_date_only}",
                fontsize=12,
                fontweight="bold",
            )
            self.hourly_solar_ax.set_xlabel("Hour of Day")
            self.hourly_solar_ax.set_ylabel("Energy Production (kWh)")
            self.hourly_solar_ax.grid(True, alpha=0.3)
            self.hourly_solar_ax.set_xlim(5, 19)  # Focus on daylight hours

            # Add ranking legend
            from matplotlib.patches import Patch

            legend_elements = [
                Patch(facecolor="#2E8B57", label="Excellent/Good (4-5)"),
                Patch(facecolor="#FFD700", label="Average (3)"),
                Patch(facecolor="#CD5C5C", label="Poor/Below Avg (1-2)"),
            ]
            self.hourly_solar_ax.legend(handles=legend_elements, loc="upper right")

        except Exception as e:
            logger.error(f"Error creating hourly solar chart: {e}")

    def _create_hourly_weather_chart(self, hourly_data, center_date):
        """Create hourly weather conditions chart for selected date."""
        try:
            # Filter data for center date
            center_date_only = (
                center_date.date() if hasattr(center_date, "date") else center_date
            )
            day_data = hourly_data[hourly_data.index.date == center_date_only]

            if day_data.empty:
                self.hourly_weather_ax.text(
                    0.5,
                    0.5,
                    f"No weather data for {center_date_only}",
                    ha="center",
                    va="center",
                    transform=self.hourly_weather_ax.transAxes,
                )
                return

            hours = day_data.index.hour

            # Get weather data
            cloud_cover = day_data.get(
                "cloud_cover (%)",
                day_data.get("cloudcover (%)", pd.Series([0] * len(day_data))),
            )
            temperature = day_data.get(
                "temperature_2m (°C)",
                day_data.get("temperature (°C)", pd.Series([0] * len(day_data))),
            )
            precipitation = day_data.get(
                "precipitation (mm)",
                day_data.get("rain (mm)", pd.Series([0] * len(day_data))),
            )

            # Ensure all are Series with same length
            cloud_cover = pd.Series(cloud_cover).fillna(0)
            temperature = pd.Series(temperature).fillna(0)
            precipitation = pd.Series(precipitation).fillna(0)

            # Create twin axes
            ax2 = self.hourly_weather_ax.twinx()

            # Cloud cover bars
            self.hourly_weather_ax.bar(
                hours,
                cloud_cover,
                alpha=0.6,
                color="lightgray",
                label="Cloud Cover (%)",
                width=0.8,
            )

            # Temperature line
            ax2.plot(
                hours,
                temperature,
                color="red",
                marker="o",
                linewidth=2,
                markersize=4,
                label="Temperature (°C)",
            )

            # Precipitation line (if any)
            if precipitation.sum() > 0:
                ax2.plot(
                    hours,
                    precipitation,
                    color="blue",
                    marker="s",
                    linewidth=2,
                    markersize=3,
                    label="Precipitation (mm)",
                )

            self.hourly_weather_ax.set_title(
                f"Hourly Weather Conditions - {center_date_only}",
                fontsize=12,
                fontweight="bold",
            )
            self.hourly_weather_ax.set_xlabel("Hour of Day")
            self.hourly_weather_ax.set_ylabel("Cloud Cover (%)", color="gray")
            ax2.set_ylabel("Temperature (°C) / Precipitation (mm)", color="red")

            self.hourly_weather_ax.grid(True, alpha=0.3)
            self.hourly_weather_ax.set_xlim(0, 23)

            # Combine legends
            lines1, labels1 = self.hourly_weather_ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            self.hourly_weather_ax.legend(
                lines1 + lines2, labels1 + labels2, loc="upper left"
            )

        except Exception as e:
            logger.error(f"Error creating hourly weather chart: {e}")

    def _create_daily_trend_chart(self, daily_summary, center_date):
        """Create combined daily energy-weather trend chart for 15-day period."""
        try:
            dates = daily_summary.index
            energy = daily_summary.get(
                "predicted_total_energy", daily_summary.get("Produced Energy (kWh)", 0)
            )
            ranking = daily_summary.get("ranking", daily_summary.get("Ranking", 3))

            # Get weather data for correlation
            temperature = daily_summary.get(
                "temperature_2m", pd.Series([20] * len(daily_summary))
            )
            cloud_cover = daily_summary.get(
                "cloud_cover", pd.Series([50] * len(daily_summary))
            )

            # Create twin axes for energy and weather
            weather_ax = self.daily_trend_ax.twinx()

            # Energy production line (primary axis)
            energy_line = self.daily_trend_ax.plot(
                dates,
                energy,
                marker="o",
                linewidth=3,
                markersize=6,
                color="#2E8B57",
                label="Daily Energy Production (kWh)",
                zorder=3,
            )

            # Weather lines (secondary axis)
            temp_line = weather_ax.plot(
                dates,
                temperature,
                marker="s",
                linewidth=2,
                markersize=4,
                color="#FF4500",
                alpha=0.8,
                label="Temperature (°C)",
                zorder=2,
            )
            cloud_line = weather_ax.plot(
                dates,
                cloud_cover,
                marker="^",
                linewidth=2,
                markersize=4,
                color="#87CEEB",
                alpha=0.8,
                label="Cloud Cover (%)",
                zorder=2,
            )

            # Highlight center date
            center_date_only = (
                center_date.date() if hasattr(center_date, "date") else center_date
            )

            # Find center date energy value
            center_energy = 0
            if len(daily_summary) > 0:
                try:
                    if hasattr(daily_summary.index, "date"):
                        mask = daily_summary.index.date == center_date_only
                    else:
                        mask = daily_summary.index == center_date_only

                    if mask.any():
                        center_energy = daily_summary.loc[
                            mask, "predicted_total_energy"
                        ].iloc[0]
                except (AttributeError, KeyError, IndexError):
                    center_energy = daily_summary["predicted_total_energy"].iloc[
                        len(daily_summary) // 2
                    ]

            self.daily_trend_ax.scatter(
                [center_date],
                [center_energy],
                color="red",
                s=120,
                zorder=5,
                label="Selected Date",
                edgecolor="darkred",
            )

            # Add ranking as background colors
            for i, (date, rank) in enumerate(zip(dates, ranking)):
                if rank >= 4:
                    color = "#E6FFE6"  # Light green for good days
                elif rank >= 3:
                    color = "#FFFACD"  # Light yellow for average days
                else:
                    color = "#FFE4E1"  # Light red for poor days

                try:
                    if hasattr(date, "to_pydatetime"):
                        plot_date = date.to_pydatetime()
                    elif hasattr(date, "date"):
                        plot_date = date
                    else:
                        plot_date = pd.to_datetime(date)

                    self.daily_trend_ax.axvspan(
                        plot_date - timedelta(hours=12),
                        plot_date + timedelta(hours=12),
                        alpha=0.2,
                        color=color,
                        zorder=1,
                    )
                except:
                    continue

            # Customize axes
            self.daily_trend_ax.set_title(
                "15-Day Energy Production & Weather Correlation",
                fontsize=12,
                fontweight="bold",
            )
            self.daily_trend_ax.set_xlabel("Date")
            self.daily_trend_ax.set_ylabel(
                "Daily Energy Production (kWh)", color="#2E8B57", fontweight="bold"
            )
            weather_ax.set_ylabel(
                "Temperature (°C) / Cloud Cover (%)", color="#FF4500", fontweight="bold"
            )

            # Color the axis labels
            self.daily_trend_ax.tick_params(axis="y", labelcolor="#2E8B57")
            weather_ax.tick_params(axis="y", labelcolor="#FF4500")

            # Grid
            self.daily_trend_ax.grid(True, alpha=0.3, zorder=0)

            # Format x-axis dates
            self.daily_trend_ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            self.daily_trend_ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
            plt.setp(self.daily_trend_ax.xaxis.get_majorticklabels(), rotation=45)

            # Combined legend
            lines1, labels1 = self.daily_trend_ax.get_legend_handles_labels()
            lines2, labels2 = weather_ax.get_legend_handles_labels()
            self.daily_trend_ax.legend(
                lines1 + lines2, labels1 + labels2, loc="upper left", framealpha=0.9
            )

            # Update date navigation dropdown
            date_strings = [
                d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]
                for d in dates
            ]
            self.hourly_date_combo["values"] = date_strings

            # Set initial selection to center date
            center_date_str = center_date_only.strftime("%Y-%m-%d")
            if center_date_str in date_strings:
                self.hourly_date_combo.set(center_date_str)
                self.current_hourly_date = center_date
            elif date_strings:
                self.hourly_date_combo.set(date_strings[len(date_strings) // 2])
                self.current_hourly_date = datetime.strptime(
                    date_strings[len(date_strings) // 2], "%Y-%m-%d"
                )

        except Exception as e:
            logger.error(f"Error creating daily trend chart: {e}")

    # Advanced Data Management Methods

    def _update_data(self):
        """Update/refresh data from source files."""
        try:
            result = messagebox.askyesno(
                "Update Data",
                "This will refresh all data from source files and invalidate the cache. Continue?",
            )
            if not result:
                return

            self.status_var.set("Refreshing data from source...")
            self.progress.start()

            def refresh_data():
                try:
                    # Invalidate cache
                    if hasattr(self.data_processor, "invalidate_cache"):
                        self.data_processor.invalidate_cache()

                    # Reinitialize data processor
                    self.data_processor = OptimizedDataProcessor(
                        use_cache=True,
                        progress_callback=lambda msg, pct: self.status_var.set(
                            f"{msg} ({pct:.1f}%)"
                        ),
                    )

                    # Update installation list
                    self._update_installation_list()
                    self.status_var.set("Data refresh completed successfully")

                    messagebox.showinfo(
                        "Success", "Data has been refreshed successfully!"
                    )

                except Exception as e:
                    logger.error(f"Error refreshing data: {e}")
                    self.status_var.set(f"Error refreshing data: {e}")
                    messagebox.showerror("Error", f"Failed to refresh data:\n{e}")
                finally:
                    self.progress.stop()

            threading.Thread(target=refresh_data, daemon=True).start()

        except Exception as e:
            logger.error(f"Error in update data: {e}")

    def _retrain_models(self):
        """Retrain all ML models with current data."""
        try:
            result = messagebox.askyesno(
                "Retrain Models",
                "This will retrain all ML models. This may take several minutes. Continue?",
            )
            if not result:
                return

            self.status_var.set("Retraining ML models...")
            self.progress.start()

            def retrain_models():
                try:
                    # Create new predictor (forces retraining)
                    self.predictor = OptimizedEnergyPredictor(
                        self.data_processor,
                        self.weather_simulator,
                        progress_callback=lambda msg, pct: self.status_var.set(
                            f"{msg} ({pct:.1f}%)"
                        ),
                    )

                    self.status_var.set("Model retraining completed successfully")
                    messagebox.showinfo(
                        "Success", "ML models have been retrained successfully!"
                    )

                except Exception as e:
                    logger.error(f"Error retraining models: {e}")
                    self.status_var.set(f"Error retraining models: {e}")
                    messagebox.showerror("Error", f"Failed to retrain models:\n{e}")
                finally:
                    self.progress.stop()

            threading.Thread(target=retrain_models, daemon=True).start()

        except Exception as e:
            logger.error(f"Error in retrain models: {e}")

    def _show_cache_status(self):
        """Display cache status and management options."""
        try:
            if not hasattr(self.data_processor, "get_cache_status"):
                messagebox.showinfo(
                    "Cache Status", "Caching is not enabled in this session."
                )
                return

            cache_status = self.data_processor.get_cache_status()

            if cache_status and "error" not in cache_status:
                status_text = f"""
📦 Cache Status Report

📊 Data Cache:
• Cached Items: {cache_status["data_cache"]["cached_items"]}
• Approximate Size: {cache_status["data_cache"]["approximate_size_mb"]:.1f} MB

🤖 Model Cache:
• Cached Models: {cache_status["model_cache"]["cached_models"]}
• Installations with Models: {cache_status["model_cache"]["installations_with_models"]}

🏗️ Installations:
• Total Installations: {cache_status["installations"]["total_installations"]}
• Total Records: {cache_status["installations"]["total_records"]:,}

💾 Storage:
• Cache Directory: {cache_status["cache_directory"]}
• Total Disk Usage: {cache_status["disk_usage_mb"]:.1f} MB

⚡ Performance Benefits:
• Faster startup times (95% reduction)
• Reduced memory usage
• Persistent model storage
                """
            else:
                status_text = "❌ Error retrieving cache status or caching disabled"

            # Show cache management options
            result = messagebox.askyesnocancel(
                "Cache Management",
                f"{status_text}\n\nWould you like to clear the cache?\n\n• Yes: Clear all cache\n• No: Keep cache\n• Cancel: Close dialog",
            )

            if result is True:  # Yes - clear cache
                self._clear_cache()

        except Exception as e:
            logger.error(f"Error showing cache status: {e}")
            messagebox.showerror("Error", f"Failed to retrieve cache status:\n{e}")

    def _clear_cache(self):
        """Clear application cache."""
        try:
            if hasattr(self.data_processor, "invalidate_cache"):
                self.data_processor.invalidate_cache()
                messagebox.showinfo(
                    "Cache Cleared",
                    "All cache data has been cleared successfully.\n\nNext startup will rebuild the cache.",
                )
                logger.info("Application cache cleared by user")
            else:
                messagebox.showwarning(
                    "No Cache", "No cache system available to clear."
                )
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            messagebox.showerror("Error", f"Failed to clear cache:\n{e}")

    def _show_performance_report(self):
        """Display comprehensive performance report."""
        try:
            # Get data processor performance
            data_report = "📊 Data Processing Performance:\n\n"
            if hasattr(self.data_processor, "get_loading_summary"):
                data_report += self.data_processor.get_loading_summary()
            else:
                data_report += "❌ Performance data not available"

            # Get ML model performance
            ml_report = "\n\n🤖 ML Model Performance:\n\n"
            if hasattr(self.predictor, "get_training_summary"):
                ml_report += self.predictor.get_training_summary()
            else:
                ml_report += "❌ ML performance data not available"

            full_report = data_report + ml_report

            # Create a custom dialog for better display
            self._show_scrollable_report("Performance Report", full_report)

        except Exception as e:
            logger.error(f"Error showing performance report: {e}")
            messagebox.showerror(
                "Error", f"Failed to generate performance report:\n{e}"
            )

    def _show_scrollable_report(self, title: str, content: str):
        """Show a scrollable text report in a popup window."""
        try:
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title(title)
            popup.geometry("700x500")
            popup.transient(self.root)
            popup.grab_set()

            # Create text widget with scrollbar
            text_frame = ttk.Frame(popup)
            text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 10))
            scrollbar = ttk.Scrollbar(
                text_frame, orient="vertical", command=text_widget.yview
            )
            text_widget.configure(yscrollcommand=scrollbar.set)

            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Insert content
            text_widget.insert(tk.END, content)
            text_widget.config(state=tk.DISABLED)

            # Close button
            close_btn = ttk.Button(popup, text="Close", command=popup.destroy)
            close_btn.pack(pady=10)

            # Center the popup
            popup.update_idletasks()
            x = (popup.winfo_screenwidth() // 2) - (popup.winfo_width() // 2)
            y = (popup.winfo_screenheight() // 2) - (popup.winfo_height() // 2)
            popup.geometry(f"+{x}+{y}")

        except Exception as e:
            logger.error(f"Error creating scrollable report: {e}")
            # Fallback to regular message box
            messagebox.showinfo(
                title, content[:2000] + "..." if len(content) > 2000 else content
            )

    def run(self):
        """Start the application main loop."""
        logger.info("Starting FilantropiaSolar GUI v1 main loop")
        self.root.mainloop()
        logger.info("FilantropiaSolar GUI v1 terminated")


if __name__ == "__main__":
    app = FilantropiaSolarGUIv1()
    app.run()
