"""
Utilities module for FilantropiaSolar
"""

from .energy_ranking import (
    calculate_specific_energy_ranking,
    get_ranking_description,
    get_ranking_color,
    calculate_average_ranking,
    get_optimal_hours,
    generate_ranking_summary
)

__all__ = [
    'calculate_specific_energy_ranking',
    'get_ranking_description', 
    'get_ranking_color',
    'calculate_average_ranking',
    'get_optimal_hours',
    'generate_ranking_summary'
]