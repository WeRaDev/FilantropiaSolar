"""
Output Window

Displays prediction results in a structured format.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class OutputWindow:
    """
    Output window for displaying prediction results.
    """
    
    def __init__(self, parent):
        """Initialize the output window."""
        self.parent = parent
        self.results = None
        
        # Create GUI
        self._create_widgets()
        
    def _create_widgets(self):
        """Create the GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.parent, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Prediction Results & Analysis", 
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Create notebook for different result views
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Summary tab
        summary_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(summary_frame, text="Summary")
        self._create_summary_tab(summary_frame)
        
        # Detailed tab
        detailed_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(detailed_frame, text="Detailed Results")
        self._create_detailed_tab(detailed_frame)
        
        # Initial state
        self._show_no_data()
        
    def _create_summary_tab(self, parent):
        """Create summary results tab."""
        # Scrollable frame
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self.summary_frame = ttk.Frame(canvas)
        
        self.summary_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.summary_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
    def _create_detailed_tab(self, parent):
        """Create detailed results tab."""
        # Text widget with scrollbars
        text_frame = ttk.Frame(parent)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.detailed_text = tk.Text(text_frame, wrap=tk.WORD, font=('Courier', 10))
        scrollbar_y = ttk.Scrollbar(text_frame, orient="vertical", command=self.detailed_text.yview)
        scrollbar_x = ttk.Scrollbar(text_frame, orient="horizontal", command=self.detailed_text.xview)
        
        self.detailed_text.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.detailed_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        scrollbar_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
    def display_results(self, results: Dict[str, Any]):
        """Display prediction results."""
        try:
            self.results = results
            self._update_summary_display()
            self._update_detailed_display()
            
            logger.info("Results displayed in output window")
            
        except Exception as e:
            logger.error(f"Error displaying results: {e}")
            
    def _update_summary_display(self):
        """Update the summary display."""
        # Clear existing content
        for widget in self.summary_frame.winfo_children():
            widget.destroy()
            
        if not self.results:
            self._show_no_data()
            return
            
        try:
            row = 0
            
            # Installation info
            inst_info = self.results['installation_info']
            ttk.Label(self.summary_frame, text="Installation Information", 
                     font=('Arial', 12, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1
            
            ttk.Label(self.summary_frame, text="Location:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=inst_info['location'], 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 1
            
            ttk.Label(self.summary_frame, text="Capacity:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=f"{inst_info['capacity_kwp']} kWp", 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 2
            
            # Period info
            period_info = self.results['prediction_period']
            ttk.Label(self.summary_frame, text="Prediction Period", 
                     font=('Arial', 12, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1
            
            ttk.Label(self.summary_frame, text="Start Date:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=str(period_info['start'].date()), 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 1
            
            ttk.Label(self.summary_frame, text="End Date:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=str(period_info['end'].date()), 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 1
            
            ttk.Label(self.summary_frame, text="Center Date:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=str(period_info['center_date'].date()), 
                     font=('Arial', 10, 'bold', 'underline')).grid(row=row, column=1, sticky=tk.W)
            row += 2
            
            # Statistics
            stats = self.results['period_statistics']
            ttk.Label(self.summary_frame, text="Energy Statistics (15 days)", 
                     font=('Arial', 12, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1
            
            ttk.Label(self.summary_frame, text="Total Energy:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=f"{stats['total_energy_kwh']:.1f} kWh", 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 1
            
            ttk.Label(self.summary_frame, text="Average Specific Energy:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=f"{stats['average_specific_energy']:.2f} kWh/kWp", 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 1
            
            ttk.Label(self.summary_frame, text="Peak Energy Hour:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=f"{stats['peak_hour_energy']:.2f} kWh/kWp", 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 2
            
            # Data source
            source = self.results['data_source']
            ttk.Label(self.summary_frame, text="Data Source Information", 
                     font=('Arial', 12, 'bold')).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
            row += 1
            
            data_type = "Weather Simulation" if source['used_simulation'] else "Historical Data"
            ttk.Label(self.summary_frame, text="Data Type:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=data_type, 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 1
            
            ttk.Label(self.summary_frame, text="Model Used:").grid(row=row, column=0, sticky=tk.W, padx=(20, 10))
            ttk.Label(self.summary_frame, text=source['model_used'].replace('_', ' ').title(), 
                     font=('Arial', 10, 'bold')).grid(row=row, column=1, sticky=tk.W)
            row += 1
            
        except Exception as e:
            logger.error(f"Error updating summary display: {e}")
            
    def _update_detailed_display(self):
        """Update the detailed display."""
        self.detailed_text.delete(1.0, tk.END)
        
        if not self.results:
            self.detailed_text.insert(tk.END, "No prediction results available.\n\n")
            self.detailed_text.insert(tk.END, "Generate a prediction using the Input tab to see detailed results here.")
            return
            
        try:
            # Format detailed results
            text = "FILANTROPIA SOLAR - PREDICTION RESULTS\n"
            text += "=" * 50 + "\n\n"
            
            # Installation details
            inst_info = self.results['installation_info']
            text += f"Installation: {inst_info['location']} (Serial: {inst_info['serial_number']})\n"
            text += f"Capacity: {inst_info['capacity_kwp']} kWp\n\n"
            
            # Prediction period
            period = self.results['prediction_period']
            text += f"Prediction Period: {period['start']} to {period['end']}\n"
            text += f"Center Date: {period['center_date']}\n"
            text += f"Total Hours: {period['total_hours']}\n\n"
            
            # Statistics
            stats = self.results['period_statistics']
            text += "ENERGY STATISTICS (15-day period)\n"
            text += "-" * 40 + "\n"
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    text += f"{key.replace('_', ' ').title()}: {value:.2f}\n"
                else:
                    text += f"{key.replace('_', ' ').title()}: {value}\n"
            
            text += "\n"
            
            # Daily summary
            if 'daily_summary' in self.results:
                daily = self.results['daily_summary']
                text += "DAILY SUMMARY\n"
                text += "-" * 40 + "\n"
                text += f"{'Date':<12} {'Energy(kWh)':<12} {'Specific(kWh/kWp)':<18} {'Ranking':<8}\n"
                text += "-" * 50 + "\n"
                
                for date, row in daily.iterrows():
                    energy = row.get('predicted_total_energy', 0)
                    specific = row.get('predicted_specific_energy', 0)
                    ranking = row.get('ranking', 3)
                    text += f"{str(date):<12} {energy:<12.1f} {specific:<18.2f} {ranking:<8}\n"
            
            # Data source info
            source = self.results['data_source']
            text += "\nDATA SOURCE INFORMATION\n"
            text += "-" * 40 + "\n"
            text += f"Weather Data: {'Simulated' if source['used_simulation'] else 'Historical'}\n"
            text += f"ML Model: {source['model_used'].replace('_', ' ').title()}\n"
            
            if 'model_performance' in source and source['model_used'] in source['model_performance']:
                perf = source['model_performance'][source['model_used']]
                text += f"Model R²: {perf.get('r2', 0):.3f}\n"
                text += f"Model MAE: {perf.get('mae', 0):.3f} kWh/kWp\n"
                
            # Insert text
            self.detailed_text.insert(tk.END, text)
            
        except Exception as e:
            logger.error(f"Error updating detailed display: {e}")
            self.detailed_text.insert(tk.END, f"Error displaying results: {str(e)}")
            
    def _show_no_data(self):
        """Show no data message."""
        for widget in self.summary_frame.winfo_children():
            widget.destroy()
            
        ttk.Label(self.summary_frame, text="No prediction results available.", 
                 font=('Arial', 12)).grid(row=0, column=0, pady=20)
        ttk.Label(self.summary_frame, text="Generate a prediction using the Input tab to see results here.", 
                 foreground="gray").grid(row=1, column=0)
        
    def clear_results(self):
        """Clear displayed results."""
        self.results = None
        self._show_no_data()
        self.detailed_text.delete(1.0, tk.END)
        self.detailed_text.insert(tk.END, "No prediction results available.")