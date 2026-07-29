"""
Responsive Input Window

Shows available data information upfront and provides clear user feedback.
Displays historical date ranges and installation details immediately.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from tkcalendar import DateEntry

# Local imports
from ..data_processing.comprehensive_data_processor import (
    ComprehensiveDataProcessor,
)

logger = logging.getLogger(__name__)


class ResponsiveInputWindow:
    """
    Responsive input window for the FilantropiaSolar application.

    Features:
    - Immediate display of available data ranges
    - Clear visual feedback about data availability
    - Installation details shown upfront
    - Real-time validation and guidance
    """

    def __init__(
        self,
        parent,
        data_processor: ComprehensiveDataProcessor,
        on_predict_callback: Callable[[str, datetime, bool], None],
    ):
        """Initialize the responsive input window."""
        self.parent = parent
        self.data_processor = data_processor
        self.on_predict_callback = on_predict_callback

        # Data
        self.installations = data_processor.get_installation_list()
        self.historical_date_range = data_processor.get_date_range()

        # GUI variables
        self.selected_installation = tk.StringVar()
        self.selected_date = tk.StringVar()
        self.use_simulation = tk.BooleanVar(value=False)
        self.date_mode = tk.StringVar(value="historical")  # "historical" or "future"

        # Create GUI
        self._create_widgets()
        self._setup_callbacks()

        # Initialize with first installation
        if self.installations:
            self.selected_installation.set(self.installations[0][0])
            self._on_installation_changed()

    def _create_widgets(self):
        """Create the GUI widgets."""
        # Configure parent to expand
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        # Create scrollable canvas
        canvas = tk.Canvas(self.parent)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Bind mouse wheel scrolling for all platforms
        def _on_mousewheel(event):
            # macOS uses event.delta directly, Windows/Linux use event.delta/120
            if abs(event.delta) < 5:  # macOS style
                canvas.yview_scroll(int(-1 * event.delta), "units")
            else:  # Windows/Linux style
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))  # Linux

        # Store canvas reference for later use
        self.canvas = canvas

        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Main frame inside scrollable area
        main_frame = ttk.Frame(scrollable_frame, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(
            main_frame, text="Solar Energy Prediction", font=("Arial", 14, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 10))

        # Data Overview Section (NEW - shows what's available immediately)
        self._create_data_overview_section(main_frame, 1)

        # Installation Selection Section
        self._create_installation_section(main_frame, 2)

        # Date Selection Section
        self._create_date_section(main_frame, 3)

        # Prediction Options Section
        self._create_options_section(main_frame, 4)

        # Action Buttons
        self._create_action_buttons(main_frame, 5)

        # Status Section
        self._create_status_section(main_frame, 6)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)

    def _create_data_overview_section(self, parent, row):
        """Create data overview section showing available data at a glance."""
        # Section frame
        overview_frame = ttk.LabelFrame(
            parent, text="📊 Available Data Overview", padding="10"
        )
        overview_frame.grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8)
        )
        overview_frame.columnconfigure(1, weight=1)

        # Create summary text
        summary_text = self._generate_data_summary()

        # Summary display
        summary_label = ttk.Label(
            overview_frame, text=summary_text, font=("Courier", 9), foreground="navy"
        )
        summary_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

        # Highlight historical date range
        if self.historical_date_range[0] and self.historical_date_range[1]:
            date_range_frame = ttk.Frame(overview_frame)
            date_range_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E))

            ttk.Label(
                date_range_frame,
                text="📅 Historical Data Range:",
                font=("Arial", 10, "bold"),
            ).grid(row=0, column=0, sticky=tk.W)

            range_text = f"{self.historical_date_range[0].strftime('%Y-%m-%d')} to {self.historical_date_range[1].strftime('%Y-%m-%d')}"
            ttk.Label(
                date_range_frame,
                text=range_text,
                foreground="darkgreen",
                font=("Arial", 10, "bold"),
            ).grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

            # Duration
            days = (self.historical_date_range[1] - self.historical_date_range[0]).days
            ttk.Label(
                date_range_frame, text=f"({days} days of data)", foreground="gray"
            ).grid(row=0, column=2, sticky=tk.W, padx=(5, 0))

    def _generate_data_summary(self):
        """Generate a compact summary of available data."""
        # Group by location
        locations = {}
        total_capacity = 0
        for inst_id, info in self.installations:
            if info.location not in locations:
                locations[info.location] = []
            locations[info.location].append(info)
            total_capacity += info.installed_power_kwp

        # Create compact summary
        location_summary = []
        for location, installs in locations.items():
            capacity = sum(info.installed_power_kwp for info in installs)
            location_summary.append(f"{location}: {len(installs)}({capacity}kWp)")

        summary = f"🏠 {len(self.installations)} Installations: {', '.join(location_summary)}\n"
        summary += f"💡 Total Capacity: {total_capacity} kWp"

        return summary

    def _create_installation_section(self, parent, row):
        """Create the installation selection section."""
        # Section frame
        install_frame = ttk.LabelFrame(
            parent, text="🏠 Installation Selection", padding="10"
        )
        install_frame.grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8)
        )
        install_frame.columnconfigure(1, weight=1)

        # Installation dropdown
        ttk.Label(install_frame, text="Installation:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )

        installation_names = [
            f"{info.location}_{info.serial_number} ({info.installed_power_kwp} kWp)"
            for _, info in self.installations
        ]
        self.installation_combo = ttk.Combobox(
            install_frame,
            textvariable=self.selected_installation,
            values=installation_names,
            state="readonly",
            width=50,
        )
        self.installation_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))

        # Installation details frame
        details_frame = ttk.Frame(install_frame)
        details_frame.grid(
            row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0)
        )
        details_frame.columnconfigure(1, weight=1)
        details_frame.columnconfigure(3, weight=1)

        # Capacity display
        ttk.Label(details_frame, text="Capacity:").grid(row=0, column=0, sticky=tk.W)
        self.capacity_label = ttk.Label(
            details_frame, text="-", font=("Arial", 10, "bold"), foreground="darkblue"
        )
        self.capacity_label.grid(row=0, column=1, sticky=tk.W, padx=(5, 20))

        # Location display
        ttk.Label(details_frame, text="Location:").grid(row=0, column=2, sticky=tk.W)
        self.location_label = ttk.Label(
            details_frame, text="-", font=("Arial", 10, "bold"), foreground="darkblue"
        )
        self.location_label.grid(row=0, column=3, sticky=tk.W, padx=(5, 0))

        # Coordinates display
        ttk.Label(details_frame, text="Coordinates:").grid(row=1, column=0, sticky=tk.W)
        self.coordinates_label = ttk.Label(details_frame, text="-", foreground="gray")
        self.coordinates_label.grid(
            row=1, column=1, columnspan=3, sticky=tk.W, padx=(5, 0)
        )

    def _create_date_section(self, parent, row):
        """Create the date selection section."""
        # Section frame
        date_frame = ttk.LabelFrame(parent, text="📅 Date Selection", padding="10")
        date_frame.grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8)
        )
        date_frame.columnconfigure(1, weight=1)

        # Date mode selection
        mode_frame = ttk.Frame(date_frame)
        mode_frame.grid(
            row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10)
        )

        ttk.Label(mode_frame, text="Date Mode:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10)
        )

        ttk.Radiobutton(
            mode_frame,
            text="Historical Data (Real Data)",
            variable=self.date_mode,
            value="historical",
        ).grid(row=0, column=1, sticky=tk.W, padx=(0, 20))

        ttk.Radiobutton(
            mode_frame,
            text="Future/Simulation (Predicted Weather)",
            variable=self.date_mode,
            value="future",
        ).grid(row=0, column=2, sticky=tk.W)

        # Date selection
        ttk.Label(date_frame, text="Select Date:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10)
        )

        # Date entry widget
        self.date_entry = DateEntry(
            date_frame,
            width=12,
            background="darkblue",
            foreground="white",
            borderwidth=2,
            date_pattern="yyyy-mm-dd",
        )
        self.date_entry.grid(row=1, column=1, sticky=tk.W, padx=(0, 10))

        # Date range info and validation
        self.date_info_frame = ttk.Frame(date_frame)
        self.date_info_frame.grid(
            row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0)
        )

        self.date_info_label = ttk.Label(
            self.date_info_frame, text="", foreground="blue"
        )
        self.date_info_label.grid(row=0, column=0, sticky=tk.W)

        # Date validation status icon
        self.date_status_label = ttk.Label(
            self.date_info_frame, text="", font=("Arial", 12)
        )
        self.date_status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))

    def _create_options_section(self, parent, row):
        """Create the prediction options section."""
        # Section frame
        options_frame = ttk.LabelFrame(
            parent, text="⚙️ Prediction Options", padding="10"
        )
        options_frame.grid(
            row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8)
        )

        # Simulation option
        self.simulation_check = ttk.Checkbutton(
            options_frame,
            text="Use weather simulation for missing data",
            variable=self.use_simulation,
        )
        self.simulation_check.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        # Period info
        period_info = ttk.Label(
            options_frame,
            text="📊 Prediction will cover 15 days: 7 days before + selected date + 7 days after",
            foreground="gray",
        )
        period_info.grid(row=1, column=0, sticky=tk.W)

    def _create_action_buttons(self, parent, row):
        """Create the action buttons."""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=3, pady=(10, 8))

        # Predict button
        self.predict_button = ttk.Button(
            button_frame,
            text="🚀 Generate Prediction",
            command=self._on_predict_clicked,
            style="Accent.TButton",
        )
        self.predict_button.grid(row=0, column=0, padx=(0, 10))

        # Clear button
        clear_button = ttk.Button(
            button_frame, text="🗑️ Clear Selection", command=self._on_clear_clicked
        )
        clear_button.grid(row=0, column=1, padx=(10, 0))

        # Quick date buttons
        quick_frame = ttk.Frame(button_frame)
        quick_frame.grid(row=0, column=2, padx=(20, 0))

        ttk.Label(quick_frame, text="Quick Select:", foreground="gray").grid(
            row=0, column=0, padx=(0, 5)
        )

        ttk.Button(
            quick_frame,
            text="Today",
            width=8,
            command=lambda: self._set_quick_date(datetime.now()),
        ).grid(row=0, column=1, padx=2)

        ttk.Button(
            quick_frame,
            text="Tomorrow",
            width=8,
            command=lambda: self._set_quick_date(datetime.now() + timedelta(days=1)),
        ).grid(row=0, column=2, padx=2)

        ttk.Button(
            quick_frame,
            text="Next Week",
            width=8,
            command=lambda: self._set_quick_date(datetime.now() + timedelta(days=7)),
        ).grid(row=0, column=3, padx=2)

    def _create_status_section(self, parent, row):
        """Create the status section."""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)

        # Status label
        self.status_label = ttk.Label(
            status_frame,
            text="✅ Ready - Select an installation and date to generate predictions.",
            foreground="green",
            font=("Arial", 10),
        )
        self.status_label.grid(row=0, column=0, sticky=tk.W)

    def _setup_callbacks(self):
        """Setup event callbacks."""
        self.installation_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._on_installation_changed()
        )
        self.date_mode.trace_add("write", lambda *args: self._on_date_mode_changed())
        self.date_entry.bind("<<DateEntrySelected>>", lambda e: self._on_date_changed())

    def _set_quick_date(self, date: datetime):
        """Set a quick date and update mode appropriately."""
        self.date_entry.set_date(date.date())

        # Determine if this should be historical or future mode
        if self.data_processor.is_date_in_historical_range(date):
            self.date_mode.set("historical")
        else:
            self.date_mode.set("future")

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
                self.coordinates_label.config(
                    text=f"{installation_info.latitude:.3f}°N, {installation_info.longitude:.3f}°E"
                )

                # Update status
                self.status_label.config(
                    text=f"✅ Selected: {installation_info.location} installation with "
                    f"{installation_info.installed_power_kwp} kWp capacity"
                )

                logger.info(
                    f"Selected installation: {installation_info.installation_id}"
                )

        except Exception as e:
            logger.error(f"Error handling installation change: {e}")

    def _on_date_mode_changed(self):
        """Handle date mode change."""
        try:
            mode = self.date_mode.get()

            if mode == "historical":
                # Set date limits to historical range
                if self.historical_date_range[0] and self.historical_date_range[1]:
                    self.date_entry.config(
                        mindate=self.historical_date_range[0].date(),
                        maxdate=self.historical_date_range[1].date(),
                    )
                    self.date_info_label.config(
                        text=f"Historical data available: {self.historical_date_range[0].date()} "
                        f"to {self.historical_date_range[1].date()}",
                        foreground="darkgreen",
                    )
                    # Set default date to middle of range
                    mid_date = (
                        self.historical_date_range[0]
                        + (
                            self.historical_date_range[1]
                            - self.historical_date_range[0]
                        )
                        / 2
                    )
                    self.date_entry.set_date(mid_date.date())
                    self.date_status_label.config(text="📊", foreground="green")

            else:  # future mode
                # Remove date limits for future dates
                self.date_entry.config(mindate=None, maxdate=None)
                self.date_info_label.config(
                    text="Future dates will use weather simulation", foreground="orange"
                )
                # Set default to tomorrow
                tomorrow = datetime.now() + timedelta(days=1)
                self.date_entry.set_date(tomorrow.date())
                self.date_status_label.config(text="🔮", foreground="orange")

                # Enable simulation checkbox
                self.use_simulation.set(True)

            self._on_date_changed()

        except Exception as e:
            logger.error(f"Error handling date mode change: {e}")

    def _on_date_changed(self):
        """Handle date selection change."""
        try:
            selected_date = self.date_entry.get_date()
            selected_datetime = datetime.combine(selected_date, datetime.min.time())

            # Check if date is in historical range
            is_historical = self.data_processor.is_date_in_historical_range(
                selected_datetime
            )

            if is_historical:
                self.date_info_label.config(
                    text="✅ Selected date has historical data available",
                    foreground="darkgreen",
                )
                self.date_status_label.config(text="📊", foreground="green")
                # Simulation is optional for historical dates
                self.simulation_check.config(state="normal")
            else:
                self.date_info_label.config(
                    text="🔮 Selected date requires weather simulation",
                    foreground="orange",
                )
                self.date_status_label.config(text="🔮", foreground="orange")
                # Force simulation for non-historical dates
                self.use_simulation.set(True)
                self.simulation_check.config(state="disabled")

            # Update status message
            date_str = selected_date.strftime("%Y-%m-%d")
            if is_historical:
                self.status_label.config(
                    text=f"✅ Ready to predict for {date_str} using historical data",
                    foreground="green",
                )
            else:
                self.status_label.config(
                    text=f"🔮 Ready to predict for {date_str} using weather simulation",
                    foreground="orange",
                )

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
            try:
                selected_date = self.date_entry.get_date()
                selected_datetime = datetime.combine(selected_date, datetime.min.time())
            except Exception as e:
                messagebox.showerror("Error", f"Invalid date selection: {e}")
                return

            # Update UI to show processing
            self.predict_button.config(state="disabled", text="🔄 Processing...")
            self.status_label.config(
                text="🔄 Generating predictions... This may take a moment.",
                foreground="blue",
            )

            # Call the prediction callback
            self.on_predict_callback(
                installation_id, selected_datetime, self.use_simulation.get()
            )

            # Re-enable button (callback will handle final status)
            self.root.after(
                1000,
                lambda: self.predict_button.config(
                    state="normal", text="🚀 Generate Prediction"
                ),
            )

        except Exception as e:
            logger.error(f"Error handling predict click: {e}")
            messagebox.showerror("Error", f"Failed to start prediction: {e}")
            self.predict_button.config(state="normal", text="🚀 Generate Prediction")

    def _on_clear_clicked(self):
        """Handle clear button click."""
        if self.installations:
            self.selected_installation.set(self.installations[0][0])
            self._on_installation_changed()

        self.date_mode.set("historical")
        self.use_simulation.set(False)
        self._on_date_mode_changed()

        self.status_label.config(
            text="✅ Selection cleared - Ready for new prediction", foreground="green"
        )

    @property
    def root(self):
        """Get the root window for after() calls."""
        return self.parent.winfo_toplevel()
