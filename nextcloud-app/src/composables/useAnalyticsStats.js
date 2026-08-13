/**
 * Composable exposing derived analytics statistics for AnalyticsModal.
 *
 * All values are pure computed derivations of the analysis data and the
 * current selection/timeframe. Extracted from AnalyticsModal.vue to keep the
 * modal a thin orchestrator.
 */

import { computed } from 'vue'
import { calculateNormalizedRank } from '../utils/ranking.js'

/**
 * @param {object} deps - Reactive dependencies.
 * @param {import('vue').ComputedRef<object|null>} deps.analysisData - Analysis payload from the store.
 * @param {import('vue').ComputedRef<object|null>} deps.selectedObject - Selected installation.
 * @param {import('vue').Ref<string>} deps.currentTimeframe - 'day'|'week'|'month'|'year'.
 * @param {import('vue').Ref<number>} deps.currentDayIndex - Active day index.
 * @param {import('vue').ComputedRef<number>} deps.timeframeDays - Days in the current timeframe.
 * @return {object} Computed refs used by the modal template.
 */
const rowHour = (h) => {
    if (h?.hour !== undefined && h?.hour !== null && h?.hour !== '') {
        const n = Number(h.hour)
        if (!Number.isNaN(n)) return n
    }
    const ts = h?.timestamp || ''
    const m = ts.match(/T(\d{1,2})/) || ts.match(/\s(\d{2}):/)
    return m ? parseInt(m[1], 10) : 0
}

export function useAnalyticsStats({
    analysisData,
    selectedObject,
    currentTimeframe,
    currentDayIndex,
    timeframeDays,
}) {
    const hourlyData = computed(() => analysisData.value?.hourly_data || [])

    const totalDays = computed(() => {
        if (!hourlyData.value.length) return timeframeDays.value
        const dates = new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))
        return dates.size || timeframeDays.value
    })

    const currentDayLabel = computed(() => {
        if (!hourlyData.value.length) return 'Day 1'
        const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))]
        return dates[currentDayIndex.value] || `Day ${currentDayIndex.value + 1}`
    })

    const chartTitle = computed(() => {
        if (currentTimeframe.value === 'day') {
            return 'Hourly Energy Production & Weather'
        }
        return `Daily Energy Production (${totalDays.value} days)`
    })

    const dateRangeLabel = computed(() => {
        if (!hourlyData.value.length) return ''
        const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))].sort()
        if (dates.length === 0) return ''
        return `${dates[0]} to ${dates[dates.length - 1]}`
    })

    const periodStats = computed(() => {
        const capacity = selectedObject.value?.capacity_kwp || 1
        const days = totalDays.value || 1
        const apiStats = analysisData.value?.period_statistics || {}

        const total = apiStats.total_energy_kwh
            || apiStats.total_production_kwh
            || hourlyData.value.reduce((sum, h) => sum + (Number(h.production_kwh) || 0), 0)

        const len = hourlyData.value.length || 1
        const avgTemp = hourlyData.value.reduce((sum, h) => sum + (h.temperature || 0), 0) / len
        const avgCloud = hourlyData.value.reduce((sum, h) => sum + (h.cloud_cover || 0), 0) / len
        const avgHumidity = hourlyData.value.reduce((sum, h) => sum + (h.humidity || 0), 0) / len
        const avgWind = hourlyData.value.reduce((sum, h) => sum + (h.wind_speed || 0), 0) / len
        const avgRadiation = hourlyData.value.reduce((sum, h) => sum + (h.radiation || h.shortwave_radiation || 0), 0) / len
        const peakHour = hourlyData.value.length
            ? Math.max(...hourlyData.value.map(h => h.production_kwh || 0))
            : 0

        const gridPrice = 0.15

        return {
            totalEnergy: total,
            avgDaily: apiStats.avg_daily_kwh || total / days,
            lightSaved: apiStats.total_savings_eur || total * gridPrice,
            specificEnergy: total / capacity / days,
            peakHourEnergy: peakHour / capacity,
            avgTemperature: avgTemp,
            avgHumidity: avgHumidity,
            avgCloudCover: avgCloud,
            avgWindSpeed: avgWind,
            avgRadiation: avgRadiation,
        }
    })

    const dailySummary = computed(() => {
        if (!hourlyData.value.length) return []

        const capacity = selectedObject.value?.capacity_kwp || 1

        // For 'day' timeframe, show hourly values
        if (currentTimeframe.value === 'day') {
            const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))].sort()
            const currentDate = dates[currentDayIndex.value]
            const dayData = hourlyData.value.filter(h => (h.timestamp || '').split('T')[0] === currentDate)

            return dayData
                .filter(h => (h.production_kwh || 0) > 0.01)
                .map(h => ({
                    date: `${rowHour(h)}:00`,
                    energy: h.production_kwh || 0,
                    specificEnergy: (h.production_kwh || 0) / capacity,
                    peak: h.production_kwh || 0,
                    temp: h.temperature || 0,
                    humidity: h.humidity || 0,
                    cloud: h.cloud_cover || 0,
                    wind: h.wind_speed || 0,
                    radiation: h.radiation || h.shortwave_radiation || 0,
                    rank: calculateNormalizedRank(h.production_kwh || 0, capacity, 1),
                }))
        }

        // For other timeframes, prefer API-provided daily data
        const apiDaily = analysisData.value?.daily_data || []
        if (apiDaily.length > 0) {
            return apiDaily.map(d => {
                const dayHourly = hourlyData.value.filter(h =>
                    (h.timestamp || '').split('T')[0] === d.date && (h.production_kwh || 0) > 0.01,
                )
                const activeHours = dayHourly.length || 1
                return {
                    date: (d.date || '').slice(5),
                    energy: d.total_production_kwh || 0,
                    specificEnergy: d.specific_energy_kwh_kwp || 0,
                    peak: d.peak_production_kwh || 0,
                    temp: d.avg_temperature || 0,
                    humidity: d.avg_humidity || 0,
                    cloud: d.avg_cloud_cover || 0,
                    wind: d.avg_wind_speed || 0,
                    radiation: d.avg_radiation || 0,
                    activeHours,
                    rank: calculateNormalizedRank(d.total_production_kwh || 0, capacity, activeHours),
                }
            })
        }

        // Fallback: aggregate from hourly data
        const byDate = {}
        hourlyData.value.forEach(h => {
            const date = (h.timestamp || '').split('T')[0]
            if (!byDate[date]) {
                byDate[date] = { energy: 0, peak: 0, temps: [], clouds: [], humidities: [], winds: [], radiations: [], activeHours: 0 }
            }
            byDate[date].energy += h.production_kwh || 0
            byDate[date].peak = Math.max(byDate[date].peak, h.production_kwh || 0)
            if ((h.production_kwh || 0) > 0.01) byDate[date].activeHours++
            byDate[date].temps.push(h.temperature || 0)
            byDate[date].clouds.push(h.cloud_cover || 0)
            byDate[date].humidities.push(h.humidity || 0)
            byDate[date].winds.push(h.wind_speed || 0)
            byDate[date].radiations.push(h.radiation || 0)
        })

        const mean = arr => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0)

        return Object.entries(byDate)
            .map(([date, data]) => {
                const activeHours = data.activeHours || 1
                const rank = calculateNormalizedRank(data.energy, capacity, activeHours)
                if (rank === 0) return null
                return {
                    date: date.slice(5),
                    energy: data.energy,
                    specificEnergy: data.energy / capacity,
                    peak: data.peak,
                    temp: mean(data.temps),
                    humidity: mean(data.humidities),
                    cloud: mean(data.clouds),
                    wind: mean(data.winds),
                    radiation: mean(data.radiations),
                    activeHours,
                    rank,
                }
            })
            .filter(d => d !== null)
    })

    return {
        hourlyData,
        totalDays,
        currentDayLabel,
        chartTitle,
        dateRangeLabel,
        periodStats,
        dailySummary,
    }
}
