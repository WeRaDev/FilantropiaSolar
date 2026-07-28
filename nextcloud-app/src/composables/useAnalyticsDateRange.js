/**
 * Composable owning date/timeframe/analysis-mode orchestration for AnalyticsModal.
 *
 * Extracted from AnalyticsModal.vue to keep the modal a thin orchestrator.
 * Analysis generation itself stays in the modal and is injected as a callback.
 */

import { ref, computed } from 'vue'

/**
 * @param {object} deps - Reactive dependencies.
 * @param {import('vue').ComputedRef<object|null>} deps.selectedObject - Selected installation.
 * @param {import('vue').ComputedRef<object|null>} deps.analysisData - Analysis payload from the store.
 * @param {Function} deps.generateAnalysis - Async callback that (re)generates analysis with current settings.
 * @return {object} Refs, computed refs, and handlers for date/mode orchestration.
 */
export function useAnalyticsDateRange({ selectedObject, analysisData, generateAnalysis }) {
    const centerDate = ref(new Date().toISOString().split('T')[0])
    const currentTimeframe = ref('week')
    const analysisMode = ref('predicted') // 'historical' or 'predicted'

    // Timeframe options
    const timeframes = [
        { label: 'Day', value: 'day', days: 1 },
        { label: 'Week', value: 'week', days: 7 },
        { label: 'Month', value: 'month', days: 30 },
        { label: 'Year', value: 'year', days: 365 },
    ]

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

    const setTimeframe = async (tf) => {
        currentTimeframe.value = tf
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

    return {
        centerDate,
        currentTimeframe,
        analysisMode,
        timeframes,
        timeframeDays,
        maxDate,
        effectiveMaxDate,
        dataMode,
        dataModeLabel,
        setTimeframe,
        onDateChange,
        setAnalysisMode,
        toggleAnalysisMode,
    }
}
