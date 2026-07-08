import { defineStore } from 'pinia'
import axios from '@nextcloud/axios'
import { generateUrl } from '@nextcloud/router'

const API_BASE = '/apps/filantropia_solar/api/v1/admin'

export const useAdminStore = defineStore('admin', {
    state: () => ({
        loading: false,
        actionLoading: false,
        stations: [],
        cacheStatus: null,
        modelInfo: null,
        modelDetails: {},
        settings: {
            ml_service_url: '',
        },
        message: '',
        error: '',
    }),
    getters: {
        datasetCount: (state) => state.stations.length,
    },
    actions: {
        clearFeedback() {
            this.message = ''
            this.error = ''
        },

        async bootstrap() {
            const response = await axios.get(generateUrl(`${API_BASE}/bootstrap`))
            this.settings = {
                ...this.settings,
                ...(response.data?.settings || {}),
            }
            return response.data
        },

        async loadAll() {
            this.loading = true
            this.clearFeedback()
            try {
                await this.bootstrap()
                await Promise.all([
                    this.fetchStations(),
                    this.fetchModelInfo(),
                    this.fetchCacheStatus(),
                ])
            } finally {
                this.loading = false
            }
        },

        async fetchStations() {
            const response = await axios.get(generateUrl(`${API_BASE}/stations`))
            this.stations = response.data?.stations || []
            return this.stations
        },

        async saveStation(payload) {
            this.actionLoading = true
            this.clearFeedback()
            try {
                const hasId = Boolean(payload.id)
                const endpoint = hasId
                    ? generateUrl(`${API_BASE}/stations/${payload.id}`)
                    : generateUrl(`${API_BASE}/stations`)
                const request = hasId
                    ? axios.put(endpoint, payload)
                    : axios.post(endpoint, payload)

                const response = await request
                this.message = response.data?.message || (hasId ? 'Station updated' : 'Station created')
                await this.fetchStations()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Failed to save station'
                throw error
            } finally {
                this.actionLoading = false
            }
        },

        async deleteStation(stationId) {
            this.actionLoading = true
            this.clearFeedback()
            try {
                const response = await axios.delete(generateUrl(`${API_BASE}/stations/${stationId}`))
                this.message = response.data?.message || 'Station deleted'
                await this.fetchStations()
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Failed to delete station'
                throw error
            } finally {
                this.actionLoading = false
            }
        },

        async reimportDataset() {
            this.actionLoading = true
            this.clearFeedback()
            try {
                const response = await axios.post(generateUrl(`${API_BASE}/dataset/reimport`))
                const result = response.data?.result || {}
                this.message = `Dataset import complete: ${result.created || 0} created, ${result.updated || 0} updated`
                await this.fetchStations()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Failed to re-import dataset'
                throw error
            } finally {
                this.actionLoading = false
            }
        },

        async fetchCacheStatus() {
            const response = await axios.get(generateUrl(`${API_BASE}/ml/cache`))
            this.cacheStatus = response.data || null
            return this.cacheStatus
        },

        async clearCache() {
            this.actionLoading = true
            this.clearFeedback()
            try {
                const response = await axios.post(generateUrl(`${API_BASE}/ml/cache/clear`))
                this.message = response.data?.message || 'ML cache cleared'
                await this.fetchCacheStatus()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Failed to clear cache'
                throw error
            } finally {
                this.actionLoading = false
            }
        },

        async fetchModelInfo() {
            const response = await axios.get(generateUrl(`${API_BASE}/ml/model-info`))
            this.modelInfo = response.data || null
            return this.modelInfo
        },

        async fetchModelDetails(modelId) {
            const response = await axios.get(generateUrl(`${API_BASE}/ml/model/${encodeURIComponent(modelId)}`))
            this.modelDetails[modelId] = response.data || null
            return this.modelDetails[modelId]
        },

        async trainAll() {
            this.actionLoading = true
            this.clearFeedback()
            try {
                const response = await axios.post(generateUrl(`${API_BASE}/ml/train`))
                this.message = 'Training request for all dataset stations submitted'
                await this.fetchModelInfo()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Failed to start training'
                throw error
            } finally {
                this.actionLoading = false
            }
        },

        async trainStation(stationId) {
            this.actionLoading = true
            this.clearFeedback()
            try {
                const response = await axios.post(generateUrl(`${API_BASE}/ml/train/${encodeURIComponent(stationId)}`))
                this.message = `Training request for ${stationId} submitted`
                await this.fetchModelInfo()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Failed to train station model'
                throw error
            } finally {
                this.actionLoading = false
            }
        },

        async saveSettings() {
            this.actionLoading = true
            this.clearFeedback()
            try {
                const response = await axios.post(generateUrl(`${API_BASE}/settings`), this.settings)
                this.settings = {
                    ...this.settings,
                    ...(response.data?.settings || {}),
                }
                this.message = response.data?.message || 'Settings saved'
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Failed to save settings'
                throw error
            } finally {
                this.actionLoading = false
            }
        },
    },
})
