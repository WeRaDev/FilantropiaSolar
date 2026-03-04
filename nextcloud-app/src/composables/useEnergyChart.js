/**
 * Composable for rendering energy + weather Chart.js charts.
 *
 * Extracted from AnalyticsModal.vue to keep the modal under ~800 lines.
 * Handles hourly (single-day) and daily-aggregate (week/month/year) charts.
 */

import { Chart, registerables } from 'chart.js'
import { getRankingColor as _getRankingColor } from '../utils/ranking.js'

Chart.register(...registerables)

/**
 * @param {Object} options
 * @param {import('vue').Ref<HTMLCanvasElement|null>} options.canvasRef   - Template ref to <canvas>
 * @param {import('vue').ComputedRef<Array>}          options.hourlyData  - Hourly data from API
 * @param {import('vue').Ref<string>}                 options.currentTimeframe - 'day'|'week'|'month'|'year'
 * @param {import('vue').Ref<number>}                 options.currentDayIndex
 * @param {import('vue').ComputedRef<number>}         options.totalDays
 * @param {import('vue').ComputedRef<number>}         options.timeframeDays
 * @param {import('vue').ComputedRef<Object|null>}    options.selectedObject
 * @param {import('vue').Ref<Object>}                 options.weatherLayers
 * @returns {{ renderChart: Function, destroyChart: Function }}
 */
export function useEnergyChart({
    canvasRef,
    hourlyData,
    currentTimeframe,
    currentDayIndex,
    totalDays,
    timeframeDays,
    selectedObject,
    weatherLayers,
}) {
    let chartInstance = null

    // Capacity shorthand
    const capacity = () => selectedObject.value?.capacity_kwp || 1

    // Ranking color wrapper using shared utility
    const getRankingColor = (energy, activeHours = 1) =>
        _getRankingColor(energy, capacity(), activeHours)

    // ---- Public API --------------------------------------------------------

    /**
     * Render (or re-render) the chart appropriate for the current timeframe.
     */
    const renderChart = () => {
        if (!canvasRef.value || !hourlyData.value.length) return

        if (chartInstance) {
            chartInstance.destroy()
        }

        const ctx = canvasRef.value.getContext('2d')

        if (currentTimeframe.value === 'day') {
            renderHourlyChart(ctx)
        } else {
            renderDailyChart(ctx)
        }
    }

    /**
     * Destroy the chart instance (call on unmount).
     */
    const destroyChart = () => {
        if (chartInstance) {
            chartInstance.destroy()
            chartInstance = null
        }
    }

    // ---- Hourly chart (single day) -----------------------------------------

    const renderHourlyChart = (ctx) => {
        const dates = [...new Set(
            hourlyData.value.map(p => (p.timestamp || '').split('T')[0]),
        )].sort()
        const currentDate = dates[currentDayIndex.value]
        let dayData = hourlyData.value.filter(
            p => (p.timestamp || '').split('T')[0] === currentDate,
        )

        if (dayData.length === 0) return

        dayData.sort((a, b) => (a.hour || 0) - (b.hour || 0))
        dayData = dayData.filter(
            d => (d.production_kwh || 0) > 0 || (d.hour >= 6 && d.hour <= 20),
        )

        const labels = dayData.map(d => `${d.hour || 0}:00`)

        const datasets = [
            {
                label: 'Energy (kWh)',
                type: 'bar',
                data: dayData.map(d => d.production_kwh || 0),
                backgroundColor: dayData.map(d => getRankingColor(d.production_kwh || 0, 1)),
                borderWidth: 1,
                yAxisID: 'y',
                order: 4,
            },
        ]

        pushWeatherDatasets(datasets, dayData, {
            tempKey: 'temperature',
            cloudKey: 'cloud_cover',
            humidityKey: 'humidity',
            windKey: 'wind_speed',
            mapper: (key) => dayData.map(d => d[key] || 0),
        })

        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: getChartOptions(`Hourly - ${currentDate}`),
        })
    }

    // ---- Daily aggregate chart (week/month/year) ---------------------------

    const renderDailyChart = (ctx) => {
        const dailyAgg = {}
        hourlyData.value.forEach(h => {
            const date = (h.timestamp || '').split('T')[0]
            if (!dailyAgg[date]) {
                dailyAgg[date] = {
                    energy: 0, activeHours: 0,
                    temps: [], clouds: [], humidities: [], winds: [],
                }
            }
            dailyAgg[date].energy += h.production_kwh || 0
            if ((h.production_kwh || 0) > 0.01) dailyAgg[date].activeHours++
            dailyAgg[date].temps.push(h.temperature || 0)
            dailyAgg[date].clouds.push(h.cloud_cover || 0)
            dailyAgg[date].humidities.push(h.humidity || 0)
            dailyAgg[date].winds.push(h.wind_speed || 0)
        })

        const dates = Object.keys(dailyAgg).sort()
        const energyData = dates.map(d => dailyAgg[d].energy)
        const tempData = dates.map(d => avg(dailyAgg[d].temps))
        const cloudData = dates.map(d => avg(dailyAgg[d].clouds))
        const humidityData = dates.map(d => avg(dailyAgg[d].humidities))
        const windData = dates.map(d => avg(dailyAgg[d].winds))
        const activeHoursData = dates.map(d => dailyAgg[d].activeHours || 1)
        const labels = dates.map(d => d.slice(5)) // MM-DD

        const isLarge = dates.length > 60

        const datasets = [
            {
                label: 'Daily Energy (kWh)',
                type: isLarge ? 'line' : 'bar',
                data: energyData,
                backgroundColor: isLarge
                    ? 'rgba(34, 165, 89, 0.2)'
                    : energyData.map((e, i) => getRankingColor(e, activeHoursData[i])),
                borderColor: isLarge ? '#22A559' : undefined,
                borderWidth: isLarge ? 2 : 1,
                fill: isLarge,
                tension: isLarge ? 0.3 : 0,
                pointRadius: isLarge ? 0 : undefined,
                yAxisID: 'y',
                order: 4,
            },
        ]

        pushWeatherDatasets(datasets, null, {
            tempKey: 'temperature',
            cloudKey: 'cloud_cover',
            humidityKey: 'humidity',
            windKey: 'wind_speed',
            mapper: (key) => {
                if (key === 'temperature') return tempData
                if (key === 'cloud_cover') return cloudData
                if (key === 'humidity') return humidityData
                return windData
            },
            prefix: 'Avg ',
        })

        chartInstance = new Chart(ctx, {
            type: 'bar',
            data: { labels, datasets },
            options: getChartOptions(`${totalDays.value}-Day Period`),
        })
    }

    // ---- Weather dataset builder -------------------------------------------

    const WEATHER_CONFIGS = {
        temperature: {
            label: 'Temperature (C)',
            borderColor: '#FFA500',
            bg: 'rgba(255, 165, 0, 0.1)',
            axis: 'y1', order: 3, fill: false, dash: null,
        },
        cloudCover: {
            label: 'Cloud Cover (%)',
            borderColor: '#888888',
            bg: 'rgba(136, 136, 136, 0.2)',
            axis: 'y2', order: 0, fill: true, dash: null,
        },
        humidity: {
            label: 'Humidity (%)',
            borderColor: '#4169E1',
            bg: 'rgba(65, 105, 225, 0.1)',
            axis: 'y2', order: 1, fill: false, dash: [5, 5],
        },
        windSpeed: {
            label: 'Wind Speed (m/s)',
            borderColor: '#9B59B6',
            bg: 'rgba(155, 89, 182, 0.1)',
            axis: 'y3', order: 2, fill: false, dash: null,
        },
    }

    const LAYER_DATA_KEYS = {
        temperature: 'temperature',
        cloudCover: 'cloud_cover',
        humidity: 'humidity',
        windSpeed: 'wind_speed',
    }

    /**
     * Append weather line datasets based on visible layers.
     */
    const pushWeatherDatasets = (datasets, _unused, { mapper, prefix = '' }) => {
        for (const [layer, cfg] of Object.entries(WEATHER_CONFIGS)) {
            if (!weatherLayers.value[layer]) continue
            const dataKey = LAYER_DATA_KEYS[layer]
            const ds = {
                label: prefix ? `${prefix}${cfg.label}` : cfg.label,
                type: 'line',
                data: mapper(dataKey),
                borderColor: cfg.borderColor,
                backgroundColor: cfg.bg,
                tension: 0.4,
                fill: cfg.fill,
                yAxisID: cfg.axis,
                order: cfg.order,
            }
            if (cfg.dash) ds.borderDash = cfg.dash
            datasets.push(ds)
        }
    }

    // ---- Chart options ------------------------------------------------------

    const getChartOptions = (title) => {
        const isLargeDataset = timeframeDays.value > 60

        return {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: true, position: 'top' },
                title: {
                    display: true,
                    text: title,
                    font: { size: 14, weight: 'bold' },
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const label = context.dataset.label || ''
                            const value = context.parsed.y
                            if (label.includes('Energy')) return `${label}: ${value.toFixed(2)} kWh`
                            if (label.includes('Temp')) return `${label}: ${value.toFixed(1)} C`
                            if (label.includes('Cloud') || label.includes('Humidity')) return `${label}: ${value.toFixed(0)}%`
                            if (label.includes('Wind')) return `${label}: ${value.toFixed(1)} m/s`
                            return `${label}: ${value}`
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: {
                        maxTicksLimit: isLargeDataset ? 24 : undefined,
                        maxRotation: isLargeDataset ? 45 : 0,
                        autoSkip: true,
                    },
                },
                y: {
                    type: 'linear', position: 'left', beginAtZero: true,
                    title: { display: true, text: 'Energy (kWh)' },
                },
                y1: {
                    type: 'linear', position: 'right',
                    title: { display: true, text: 'Temperature (C)' },
                    grid: { drawOnChartArea: false },
                },
                y2: {
                    type: 'linear', position: 'right', min: 0, max: 100,
                    title: { display: false },
                    grid: { drawOnChartArea: false }, display: false,
                },
                y3: {
                    type: 'linear', position: 'right', min: 0,
                    title: { display: false },
                    grid: { drawOnChartArea: false }, display: false,
                },
            },
        }
    }

    // ---- Helpers ------------------------------------------------------------

    const avg = (arr) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0

    return { renderChart, destroyChart }
}
