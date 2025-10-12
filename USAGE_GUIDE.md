# FilantropiaSolar - Usage Guide

This guide provides step-by-step instructions for using the upgraded FilantropiaSolar system.

## Quick Start Guide

### 1. Running the Application

```bash
# Navigate to project directory
cd FilantropiaSolar

# Activate virtual environment (if using one)
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Run the application
python main.py
```

### 2. First Time Usage

When you run the application for the first time:

1. **Data Loading**: The system will automatically load:
   - Historical PV data from `PV Plants Datasets.xlsx`
   - Weather data from `weather_files/Lisbon_weather.csv`
   - This may take 1-2 minutes depending on data size

2. **Model Training**: Machine learning models will be trained:
   - Random Forest, Gradient Boosting, and Linear Regression models
   - Training happens automatically for each Lisbon installation
   - Progress is shown in the status label

3. **Ready State**: Once complete, the status will show "Data loaded successfully"

## Interface Overview

### Input Window (Left Panel)

#### PV Installation Selection
- **Options**: Lisbon_1, Lisbon_2, Lisbon_3, Lisbon_4
- **Purpose**: Each represents a different PV installation in Lisbon
- **Recommendation**: Start with Lisbon_1 for testing

#### Target Date
- **Format**: YYYY-MM-DD (e.g., 2024-03-15)
- **Options**: 
  - **Past dates**: Analyze historical performance
  - **Today**: Current day predictions using real-time weather
  - **Future dates**: Forecast based on weather predictions
- **Tip**: Click "Today" button to quickly set current date

#### Installed Capacity (kWp)
- **Default**: 10.0 kWp
- **Range**: Any positive number
- **Purpose**: Scales energy production to your specific installation size
- **Example**: If you have a 5 kWp system, enter 5.0

### Output Window (Right Panel)

The results display provides comprehensive information:

#### Daily Summary
- **Total Energy Production**: Sum of all hourly predictions for the day
- **Average Specific Energy**: Energy per kWp installed capacity
- **Average Ranking**: Overall quality rating for the day

#### Weather Conditions
- **Average Temperature**: Daily temperature average
- **Average Cloud Cover**: Percentage cloud coverage
- **Average Solar Radiation**: Key parameter affecting solar production

#### Hourly Breakdown
- **24-hour view**: Energy production for each hour
- **Ranking**: Quality rating (1-5) for each hour
- **Format**: "Hour XX: YY.YY kWh (Rank Z)"

#### Weekly Trend
- **±7 days**: Shows 15 days total (7 before + target day + 7 after)
- **Target marker**: "← TARGET" indicates your selected date
- **Comparison**: Compare target day with surrounding dates

### Plot Window (Bottom Panel)

#### Main Chart Elements
- **Blue bars**: Daily energy production
- **Colored edges**: Ranking quality (see legend)
- **Red line**: Temperature overlay
- **Green dashed line**: Target date marker
- **"TARGET" label**: Highlights selected date

#### Ranking Color Legend
- **Red (Rank 1)**: Poor conditions (0.1-0.2 kWh/kWp)
- **Orange (Rank 2)**: Fair conditions (0.2-0.4 kWh/kWp)
- **Gold (Rank 3)**: Good conditions (0.4-0.6 kWh/kWp)
- **Green (Rank 4)**: Very good conditions (0.6-0.8 kWh/kWp)
- **Dark Green (Rank 5)**: Excellent conditions (≥0.8 kWh/kWp)

## Step-by-Step Usage Examples

### Example 1: Analyze Today's Solar Potential

1. **Select Installation**: Choose "Lisbon_1"
2. **Set Date**: Click "Today" button
3. **Set Capacity**: Enter your system size (e.g., 5.0 for 5kWp)
4. **Generate**: Click "Generate Prediction"
5. **Review Results**: 
   - Check daily total energy production
   - Note the average ranking for planning energy usage
   - Look at hourly breakdown to identify peak hours

### Example 2: Plan for Tomorrow

1. **Select Installation**: Choose your preferred installation
2. **Set Date**: Enter tomorrow's date (YYYY-MM-DD)
3. **Set Capacity**: Enter your system capacity
4. **Generate**: Click "Generate Prediction"
5. **Plan Activities**:
   - Rank 4-5 hours: Schedule energy-intensive tasks
   - Rank 1-2 hours: Minimize electrical usage
   - Use weekly trend to compare with other days

### Example 3: Analyze Historical Performance

1. **Select Installation**: Choose installation to analyze
2. **Set Date**: Enter a past date (e.g., 2023-06-15)
3. **Set Capacity**: Enter system capacity
4. **Generate**: Click "Generate Prediction"
5. **Compare**: Use the plot to see how the selected day compares with surrounding dates

### Example 4: Weekly Energy Planning

1. **Select Installation**: Choose your installation
2. **Set Date**: Pick any date of interest
3. **Generate**: Click "Generate Prediction"
4. **Analyze Trend**: Look at the ±7 days view in both text and chart
5. **Identify Patterns**: 
   - Find best days for high energy consumption
   - Schedule maintenance on low-production days
   - Plan battery charging/discharging cycles

## Understanding the Ranking System

### Ranking Interpretation

| Rank | Specific Energy | Recommended Usage |
|------|----------------|-------------------|
| 5 | ≥0.8 kWh/kWp | Maximum energy consumption, run all appliances |
| 4 | 0.6-0.8 kWh/kWp | High energy usage, washing machines, dryers |
| 3 | 0.4-0.6 kWh/kWp | Moderate usage, normal household activities |
| 2 | 0.2-0.4 kWh/kWp | Light usage only, avoid heavy appliances |
| 1 | 0.1-0.2 kWh/kWp | Minimal solar production, rely on grid/battery |

### Practical Applications

#### For Homeowners
- **Rank 5 hours**: Run dishwashers, washing machines, electric cars charging
- **Rank 4 hours**: Most appliances, heat pumps, air conditioning
- **Rank 3 hours**: Normal usage, computers, lights, TV
- **Rank 2 hours**: Light usage, avoid heating/cooling systems
- **Rank 1 hours**: Essential devices only, rely on stored energy

#### For Businesses
- **Rank 5 hours**: Schedule energy-intensive manufacturing
- **Rank 4 hours**: Normal operations, office equipment
- **Rank 3 hours**: Reduced load operations
- **Rank 2 hours**: Essential services only
- **Rank 1 hours**: Switch to backup power/grid

## Troubleshooting

### Common Issues and Solutions

#### "Error loading data"
- **Check**: Ensure Excel files are in the project directory
- **Solution**: Verify `PV Plants Datasets.xlsx` and weather files exist
- **Location**: Files should be in the main project folder

#### "Could not retrieve weather data"
- **Cause**: Internet connection or API issues
- **Solution**: Check internet connection
- **Fallback**: System uses default weather values when API fails

#### "No trained model available"
- **Cause**: Model training failed or insufficient data
- **Solution**: Ensure historical data contains enough records
- **Minimum**: At least 50 data points needed for training

#### "Invalid date format"
- **Format**: Must use YYYY-MM-DD format
- **Examples**: 2024-03-15, 2023-12-01
- **Avoid**: MM/DD/YYYY, DD/MM/YYYY formats

#### GUI not responding
- **Solution**: Close and restart the application
- **Check**: Ensure Python tkinter is properly installed
- **Alternative**: Try running on a different machine

### Performance Tips

#### For Better Predictions
1. **Use recent dates**: Newer weather data provides better accuracy
2. **Correct capacity**: Enter accurate kWp rating for your system
3. **Stable internet**: Ensures reliable weather data retrieval
4. **Regular updates**: Restart application periodically to refresh models

#### For Faster Operation
1. **Close unused applications**: Free up system memory
2. **Stable power**: Avoid interruptions during model training
3. **SSD storage**: Faster file access improves loading times

## Export and Data Management

### Exporting Results
1. **Generate Prediction**: Create the forecast you want to save
2. **Click Export**: Use "Export Results" button in output panel
3. **File Location**: CSV file saved in project directory
4. **Filename Format**: `predictions_{installation}_{date}.csv`
5. **Content**: Complete hourly data with all weather and energy parameters

### File Management
- **Models**: Trained models saved in `models/` directory
- **Logs**: Application logs in `logs/application.log`
- **Exports**: Exported data in project root directory

## Advanced Usage

### Customizing Predictions
- **Multiple Installations**: Compare different installations by switching between them
- **Date Ranges**: Analyze seasonal patterns by testing different months
- **Capacity Scaling**: Test different system sizes to plan upgrades

### Data Analysis
- **Seasonal Comparison**: Compare same dates across different years
- **Weather Impact**: Observe how weather changes affect rankings
- **System Planning**: Use predictions for sizing battery systems or grid connections

## Best Practices

### Daily Usage
1. **Morning Check**: Analyze today's forecast to plan daily activities
2. **Weekly Planning**: Check next 7 days for energy-intensive task scheduling
3. **Regular Monitoring**: Compare actual vs predicted performance

### System Optimization
1. **Peak Hour Identification**: Use hourly breakdown to find best production times
2. **Load Shifting**: Move flexible tasks to high-ranking hours
3. **Storage Planning**: Charge batteries during peak production periods

### Data Interpretation
1. **Trends Over Time**: Look for patterns in weekly views
2. **Weather Correlation**: Notice how weather affects production
3. **Seasonal Variations**: Understand yearly cycles for long-term planning

---

**Need Help?** Check the main README.md for detailed technical information or create an issue on the project repository.