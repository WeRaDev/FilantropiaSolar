"""
Energy Ranking System for FilantropiaSolar
Provides ranking functionality based on specific energy values (kWh/kWp)
"""

import numpy as np
import pandas as pd

# Energy ranking thresholds (kWh/kWp)
RANK_1_MIN_THRESHOLD = 0.1  # Poor performance minimum
RANK_2_THRESHOLD = 0.2  # Fair performance start
RANK_3_THRESHOLD = 0.4  # Good performance start
RANK_4_THRESHOLD = 0.6  # Very Good performance start
RANK_5_THRESHOLD = 0.8  # Excellent performance start
OPTIMAL_RANK_THRESHOLD = 4  # Minimum rank considered optimal


def calculate_specific_energy_ranking(specific_energy):
    """
    Calculate ranking (1-5) based on specific energy value (kWh/kWp)

    Ranking system:
    - Rank 1: 0.1 - 0.2 kWh/kWp (Poor)
    - Rank 2: 0.2 - 0.4 kWh/kWp (Fair)
    - Rank 3: 0.4 - 0.6 kWh/kWp (Good)
    - Rank 4: 0.6 - 0.8 kWh/kWp (Very Good)
    - Rank 5: 0.8 - 1.0+ kWh/kWp (Excellent)

    Args:
        specific_energy (float or pd.Series): Specific energy value(s) in kWh/kWp

    Returns:
        int or pd.Series: Ranking value(s) from 1 to 5
    """
    if isinstance(specific_energy, pd.Series):
        return specific_energy.apply(_get_single_ranking)
    else:
        return _get_single_ranking(specific_energy)


def _get_single_ranking(value):
    """Helper function to rank a single specific energy value"""
    if pd.isna(value) or value < RANK_1_MIN_THRESHOLD or value < RANK_2_THRESHOLD:
        return 1
    elif value < RANK_3_THRESHOLD:
        return 2
    elif value < RANK_4_THRESHOLD:
        return 3
    elif value < RANK_5_THRESHOLD:
        return 4
    else:  # >= RANK_5_THRESHOLD
        return 5


def get_ranking_description(rank):
    """
    Get description for a given ranking

    Args:
        rank (int): Ranking from 1 to 5

    Returns:
        str: Description of the ranking
    """
    descriptions = {
        1: "Poor (0.1-0.2 kWh/kWp)",
        2: "Fair (0.2-0.4 kWh/kWp)",
        3: "Good (0.4-0.6 kWh/kWp)",
        4: "Very Good (0.6-0.8 kWh/kWp)",
        5: "Excellent (≥0.8 kWh/kWp)",
    }
    return descriptions.get(rank, "Unknown")


def get_ranking_color(rank):
    """
    Get color code for visualization based on ranking

    Args:
        rank (int): Ranking from 1 to 5

    Returns:
        str: Hex color code
    """
    colors = {
        1: "#FF4444",  # Red
        2: "#FF8C00",  # Orange
        3: "#FFD700",  # Gold
        4: "#32CD32",  # Green
        5: "#00AA00",  # Dark Green
    }
    return colors.get(rank, "#666666")


def calculate_average_ranking(rankings):
    """
    Calculate average ranking from a list or series of rankings

    Args:
        rankings (list or pd.Series): List of ranking values

    Returns:
        float: Average ranking rounded to 1 decimal place
    """
    if isinstance(rankings, (list, pd.Series)):
        valid_rankings = [r for r in rankings if not pd.isna(r)]
        if valid_rankings:
            return round(np.mean(valid_rankings), 1)
    return 0.0


def get_optimal_hours(df, date, ranking_threshold=4):
    """
    Get optimal hours for solar energy usage based on ranking threshold

    Args:
        df (pd.DataFrame): DataFrame with columns ['Date', 'Hour', 'Ranking']
        date (str or pd.Timestamp): Target date
        ranking_threshold (int): Minimum ranking for optimal hours

    Returns:
        list: List of optimal hours
    """
    if isinstance(date, str):
        date = pd.to_datetime(date).date()
    elif hasattr(date, "date"):
        date = date.date()

    day_data = df[df["Date"].dt.date == date]
    optimal_hours = day_data[day_data["Ranking"] >= ranking_threshold]["Hour"].tolist()

    return sorted(optimal_hours)


def generate_ranking_summary(df):
    """
    Generate summary statistics for rankings in a DataFrame

    Args:
        df (pd.DataFrame): DataFrame containing 'Ranking' column

    Returns:
        dict: Summary statistics
    """
    if "Ranking" not in df.columns:
        return {}

    rankings = df["Ranking"].dropna()

    if rankings.empty:
        return {}

    summary = {
        "average_ranking": round(rankings.mean(), 2),
        "median_ranking": rankings.median(),
        "ranking_distribution": rankings.value_counts().sort_index().to_dict(),
        "optimal_hours_count": len(
            rankings[rankings >= OPTIMAL_RANK_THRESHOLD],
        ),  # Rank 4 and 5
        "total_hours": len(rankings),
    }

    # Calculate percentage of optimal hours
    if summary["total_hours"] > 0:
        summary["optimal_hours_percentage"] = round(
            (summary["optimal_hours_count"] / summary["total_hours"]) * 100,
            1,
        )

    return summary


# Backward-compatibility shims expected by tests


def get_energy_rank(specific_energy):
    """Alias for calculate_specific_energy_ranking for backward compatibility."""
    return calculate_specific_energy_ranking(specific_energy)


def get_rank_color(rank: int) -> str:
    """Alias for get_ranking_color for backward compatibility."""
    return get_ranking_color(rank)
