/**
 * Ranking constants and utility functions for FilantropiaSolar.
 *
 * Normalized Specific Energy (NSE) formula: Y / (X * Z)
 *   Y = energy (kWh), X = capacity (kWp), Z = active hours
 *
 * Calibrated for Portuguese PV installations (4-5 kWh/kWp daily yield).
 */

// Colors for each rank tier (R0-R5)
export const RANKING_COLORS = {
    0: '#B0B0B0', // R0: Zero/negligible (excluded from display)
    1: '#DC143C', // R1: Poor (red)
    2: '#FF8C00', // R2: Below Avg (orange)
    3: '#FFD700', // R3: Average (yellow)
    4: '#32CD32', // R4: Good (green)
    5: '#87CEEB', // R5: Excellent (light-blue)
}

// NSE thresholds (kWh/kWp/hour)
export const RANK_THRESHOLDS = {
    R0: 0.05,  // < 0.05 = R0 (excluded - negligible)
    R1: 0.15,  // 0.05-0.15 = R1 (Poor)
    R2: 0.30,  // 0.15-0.30 = R2 (Below avg)
    R3: 0.50,  // 0.30-0.50 = R3 (Average)
    R4: 0.70,  // 0.50-0.70 = R4 (Good)
    // >= 0.70 = R5 (Excellent)
}

// Short labels for table display
export const RANK_LABELS = {
    0: 'N/P',   // Not productive
    1: 'Poor',
    2: 'Below',
    3: 'Avg',
    4: 'Good',
    5: 'Excel',
}

/**
 * Calculate normalized rank using Y/(X*Z) formula.
 * @param {number} energy    - Production in kWh (Y)
 * @param {number} capacity  - Capacity in kWp (X)
 * @param {number} activeHours - Active hours (Z)
 * @returns {number} Rank 0-5
 */
export function calculateNormalizedRank(energy, capacity, activeHours) {
    if (!energy || !capacity || !activeHours) return 0
    const nse = energy / (capacity * activeHours)

    if (nse < RANK_THRESHOLDS.R0) return 0
    if (nse < RANK_THRESHOLDS.R1) return 1
    if (nse < RANK_THRESHOLDS.R2) return 2
    if (nse < RANK_THRESHOLDS.R3) return 3
    if (nse < RANK_THRESHOLDS.R4) return 4
    return 5
}

/**
 * Simple rank based on specific energy (kWh/kWp) without active-hours normalization.
 * @param {number} energy   - Production in kWh
 * @param {number} capacity - Capacity in kWp
 * @returns {number} Rank 0-5
 */
export function getRank(energy, capacity) {
    const se = energy / (capacity || 1)

    if (se < RANK_THRESHOLDS.R0) return 0
    if (se < RANK_THRESHOLDS.R1) return 1
    if (se < RANK_THRESHOLDS.R2) return 2
    if (se < RANK_THRESHOLDS.R3) return 3
    if (se < RANK_THRESHOLDS.R4) return 4
    return 5
}

/**
 * Get human-readable label for a rank tier.
 * @param {number} rank - Rank 0-5
 * @returns {string}
 */
export function getRatingLabel(rank) {
    return RANK_LABELS[rank] || 'N/A'
}

/**
 * Get background color for a given energy/activeHours pair using the normalized ranking.
 * @param {number} energy      - Production in kWh
 * @param {number} capacity    - Capacity in kWp
 * @param {number} activeHours - Active hours (default 1)
 * @returns {string} CSS color
 */
export function getRankingColor(energy, capacity, activeHours = 1) {
    const nse = energy / ((capacity || 1) * activeHours)

    if (nse < RANK_THRESHOLDS.R0) return RANKING_COLORS[0]
    if (nse < RANK_THRESHOLDS.R1) return RANKING_COLORS[1]
    if (nse < RANK_THRESHOLDS.R2) return RANKING_COLORS[2]
    if (nse < RANK_THRESHOLDS.R3) return RANKING_COLORS[3]
    if (nse < RANK_THRESHOLDS.R4) return RANKING_COLORS[4]
    return RANKING_COLORS[5]
}
