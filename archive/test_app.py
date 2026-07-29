#!/usr/bin/env python3
"""
Simple test script for FilantropiaSolar
Tests core functionality without GUI
"""

import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.data_processing.lisbon_data_processor import LisbonDataProcessor
from src.prediction.energy_predictor import EnergyPredictor
from src.utils.energy_ranking import calculate_specific_energy_ranking, get_ranking_description

def test_data_loading():
    """Test data loading functionality"""
    print("🔄 Testing data loading...")
    
    processor = LisbonDataProcessor()
    
    # Load PV data
    pv_data = processor.load_pv_data()
    if pv_data:
        print(f"✅ Loaded PV data for {len(pv_data)} installations")
        for installation, df in pv_data.items():
            print(f"   - {installation}: {len(df)} records")
    else:
        print("❌ Failed to load PV data")
        return False
    
    # Load weather data
    weather_data = processor.load_weather_data()
    if not weather_data.empty:
        print(f"✅ Loaded weather data: {len(weather_data)} records")
    else:
        print("❌ Failed to load weather data")
        return False
    
    return True

def test_model_training():
    """Test model training"""
    print("\n🔄 Testing model training...")
    
    processor = LisbonDataProcessor()
    processor.load_pv_data()
    processor.load_weather_data()
    
    # Test with Lisbon_1
    installation = "Lisbon_1"
    merged_data = processor.merge_pv_weather_data(installation)
    
    if merged_data.empty:
        print("❌ No merged data available")
        return False
    
    print(f"✅ Merged data: {len(merged_data)} records")
    
    # Train model
    predictor = EnergyPredictor(installation)
    results = predictor.train_models(merged_data)
    
    if results:
        print(f"✅ Model trained successfully")
        for model_name, metrics in results.items():
            print(f"   - {model_name}: R²={metrics['r2']:.3f}, MAE={metrics['mae']:.3f}")
        
        if predictor.best_model_name:
            print(f"✅ Best model selected: {predictor.best_model_name}")
            return True
    
    print("❌ Model training failed")
    return False

def test_historical_prediction():
    """Test prediction with historical data"""
    print("\n🔄 Testing historical prediction...")
    
    processor = LisbonDataProcessor()
    processor.load_pv_data()
    processor.load_weather_data()
    
    installation = "Lisbon_1"
    merged_data = processor.merge_pv_weather_data(installation)
    
    # Train model
    predictor = EnergyPredictor(installation)
    predictor.train_models(merged_data)
    
    if not predictor.is_trained:
        print("❌ Model not trained")
        return False
    
    # Use a subset of historical weather data for prediction
    historical_sample = processor.weather_data.head(24).copy()  # First 24 hours
    
    try:
        predictions = predictor.predict_energy(historical_sample, installed_capacity_kwp=10.0)
        
        if predictions.empty:
            print("❌ No predictions generated")
            return False
        
        print(f"✅ Generated {len(predictions)} predictions")
        
        # Show sample results
        if len(predictions) > 0:
            sample = predictions.iloc[0]
            energy = sample['Predicted Energy (kWh)']
            specific_energy = sample['Specific Energy (kWh/kWp)']
            ranking = sample['Ranking']
            
            print(f"   Sample result:")
            print(f"   - Energy: {energy:.2f} kWh")
            print(f"   - Specific Energy: {specific_energy:.3f} kWh/kWp")
            print(f"   - Ranking: {ranking} ({get_ranking_description(ranking)})")
            
        return True
        
    except Exception as e:
        print(f"❌ Prediction failed: {e}")
        return False

def test_ranking_system():
    """Test ranking system"""
    print("\n🔄 Testing ranking system...")
    
    test_values = [0.15, 0.35, 0.55, 0.75, 0.95]
    expected_ranks = [1, 2, 3, 4, 5]
    
    for value, expected in zip(test_values, expected_ranks):
        rank = calculate_specific_energy_ranking(value)
        description = get_ranking_description(rank)
        
        if rank == expected:
            print(f"✅ {value} kWh/kWp → Rank {rank} ({description})")
        else:
            print(f"❌ {value} kWh/kWp → Expected {expected}, got {rank}")
            return False
    
    return True

def main():
    """Run all tests"""
    print("🌞 FilantropiaSolar - System Test\n")
    
    tests = [
        ("Data Loading", test_data_loading),
        ("Model Training", test_model_training),
        ("Historical Prediction", test_historical_prediction),
        ("Ranking System", test_ranking_system)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED\n")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED\n")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}\n")
    
    print(f"🏁 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The application is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)