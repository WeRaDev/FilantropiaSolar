<template>
    <teleport to="body">
        <transition name="modal-fade">
            <div v-if="isOpen" class="analytics-modal-overlay" @click.self="closeModal">
                <div class="analytics-modal">
                    <AnalyticsHeader
                        :selected-object="selectedObject"
                        :analysis-mode="analysisMode"
                        :center-date="centerDate"
                        :effective-min-date="effectiveMinDate"
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
                        @add-historical="onAddHistorical"
                        @export="exportData"
                        @close="closeModal"
                    />

                    <!-- Modal Body -->
                    <div class="modal-body">
                        <!-- Loading / no-data states -->
                        <ModalStatePanel
                            v-if="isLoading || !analysisData"
                            :state="isLoading ? 'loading' : 'no-data'"
                            :loading-message="loadingMessage"
                            :timeframe-days="timeframeDays"
                            @generate="generateAnalysis"
                        />

                        <!-- Main content: Chart + Overview -->
                        <div v-else class="analysis-content">
                            <ChartSection
                                :chart-title="chartTitle"
                                :current-timeframe="currentTimeframe"
                                :current-day-index="currentDayIndex"
                                :total-days="totalDays"
                                :current-day-label="currentDayLabel"
                                :date-range-label="dateRangeLabel"
                                :data-mode="dataMode"
                                :data-mode-label="dataModeLabel"
                                @prev-day="prevDay"
                                @next-day="nextDay"
                                @canvas-el="onCanvasEl"
                            />

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
import { useAnalyticsDateRange } from '../composables/useAnalyticsDateRange.js'
import AnalyticsHeader from './analytics/AnalyticsHeader.vue'
import ChartSection from './analytics/ChartSection.vue'
import ModalStatePanel from './analytics/ModalStatePanel.vue'
import KeyMetricsPanel from './analytics/KeyMetricsPanel.vue'
import DailySummaryPanel from './analytics/DailySummaryPanel.vue'

export default {
    name: 'AnalyticsModal',
    components: {
        AnalyticsHeader,
        ChartSection,
        ModalStatePanel,
        KeyMetricsPanel,
        DailySummaryPanel,
    },
    setup() {
        const store = useAppStore()

        // Refs / local state
        const combinedChartRef = ref(null)
        const currentDayIndex = ref(0)
        const isSimulating = ref(false)
        const weatherLayers = ref({
            temperature: true,
            cloudCover: true,
            humidity: true,
            windSpeed: true,
        })

        // Store-backed computed
        const isOpen = computed(() => store.analyticsModalOpen)
        const selectedObject = computed(() => store.selectedObject)
        const analysisData = computed(() => store.analysisData)
        const isLoading = computed(() => store.analysisLoading)
        const loadingMessage = computed(() => isSimulating.value ? 'Running simulation...' : 'Generating analysis...')

        // Analysis generation (hoisted so the date-range composable can receive it)
        async function generateAnalysis() {
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

        // Date/timeframe/mode orchestration
        const {
            centerDate,
            currentTimeframe,
            analysisMode,
            timeframes,
            timeframeDays,
            effectiveMaxDate,
            effectiveMinDate,
            dataMode,
            dataModeLabel,
            setTimeframe: setDateRangeTimeframe,
            onDateChange,
            setAnalysisMode,
            toggleAnalysisMode,
            initForOpen,
        } = useAnalyticsDateRange({
            selectedObject,
            analysisData,
            generateAnalysis,
        })

        // Wrap store side effect around timeframe changes
        const setTimeframe = async (tf) => {
            store.setAnalyticsTimeframe(tf)
            await setDateRangeTimeframe(tf)
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

        const onCanvasEl = (el) => {
            combinedChartRef.value = el
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

        // Open: default Historical + Day, NC calendar bounds, load series
        watch(isOpen, async (open) => {
            if (open) {
                initForOpen()
                store.setAnalyticsTimeframe('day')
                await generateAnalysis()
                currentDayIndex.value = Math.max(0, Math.floor(totalDays.value / 2))
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
            effectiveMinDate,
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
            onCanvasEl,
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

/* Analysis Content - Two Columns */
.analysis-content {
    display: flex;
    height: 100%;
    overflow: hidden;
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

    .overview-section {
        width: 100%;
        height: 50%;
    }
}
</style>
