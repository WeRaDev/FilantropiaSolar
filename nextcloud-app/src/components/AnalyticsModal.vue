<template>
    <teleport to="body">
        <transition name="modal-fade">
            <div v-if="isOpen" class="analytics-modal-overlay" @click.self="closeModal">
                <div class="analytics-modal">
                    <!-- Modal Header -->
                    <header class="modal-header">
                        <div class="header-left">
                            <span class="status-badge" :class="selectedObject?.status || 'offline'"></span>
                            <h2>{{ selectedObject?.name || 'Installation Analysis' }}</h2>
                            <span class="location-badge">{{ selectedObject?.location }}</span>
                            <span class="capacity-badge">{{ selectedObject?.capacity_kwp }} kWp</span>
                        </div>
                        <div class="header-center">
                            <!-- Historical/Predicted Toggle -->
                            <div class="mode-toggle">
                                <span 
                                    class="mode-label" 
                                    :class="{ active: analysisMode === 'historical' }"
                                    @click="setAnalysisMode('historical')">
                                    Historical
                                </span>
                                <label class="toggle-switch">
                                    <input 
                                        type="checkbox" 
                                        :checked="analysisMode === 'predicted'"
                                        @change="toggleAnalysisMode"
                                    />
                                    <span class="toggle-slider"></span>
                                </label>
                                <span 
                                    class="mode-label" 
                                    :class="{ active: analysisMode === 'predicted' }"
                                    @click="setAnalysisMode('predicted')">
                                    Predicted
                                </span>
                            </div>
                            <!-- Date picker -->
                        <div class="date-picker-group">
                            <label for="center-date">Center Date:</label>
                            <input 
                                id="center-date"
                                type="date" 
                                ref="dateInputRef"
                                v-model="centerDate"
                                :max="effectiveMaxDate"
                                @change="onDateChange"
                                class="date-input"
                            />
                            <button class="calendar-btn" @click="openCalendar" title="Open calendar">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                                    <line x1="16" y1="2" x2="16" y2="6"/>
                                    <line x1="8" y1="2" x2="8" y2="6"/>
                                    <line x1="3" y1="10" x2="21" y2="10"/>
                                </svg>
                            </button>
                        </div>
                            <!-- Timeframe buttons -->
                                    <div class="timeframe-buttons">
                                <button 
                                    v-for="tf in timeframes" 
                                    :key="tf.value"
                                    class="tf-btn"
                                    :class="{ active: currentTimeframe === tf.value }"
                                    @click="setTimeframe(tf.value)">
                                    {{ tf.label }}
                                </button>
                            </div>
                            <!-- Weather data toggle (v3.0.5) -->
                            <div class="weather-toggle">
                                <button class="weather-toggle-btn" @click="toggleWeatherDropdown" title="Weather layers">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M3 15h4v6H3zM9 11h4v10H9zM15 7h4v14h-4z"/>
                                    </svg>
                                    <span>Weather</span>
                                </button>
                                <div v-if="showWeatherDropdown" class="weather-dropdown">
                                    <label class="weather-option">
                                        <input type="checkbox" v-model="weatherLayers.temperature" @change="renderCombinedChart" />
                                        <span class="weather-color" style="background: #FFA500;"></span>
                                        Temperature
                                    </label>
                                    <label class="weather-option">
                                        <input type="checkbox" v-model="weatherLayers.cloudCover" @change="renderCombinedChart" />
                                        <span class="weather-color" style="background: #888888;"></span>
                                        Cloud Cover
                                    </label>
                                    <label class="weather-option">
                                        <input type="checkbox" v-model="weatherLayers.humidity" @change="renderCombinedChart" />
                                        <span class="weather-color" style="background: #4169E1;"></span>
                                        Humidity
                                    </label>
                                    <label class="weather-option">
                                        <input type="checkbox" v-model="weatherLayers.windSpeed" @change="renderCombinedChart" />
                        <span class="weather-color" style="background: #9B59B6;"></span>
                        Wind Speed
                                    </label>
                                </div>
                            </div>
                        </div>
                        <div class="header-right">
                            <!-- ML Module Info button (v3.0.6) -->
                            <div class="ml-info-wrapper">
                                <button class="btn-info" @click="showMlInfo = !showMlInfo" title="ML Module Info">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <circle cx="12" cy="12" r="10"/>
                                        <path d="M12 16v-4M12 8h.01"/>
                                    </svg>
                                    <span>ML Info</span>
                                </button>
                                <div v-if="showMlInfo" class="ml-info-popover">
                                    <h4>Data Source & Model Info</h4>
                                    <div class="ml-info-row"><span class="ml-info-label">PV Data:</span> Sarmas et al. (2025)</div>
                                    <div class="ml-info-row">Photovoltaic Power Production Dataset</div>
                                    <div class="ml-info-row"><span class="ml-info-label">DOI:</span> 10.17632/dbh93b6vp8.3</div>
                                    <div class="ml-info-row"><span class="ml-info-label">Weather Source:</span> {{ analysisData?.weather_source || 'synthetic' }}</div>
                                    <div class="ml-info-row"><span class="ml-info-label">Data points:</span> {{ analysisData?.hourly_data?.length || 0 }} hourly, {{ analysisData?.daily_data?.length || 0 }} daily</div>
                                    <div class="ml-info-row"><span class="ml-info-label">Prediction Method:</span> {{ analysisData?.weather_source === 'measured' ? 'Measured Data' : (analysisData?.model_info?.name || 'Physics-based Estimation') }}</div>
                    <div class="ml-info-row"><span class="ml-info-label">Model R²:</span> {{ analysisData?.model_info?.r2 != null ? analysisData.model_info.r2.toFixed(4) : 'N/A (physics-based)' }}</div>
                                    <div class="ml-info-row"><span class="ml-info-label">Model MAE:</span> {{ analysisData?.model_info?.mae != null ? analysisData.model_info.mae.toFixed(4) : 'N/A (physics-based)' }}</div>
                                </div>
                            </div>
                            <!-- Export Data button -->
                            <button 
                                class="btn-export"
                                :disabled="isExporting || !analysisData"
                                @click="exportData"
                                title="Export to Files">
                                <span v-if="isExporting" class="spinner-sm"></span>
                                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                    <polyline points="7 10 12 15 17 10"/>
                                    <line x1="12" y1="15" x2="12" y2="3"/>
                                </svg>
                                <span>Export</span>
                            </button>
                            <!-- Simulate button removed - replaced by toggle switch -->
                            <button class="btn-close" @click="closeModal" title="Close (Esc)">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M18 6 6 18M6 6l12 12"/>
                                </svg>
                            </button>
                        </div>
                    </header>

                    <!-- Modal Body -->
                    <div class="modal-body">
                        <!-- Loading state -->
                        <div v-if="isLoading" class="loading-overlay">
                            <div class="spinner"></div>
                            <p>{{ loadingMessage }}</p>
                        </div>

                        <!-- No data state -->
                        <div v-else-if="!analysisData" class="no-data-state">
                            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <path d="M3 3v18h18"/>
                                <path d="m19 9-5 5-4-4-3 3"/>
                            </svg>
                            <h3>No Analysis Data</h3>
                            <p>Click below to generate analysis for this installation.</p>
                            <button class="btn-primary" @click="generateAnalysis">
                                Generate {{ timeframeDays }}-Day Analysis
                            </button>
                        </div>

                        <!-- Main content: Chart + Overview -->
                        <div v-else class="analysis-content">
                            <!-- Left: Combined Chart -->
                            <div class="chart-section">
                                <div class="chart-header">
                                    <h3>{{ chartTitle }}</h3>
                                    <!-- Day navigation only for 'day' timeframe -->
                                    <div v-if="currentTimeframe === 'day'" class="day-nav">
                                        <button class="nav-btn" @click="prevDay" :disabled="currentDayIndex <= 0">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                <path d="m15 18-6-6 6-6"/>
                                            </svg>
                                        </button>
                                        <span class="day-label">{{ currentDayLabel }}</span>
                                        <button class="nav-btn" @click="nextDay" :disabled="currentDayIndex >= totalDays - 1">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                <path d="m9 18 6-6-6-6"/>
                                            </svg>
                                        </button>
                                    </div>
                                    <div v-else class="timeframe-info">
                                        <span>{{ totalDays }} days: {{ dateRangeLabel }}</span>
                                    </div>
                                </div>
                                <div class="chart-container">
                                    <canvas ref="combinedChartRef"></canvas>
                                </div>
                                <!-- Data mode indicator -->
                                <div class="data-mode-badge" :class="dataMode">
                                    {{ dataModeLabel }}
                                </div>
                            </div>

                            <!-- Right: Overview Metrics -->
                            <div class="overview-section">
                                <!-- Key Metrics -->
                                <div class="metrics-card">
                                    <h3>Key Metrics ({{ totalDays }}-day)</h3>
                                    <div class="metrics-grid">
                                        <div class="metric">
                                            <span class="metric-value">{{ periodStats.totalEnergy.toFixed(1) }}</span>
                                            <span class="metric-label">Total kWh</span>
                                        </div>
                                        <div class="metric">
                                            <span class="metric-value">{{ periodStats.avgDaily.toFixed(1) }}</span>
                                            <span class="metric-label">Avg Daily kWh</span>
                                        </div>
                                        <div class="metric metric-highlight">
                                            <span class="metric-value">&euro;{{ periodStats.lightSaved.toFixed(2) }}</span>
                                            <span class="metric-label">Light Saved</span>
                                        </div>
                                        <div class="metric">
                                            <span class="metric-value">{{ periodStats.peakHourEnergy.toFixed(2) }}</span>
                                            <span class="metric-label">Peak kWh/kWp</span>
                                        </div>
                                        <div class="metric">
                                            <span class="metric-value">{{ periodStats.avgTemperature.toFixed(1) }}</span>
                                            <span class="metric-label">Avg Temp C</span>
                                        </div>
                                        <div class="metric">
                                            <span class="metric-value">{{ periodStats.avgCloudCover.toFixed(0) }}</span>
                                            <span class="metric-label">Avg Cloud %</span>
                                        </div>
                                    </div>
                                </div>

                                <!-- Daily Summary Table -->
                                <div class="daily-card">
                                    <h3>Daily Summary</h3>
                                    <div class="daily-table-wrapper">
                                        <table class="daily-table">
                                            <thead>
                                                <tr>
                                                    <th>#</th>
                                                    <th>Date</th>
                                                    <th>kWh</th>
                                                    <th>&euro;</th>
                                                    <th>Temp</th>
                                                    <th>Rating</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr v-for="(day, idx) in dailySummary" :key="idx"
                                                    :class="{ active: idx === currentDayIndex }"
                                                    @click="goToDay(idx)">
                                                    <td>{{ idx + 1 }}</td>
                                                    <td>{{ day.date }}</td>
                                                    <td>{{ day.energy.toFixed(1) }}</td>
                                                    <td>&euro;{{ (day.energy * 0.15).toFixed(2) }}</td>
                                                    <td>{{ day.temp.toFixed(0) }}</td>
                                                    <td>
                                                        <span class="rating" :class="'rank-' + day.rank">
                                                            {{ getRatingLabel(day.rank) }}
                                                        </span>
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </transition>
    </teleport>
</template>

<script>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '../store/app.js'
import { Chart, registerables } from 'chart.js'

Chart.register(...registerables)

// Ranking colors for v3.0.5 (based on normalized specific energy)
// R0: excluded (negligible production), R1-R5 visible with distinct colors
const RANKING_COLORS = {
    0: '#B0B0B0', // R0: Zero/negligible (excluded from display)
    1: '#DC143C', // R1: Poor (red)
    2: '#FF8C00', // R2: Below Avg (orange)
    3: '#FFD700', // R3: Average (yellow)
    4: '#32CD32', // R4: Good (green)
    5: '#87CEEB'  // R5: Excellent (light-blue)
}

// Ranking thresholds based on normalized specific energy: Y/(X*Z)
// Y = energy (kWh), X = capacity (kWp), Z = active hours
// For Portugal: typical daily yield is 4-5 kWh/kWp, peak hours ~6-8
// So hourly normalized yield ~0.5-0.8 kWh/kWp/hour at peak
// These thresholds are calibrated for hourly performance
const RANK_THRESHOLDS = {
    R0: 0.05,   // < 0.05 = R0 (excluded - negligible)
    R1: 0.15,   // 0.05-0.15 = R1 (Poor - very low output)
    R2: 0.30,   // 0.15-0.30 = R2 (Below avg - cloudy/suboptimal)
    R3: 0.50,   // 0.30-0.50 = R3 (Average - normal conditions)
    R4: 0.70,   // 0.50-0.70 = R4 (Good - favorable conditions)
    // >= 0.70 = R5 (Excellent - optimal conditions)
}

const RANK_LABELS = {
    0: 'N/P',     // Not productive
    1: 'Poor',
    2: 'Below',
    3: 'Avg',
    4: 'Good',
    5: 'Excel'
}

export default {
    name: 'AnalyticsModal',
    setup() {
        const store = useAppStore()
        
        // Refs
        const combinedChartRef = ref(null)
        const dateInputRef = ref(null)
        const currentDayIndex = ref(0)
        const currentTimeframe = ref('week')
        const isSimulating = ref(false)
        const isExporting = ref(false)
        const centerDate = ref(new Date().toISOString().split('T')[0])
        const analysisMode = ref('predicted')  // 'historical' or 'predicted'
        const showMlInfo = ref(false)
        const showWeatherDropdown = ref(false)
        
        // Weather layer visibility (all on by default)
        const weatherLayers = ref({
            temperature: true,
            cloudCover: true,
            humidity: true,
            windSpeed: true
        })
        
        // Chart instance
        let combinedChart = null

        // Timeframe options
        const timeframes = [
            { label: 'Day', value: 'day', days: 1 },
            { label: 'Week', value: 'week', days: 7 },
            { label: 'Month', value: 'month', days: 30 },
            { label: 'Year', value: 'year', days: 365 }
        ]

        // Computed
        const isOpen = computed(() => store.analyticsModalOpen)
        const selectedObject = computed(() => store.selectedObject)
        const analysisData = computed(() => store.analysisData)
        const isLoading = computed(() => store.analysisLoading)
        const loadingMessage = computed(() => isSimulating.value ? 'Running simulation...' : 'Generating analysis...')
        const dataMode = computed(() => analysisData.value?.mode || 'historical')
        
        // Dynamic data mode label reflecting weather source
        const dataModeLabel = computed(() => {
            const mode = dataMode.value
            const weatherSource = analysisData.value?.weather_source || ''
            if (mode === 'historical' || analysisMode.value === 'historical') {
                if (weatherSource === 'measured') return 'Historical Data (Measured)'
                if (weatherSource === 'api') return 'Historical Data (API Weather)'
                return 'Historical Data'
            }
            // Predicted / simulated
            if (weatherSource === 'api') return 'Predicted (API Weather)'
            if (weatherSource === 'synthetic') return 'Predicted (Simulated Weather)'
            if (weatherSource === 'historical_file') return 'Predicted (Historical Weather)'
            return 'Predicted Data'
        })
        
        const timeframeDays = computed(() => {
            const tf = timeframes.find(t => t.value === currentTimeframe.value)
            return tf?.days || 21
        })

        const maxDate = computed(() => {
            // For historical installations, use their to_date as max
            const toDate = selectedObject.value?.customData?.toDate?.split('T')[0]
            return toDate || new Date().toISOString().split('T')[0]
        })
        
        const minDate = computed(() => {
            const fromDate = selectedObject.value?.customData?.fromDate?.split('T')[0]
            return fromDate || null
        })
        
        // Effective max date based on analysis mode
        const effectiveMaxDate = computed(() => {
            if (analysisMode.value === 'predicted') {
                // In predicted mode, allow any future date (1 year ahead)
                const futureDate = new Date()
                futureDate.setFullYear(futureDate.getFullYear() + 1)
                return futureDate.toISOString().split('T')[0]
            }
            return maxDate.value
        })
        
        // Clamp center date within historical data range, accounting for half-window
        const clampCenterDate = () => {
            if (analysisMode.value !== 'historical') return
            
            const halfDays = Math.floor(timeframeDays.value / 2)
            const from = minDate.value
            const to = maxDate.value
            
            if (to) {
                // Ensure center - halfDays doesn't go before from_date
                // and center + halfDays doesn't go after to_date
                const toMs = new Date(to).getTime()
                const maxCenter = new Date(toMs - halfDays * 86400000).toISOString().split('T')[0]
                if (centerDate.value > maxCenter) {
                    centerDate.value = maxCenter
                }
            }
            if (from) {
                const fromMs = new Date(from).getTime()
                const minCenter = new Date(fromMs + halfDays * 86400000).toISOString().split('T')[0]
                if (centerDate.value < minCenter) {
                    centerDate.value = minCenter
                }
            }
        }

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

        // Hourly data from API
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

        // Period statistics - includes all weather metrics
        const periodStats = computed(() => {
            const capacity = selectedObject.value?.capacity_kwp || 1
            const days = totalDays.value || 1
            const apiStats = analysisData.value?.period_statistics || {}
            
            const total = apiStats.total_energy_kwh || 
                hourlyData.value.reduce((sum, h) => sum + (h.production_kwh || 0), 0)
            
            // Calculate all weather averages from hourly data
            const len = hourlyData.value.length || 1
            const avgTemp = hourlyData.value.reduce((sum, h) => sum + (h.temperature || 0), 0) / len
            const avgCloud = hourlyData.value.reduce((sum, h) => sum + (h.cloud_cover || 0), 0) / len
            const avgHumidity = hourlyData.value.reduce((sum, h) => sum + (h.humidity || 0), 0) / len
            const avgWind = hourlyData.value.reduce((sum, h) => sum + (h.wind_speed || 0), 0) / len
            const avgRadiation = hourlyData.value.reduce((sum, h) => sum + (h.radiation || 0), 0) / len
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
                avgRadiation: avgRadiation
            }
        })

        // Summary data for table - shows hourly for 'day' timeframe, daily for others
        const dailySummary = computed(() => {
            if (!hourlyData.value.length) return []
            
            const capacity = selectedObject.value?.capacity_kwp || 1
            
            // For 'day' timeframe, show hourly values
            if (currentTimeframe.value === 'day') {
                const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))].sort()
                const currentDate = dates[currentDayIndex.value]
                const dayData = hourlyData.value.filter(h => (h.timestamp || '').split('T')[0] === currentDate)
                
                return dayData
                    .filter(h => (h.production_kwh || 0) > 0.01)  // Filter R0 hours
                    .map(h => {
                        const specificEnergy = (h.production_kwh || 0) / capacity
                        return {
                            date: `${h.hour || 0}:00`,  // Show hour instead of date
                            energy: h.production_kwh || 0,
                            specificEnergy: specificEnergy,
                            peak: h.production_kwh || 0,  // For hourly, peak = production
                            temp: h.temperature || 0,
                            humidity: h.humidity || 0,
                            cloud: h.cloud_cover || 0,
                            wind: h.wind_speed || 0,
                            radiation: h.radiation || 0,
                            rank: calculateNormalizedRank(h.production_kwh || 0, capacity, 1)  // 1 hour
                        }
                    })
            }
            
            // For other timeframes, show daily values
            const apiDaily = analysisData.value?.daily_data || []
            if (apiDaily.length > 0) {
                // Use API-provided data with new fields (already filtered for R0)
                return apiDaily.map(d => {
                    // Count active hours (hours with production > R0 threshold)
                    const dayHourly = hourlyData.value.filter(h => 
                        (h.timestamp || '').split('T')[0] === d.date && (h.production_kwh || 0) > 0.01
                    )
                    const activeHours = dayHourly.length || 1
                    const normalizedRank = calculateNormalizedRank(d.total_production_kwh || 0, capacity, activeHours)
                    
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
                        activeHours: activeHours,
                        rank: normalizedRank
                    }
                })
            }
            
            // Calculate from hourly (fallback)
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
            
            return Object.entries(byDate)
                .map(([date, data]) => {
                    const specificEnergy = data.energy / capacity
                    const activeHours = data.activeHours || 1
                    const rank = calculateNormalizedRank(data.energy, capacity, activeHours)
                    // Filter out R0 days
                    if (rank === 0) return null
                    return {
                        date: date.slice(5),
                        energy: data.energy,
                        specificEnergy: specificEnergy,
                        peak: data.peak,
                        temp: data.temps.reduce((a, b) => a + b, 0) / data.temps.length,
                        humidity: data.humidities.reduce((a, b) => a + b, 0) / data.humidities.length,
                        cloud: data.clouds.reduce((a, b) => a + b, 0) / data.clouds.length,
                        wind: data.winds.reduce((a, b) => a + b, 0) / data.winds.length,
                        radiation: data.radiations.reduce((a, b) => a + b, 0) / data.radiations.length,
                        activeHours: activeHours,
                        rank: rank
                    }
                })
                .filter(d => d !== null)  // Remove R0 days
        })

        // Methods
        // Calculate normalized rank based on Y/(X*Z) formula
        // Y = energy (kWh), X = capacity (kWp), Z = active hours
        const calculateNormalizedRank = (energy, capacity, activeHours) => {
            if (!energy || !capacity || !activeHours) return 0
            // Normalized specific energy = Y / (X * Z)
            const normalizedSpecificEnergy = energy / (capacity * activeHours)
            
            if (normalizedSpecificEnergy < RANK_THRESHOLDS.R0) return 0  // R0: excluded
            if (normalizedSpecificEnergy < RANK_THRESHOLDS.R1) return 1  // R1: Poor
            if (normalizedSpecificEnergy < RANK_THRESHOLDS.R2) return 2  // R2: Below avg
            if (normalizedSpecificEnergy < RANK_THRESHOLDS.R3) return 3  // R3: Average
            if (normalizedSpecificEnergy < RANK_THRESHOLDS.R4) return 4  // R4: Good
            return 5  // R5: Excellent
        }
        
        // Simple rank based on specific energy (kWh/kWp) - for backward compatibility
        const getRank = (energy, capacity = null) => {
            const cap = capacity || selectedObject.value?.capacity_kwp || 1
            const specificEnergy = energy / cap
            
            if (specificEnergy < RANK_THRESHOLDS.R0) return 0  // R0: excluded
            if (specificEnergy < RANK_THRESHOLDS.R1) return 1  // R1: Poor
            if (specificEnergy < RANK_THRESHOLDS.R2) return 2  // R2: Below avg
            if (specificEnergy < RANK_THRESHOLDS.R3) return 3  // R3: Average
            if (specificEnergy < RANK_THRESHOLDS.R4) return 4  // R4: Good
            return 5  // R5: Excellent
        }

        const getRatingLabel = (rank) => {
            return RANK_LABELS[rank] || 'N/A'
        }

        const closeModal = () => {
            store.closeAnalyticsModal()
        }

        const setTimeframe = async (tf) => {
            currentTimeframe.value = tf
            store.setAnalyticsTimeframe(tf)
            clampCenterDate()
            await generateAnalysis()
        }

        const onDateChange = async () => {
            clampCenterDate()
            await generateAnalysis()
        }

        const openCalendar = () => {
            if (dateInputRef.value) {
                dateInputRef.value.showPicker()
            }
        }
        
        // Analysis mode toggle methods
        const setAnalysisMode = async (mode) => {
            if (analysisMode.value !== mode) {
                analysisMode.value = mode
                if (mode === 'historical') {
                    // Set center date to middle of historical data range
                    const to = maxDate.value
                    if (to) {
                        centerDate.value = to
                    }
                    clampCenterDate()
                }
                await generateAnalysis()
            }
        }
        
        const toggleAnalysisMode = async () => {
            const newMode = analysisMode.value === 'historical' ? 'predicted' : 'historical'
            await setAnalysisMode(newMode)
        }

        const generateAnalysis = async () => {
            if (!selectedObject.value) return
            
            // Use mode from toggle: historical or predicted (simulated)
            const mode = analysisMode.value === 'predicted' ? 'simulated' : 'historical'
            await store.generateAnalysisWithMode(
                selectedObject.value.id, 
                centerDate.value, 
                timeframeDays.value,
                mode
            )
            currentDayIndex.value = Math.floor(totalDays.value / 2)
            await nextTick()
            renderCombinedChart()
        }

        const exportData = async () => {
            if (!selectedObject.value || !analysisData.value) return
            isExporting.value = true
            try {
                // Export the current analysis data as CSV
                await store.exportAnalysisReport(
                    selectedObject.value,
                    analysisData.value,
                    centerDate.value,
                    timeframeDays.value
                )
            } catch (e) {
                console.error('Export failed:', e)
            } finally {
                isExporting.value = false
            }
        }

        const prevDay = () => {
            if (currentDayIndex.value > 0) {
                currentDayIndex.value--
                renderCombinedChart()
            }
        }

        const nextDay = () => {
            if (currentDayIndex.value < totalDays.value - 1) {
                currentDayIndex.value++
                renderCombinedChart()
            }
        }

        // When user clicks on a specific row in the daily summary
        // For 'day' timeframe: clicking on hours does NOT change chart (v3.0.5 fix)
        // For other timeframes: switch to 'day' view for that date
        const goToDay = (idx) => {
            // In day timeframe, clicking on hourly rows should NOT change anything
            // The chart shows the whole day regardless of hour clicked
            if (currentTimeframe.value === 'day') {
                // Do nothing - chart stays the same for the selected day
                return
            }
            
            // For week/month/21-day: switch to day view and update index
            currentDayIndex.value = idx
            currentTimeframe.value = 'day'
            renderCombinedChart()
        }
        
        // Toggle weather dropdown
        const toggleWeatherDropdown = () => {
            showWeatherDropdown.value = !showWeatherDropdown.value
        }

        // Render combined energy + weather chart
        const renderCombinedChart = () => {
            if (!combinedChartRef.value || !hourlyData.value.length) return

            // Destroy existing chart
            if (combinedChart) {
                combinedChart.destroy()
            }

            const ctx = combinedChartRef.value.getContext('2d')

            // For 'day' timeframe: show hourly data for one day
            // For other timeframes: show daily aggregates
            if (currentTimeframe.value === 'day') {
                renderHourlyChart(ctx)
            } else {
                renderDailyChart(ctx)
            }
        }

        // Render hourly chart for single day view
        const renderHourlyChart = (ctx) => {
            const dates = [...new Set(hourlyData.value.map(p => (p.timestamp || '').split('T')[0]))].sort()
            const currentDate = dates[currentDayIndex.value]
            let dayData = hourlyData.value.filter(p => (p.timestamp || '').split('T')[0] === currentDate)

            if (dayData.length === 0) return

            // Sort by hour
            dayData.sort((a, b) => (a.hour || 0) - (b.hour || 0))

            // Filter to daylight hours (non-zero values or 6-20h)
            dayData = dayData.filter(d => (d.production_kwh || 0) > 0 || (d.hour >= 6 && d.hour <= 20))

            const labels = dayData.map(d => `${d.hour || 0}:00`)

            // Build datasets array based on weather layer visibility
            // For hourly data, activeHours = 1 (each bar represents 1 hour)
            const datasets = [
                {
                    label: 'Energy (kWh)',
                    type: 'bar',
                    data: dayData.map(d => d.production_kwh || 0),
                    backgroundColor: dayData.map(d => getRankingColor(d.production_kwh || 0, 1)),
                    borderWidth: 1,
                    yAxisID: 'y',
                    order: 4
                }
            ]
            
            if (weatherLayers.value.temperature) {
                datasets.push({
                    label: 'Temperature (C)',
                    type: 'line',
                    data: dayData.map(d => d.temperature || 0),
                    borderColor: '#FFA500',
                    backgroundColor: 'rgba(255, 165, 0, 0.1)',
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1',
                    order: 3
                })
            }
            
            if (weatherLayers.value.cloudCover) {
                datasets.push({
                    label: 'Cloud Cover (%)',
                    type: 'line',
                    data: dayData.map(d => d.cloud_cover || 0),
                    borderColor: '#888888',
                    backgroundColor: 'rgba(136, 136, 136, 0.2)',
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y2',
                    order: 0
                })
            }
            
            if (weatherLayers.value.humidity) {
                datasets.push({
                    label: 'Humidity (%)',
                    type: 'line',
                    data: dayData.map(d => d.humidity || 0),
                    borderColor: '#4169E1',
                    backgroundColor: 'rgba(65, 105, 225, 0.1)',
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y2',
                    order: 1,
                    borderDash: [5, 5]
                })
            }
            
            if (weatherLayers.value.windSpeed) {
                datasets.push({
                    label: 'Wind Speed (m/s)',
                    type: 'line',
                    data: dayData.map(d => d.wind_speed || 0),
                    borderColor: '#9B59B6',
                    backgroundColor: 'rgba(155, 89, 182, 0.1)',
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y3',
                    order: 2
                })
            }

            combinedChart = new Chart(ctx, {
                type: 'bar',
                data: { labels, datasets },
                options: getChartOptions(`Hourly - ${currentDate}`)
            })
        }

        // Render daily aggregates chart for week/month/21-day view
        const renderDailyChart = (ctx) => {
            // Aggregate hourly data by date, tracking active hours for ranking
            const dailyAgg = {}
            hourlyData.value.forEach(h => {
                const date = (h.timestamp || '').split('T')[0]
                if (!dailyAgg[date]) {
                    dailyAgg[date] = { energy: 0, activeHours: 0, temps: [], clouds: [], humidities: [], winds: [] }
                }
                dailyAgg[date].energy += h.production_kwh || 0
                // Count active hours (production > 0.01 kWh threshold)
                if ((h.production_kwh || 0) > 0.01) dailyAgg[date].activeHours++
                dailyAgg[date].temps.push(h.temperature || 0)
                dailyAgg[date].clouds.push(h.cloud_cover || 0)
                dailyAgg[date].humidities.push(h.humidity || 0)
                dailyAgg[date].winds.push(h.wind_speed || 0)
            })

            const dates = Object.keys(dailyAgg).sort()
            const energyData = dates.map(d => dailyAgg[d].energy)
            const tempData = dates.map(d => 
                dailyAgg[d].temps.reduce((a, b) => a + b, 0) / dailyAgg[d].temps.length
            )
            const cloudData = dates.map(d => 
                dailyAgg[d].clouds.reduce((a, b) => a + b, 0) / dailyAgg[d].clouds.length
            )
            const humidityData = dates.map(d => 
                dailyAgg[d].humidities.reduce((a, b) => a + b, 0) / dailyAgg[d].humidities.length
            )
            const windData = dates.map(d => 
                dailyAgg[d].winds.reduce((a, b) => a + b, 0) / dailyAgg[d].winds.length
            )

            // Get active hours for each day for ranking calculation
            const activeHoursData = dates.map(d => dailyAgg[d].activeHours || 1)
            const labels = dates.map(d => d.slice(5)) // MM-DD format

            // For large datasets (Year), use line instead of bar for better visibility
            const isLarge = dates.length > 60
            
            // Build datasets array based on weather layer visibility
            const datasets = [
                {
                    label: 'Daily Energy (kWh)',
                    type: isLarge ? 'line' : 'bar',
                    data: energyData,
                    // Use same normalized ranking as Daily Summary: energy / (capacity * activeHours)
                    backgroundColor: isLarge
                        ? 'rgba(34, 165, 89, 0.2)'
                        : energyData.map((e, i) => getRankingColor(e, activeHoursData[i])),
                    borderColor: isLarge ? '#22A559' : undefined,
                    borderWidth: isLarge ? 2 : 1,
                    fill: isLarge,
                    tension: isLarge ? 0.3 : 0,
                    pointRadius: isLarge ? 0 : undefined,
                    yAxisID: 'y',
                    order: 4
                }
            ]
            
            if (weatherLayers.value.temperature) {
                datasets.push({
                    label: 'Avg Temperature (C)',
                    type: 'line',
                    data: tempData,
                    borderColor: '#FFA500',
                    backgroundColor: 'rgba(255, 165, 0, 0.1)',
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1',
                    order: 3
                })
            }
            
            if (weatherLayers.value.cloudCover) {
                datasets.push({
                    label: 'Avg Cloud Cover (%)',
                    type: 'line',
                    data: cloudData,
                    borderColor: '#888888',
                    backgroundColor: 'rgba(136, 136, 136, 0.2)',
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y2',
                    order: 0
                })
            }
            
            if (weatherLayers.value.humidity) {
                datasets.push({
                    label: 'Avg Humidity (%)',
                    type: 'line',
                    data: humidityData,
                    borderColor: '#4169E1',
                    backgroundColor: 'rgba(65, 105, 225, 0.1)',
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y2',
                    order: 1,
                    borderDash: [5, 5]
                })
            }
            
            if (weatherLayers.value.windSpeed) {
                datasets.push({
                    label: 'Avg Wind (m/s)',
                    type: 'line',
                    data: windData,
                    borderColor: '#9B59B6',
                    backgroundColor: 'rgba(155, 89, 182, 0.1)',
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y3',
                    order: 2
                })
            }

            combinedChart = new Chart(ctx, {
                type: 'bar',
                data: { labels, datasets },
                options: getChartOptions(`${totalDays.value}-Day Period`)
            })
        }

        // Get ranking color based on normalized specific energy: Y/(X*Z)
        // Y = energy (kWh), X = capacity (kWp), Z = active hours
        // This ensures chart colors match the Daily Summary ratings
        const getRankingColor = (energy, activeHours = 1) => {
            const capacity = selectedObject.value?.capacity_kwp || 1
            const normalizedSE = energy / (capacity * activeHours)
            
            // Use ranking thresholds based on normalized specific energy
            if (normalizedSE < RANK_THRESHOLDS.R0) return RANKING_COLORS[0]  // R0: excluded
            if (normalizedSE < RANK_THRESHOLDS.R1) return RANKING_COLORS[1]  // R1: Poor
            if (normalizedSE < RANK_THRESHOLDS.R2) return RANKING_COLORS[2]  // R2: Below avg
            if (normalizedSE < RANK_THRESHOLDS.R3) return RANKING_COLORS[3]  // R3: Average
            if (normalizedSE < RANK_THRESHOLDS.R4) return RANKING_COLORS[4]  // R4: Good
            return RANKING_COLORS[5]  // R5: Excellent
        }

        // Common chart options
        const getChartOptions = (title) => {
            // For large datasets (Year), limit x-axis labels and widen bars
            const isLargeDataset = timeframeDays.value > 60
            
            return {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: true,
                        text: title,
                        font: { size: 14, weight: 'bold' }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.dataset.label || ''
                                const value = context.parsed.y
                                if (label.includes('Energy')) return `${label}: ${value.toFixed(2)} kWh`
                                if (label.includes('Temp')) return `${label}: ${value.toFixed(1)} C`
                                if (label.includes('Cloud') || label.includes('Humidity')) return `${label}: ${value.toFixed(0)}%`
                                if (label.includes('Wind')) return `${label}: ${value.toFixed(1)} m/s`
                                return `${label}: ${value}`
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            maxTicksLimit: isLargeDataset ? 24 : undefined,
                            maxRotation: isLargeDataset ? 45 : 0,
                            autoSkip: true
                        }
                    },
                    y: {
                        type: 'linear',
                        position: 'left',
                        beginAtZero: true,
                        title: { display: true, text: 'Energy (kWh)' }
                    },
                    y1: {
                        type: 'linear',
                        position: 'right',
                        title: { display: true, text: 'Temperature (C)' },
                        grid: { drawOnChartArea: false }
                    },
                    y2: {
                        type: 'linear',
                        position: 'right',
                        min: 0,
                        max: 100,
                        title: { display: false },
                        grid: { drawOnChartArea: false },
                        display: false
                    },
                    y3: {
                        type: 'linear',
                        position: 'right',
                        min: 0,
                        title: { display: false },
                        grid: { drawOnChartArea: false },
                        display: false
                    }
                }
            }
        }

        // Keyboard handler for Escape
        const handleKeydown = (e) => {
            if (e.key === 'Escape' && isOpen.value) {
                closeModal()
            }
        }

        // Watch for modal open to render chart
        watch(isOpen, async (open) => {
            if (open && analysisData.value) {
                currentDayIndex.value = Math.floor(totalDays.value / 2)
                await nextTick()
                setTimeout(() => renderCombinedChart(), 100)
            }
        })

        // Watch analysis data changes
        watch(analysisData, async (data) => {
            if (data && isOpen.value) {
                currentDayIndex.value = Math.floor(totalDays.value / 2)
                await nextTick()
                setTimeout(() => renderCombinedChart(), 100)
            }
        })

        onMounted(() => {
            document.addEventListener('keydown', handleKeydown)
        })

        onUnmounted(() => {
            document.removeEventListener('keydown', handleKeydown)
            if (combinedChart) {
                combinedChart.destroy()
            }
        })

        return {
            combinedChartRef,
            dateInputRef,
            isOpen,
            selectedObject,
            analysisData,
            isLoading,
            loadingMessage,
            isSimulating,
            isExporting,
            dataMode,
            timeframes,
            currentTimeframe,
            timeframeDays,
            currentDayIndex,
            currentDayLabel,
            totalDays,
            periodStats,
            dailySummary,
            getRatingLabel,
            closeModal,
            setTimeframe,
            generateAnalysis,
            exportData,
            prevDay,
            nextDay,
            goToDay,
            centerDate,
            maxDate,
            effectiveMaxDate,
            chartTitle,
            dateRangeLabel,
            onDateChange,
            openCalendar,
            // v3.0.4: Analysis mode toggle
            analysisMode,
            setAnalysisMode,
            toggleAnalysisMode,
            // v3.0.5: Weather layer toggles
            showWeatherDropdown,
            weatherLayers,
            toggleWeatherDropdown,
            renderCombinedChart,
            // v3.0.6: Dynamic data label + ML info
            dataModeLabel,
            showMlInfo
        }
    }
}
</script>

<style scoped>
/* Modal Overlay */
.analytics-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    padding: 24px;
}

/* Modal Container */
.analytics-modal {
    background: var(--color-main-background, #fff);
    border-radius: 12px;
    width: 100%;
    max-width: 1400px;
    height: 90vh;
    max-height: 900px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

/* Modal Header */
.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: var(--color-background-dark, #f5f5f5);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    gap: 16px;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.status-badge {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}
.status-badge.active { background: #22A559; }
.status-badge.warning { background: #F5A623; }
.status-badge.offline { background: #CC2020; }

.modal-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}

.location-badge, .capacity-badge {
    font-size: 12px;
    padding: 4px 8px;
    background: var(--color-background-hover, #e8e8e8);
    border-radius: 4px;
    color: var(--color-text-lighter, #666);
}

.header-center {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
}

/* Mode Toggle Switch */
.mode-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px;
    background: var(--color-background-hover, #e8e8e8);
    border-radius: 20px;
}

.mode-label {
    font-size: 12px;
    color: var(--color-text-lighter, #888);
    cursor: pointer;
    transition: color 0.2s;
}

.mode-label.active {
    color: var(--color-primary, #0082c9);
    font-weight: 600;
}

.toggle-switch {
    position: relative;
    display: inline-block;
    width: 40px;
    height: 20px;
}

.toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #32CD32;
    transition: 0.3s;
    border-radius: 20px;
}

.toggle-slider:before {
    position: absolute;
    content: "";
    height: 14px;
    width: 14px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: 0.3s;
    border-radius: 50%;
}

input:checked + .toggle-slider {
    background-color: #F5A623;
}

input:checked + .toggle-slider:before {
    transform: translateX(20px);
}

.date-picker-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.date-picker-group label {
    font-size: 13px;
    color: var(--color-text-lighter, #666);
}

.date-input {
    padding: 6px 10px;
    border: 1px solid var(--color-border, #ccc);
    border-radius: 6px;
    font-size: 13px;
    background: var(--color-main-background, #fff);
}

.date-input:hover {
    border-color: var(--color-primary, #0082c9);
}

.calendar-btn {
    padding: 6px 8px;
    border: 1px solid var(--color-border, #ccc);
    background: var(--color-main-background, #fff);
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.calendar-btn:hover {
    background: var(--color-background-hover, #f0f0f0);
    border-color: var(--color-primary, #0082c9);
}

.timeframe-buttons {
    display: flex;
    gap: 8px;
}

.tf-btn {
    padding: 8px 16px;
    border: 1px solid var(--color-border, #ccc);
    background: var(--color-main-background, #fff);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.tf-btn:hover {
    background: var(--color-background-hover, #f0f0f0);
}

.tf-btn.active {
    background: var(--color-primary, #0082c9);
    color: white;
    border-color: var(--color-primary, #0082c9);
}

/* Weather Toggle Dropdown (v3.0.5) */
.weather-toggle {
    position: relative;
}

.weather-toggle-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border: 1px solid var(--color-border, #ccc);
    background: var(--color-main-background, #fff);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.weather-toggle-btn:hover {
    background: var(--color-background-hover, #f0f0f0);
    border-color: var(--color-primary, #0082c9);
}

.weather-dropdown {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 4px;
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #ccc);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 100;
    min-width: 160px;
    padding: 8px 0;
}

.weather-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 13px;
    transition: background 0.2s;
}

.weather-option:hover {
    background: var(--color-background-hover, #f5f5f5);
}

.weather-option input {
    cursor: pointer;
}

.weather-color {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    flex-shrink: 0;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 12px;
}

/* ML Info Button & Popover (v3.0.6) */
.ml-info-wrapper {
    position: relative;
}

.btn-info {
    padding: 8px 12px;
    background: var(--color-background-dark, #f0f0f0);
    color: var(--color-main-text, #333);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
}

.btn-info:hover {
    background: var(--color-background-hover, #e8e8e8);
    border-color: var(--color-primary, #0082c9);
}

.ml-info-popover {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 8px;
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #ccc);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    z-index: 200;
    min-width: 320px;
    padding: 16px;
}

.ml-info-popover h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-main-text, #333);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    padding-bottom: 8px;
}

.ml-info-row {
    font-size: 12px;
    color: var(--color-text-lighter, #666);
    padding: 3px 0;
    line-height: 1.5;
}

.ml-info-label {
    font-weight: 600;
    color: var(--color-main-text, #333);
}

/* Light Saved highlight */
.metric-highlight .metric-value {
    color: #22A559;
}

.btn-export {
    padding: 8px 12px;
    background: var(--color-background-dark, #f0f0f0);
    color: var(--color-main-text, #333);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
}

.btn-export:hover:not(:disabled) {
    background: var(--color-background-hover, #e8e8e8);
    border-color: var(--color-border-dark, #ccc);
}

.btn-export:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-simulate {
    padding: 8px 16px;
    background: #F5A623;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
}

.btn-simulate:hover:not(:disabled) {
    background: #e09000;
}

.btn-simulate:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.btn-close {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    color: var(--color-text-lighter, #666);
    border-radius: 4px;
}

.btn-close:hover {
    background: var(--color-background-hover, #e8e8e8);
    color: var(--color-main-text, #333);
}

/* Modal Body */
.modal-body {
    flex: 1;
    overflow: hidden;
    position: relative;
}

/* Loading Overlay */
.loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.9);
    gap: 16px;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--color-border, #e0e0e0);
    border-top-color: var(--color-primary, #0082c9);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

.spinner-sm {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* No Data State */
.no-data-state {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--color-text-lighter, #666);
    gap: 16px;
}

.no-data-state h3 {
    margin: 0;
    font-size: 20px;
    color: var(--color-main-text, #333);
}

.btn-primary {
    padding: 12px 24px;
    background: var(--color-primary, #0082c9);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
}

.btn-primary:hover {
    background: var(--color-primary-hover, #0070b0);
}

/* Analysis Content - Two Columns */
.analysis-content {
    display: flex;
    height: 100%;
    overflow: hidden;
}

/* Chart Section - Left */
.chart-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
    border-right: 1px solid var(--color-border, #e0e0e0);
    position: relative;
}

.chart-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}

.chart-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}

.day-nav {
    display: flex;
    align-items: center;
    gap: 8px;
}

.nav-btn {
    background: var(--color-background-dark, #f5f5f5);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 4px;
    padding: 4px 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
}

.nav-btn:hover:not(:disabled) {
    background: var(--color-background-hover, #e8e8e8);
}

.nav-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.day-label {
    font-size: 13px;
    min-width: 100px;
    text-align: center;
}

.chart-container {
    flex: 1;
    min-height: 0;
    position: relative;
}

.chart-container canvas {
    width: 100% !important;
    height: 100% !important;
}

.data-mode-badge {
    position: absolute;
    bottom: 20px;
    left: 20px;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
}

.data-mode-badge.historical {
    background: #e8f5e9;
    color: #2e7d32;
}

.data-mode-badge.simulated {
    background: #fff3e0;
    color: #ef6c00;
}

/* Overview Section - Right */
.overview-section {
    width: 380px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 20px;
    gap: 20px;
}

.metrics-card, .daily-card {
    background: var(--color-background-dark, #f8f8f8);
    border-radius: 8px;
    padding: 16px;
}

.metrics-card h3, .daily-card h3 {
    margin: 0 0 16px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-lighter, #666);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}

.metric {
    text-align: center;
}

.metric-value {
    display: block;
    font-size: 24px;
    font-weight: 700;
    color: var(--color-main-text, #333);
}

.metric-label {
    display: block;
    font-size: 11px;
    color: var(--color-text-lighter, #888);
    margin-top: 4px;
}

/* Daily Table */
.daily-table-wrapper {
    max-height: 300px;
    overflow-y: auto;
}

.daily-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}

.daily-table th,
.daily-table td {
    padding: 8px 6px;
    text-align: left;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.daily-table th {
    font-weight: 600;
    color: var(--color-text-lighter, #666);
    position: sticky;
    top: 0;
    background: var(--color-background-dark, #f8f8f8);
}

.daily-table tr.active {
    background: var(--color-primary-light, #e3f2fd);
}

.daily-table tr:hover {
    background: var(--color-background-hover, #f0f0f0);
    cursor: pointer;
}

.rating {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
}

/* Ranking colors based on specific energy (kWh/kWp) */
.rating.rank-0 { background: #B0B0B0; color: white; }  /* R0: Zero (hidden) */
.rating.rank-1 { background: #DC143C; color: white; }  /* R1: Poor (red) */
.rating.rank-2 { background: #FF8C00; color: white; }  /* R2: Below Avg (orange) */
.rating.rank-3 { background: #FFD700; color: #333; }   /* R3: Average (yellow) */
.rating.rank-4 { background: #32CD32; color: white; }  /* R4: Good (green) */
.rating.rank-5 { background: #87CEEB; color: #333; }   /* R5: Excellent (light-blue) */

/* Modal Transitions */
.modal-fade-enter-active,
.modal-fade-leave-active {
    transition: opacity 0.2s ease;
}

.modal-fade-enter-active .analytics-modal,
.modal-fade-leave-active .analytics-modal {
    transition: transform 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
    opacity: 0;
}

.modal-fade-enter-from .analytics-modal,
.modal-fade-leave-to .analytics-modal {
    transform: scale(0.95);
}

/* Responsive */
@media (max-width: 1000px) {
    .analysis-content {
        flex-direction: column;
    }
    
    .chart-section {
        border-right: none;
        border-bottom: 1px solid var(--color-border, #e0e0e0);
        height: 50%;
    }
    
    .overview-section {
        width: 100%;
        height: 50%;
    }
}
</style>
