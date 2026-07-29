#!/usr/bin/env python3
"""
Test Enhanced FilantropiaSolar Application (Simplified)

Test version without the plot window to isolate GUI issues.
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
    from src.gui.output_window import OutputWindow
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def main():
    """Simple test main function."""
    logging.basicConfig(level=logging.INFO)
    
    print("Loading data processor...")
    data_processor = ComprehensiveDataProcessor()
    
    print("Creating simple GUI test...")
    root = tk.Tk()
    root.title("Enhanced FilantropiaSolar - Test")
    root.geometry("800x600")
    
    # Create notebook
    notebook = ttk.Notebook(root, padding="10")
    notebook.pack(fill=tk.BOTH, expand=True)
    
    # Test input window
    input_frame = ttk.Frame(notebook)
    notebook.add(input_frame, text="Input Test")
    
    def dummy_callback(inst_id, date, sim):
        print(f"Callback: {inst_id}, {date}, {sim}")
        messagebox.showinfo("Test", f"Prediction requested for {inst_id} on {date}")
    
    input_window = EnhancedInputWindow(input_frame, data_processor, dummy_callback)
    
    # Test output window
    output_frame = ttk.Frame(notebook)
    notebook.add(output_frame, text="Output Test")
    
    output_window = OutputWindow(output_frame)
    
    print("Starting GUI...")
    root.mainloop()


if __name__ == "__main__":
    main()