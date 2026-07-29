"""
Utilities module for FilantropiaSolar
"""

from .energy_ranking import (
    calculate_average_ranking,
    calculate_specific_energy_ranking,
    generate_ranking_summary,
    get_optimal_hours,
    get_ranking_color,
    get_ranking_description,
)

__all__ = [
    "calculate_average_ranking",
    "calculate_specific_energy_ranking",
    "generate_ranking_summary",
    "get_optimal_hours",
    "get_ranking_color",
    "get_ranking_description",
]
