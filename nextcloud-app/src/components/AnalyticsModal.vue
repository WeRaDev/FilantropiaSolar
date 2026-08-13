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
                        @weather-change="scheduleChartRender"
                        @add-historical="onAddHistorical"
                        @export="exportData"
                        @close="closeModal"
                    />

                    <!-- Modal Body: keep chart mounted so canvas survives mode switches -->
                    <div class="modal-body">
                        <ModalStatePanel
                            v-if="isLoading || !analysisData"
                            :state="isLoading ? 'loading' : 'no-data'"
                            :loading-message="loadingMessage"
                            :timeframe-days="timeframeDays"
                            :error-message="analysisError || ''"
                            @generate="generateAnalysis"
                        />

                        <div
                            v-show="analysisData && !isLoading"
                            class="analysis-content"
                        >
                            <ChartSection
                                :chart-title="chartTitle"
                                :current-timeframe="currentTimeframe"
                                :current-day-index="currentDayIndex"
                                :total-days="totalDays"
                                :current-day-label="currentDayLabel"
                                :date-range-label="dateRangeLabel"
                                :data-mode="dataMode"
                                :data-mode-label="dataModeLabel"
                                :can-prev-day="canPrevDay"
                                :can-next-day="canNextDay"
                                @prev-day="prevDay"
                                @next-day="nextDay"
                                @canvas-el="onCanvasEl"
                                @view-data="openViewData"
                            />

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

        <!-- Outside transition: single-root fade + always available overlay -->
        <ViewDataTable
            :open="viewDataOpen"
            :hourly-data="hourlyData"
            :station-name="selectedObject?.name || ''"
            :range-label="dateRangeLabel || currentDayLabel"
            :mode-label="dataModeLabel"
            :analysis-mode="analysisMode"
            @close="viewDataOpen = false"
        />
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
import ViewDataTable from './analytics/ViewDataTable.vue'

export default {
    name: 'AnalyticsModal',
    components: {
        AnalyticsHeader,
        ChartSection,
        ModalStatePanel,
        KeyMetricsPanel,
        DailySummaryPanel,
        ViewDataTable,
    },
    setup() {
        const store = useAppStore()

        // Refs / local state
        const combinedChartRef = ref(null)
        const currentDayIndex = ref(0)
        const isSimulating = ref(false)
        const viewDataOpen = ref(false)
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
        const analysisError = computed(() => store.analysisError || '')
        const loadingMessage = computed(() => isSimulating.value ? 'Running simulation...' : 'Generating analysis...')

        // Analysis generation (hoisted so the date-range composable can receive it)
        const scheduleChartRender = (delay = 0) => {
            setTimeout(async () => {
                await nextTick()
                const ok = renderCombinedChart()
                // Second pass after flex layout assigns canvas size
                requestAnimationFrame(() => renderCombinedChart())
                // If canvas was still 0x0, try again shortly
                if (ok === false) {
                    setTimeout(() => renderCombinedChart(), 120)
                }
            }, delay)
        }

        async function generateAnalysis() {
            if (!selectedObject.value) return
            const mode = analysisMode.value === 'predicted' ? 'simulated' : 'historical'
            isSimulating.value = mode !== 'historical'
            // Drop stale series immediately so Predicted never shows Historical totals
            store.analysisData = null
            try {
                await store.generateAnalysisWithMode(
                    selectedObject.value.id,
                    centerDate.value,
                    timeframeDays.value,
                    mode,
                )
                currentDayIndex.value = currentTimeframe.value === 'day'
                    ? 0
                    : Math.max(0, Math.floor((totalDays.value || 1) / 2))
                scheduleChartRender(0)
                scheduleChartRender(80)
                scheduleChartRender(250)
            } catch (e) {
                console.error('generateAnalysis failed', e)
            } finally {
                isSimulating.value = false
            }
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
            viewDataOpen.value = false
            store.closeAnalyticsModal()
        }

        const openViewData = () => {
            viewDataOpen.value = true
        }

        // Header "Add historical data" — open measured upload for the selected station
        const onAddHistorical = () => {
            try {
                if (typeof store.openUploadHistoricalModal === 'function') {
                    store.openUploadHistoricalModal()
                    return
                }
                if (typeof store.openEditStationModal === 'function') {
                    store.openEditStationModal()
                }
            } catch (e) {
                console.error('onAddHistorical failed', e)
            }
        }

        const onCanvasEl = (el) => {
            combinedChartRef.value = el
            if (el && analysisData.value) {
                scheduleChartRender(0)
                scheduleChartRender(100)
            }
        }

        const shiftYmd = (ymd, deltaDays) => {
            const [y, m, day] = ymd.split('-').map(Number)
            const d = new Date(y, m - 1, day)
            d.setDate(d.getDate() + deltaDays)
            const yy = d.getFullYear()
            const mm = String(d.getMonth() + 1).padStart(2, '0')
            const dd = String(d.getDate()).padStart(2, '0')
            return `${yy}-${mm}-${dd}`
        }

        const canPrevDay = computed(() => {
            if (currentTimeframe.value !== 'day') {
                return currentDayIndex.value > 0
            }
            const min = effectiveMinDate.value
            if (!min) return true
            return centerDate.value > min
        })

        const canNextDay = computed(() => {
            if (currentTimeframe.value !== 'day') {
                return currentDayIndex.value < totalDays.value - 1
            }
            const max = effectiveMaxDate.value
            if (!max) return true
            return centerDate.value < max
        })

        // Day timeframe: arrows change centerDate (calendar). Multi-day: index within window.
        const prevDay = async () => {
            if (currentTimeframe.value === 'day') {
                if (!canPrevDay.value) return
                centerDate.value = shiftYmd(centerDate.value, -1)
                await onDateChange()
                return
            }
            if (currentDayIndex.value > 0) {
                currentDayIndex.value--
                scheduleChartRender(0)
            }
        }

        const nextDay = async () => {
            if (currentTimeframe.value === 'day') {
                if (!canNextDay.value) return
                centerDate.value = shiftYmd(centerDate.value, 1)
                await onDateChange()
                return
            }
            if (currentDayIndex.value < totalDays.value - 1) {
                currentDayIndex.value++
                scheduleChartRender(0)
            }
        }

        // For 'day' timeframe clicking rows does nothing; otherwise switch to that day
        const goToDay = (idx) => {
            if (currentTimeframe.value === 'day') {
                return
            }
            currentDayIndex.value = idx
            currentTimeframe.value = 'day'
            scheduleChartRender(0)
        }

        // Keyboard handler for Escape
        const handleKeydown = (e) => {
            if (e.key === 'Escape' && isOpen.value) {
                closeModal()
            }
        }

        // Open: default Historical + Day, NC calendar bounds, load series
        watch(isOpen, async (open) => {
            if (!open) {
                viewDataOpen.value = false
                destroyChart()
                combinedChartRef.value = null
                return
            }
            try {
                initForOpen()
                store.setAnalyticsTimeframe('day')
                currentDayIndex.value = 0
                await generateAnalysis()
                currentDayIndex.value = 0
                scheduleChartRender(50)
            } catch (e) {
                console.error('Analytics open/generate failed', e)
            }
        })

        // Re-render chart when analysis data changes
        watch(analysisData, (data) => {
            if (data && isOpen.value) {
                currentDayIndex.value = currentTimeframe.value === 'day'
                    ? 0
                    : Math.max(0, Math.floor((totalDays.value || 1) / 2))
                scheduleChartRender(0)
                scheduleChartRender(120)
            }
        })

        // Loading overlay hides content via v-show — reflow canvas when it clears
        watch(isLoading, (loading) => {
            if (!loading && analysisData.value && isOpen.value) {
                scheduleChartRender(0)
                scheduleChartRender(100)
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
            analysisError,
            loadingMessage,
            isExporting,
            viewDataOpen,
            hourlyData,
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
            openViewData,
            onAddHistorical,
            setTimeframe,
            onDateChange,
            setAnalysisMode,
            toggleAnalysisMode,
            generateAnalysis,
            exportData,
            prevDay,
            nextDay,
            goToDay,
            canPrevDay,
            canNextDay,
            onCanvasEl,
            scheduleChartRender,
            renderCombinedChart,
        }
    },
}
</script>

<style scoped>
/* Modal Overlay */
.analytics-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: stretch;
    justify-content: center;
    z-index: 10000;
    padding: max(8px, min(24px, 2vh)) max(8px, min(24px, 2vw));
    box-sizing: border-box;
}

/* Modal Container — fills viewport; no fixed max-height that clips UI */
.analytics-modal {
    background: var(--color-main-background, #fff);
    border-radius: 12px;
    width: min(1400px, 100%);
    height: 100%;
    max-height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

/* Modal Body */
.modal-body {
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    position: relative;
}

/* Analysis Content - Two Columns */
.analysis-content {
    display: flex;
    height: 100%;
    min-height: 0;
    overflow: hidden;
}

/* Overview Section - Right */
.overview-section {
    width: min(380px, 36vw);
    flex: 0 0 auto;
    min-width: 260px;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 16px;
    gap: 16px;
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
@media (max-width: 1100px) {
    .analysis-content {
        flex-direction: column;
    }

    .overview-section {
        width: 100%;
        min-width: 0;
        max-height: 42%;
        border-top: 1px solid var(--color-border, #e0e0e0);
    }
}

@media (max-height: 700px) {
    .analytics-modal-overlay {
        padding: 4px;
    }
}
</style>
