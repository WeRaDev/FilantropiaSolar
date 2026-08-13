/**
 * Composable handling CSV export of the current analysis.
 * Supports destination: 'computer' | 'nextcloud'.
 */

import { ref } from 'vue'

/**
 * @param {object} deps - Reactive dependencies.
 * @param {object} deps.store - Pinia app store instance.
 * @param {import('vue').ComputedRef<object|null>} deps.selectedObject - Selected installation.
 * @param {import('vue').ComputedRef<object|null>} deps.analysisData - Analysis payload.
 * @param {import('vue').Ref<string>} deps.centerDate - Center date (YYYY-MM-DD).
 * @param {import('vue').ComputedRef<number>} deps.timeframeDays - Days in current timeframe.
 * @return {{ isExporting: import('vue').Ref<boolean>, exportData: Function }} Export state and action.
 */
export function useAnalyticsExport({
	store,
	selectedObject,
	analysisData,
	centerDate,
	timeframeDays,
}) {
	const isExporting = ref(false)

	/**
	 * @param {'computer'|'nextcloud'} [destination='computer']
	 */
	const exportData = async (destination = 'computer') => {
		if (!selectedObject.value || !analysisData.value) return
		isExporting.value = true
		try {
			await store.exportAnalysisReport(
				selectedObject.value,
				analysisData.value,
				centerDate.value,
				timeframeDays.value,
				destination,
			)
		} catch (e) {
			console.error('Export failed:', e)
		} finally {
			isExporting.value = false
		}
	}

	return { isExporting, exportData }
}
