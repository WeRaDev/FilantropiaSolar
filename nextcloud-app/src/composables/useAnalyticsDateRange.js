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
function localYmd(d = new Date()) {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
}

export function useAnalyticsDateRange({ selectedObject, analysisData, generateAnalysis }) {
    const centerDate = ref(localYmd())
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

    /** YYYY-MM-DD helper */
    const ymd = (v) => {
        if (!v) return null
        const s = String(v)
        return s.includes('T') ? s.split('T')[0] : s.slice(0, 10)
    }

    /**
     * Historical calendar min = installation date (dataset start) when set,
     * else series_from, else other ops start candidates.
     * Never allow dates before the station was installed.
     */
    const minDate = computed(() => {
        const o = selectedObject.value
        const cd = o?.customData || {}
        // Installation date is the dataset start when set.
        const install = ymd(cd.installationDate) || ymd(o?.installation_date)
        if (install) return install
        const seriesFrom = ymd(cd.seriesFromDate) || ymd(o?.series_from_date)
        if (seriesFrom) return seriesFrom
        const candidates = [
            ymd(cd.installedAt),
            ymd(o?.installed_at),
            ymd(cd.fromDate),
            ymd(o?.from_date),
        ].filter(Boolean)
        if (!candidates.length) return null
        return candidates.reduce((a, b) => (a < b ? a : b))
    })

    const maxDate = computed(() => {
        const o = selectedObject.value
        const cd = o?.customData || {}
        const today = localYmd()
        const seriesTo = ymd(cd.seriesToDate) || ymd(o?.series_to_date)
        if (seriesTo && seriesTo < today) return seriesTo
        return today
    })

    const effectiveMaxDate = computed(() => {
        if (analysisMode.value === 'predicted') {
            const futureDate = new Date()
            futureDate.setFullYear(futureDate.getFullYear() + 1)
            return localYmd(futureDate)
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
            const maxCenter = localYmd(new Date(toMs - halfDays * 86400000))
            if (centerDate.value > maxCenter) {
                centerDate.value = maxCenter
            }
            if (centerDate.value > to) {
                centerDate.value = to
            }
        }
        if (from) {
            const fromMs = new Date(from).getTime()
            const minCenter = localYmd(new Date(fromMs + halfDays * 86400000))
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
        const to = maxDate.value || localYmd()
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
