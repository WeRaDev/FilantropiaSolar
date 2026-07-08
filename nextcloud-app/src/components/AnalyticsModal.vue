<template>
    <teleport to="body">
        <transition name="modal-fade">
            <div v-if="isOpen" class="analytics-modal-overlay" @click.self="closeModal">
                <div class="analytics-modal">
                    <AnalyticsHeader
                        :selected-object="selectedObject"
                        :analysis-mode="analysisMode"
                        :center-date="centerDate"
                        :effective-max-date="effectiveMaxDate"
                        :timeframes="timeframes"
                        :current-timeframe="currentTimeframe"
                        :weather-layers="weatherLayers"
                        :analysis-data="analysisData"
                        :is-exporting="isExporting"
                        @update:center-date="centerDate = $event"
                        @update:weather-layers="weatherLayers = $event"
                        @set-analysis-mode="setAnalysisMode"
                        @toggle-analysis-mode="toggleAnalysisMode"
                        @date-change="onDateChange"
                        @set-timeframe="setTimeframe"
                        @weather-change="renderCombinedChart"
                        @export="exportData"
                        @close="closeModal"
                    />

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
                                        <button class="nav-btn" :disabled="currentDayIndex <= 0" @click="prevDay">
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                <path d="m15 18-6-6 6-6"/>
                                            </svg>
                                        </button>
                                        <span class="day-label">{{ currentDayLabel }}</span>
                                        <button class="nav-btn" :disabled="currentDayIndex >= totalDays - 1" @click="nextDay">
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
                                <KeyMetricsPanel :period-stats="periodStats" :total-days="totalDays" />
                                <DailySummaryPanel
                                    :daily-summary="dailySummary"
                                    :current-day-index="currentDayIndex"
                                    @select-day="goToDay"
                                />
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
import { useEnergyChart } from '../composables/useEnergyChart.js'
import { useAnalyticsStats } from '../composables/useAnalyticsStats.js'
import { useAnalyticsExport } from '../composables/useAnalyticsExport.js'
import AnalyticsHeader from './analytics/AnalyticsHeader.vue'
import KeyMetricsPanel from './analytics/KeyMetricsPanel.vue'
import DailySummaryPanel from './analytics/DailySummaryPanel.vue'

export default {
    name: 'AnalyticsModal',
    components: {
        AnalyticsHeader,
        KeyMetricsPanel,
        DailySummaryPanel,
    },
    setup() {
        const store = useAppStore()

        // Refs / local state
        const combinedChartRef = ref(null)
        const currentDayIndex = ref(0)
        const currentTimeframe = ref('week')
        const isSimulating = ref(false)
        const centerDate = ref(new Date().toISOString().split('T')[0])
        const analysisMode = ref('predicted') // 'historical' or 'predicted'
        const weatherLayers = ref({
            temperature: true,
            cloudCover: true,
            humidity: true,
            windSpeed: true,
        })

        // Timeframe options
        const timeframes = [
            { label: 'Day', value: 'day', days: 1 },
            { label: 'Week', value: 'week', days: 7 },
            { label: 'Month', value: 'month', days: 30 },
            { label: 'Year', value: 'year', days: 365 },
        ]

        // Store-backed computed
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

        // Derived analytics statistics
        const {
            hourlyData,
            totalDays,
            currentDayLabel,
            chartTitle,
            dateRangeLabel,
            periodStats,
            dailySummary,
        } = useAnalyticsStats({
            analysisData,
            selectedObject,
            currentTimeframe,
            currentDayIndex,
            timeframeDays,
        })

        // Export handling
        const { isExporting, exportData } = useAnalyticsExport({
            store,
            selectedObject,
            analysisData,
            centerDate,
            timeframeDays,
        })

        // Chart composable - delegates all Chart.js rendering
        const { renderChart: renderCombinedChart, destroyChart } = useEnergyChart({
            canvasRef: combinedChartRef,
            hourlyData,
            currentTimeframe,
            currentDayIndex,
            totalDays,
            timeframeDays,
            selectedObject,
            weatherLayers,
        })

        // Methods
        const closeModal = () => {
            store.closeAnalyticsModal()
        }

        const generateAnalysis = async () => {
            if (!selectedObject.value) return
            const mode = analysisMode.value === 'predicted' ? 'simulated' : 'historical'
            await store.generateAnalysisWithMode(
                selectedObject.value.id,
                centerDate.value,
                timeframeDays.value,
                mode,
            )
            currentDayIndex.value = Math.floor(totalDays.value / 2)
            await nextTick()
            renderCombinedChart()
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

        const setAnalysisMode = async (mode) => {
            if (analysisMode.value !== mode) {
                analysisMode.value = mode
                if (mode === 'historical') {
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

        // For 'day' timeframe clicking rows does nothing; otherwise switch to that day
        const goToDay = (idx) => {
            if (currentTimeframe.value === 'day') {
                return
            }
            currentDayIndex.value = idx
            currentTimeframe.value = 'day'
            renderCombinedChart()
        }

        // Keyboard handler for Escape
        const handleKeydown = (e) => {
            if (e.key === 'Escape' && isOpen.value) {
                closeModal()
            }
        }

        // Re-render chart when the modal opens with existing data
        watch(isOpen, async (open) => {
            if (open && analysisData.value) {
                currentDayIndex.value = Math.floor(totalDays.value / 2)
                await nextTick()
                setTimeout(() => renderCombinedChart(), 100)
            }
        })

        // Re-render chart when analysis data changes
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
            destroyChart()
        })

        return {
            combinedChartRef,
            isOpen,
            selectedObject,
            analysisData,
            isLoading,
            loadingMessage,
            isExporting,
            dataMode,
            dataModeLabel,
            timeframes,
            currentTimeframe,
            timeframeDays,
            currentDayIndex,
            currentDayLabel,
            totalDays,
            periodStats,
            dailySummary,
            chartTitle,
            dateRangeLabel,
            centerDate,
            effectiveMaxDate,
            analysisMode,
            weatherLayers,
            closeModal,
            setTimeframe,
            onDateChange,
            setAnalysisMode,
            toggleAnalysisMode,
            generateAnalysis,
            exportData,
            prevDay,
            nextDay,
            goToDay,
            renderCombinedChart,
        }
    },
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
