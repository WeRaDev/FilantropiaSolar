"""
Simple Compact Input Window

Focuses on essential functionality with a compact layout that fits on smaller screens.
"""

from collections.abc import Callable
import calendar
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

# from tkcalendar import DateEntry  # Removed - using dropdowns instead

# Local imports
from ..data_processing.comprehensive_data_processor import (
    ComprehensiveDataProcessor,
)

logger = logging.getLogger(__name__)


class SimpleInputWindow:
    """
    Simple, compact input window for the FilantropiaSolar application.

    Features:
    - Compact layout that fits on smaller screens
    - Essential functionality only
    - Clear visual feedback
    """

    def __init__(
        self,
        parent,
        data_processor: ComprehensiveDataProcessor,
        on_predict_callback: Callable[[str, datetime, bool], None],
    ):
        """Initialize the simple input window."""
        self.parent = parent
        self.data_processor = data_processor
        self.on_predict_callback = on_predict_callback

        # Data
        self.installations = data_processor.get_installation_list()
        self.historical_date_range = data_processor.get_date_range()

        # GUI variables
        self.selected_installation = tk.StringVar()
        self.use_simulation = tk.BooleanVar(value=False)

        # Create GUI
        self._create_widgets()
        self._setup_callbacks()

        # Initialize with first installation
        if self.installations:
            # Set to user-friendly name instead of ID
            first_install_id, first_info = self.installations[0]
            friendly_name = f"{first_info.location}_{first_info.serial_number} ({first_info.installed_power_kwp} kWp)"
            self.selected_installation.set(friendly_name)
            self._on_installation_changed()

    def _create_widgets(self):
        """Create the GUI widgets."""
        # Configure parent
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        # Main scrollable frame with minimal padding
        main_frame = ttk.Frame(self.parent, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.grid_columnconfigure(1, weight=1)

        current_row = 0

        # Title
        title_label = ttk.Label(
            main_frame, text="☀️ Solar Energy Prediction", font=("Arial", 14, "bold")
        )
        title_label.grid(row=current_row, column=0, columnspan=3, pady=(0, 5))
        current_row += 1

        # Data Summary (compact)
        if self.historical_date_range[0] and self.historical_date_range[1]:
            data_info = f"📊 {len(self.installations)} installations • Data: {self.historical_date_range[0].strftime('%Y-%m-%d')} to {self.historical_date_range[1].strftime('%Y-%m-%d')}"
            info_label = ttk.Label(
                main_frame, text=data_info, foreground="navy", font=("Arial", 9)
            )
            info_label.grid(row=current_row, column=0, columnspan=3, pady=(0, 5))
            current_row += 1

        # Installation Selection
        ttk.Label(main_frame, text="🏠 Installation:", font=("Arial", 10, "bold")).grid(
            row=current_row, column=0, sticky=tk.W, pady=(0, 5)
        )
        current_row += 1

        installation_names = [
            f"{info.location}_{info.serial_number} ({info.installed_power_kwp} kWp)"
            for _, info in self.installations
        ]
        self.installation_combo = ttk.Combobox(
            main_frame,
            textvariable=self.selected_installation,
            values=installation_names,
            state="readonly",
            width=50,
        )
        self.installation_combo.grid(
            row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5)
        )
        current_row += 1

        # Installation details
        details_frame = ttk.Frame(main_frame)
        details_frame.grid(
            row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5)
        )
        details_frame.grid_columnconfigure(1, weight=1)
        current_row += 1

        ttk.Label(details_frame, text="📍 Location:", font=("Arial", 9)).grid(
            row=0, column=0, sticky=tk.W
        )
        self.location_label = ttk.Label(
            details_frame, text="-", font=("Arial", 9, "bold"), foreground="darkblue"
        )
        self.location_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 20))

        ttk.Label(details_frame, text="⚡ Capacity:", font=("Arial", 9)).grid(
            row=0, column=2, sticky=tk.W
        )
        self.capacity_label = ttk.Label(
            details_frame, text="-", font=("Arial", 9, "bold"), foreground="darkblue"
        )
        self.capacity_label.grid(row=0, column=3, sticky=tk.W, padx=(5, 0))

        # Date Selection
        ttk.Label(
            main_frame, text="📅 Prediction Date:", font=("Arial", 10, "bold")
        ).grid(row=current_row, column=0, sticky=tk.W, pady=(0, 5))
        current_row += 1

        date_frame = ttk.Frame(main_frame)
        date_frame.grid(
            row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )
        current_row += 1

        # Year dropdown
        ttk.Label(date_frame, text="Year:", font=("Arial", 9)).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5)
        )
        self.year_var = tk.StringVar()
        self.year_combo = ttk.Combobox(
            date_frame, textvariable=self.year_var, width=8, state="readonly"
        )
        self.year_combo.grid(row=0, column=1, padx=(0, 10))

        # Month dropdown
        ttk.Label(date_frame, text="Month:", font=("Arial", 9)).grid(
            row=0, column=2, sticky=tk.W, padx=(0, 5)
        )
        self.month_var = tk.StringVar()
        months = [
            "01-Jan",
            "02-Feb",
            "03-Mar",
            "04-Apr",
            "05-May",
            "06-Jun",
            "07-Jul",
            "08-Aug",
            "09-Sep",
            "10-Oct",
            "11-Nov",
            "12-Dec",
        ]
        self.month_combo = ttk.Combobox(
            date_frame,
            textvariable=self.month_var,
            values=months,
            width=10,
            state="readonly",
        )
        self.month_combo.grid(row=0, column=3, padx=(0, 10))

        # Day dropdown
        ttk.Label(date_frame, text="Day:", font=("Arial", 9)).grid(
            row=0, column=4, sticky=tk.W, padx=(0, 5)
        )
        self.day_var = tk.StringVar()
        self.day_combo = ttk.Combobox(
            date_frame, textvariable=self.day_var, width=6, state="readonly"
        )
        self.day_combo.grid(row=0, column=5, padx=(0, 15))

        # Quick date buttons (row 1)
        button_frame = ttk.Frame(date_frame)
        button_frame.grid(row=1, column=0, columnspan=6, pady=(10, 0))
        ttk.Button(
            button_frame,
            text="Today",
            width=8,
            command=lambda: self._set_quick_date(datetime.now()),
        ).grid(row=0, column=0, padx=2)
        ttk.Button(
            button_frame,
            text="Tomorrow",
            width=8,
            command=lambda: self._set_quick_date(datetime.now() + timedelta(days=1)),
        ).grid(row=0, column=1, padx=2)
        ttk.Button(
            button_frame,
            text="Next Week",
            width=8,
            command=lambda: self._set_quick_date(datetime.now() + timedelta(days=7)),
        ).grid(row=0, column=2, padx=2)

        # Date info
        self.date_info_label = ttk.Label(main_frame, text="", font=("Arial", 9))
        self.date_info_label.grid(
            row=current_row, column=0, columnspan=3, sticky=tk.W, pady=(0, 5)
        )
        current_row += 1

        # Options
        options_frame = ttk.Frame(main_frame)
        options_frame.grid(
            row=current_row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 5)
        )
        current_row += 1

        self.simulation_check = ttk.Checkbutton(
            options_frame,
            text="🔮 Use weather simulation for missing data",
            variable=self.use_simulation,
        )
        self.simulation_check.grid(row=0, column=0, sticky=tk.W)

        # Action Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=current_row, column=0, columnspan=3, pady=(0, 5))
        current_row += 1

        self.predict_button = ttk.Button(
            button_frame,
            text="🚀 Generate Prediction",
            command=self._on_predict_clicked,
            style="Accent.TButton",
            width=20,
        )
        self.predict_button.grid(row=0, column=0, padx=(0, 10))

        ttk.Button(
            button_frame, text="🔄 Reset", command=self._on_reset_clicked, width=12
        ).grid(row=0, column=1)

        # Status
        self.status_label = ttk.Label(
            main_frame,
            text="✅ Ready - Select installation and date, then click Generate Prediction",
            foreground="green",
            font=("Arial", 10),
            wraplength=600,
        )
        self.status_label.grid(
            row=current_row, column=0, columnspan=3, sticky=tk.W, pady=(3, 0)
        )

        # Initialize date dropdowns
        self._populate_date_dropdowns()
        if self.historical_date_range[0] and self.historical_date_range[1]:
            # Set to middle of historical range
            mid_date = (
                self.historical_date_range[0]
                + (self.historical_date_range[1] - self.historical_date_range[0]) / 2
            )
            self._set_date_from_datetime(mid_date)
            self._on_date_changed()

    def _setup_callbacks(self):
        """Setup event callbacks."""
        self.installation_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._on_installation_changed()
        )

        # Date dropdown callbacks
        self.year_combo.bind("<<ComboboxSelected>>", lambda e: self._on_date_changed())
        self.month_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._update_days_and_validate()
        )
        self.day_combo.bind("<<ComboboxSelected>>", lambda e: self._on_date_changed())

    def _populate_date_dropdowns(self):
        """Populate the year, month, and day dropdowns."""
        # Populate years (from historical range + future years)
        if self.historical_date_range[0] and self.historical_date_range[1]:
            start_year = self.historical_date_range[0].year
            end_year = max(self.historical_date_range[1].year, datetime.now().year + 5)
        else:
            start_year = datetime.now().year - 5
            end_year = datetime.now().year + 5

        years = [str(year) for year in range(start_year, end_year + 1)]
        self.year_combo["values"] = years

        # Days will be populated based on month/year selection
        self._update_days_dropdown()

    def _update_days_dropdown(self):
        """Update days dropdown based on selected year and month."""
        try:
            year_str = self.year_var.get()
            month_str = self.month_var.get()

            if year_str and month_str:
                year = int(year_str)
                month = int(month_str.split("-")[0])  # Extract month number

                # Get number of days in the month
                days_in_month = calendar.monthrange(year, month)[1]
                days = [f"{i:02d}" for i in range(1, days_in_month + 1)]
            else:
                days = [f"{i:02d}" for i in range(1, 32)]  # Default to 31 days

            self.day_combo["values"] = days

            # Keep current day if valid
            current_day = self.day_var.get()
            if current_day not in days and days:
                self.day_var.set(days[0])  # Set to first day if current is invalid

        except Exception as e:
            logger.error(f"Error updating days dropdown: {e}")
            # Fallback
            self.day_combo["values"] = [f"{i:02d}" for i in range(1, 32)]

    def _update_days_and_validate(self):
        """Update days dropdown and trigger date validation."""
        self._update_days_dropdown()
        self._on_date_changed()

    def _set_date_from_datetime(self, dt: datetime):
        """Set the dropdown values from a datetime object."""
        self.year_var.set(str(dt.year))
        self.month_var.set(f"{dt.month:02d}-{dt.strftime('%b')}")
        self._update_days_dropdown()  # Update days for the new month/year
        self.day_var.set(f"{dt.day:02d}")

    def _get_selected_date(self) -> datetime | None:
        """Get the currently selected date as a datetime object."""
        try:
            year_str = self.year_var.get()
            month_str = self.month_var.get()
            day_str = self.day_var.get()

            if year_str and month_str and day_str:
                year = int(year_str)
                month = int(month_str.split("-")[0])  # Extract month number
                day = int(day_str)
                return datetime(year, month, day)
            return None
        except Exception as e:
            logger.error(f"Error getting selected date: {e}")
            return None

    def _set_quick_date(self, date: datetime):
        """Set a quick date using the dropdown system."""
        self._set_date_from_datetime(date)
        self._on_date_changed()

    def _on_installation_changed(self):
        """Handle installation selection change."""
        try:
            selected_text = self.selected_installation.get()
            if not selected_text:
                return

            # Find the installation info
            installation_info = None
            for inst_id, info in self.installations:
                if selected_text.startswith(f"{info.location}_{info.serial_number}"):
                    installation_info = info
                    break

            if installation_info:
                # Update display labels
                self.capacity_label.config(
                    text=f"{installation_info.installed_power_kwp} kWp"
                )
                self.location_label.config(text=installation_info.location)

                self.status_label.config(
                    text=f"✅ Selected: {installation_info.location} ({installation_info.installed_power_kwp} kWp) - Choose date and generate prediction",
                    foreground="green",
                )

                logger.info(
                    f"Selected installation: {installation_info.installation_id}"
                )

        except Exception as e:
            logger.error(f"Error handling installation change: {e}")

    def _on_date_changed(self):
        """Handle date selection change."""
        try:
            selected_datetime = self._get_selected_date()
            if not selected_datetime:
                self.date_info_label.config(
                    text="⚠️ Please select a complete date", foreground="orange"
                )
                return

            # Check if date is in historical range
            is_historical = self.data_processor.is_date_in_historical_range(
                selected_datetime
            )

            if is_historical:
                self.date_info_label.config(
                    text="📊 Selected date has historical data available",
                    foreground="darkgreen",
                )
                self.simulation_check.config(state="normal")
            else:
                self.date_info_label.config(
                    text="🔮 Selected date requires weather simulation",
                    foreground="orange",
                )
                self.use_simulation.set(True)
                self.simulation_check.config(state="disabled")

        except Exception as e:
            logger.error(f"Error handling date change: {e}")

    def _on_predict_clicked(self):
        """Handle predict button click."""
        try:
            # Validate inputs
            if not self.selected_installation.get():
                messagebox.showerror("Error", "Please select an installation.")
                return

            # Get installation ID
            installation_id = None
            selected_text = self.selected_installation.get()
            for inst_id, info in self.installations:
                if selected_text.startswith(f"{info.location}_{info.serial_number}"):
                    installation_id = inst_id
                    break

            if not installation_id:
                messagebox.showerror("Error", "Invalid installation selection.")
                return

            # Get selected date
            selected_datetime = self._get_selected_date()
            if not selected_datetime:
                messagebox.showerror("Error", "Please select a valid date.")
                return

            # Update UI to show processing
            self.predict_button.config(state="disabled", text="🔄 Generating...")
            self.status_label.config(
                text="🔄 Generating 15-day prediction... This may take a moment.",
                foreground="blue",
            )

            # Call the prediction callback
            self.on_predict_callback(
                installation_id, selected_datetime, self.use_simulation.get()
            )

            # Re-enable button (callback will handle final status)
            self.parent.after(
                2000,
                lambda: self.predict_button.config(
                    state="normal", text="🚀 Generate Prediction"
                ),
            )

        except Exception as e:
            logger.error(f"Error handling predict click: {e}")
            messagebox.showerror("Error", f"Failed to start prediction: {e}")
            self.predict_button.config(state="normal", text="🚀 Generate Prediction")

    def _on_reset_clicked(self):
        """Handle reset button click."""
        if self.installations:
            # Set to user-friendly name instead of ID
            first_install_id, first_info = self.installations[0]
            friendly_name = f"{first_info.location}_{first_info.serial_number} ({first_info.installed_power_kwp} kWp)"
            self.selected_installation.set(friendly_name)
            self._on_installation_changed()

        # Reset to middle of historical range
        if self.historical_date_range[0] and self.historical_date_range[1]:
            mid_date = (
                self.historical_date_range[0]
                + (self.historical_date_range[1] - self.historical_date_range[0]) / 2
            )
            self._set_date_from_datetime(mid_date)

        self.use_simulation.set(False)
        self._on_date_changed()

        self.status_label.config(
            text="✅ Reset complete - Ready for new prediction", foreground="green"
        )
