<template>
    <div class="analytics-panel" :class="{ collapsed: isCollapsed }">
        <!-- Panel Header with toggle -->
        <div class="panel-header" @click="togglePanel">
            <div class="header-left">
                <span class="toggle-icon" :class="{ rotated: isCollapsed }">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="m6 9 6 6 6-6"/>
                    </svg>
                </span>
                <h2>Analytics</h2>
                <span v-if="selectedObject" class="selected-badge">
                    {{ selectedObject.name || selectedObject.id }}
                </span>
            </div>
            <div class="header-right" v-if="!isCollapsed">
                <!-- Day navigation (v1.2.3 feature) -->
                <div class="day-nav" v-if="analysisData">
                    <button class="nav-btn" @click.stop="prevDay" :disabled="currentDayIndex <= 0">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="m15 18-6-6 6-6"/>
                        </svg>
                    </button>
                    <span class="day-label">{{ currentDayLabel }}</span>
                    <button class="nav-btn" @click.stop="nextDay" :disabled="currentDayIndex >= totalDays - 1">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="m9 18 6-6-6-6"/>
                        </svg>
                    </button>
                    <button class="nav-btn center-btn" @click.stop="centerDay" title="Go to center day">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="3"/>
                            <path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>

        <!-- Panel Content -->
        <div class="panel-content" v-show="!isCollapsed">
            <!-- Tabs -->
            <div class="tabs">
                <button 
                    v-for="tab in tabs" 
                    :key="tab.id"
                    class="tab"
                    :class="{ active: activeTab === tab.id }"
                    @click="activeTab = tab.id">
                    {{ tab.label }}
                </button>
            </div>

            <!-- No selection message -->
            <div v-if="!selectedObject" class="no-selection">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M3 3l18 18M10.5 10.677a2 2 0 0 0 2.823 2.823"/>
                    <path d="M7.362 7.561A10.97 10.97 0 0 0 1 12s4 8 11 8a10.97 10.97 0 0 0 5.638-1.562M14 5.5a10.97 10.97 0 0 1 7 6.5c-.5 1.5-1.5 3-3 4.5"/>
                </svg>
                <p>Select an installation to view analytics</p>
            </div>

            <!-- Loading state -->
            <div v-else-if="isLoading" class="loading-state">
                <div class="spinner"></div>
                <p>Generating analysis...</p>
            </div>

            <!-- Tab content -->
            <div v-else class="tab-content">
                <!-- Energy Chart Tab -->
                <div v-show="activeTab === 'energy'" class="chart-container">
                    <div v-if="!chartData" class="chart-placeholder">
                        <p>Click "Generate Analysis" to view energy data</p>
                        <button class="btn-generate" @click="generateAnalysis">
                            Generate Analysis
                        </button>
                    </div>
                    <div v-else class="chart-wrapper">
                        <canvas ref="energyChartRef"></canvas>
                    </div>
                </div>

                <!-- Weather Chart Tab -->
                <div v-show="activeTab === 'weather'" class="chart-container">
                    <div v-if="!chartData" class="chart-placeholder">
                        <p>Generate analysis to view weather data</p>
                    </div>
                    <div v-else class="chart-wrapper">
                        <canvas ref="weatherChartRef"></canvas>
                    </div>
                </div>

                <!-- Overview Tab - v1.2.3 Feature Parity -->
                <div v-if="activeTab === 'overview'" class="overview-content">
                    <div v-if="analysisData" class="overview-sections">
                        <!-- Key Performance Metrics (v1.2.3) -->
                        <div class="metrics-section">
                            <h3 class="section-title">Key Performance Metrics ({{ totalDays }}-day period)</h3>
                            <div class="metrics-grid">
                                <div class="metric-item">
                                    <span class="metric-label">Total Energy Production</span>
                                    <span class="metric-value">{{ periodStats.totalEnergy.toFixed(2) }} kWh</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-label">Average Daily Energy</span>
                                    <span class="metric-value">{{ periodStats.avgDaily.toFixed(2) }} kWh/day</span>
                                </div>
                                <div class="metric-item metric-highlight">
                                    <span class="metric-label">Light Saved</span>
                                    <span class="metric-value">&euro;{{ periodStats.lightSaved.toFixed(2) }}</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-label">Peak Hour Energy</span>
                                    <span class="metric-value">{{ periodStats.peakHourEnergy.toFixed(2) }} kWh/kWp</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-label">Average Temperature</span>
                                    <span class="metric-value">{{ periodStats.avgTemperature.toFixed(1) }} C</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-label">Average Cloud Cover</span>
                                    <span class="metric-value">{{ periodStats.avgCloudCover.toFixed(1) }} %</span>
                                </div>
                            </div>
                        </div>

                        <!-- Daily Summary Table (v1.2.3) -->
                        <div class="daily-section">
                            <h3 class="section-title">Daily Summary</h3>
                            <div class="daily-table-wrapper">
                                <table class="daily-table">
                                    <thead>
                                        <tr>
                                            <th>Day</th>
                                            <th>Date</th>
                                            <th>Energy</th>
                                            <th>Peak</th>
                                            <th>Temp</th>
                                            <th>Cloud</th>
                                            <th>Rating</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="(day, index) in dailySummary" :key="index"
                                            :class="{ 'selected-day': index === currentDayIndex }">
                                            <td>{{ index + 1 }}</td>
                                            <td>{{ day.date }}</td>
                                            <td>{{ day.energy.toFixed(1) }}</td>
                                            <td>{{ day.peak.toFixed(1) }}</td>
                                            <td>{{ day.temp.toFixed(0) }}</td>
                                            <td>{{ day.cloud.toFixed(0) }}</td>
                                            <td>
                                                <span class="rating-badge" :class="'rank-' + day.rank">{{ getRatingLabel(day.rank) }}</span>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- Data Source Info (v1.2.3) -->
                        <div class="source-section">
                            <h3 class="section-title">Data Source & Model Info</h3>
                            <div class="source-info">
                                <div class="source-row">
                                    <span class="source-label">PV Data</span>
                                    <span class="source-value">Sarmas et al. (2025) - DOI: 10.17632/dbh93b6vp8.3</span>
                                </div>
                                <div class="source-row">
                                    <span class="source-label">Analysis Mode</span>
                                    <span class="source-value">{{ analysisData.mode || 'Historical' }}</span>
                                </div>
                                <div class="source-row">
                                    <span class="source-label">Weather Source</span>
                                    <span class="source-value">{{ analysisData.weather_source || 'Historical (local)' }}</span>
                                </div>
                                <div class="source-row" v-if="analysisData.model_info">
                                    <span class="source-label">ML Model</span>
                                    <span class="source-value">{{ analysisData.model_info.name || 'Gradient Boosting' }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-else class="chart-placeholder">
                        <p>Generate analysis to view overview</p>
                        <button class="btn-generate" @click="generateAnalysis">
                            Generate Analysis
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useAppStore } from '../store/app.js'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

// Ranking colors from v1.2.3
const RANKING_COLORS = {
    0: '#B0B0B0', // Non-productive
    1: '#DC143C', // Poor
    2: '#FF8C00', // Below Avg
    3: '#FFA500', // Average
    4: '#32CD32', // Good
    5: '#FFD700'  // Excellent
}

export default {
    name: 'AnalyticsPanel',
    setup() {
        const store = useAppStore()
        
        // Refs
        const isCollapsed = ref(false)
        const activeTab = ref('energy')
        const energyChartRef = ref(null)
        const weatherChartRef = ref(null)
        const currentDayIndex = ref(10) // Center of 21-day window
        
        // Chart instances
        let energyChart = null
        let weatherChart = null

        // Tabs config
        const tabs = [
            { id: 'energy', label: 'Energy' },
            { id: 'weather', label: 'Weather' },
            { id: 'overview', label: 'Overview' }
        ]

        // Computed
        const selectedObject = computed(() => store.selectedObject)
        const analysisData = computed(() => store.analysisData)
        const isLoading = computed(() => store.analysisLoading)
        
        // Get hourly data array - API returns 'hourly_data' not 'predictions'
        const hourlyData = computed(() => analysisData.value?.hourly_data || [])
        const chartData = computed(() => hourlyData.value.length > 0)
        
        const totalDays = computed(() => {
            if (!hourlyData.value.length) return 21
            const dates = new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))
            return dates.size || 21
        })

        const currentDayLabel = computed(() => {
            if (!hourlyData.value.length) return 'Day 11'
            const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))]
            return dates[currentDayIndex.value] || `Day ${currentDayIndex.value + 1}`
        })

        // Stats calculations - API uses 'production_kwh' not 'predicted_energy'
        const totalEnergy = computed(() => {
            if (!hourlyData.value.length) return 0
            return hourlyData.value.reduce((sum, p) => sum + (p.production_kwh || 0), 0)
        })

        const avgDaily = computed(() => {
            if (!totalDays.value) return 0
            return totalEnergy.value / totalDays.value
        })

        const peakDay = computed(() => {
            if (!hourlyData.value.length) return '-'
            const byDate = {}
            hourlyData.value.forEach(p => {
                const date = (p.timestamp || '').split('T')[0]
                byDate[date] = (byDate[date] || 0) + (p.production_kwh || 0)
            })
            const maxDate = Object.entries(byDate).sort((a, b) => b[1] - a[1])[0]
            return maxDate ? maxDate[0].slice(5) : '-'
        })

        const efficiency = computed(() => {
            if (!selectedObject.value) return 0
            return (selectedObject.value.metrics?.efficiency || 0.85) * 100
        })

        // v1.2.3 Period Statistics - comprehensive metrics
        const periodStats = computed(() => {
            const capacity = selectedObject.value?.capacity_kwp || 1
            const days = totalDays.value || 1
            
            // Use API's period_statistics if available, otherwise calculate
            const apiStats = analysisData.value?.period_statistics || {}
            
            // Calculate from hourly data
            const total = apiStats.total_energy_kwh || totalEnergy.value
            const avgTemp = hourlyData.value.length 
                ? hourlyData.value.reduce((sum, h) => sum + (h.temperature || 0), 0) / hourlyData.value.length
                : 0
            const avgCloud = hourlyData.value.length
                ? hourlyData.value.reduce((sum, h) => sum + (h.cloud_cover || 0), 0) / hourlyData.value.length
                : 0
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
                avgCloudCover: avgCloud
            }
        })

        // v1.2.3 Daily Summary - table data
        const dailySummary = computed(() => {
            if (!hourlyData.value.length) return []
            
            // Use API's daily_data if available
            const apiDaily = analysisData.value?.daily_data || []
            if (apiDaily.length > 0) {
                return apiDaily.map(d => ({
                    date: (d.date || '').slice(5), // MM-DD format
                    energy: d.total_production_kwh || 0,
                    peak: d.peak_production_kwh || 0,
                    temp: d.avg_temperature || 0,
                    cloud: d.avg_cloud_cover || d.avg_radiation ? 100 - (d.avg_radiation / 10) : 30,
                    rank: getRank(d.total_production_kwh || 0)
                }))
            }
            
            // Calculate from hourly data
            const byDate = {}
            hourlyData.value.forEach(h => {
                const date = (h.timestamp || '').split('T')[0]
                if (!byDate[date]) {
                    byDate[date] = { energy: 0, peak: 0, temps: [], clouds: [] }
                }
                byDate[date].energy += h.production_kwh || 0
                byDate[date].peak = Math.max(byDate[date].peak, h.production_kwh || 0)
                byDate[date].temps.push(h.temperature || 0)
                byDate[date].clouds.push(h.cloud_cover || 0)
            })
            
            return Object.entries(byDate).map(([date, data]) => ({
                date: date.slice(5),
                energy: data.energy,
                peak: data.peak,
                temp: data.temps.reduce((a, b) => a + b, 0) / data.temps.length,
                cloud: data.clouds.reduce((a, b) => a + b, 0) / data.clouds.length,
                rank: getRank(data.energy)
            }))
        })

        // Calculate rank based on energy (0-5 scale like v1.2.3)
        const getRank = (energy) => {
            if (energy <= 0) return 0
            // Use daily average as baseline
            const avgDaily = periodStats.value?.avgDaily || 1
            const ratio = energy / avgDaily
            if (ratio >= 1.3) return 5
            if (ratio >= 1.1) return 4
            if (ratio >= 0.9) return 3
            if (ratio >= 0.7) return 2
            return 1
        }

        // Convert rank to label (v1.2.3 style)
        const getRatingLabel = (rank) => {
            const labels = {
                0: 'N/P',
                1: 'Poor',
                2: 'Below',
                3: 'Avg',
                4: 'Good',
                5: 'Excel'
            }
            return labels[rank] || 'N/A'
        }

        // Methods
        const togglePanel = () => {
            isCollapsed.value = !isCollapsed.value
        }

        const generateAnalysis = async () => {
            if (!selectedObject.value) return
            await store.generateAnalysis(selectedObject.value.id, 21)
            await nextTick()
            renderCharts()
        }

        const prevDay = () => {
            if (currentDayIndex.value > 0) {
                currentDayIndex.value--
                renderCharts()
            }
        }

        const nextDay = () => {
            if (currentDayIndex.value < totalDays.value - 1) {
                currentDayIndex.value++
                renderCharts()
            }
        }

        const centerDay = () => {
            currentDayIndex.value = Math.floor(totalDays.value / 2)
            renderCharts()
        }

        // Get ranking color based on energy value
        const getRankingColor = (energy, maxEnergy) => {
            if (energy <= 0) return RANKING_COLORS[0]
            const ratio = energy / maxEnergy
            if (ratio >= 0.9) return RANKING_COLORS[5]
            if (ratio >= 0.7) return RANKING_COLORS[4]
            if (ratio >= 0.5) return RANKING_COLORS[3]
            if (ratio >= 0.3) return RANKING_COLORS[2]
            return RANKING_COLORS[1]
        }

        // Render energy chart
        const renderEnergyChart = () => {
            if (!energyChartRef.value || !hourlyData.value.length) return

            // Filter data for current day - API uses 'timestamp' not 'date'
            const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))]
            const currentDate = dates[currentDayIndex.value]
            const dayData = hourlyData.value.filter(p => (p.timestamp || '').split('T')[0] === currentDate)

            if (dayData.length === 0) return

            // Sort by hour - API has 'hour' field directly
            dayData.sort((a, b) => (a.hour || 0) - (b.hour || 0))

            // API uses 'production_kwh' not 'predicted_energy', and has 'rank' (1-5)
            const maxEnergy = Math.max(...dayData.map(d => d.production_kwh || 0))
            const labels = dayData.map(d => `${d.hour || 0}:00`)
            const values = dayData.map(d => d.production_kwh || 0)
            // Use rank from API if available, otherwise calculate from ratio
            const colors = dayData.map(d => {
                if (d.rank !== undefined && RANKING_COLORS[d.rank]) {
                    return RANKING_COLORS[d.rank]
                }
                return getRankingColor(d.production_kwh || 0, maxEnergy)
            })

            // Destroy existing chart
            if (energyChart) {
                energyChart.destroy()
            }

            const ctx = energyChartRef.value.getContext('2d')
            energyChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        label: 'Energy (kWh)',
                        data: values,
                        backgroundColor: colors,
                        borderColor: colors.map(c => c),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        title: {
                            display: true,
                            text: `Hourly Energy - ${currentDate} (Day ${currentDayIndex.value + 1} of ${totalDays.value})`,
                            font: { size: 14, weight: 'bold' }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Energy (kWh)' }
                        },
                        x: {
                            title: { display: true, text: 'Hour' }
                        }
                    }
                }
            })
        }

        // Render weather chart
        const renderWeatherChart = () => {
            if (!weatherChartRef.value || !hourlyData.value.length) return

            // Use timestamp from API
            const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))]
            const currentDate = dates[currentDayIndex.value]
            const dayData = hourlyData.value.filter(p => (p.timestamp || '').split('T')[0] === currentDate)

            if (dayData.length === 0) return

            // Sort by hour field from API
            dayData.sort((a, b) => (a.hour || 0) - (b.hour || 0))

            const labels = dayData.map(d => `${d.hour || 0}:00`)

            // Destroy existing chart
            if (weatherChart) {
                weatherChart.destroy()
            }

            const ctx = weatherChartRef.value.getContext('2d')
            weatherChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Temperature (C)',
                            data: dayData.map(d => d.temperature || 20),
                            borderColor: '#FF6384',
                            tension: 0.4,
                            yAxisID: 'y'
                        },
                        {
                            label: 'Humidity (%)',
                            data: dayData.map(d => d.humidity || 50),
                            borderColor: '#36A2EB',
                            tension: 0.4,
                            yAxisID: 'y1'
                        },
                        {
                            label: 'Cloud Cover (%)',
                            data: dayData.map(d => d.cloud_cover || 30),
                            borderColor: '#FFCE56',
                            tension: 0.4,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: `Weather Conditions - ${currentDate}`,
                            font: { size: 14, weight: 'bold' }
                        }
                    },
                    scales: {
                        y: {
                            type: 'linear',
                            position: 'left',
                            title: { display: true, text: 'Temperature (C)' }
                        },
                        y1: {
                            type: 'linear',
                            position: 'right',
                            title: { display: true, text: 'Percentage (%)' },
                            grid: { drawOnChartArea: false }
                        }
                    }
                }
            })
        }

        // Render both charts
        const renderCharts = () => {
            if (activeTab.value === 'energy') {
                renderEnergyChart()
            } else if (activeTab.value === 'weather') {
                renderWeatherChart()
            }
        }

        // Watch for tab changes
        watch(activeTab, async () => {
            await nextTick()
            // Extra delay to ensure canvas is mounted
            setTimeout(() => renderCharts(), 50)
        })

        // Watch for chartData changes (canvas appears/disappears)
        watch(chartData, async (hasData) => {
            if (hasData) {
                // Canvas just appeared via v-else, wait for DOM
                await nextTick()
                setTimeout(() => renderCharts(), 100)
            }
        })

        // Watch for analysis data changes
        watch(analysisData, async () => {
            if (analysisData.value) {
                currentDayIndex.value = Math.floor(totalDays.value / 2)
                // Wait for DOM updates including v-else canvas
                await nextTick()
                await nextTick()
                setTimeout(() => renderCharts(), 100)
            }
        })

        // Watch for selection changes - always regenerate for new selection
        watch(selectedObject, async (newObj, oldObj) => {
            if (newObj && newObj.id !== oldObj?.id) {
                // Clear old data and generate new
                store.analysisData = null
                await generateAnalysis()
            }
        })

        onMounted(async () => {
            if (analysisData.value) {
                await nextTick()
                setTimeout(() => renderCharts(), 100)
            }
        })

        return {
            isCollapsed,
            activeTab,
            tabs,
            energyChartRef,
            weatherChartRef,
            selectedObject,
            analysisData,
            isLoading,
            chartData,
            currentDayIndex,
            currentDayLabel,
            totalDays,
            totalEnergy,
            avgDaily,
            peakDay,
            efficiency,
            // v1.2.3 Overview metrics
            periodStats,
            dailySummary,
            getRatingLabel,
            togglePanel,
            generateAnalysis,
            prevDay,
            nextDay,
            centerDay
        }
    }
}
</script>

<style scoped>
/* Analytics Panel - 300-400px height per spec */
.analytics-panel {
    display: flex;
    flex-direction: column;
    height: 350px;
    min-height: 300px;
    max-height: 400px;
    background: var(--color-main-background, #fff);
    border-top: 1px solid var(--color-border, #e0e0e0);
    transition: height 0.3s ease;
}

.analytics-panel.collapsed {
    height: 48px;
    min-height: 48px;
}

/* Panel Header */
.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    background: var(--color-background-dark, #f5f5f5);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    cursor: pointer;
    user-select: none;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.toggle-icon {
    display: flex;
    transition: transform 0.3s ease;
}

.toggle-icon.rotated {
    transform: rotate(-90deg);
}

.panel-header h2 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
}

.selected-badge {
    padding: 2px 10px;
    background: var(--color-primary, #0082c9);
    color: #fff;
    border-radius: 12px;
    font-size: 12px;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 16px;
}

/* Day Navigation */
.day-nav {
    display: flex;
    align-items: center;
    gap: 8px;
}

.nav-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #e0e0e0);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.nav-btn:hover:not(:disabled) {
    background: var(--color-background-hover, #f5f5f5);
}

.nav-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.center-btn {
    margin-left: 4px;
}

.day-label {
    min-width: 80px;
    text-align: center;
    font-size: 13px;
    font-weight: 500;
}

/* Panel Content */
.panel-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* Tabs */
.tabs {
    display: flex;
    gap: 4px;
    padding: 8px 24px;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.tab {
    padding: 8px 20px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
    color: var(--color-text-lighter, #767676);
}

.tab:hover {
    color: var(--color-main-text, #1a1a1a);
}

.tab.active {
    color: var(--color-primary, #0082c9);
    border-bottom-color: var(--color-primary, #0082c9);
    font-weight: 500;
}

/* Tab Content */
.tab-content {
    flex: 1;
    overflow: auto;
    padding: 16px 24px;
}

/* Chart Container */
.chart-container {
    position: relative;
    height: 100%;
    min-height: 200px;
}

/* Chart Wrapper - holds the canvas */
.chart-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 200px;
}

.chart-wrapper canvas {
    width: 100% !important;
    height: 100% !important;
}

/* Chart Placeholder */
.chart-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 200px;
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 8px;
    color: var(--color-text-lighter, #767676);
}

.btn-generate {
    margin-top: 12px;
    padding: 10px 20px;
    background: var(--color-primary, #0082c9);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: background 0.2s ease;
}

.btn-generate:hover {
    background: #006ba7;
}

/* No Selection / Loading States */
.no-selection,
.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--color-text-lighter, #767676);
    padding: 24px;
}

.spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--color-border, #e0e0e0);
    border-top-color: var(--color-primary, #0082c9);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 12px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Overview Content - v1.2.3 Feature Parity */
.overview-content {
    height: 100%;
    overflow-y: auto;
}

.overview-sections {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* Section Title */
.section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--color-main-text, #1a1a1a);
    margin: 0 0 8px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    padding-bottom: 4px;
}

/* Key Performance Metrics Grid */
.metrics-section {
    background: var(--color-background-dark, #f5f5f5);
    padding: 12px;
    border-radius: 8px;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
}

.metric-item {
    display: flex;
    justify-content: space-between;
    padding: 6px 10px;
    background: var(--color-main-background, #fff);
    border-radius: 4px;
    font-size: 12px;
}

.metric-label {
    color: var(--color-text-lighter, #767676);
}

.metric-value {
    font-weight: 600;
    color: var(--color-primary, #0082c9);
}

/* Daily Summary Table */
.daily-section {
    background: var(--color-background-dark, #f5f5f5);
    padding: 12px;
    border-radius: 8px;
}

.daily-table-wrapper {
    max-height: 120px;
    overflow-y: auto;
}

.daily-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11px;
}

.daily-table th,
.daily-table td {
    padding: 4px 8px;
    text-align: center;
    border-bottom: 1px solid var(--color-border-dark, #ebebeb);
}

.daily-table th {
    background: var(--color-main-background, #fff);
    font-weight: 600;
    color: var(--color-text-lighter, #767676);
    position: sticky;
    top: 0;
}

.daily-table tr.selected-day {
    background: rgba(0, 130, 201, 0.1);
    font-weight: 600;
}

/* Rating Badge */
.rating-badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
}

.rating-badge.rank-0 { background: #B0B0B0; color: #fff; }
.rating-badge.rank-1 { background: #DC143C; color: #fff; }
.rating-badge.rank-2 { background: #FF8C00; color: #fff; }
.rating-badge.rank-3 { background: #FFA500; color: #000; }
.rating-badge.rank-4 { background: #32CD32; color: #fff; }
.rating-badge.rank-5 { background: #FFD700; color: #000; }

/* Data Source Info */
.source-section {
    background: var(--color-background-dark, #f5f5f5);
    padding: 12px;
    border-radius: 8px;
}

.source-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.source-row {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    padding: 2px 0;
}

.source-label {
    color: var(--color-text-lighter, #767676);
}

.source-value {
    color: var(--color-main-text, #1a1a1a);
    font-weight: 500;
}

/* Responsive */
@media (max-width: 1024px) {
    .metrics-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 768px) {
    .metrics-grid {
        grid-template-columns: 1fr;
    }
}
</style>
