/**
 * Composable owning date/timeframe/analysis-mode orchestration for AnalyticsModal.
 *
 * Historical (default): Day timeframe, NC series calendar bounds, provenance badge.
 * Predicted: keep existing ML path; badge always SIMULATED.
 */

import { ref, computed } from 'vue'

/**
 * @param {object} deps
 * @param {import('vue').ComputedRef<object|null>} deps.selectedObject
 * @param {import('vue').ComputedRef<object|null>} deps.analysisData
 * @param {Function} deps.generateAnalysis
 */
export function useAnalyticsDateRange({ selectedObject, analysisData, generateAnalysis }) {
    const centerDate = ref(new Date().toISOString().split('T')[0])
    const currentTimeframe = ref('day')
    const analysisMode = ref('historical') // default Historical

    const timeframes = [
        { label: 'Day', value: 'day', days: 1 },
        { label: 'Week', value: 'week', days: 7 },
        { label: 'Month', value: 'month', days: 30 },
        { label: 'Year', value: 'year', days: 365 },
    ]

    const timeframeDays = computed(() => {
        const tf = timeframes.find(t => t.value === currentTimeframe.value)
        return tf?.days || 1
    })

    /** NC series bounds preferred; fall back to installation from/to dates. */
    const seriesMinDate = computed(() => {
        const o = selectedObject.value
        return (
            o?.customData?.seriesFromDate
            || o?.customData?.fromDate?.split?.('T')?.[0]
            || o?.from_date
            || null
        )
    })

    const seriesMaxDate = computed(() => {
        const o = selectedObject.value
        const today = new Date().toISOString().split('T')[0]
        const seriesTo = o?.customData?.seriesToDate || null
        const toDate = o?.customData?.toDate?.split?.('T')?.[0] || o?.to_date || null
        // Historical calendar cannot go past today or last NC sample
        const candidates = [today]
        if (seriesTo) candidates.push(seriesTo)
        if (toDate) candidates.push(toDate)
        return candidates.sort()[0] // earliest upper bound among today/series
            ? candidates.reduce((a, b) => (a < b ? a : b))
            : today
    })

    const maxDate = computed(() => seriesMaxDate.value)
    const minDate = computed(() => seriesMinDate.value)

    const effectiveMaxDate = computed(() => {
        if (analysisMode.value === 'predicted') {
            const futureDate = new Date()
            futureDate.setFullYear(futureDate.getFullYear() + 1)
            return futureDate.toISOString().split('T')[0]
        }
        return maxDate.value
    })

    const effectiveMinDate = computed(() => {
        if (analysisMode.value === 'predicted') {
            return null
        }
        return minDate.value
    })

    const dataMode = computed(() => {
        if (analysisMode.value === 'predicted') {
            return 'simulated'
        }
        const label = analysisData.value?.series_label || analysisData.value?.mode || 'historical'
        if (label === 'mixed') return 'mixed'
        if (label === 'simulated') return 'simulated'
        if (label === 'none') return 'none'
        return 'historical'
    })

    const dataModeLabel = computed(() => {
        if (analysisMode.value === 'predicted') {
            return 'SIMULATED'
        }
        // Prefer server-composed label (MIXED (n/m), HISTORICAL, SIMULATED)
        if (analysisData.value?.data_mode_label) {
            return String(analysisData.value.data_mode_label).toUpperCase()
        }
        const mix = analysisData.value?.provenance_mix
        if (mix && (mix.measured || mix.simulated)) {
            const m = Number(mix.measured || 0)
            const s = Number(mix.simulated || 0)
            if (m > 0 && s > 0) return `MIXED (${m} measured / ${s} simulated)`
            if (m > 0) return 'HISTORICAL'
            if (s > 0) return 'SIMULATED'
        }
        return 'HISTORICAL'
    })

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
            if (centerDate.value > to) {
                centerDate.value = to
            }
        }
        if (from) {
            const fromMs = new Date(from).getTime()
            const minCenter = new Date(fromMs + halfDays * 86400000).toISOString().split('T')[0]
            if (centerDate.value < minCenter) {
                centerDate.value = minCenter
            }
            if (centerDate.value < from) {
                centerDate.value = from
            }
        }
    }

    const initForOpen = () => {
        analysisMode.value = 'historical'
        currentTimeframe.value = 'day'
        const to = maxDate.value || new Date().toISOString().split('T')[0]
        centerDate.value = to
        clampCenterDate()
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
                currentTimeframe.value = currentTimeframe.value || 'day'
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
        minDate,
        effectiveMaxDate,
        effectiveMinDate,
        dataMode,
        dataModeLabel,
        setTimeframe,
        onDateChange,
        setAnalysisMode,
        toggleAnalysisMode,
        initForOpen,
        clampCenterDate,
    }
}
