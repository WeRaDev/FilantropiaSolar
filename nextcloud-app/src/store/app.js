/**
 * Main App Store (Pinia)
 * Following layout.specs.md Section 4: Data Flow & State Management
 */

import { defineStore } from 'pinia'
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

export const useAppStore = defineStore('app', {
    state: () => ({
        // Objects data (installations)
        objects: [],
        hiddenObjectIds: JSON.parse(localStorage.getItem('fs_hidden_installations') || '[]'),
        
        // UI State
        selectedObjectId: null,
        timeRange: {
            start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 30 days ago
            end: new Date().toISOString().split('T')[0],
            label: 'Month'
        },
        filters: {
            status: [], // ['active', 'warning', 'offline'] - empty means all
            lifecycle: [], // ['virtual','planned','running'] - empty means all
            searchTerm: ''
        },

        // Analytics data
        analysisData: null,
        analysisLoading: false,

        // Analytics Modal state
        analyticsModalOpen: false,
        analyticsTimeframe: '21day',

        // Create Virtual Modal state
        createVirtualModalOpen: false,

        // Edit station modal
        editStationModalOpen: false,

        // Lifecycle chooser modal
        lifecycleModalOpen: false,

        // Loading states
        isLoadingObjects: false,
        isLoadingAnalytics: false,
        error: null,

        // Map state
        mapCenter: [39.5, -8.0], // Portugal center
        mapZoom: 7
    }),

    getters: {
        // Get selected object
        selectedObject: (state) => {
            if (!state.selectedObjectId) return null
            return state.objects.find(o => o.id === state.selectedObjectId) || null
        },

        // Filter objects based on status, search, and hidden list
        filteredObjects: (state) => {
            let result = [...state.objects]

            // Exclude hidden installations
            if (state.hiddenObjectIds.length > 0) {
                result = result.filter(o => !state.hiddenObjectIds.includes(o.id))
            }

            // Filter by status
            if (state.filters.status.length > 0) {
                result = result.filter(o => state.filters.status.includes(o.status || 'active'))
            }

            // Filter by lifecycle chips (supports virtual/planned/running/online/offline)
            if (state.filters.lifecycle && state.filters.lifecycle.length > 0) {
                result = result.filter(o => {
                    const lc = o.lifecycle_state || o.customData?.lifecycleState || 'running'
                    const st = o.status || 'active'
                    return state.filters.lifecycle.some((f) => {
                        if (f === 'online') return lc === 'running' && st === 'active' && !o.soft_removed
                        if (f === 'offline') return lc === 'running' && st !== 'active' && !o.soft_removed
                        return lc === f
                    })
                })
            }

            // Filter by search term
            if (state.filters.searchTerm) {
                const term = state.filters.searchTerm.toLowerCase()
                result = result.filter(o =>
                    (o.name || '').toLowerCase().includes(term) ||
                    (o.id || '').toLowerCase().includes(term) ||
                    (o.location || '').toLowerCase().includes(term)
                )
            }

            return result
        },

        // KPI calculations
        totalObjects: (state) => state.objects.length,
        
        activeObjectsCount: (state) => 
            state.objects.filter(o => (o.status || 'active') === 'active').length,
        
        warningObjectsCount: (state) => 
            state.objects.filter(o => o.status === 'warning').length,
        
        offlineObjectsCount: (state) => 
            state.objects.filter(o => o.status === 'offline').length,

        totalCapacity: (state) => 
            state.objects.reduce((sum, o) => sum + parseFloat(o.capacity_kwp || 0), 0),

        virtualCount: (state) =>
            state.objects.filter(o => (o.lifecycle_state || o.customData?.lifecycleState) === 'virtual' && !o.soft_removed).length,
        plannedCount: (state) =>
            state.objects.filter(o => (o.lifecycle_state || o.customData?.lifecycleState) === 'planned' && !o.soft_removed).length,
        runningCount: (state) =>
            state.objects.filter(o => (o.lifecycle_state || o.customData?.lifecycleState || 'running') === 'running' && !o.soft_removed).length,
        // Active (measured): Running with NC measured samples. Live "Online" feed is future (M4).
        onlineCount: (state) =>
            state.objects.filter(o => {
                const lc = o.lifecycle_state || o.customData?.lifecycleState || 'running'
                return !o.soft_removed && lc === 'running' && (o.has_measured_data || o.status === 'active')
            }).length,
        offlineRunningCount: (state) =>
            state.objects.filter(o => {
                const lc = o.lifecycle_state || o.customData?.lifecycleState || 'running'
                return !o.soft_removed && lc === 'running' && !(o.has_measured_data || o.status === 'active')
            }).length,
        totalEnergyKwh: (state) =>
            state.objects.reduce((sum, o) => sum + Number(o.total_production_kwh || 0), 0),
        totalSavingsEur: (state) =>
            state.objects.reduce((sum, o) => sum + Number(o.total_savings_eur || 0), 0),

        // Group objects by location for map clustering
        objectsByLocation: (state) => {
            const grouped = {}
            state.objects.forEach(obj => {
                const loc = obj.location || obj.nearest_location || 'Unknown'
                if (!grouped[loc]) grouped[loc] = []
                grouped[loc].push(obj)
            })
            return grouped
        }
    },

    actions: {
        // Fetch all objects from API
        async fetchObjects() {
            this.isLoadingObjects = true
            this.error = null

            try {
                const response = await axios.get(
                    generateUrl('/apps/filantropia_solar/api/v1/installations')
                )
                const installations = response.data.installations || response.data.data || []
                
                // Map to layout spec object model
                this.objects = installations.map(inst => {
                    const lifecycle = inst.lifecycle_state
                        || (inst.is_virtual ? 'virtual' : 'running')
                    const softRemoved = Boolean(inst.soft_removed)
                    return {
                        id: inst.id,
                        installation_id: inst.installation_id || inst.id,
                        name: inst.name || `${inst.location} PV Plant`,
                        // Use API-provided status (calculated from to_date)
                        status: inst.status || this.calculateClientStatus(inst),
                        location: inst.location || inst.nearest_location,
                        metrics: {
                            powerOutput: inst.capacity_kwp || 0,
                            efficiency: Number(inst.efficiency != null ? inst.efficiency : 0)
                        },
                        customData: {
                            serialNumber: inst.serial_number,
                            fromDate: inst.from_date || inst.series_from_date || null,
                            toDate: inst.to_date || inst.series_to_date || null,
                            installedAt: inst.installed_at || null,
                            installationDate: inst.installation_date || null,
                            seriesFromDate: inst.series_from_date || null,
                            seriesToDate: inst.series_to_date || null,
                            isVirtual: inst.is_virtual || lifecycle === 'virtual',
                            source: inst.source || 'user',
                            dbId: inst.db_id || null,
                            lifecycleState: lifecycle,
                            softRemoved,
                            publicCategory: inst.public_category
                                || (softRemoved || lifecycle === 'virtual'
                                    ? 'none'
                                    : (lifecycle === 'planned' ? 'planned' : 'existing')),
                            isPublic: Boolean(inst.is_public),
                            odooLeadId: inst.odoo_lead_id ?? null,
                            installedAt: inst.installed_at || null,
                            website: inst.website || '',
                            shortDescription: inst.short_description || '',
                            gridPriceKwh: inst.grid_price_kwh != null ? Number(inst.grid_price_kwh) : 0.15,
                        },
                        lifecycle_state: lifecycle,
                        soft_removed: softRemoved,
                        public_category: inst.public_category || null,
                        website: inst.website || '',
                        short_description: inst.short_description || '',
                        grid_price_kwh: inst.grid_price_kwh != null ? Number(inst.grid_price_kwh) : 0.15,
                        total_production_kwh: Number(inst.total_production_kwh || 0),
                        total_savings_eur: Number(inst.total_savings_eur || 0),
                        readings_count: Number(inst.readings_count || 0),
                        has_series_data: Boolean(inst.has_series_data),
                        has_measured_data: Boolean(inst.has_measured_data),
                        series_source: inst.series_source || 'none',
                        efficiency: Number(inst.efficiency != null ? inst.efficiency : 0),
                        // Use actual API coordinates if available, otherwise fallback to location lookup
                        coordinates: (inst.latitude && inst.longitude)
                            ? { lat: parseFloat(inst.latitude), lng: parseFloat(inst.longitude) }
                            : this.getLocationCoordinates(inst.location || inst.nearest_location),
                        capacity_kwp: inst.capacity_kwp,
                        latitude: inst.latitude,
                        longitude: inst.longitude,
                        lastUpdate: new Date().toISOString()
                    }
                })
            } catch (error) {
                this.error = error.message || 'Failed to load installations'
            } finally {
                this.isLoadingObjects = false
            }
        },

        // Calculate status client-side (fallback if API doesn't provide it)
        calculateClientStatus(inst) {
            const today = new Date().toISOString().split('T')[0]
            
            // Check error flag
            if (inst.error_flag) return 'warning'
            
            // No data = warning
            if (!inst.to_date) return 'warning'
            
            // Extract date part
            const toDate = inst.to_date.split('T')[0]
            
            // Compare with today
            if (toDate === today) return 'active'
            
            return 'offline'
        },

        // Get coordinates for known locations
        getLocationCoordinates(location) {
            const coords = {
                'Lisbon': { lat: 38.7223, lng: -9.1393 },
                'Setubal': { lat: 38.5244, lng: -8.8882 },
                'Faro': { lat: 37.0194, lng: -7.9304 },
                'Braga': { lat: 41.5454, lng: -8.4265 },
                'Tavira': { lat: 37.1279, lng: -7.6486 },
                'Loule': { lat: 37.1376, lng: -8.0197 }
            }
            return coords[location] || { lat: 38.7, lng: -9.1 }
        },

        // Select object (FR2.5)
        selectObject(objectId) {
            this.selectedObjectId = objectId
            
            // Center map on selected object
            const obj = this.objects.find(o => o.id === objectId)
            if (obj && obj.coordinates) {
                this.mapCenter = [obj.coordinates.lat, obj.coordinates.lng]
                this.mapZoom = 12
            }
        },

        // Clear selection
        clearSelection() {
            this.selectedObjectId = null
        },

        // Set status filter (FR2.3)
        setStatusFilter(statuses) {
            this.filters.status = statuses
            
            // Clear selection if selected object doesn't match filter (FR2.8)
            if (this.selectedObjectId && statuses.length > 0) {
                const selected = this.objects.find(o => o.id === this.selectedObjectId)
                if (selected && !statuses.includes(selected.status || 'active')) {
                    this.selectedObjectId = null
                }
            }
        },

        // Set search term (FR2.2)
        setSearchTerm(term) {
            this.filters.searchTerm = term
        },

        // Clear all filters (FR2.4)
        clearFilters() {
            this.filters.status = []
            this.filters.lifecycle = []
            this.filters.searchTerm = ''
        },

        setLifecycleFilter(states) {
            this.filters.lifecycle = states || []
        },


        // Set time range (FR1.3)
        setTimeRange(start, end, label = 'Custom') {
            this.timeRange = { start, end, label }
        },

        // Generate analysis for selected object
        async generateAnalysis(objectId, days = 21) {
            this.analysisLoading = true
            
            try {
                const obj = this.objects.find(o => o.id === objectId)
                const centerDate = obj?.customData?.toDate?.split('T')[0] || 
                    new Date().toISOString().split('T')[0]
                
                const response = await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/predict/period'),
                    {
                        mode: 'historical',
                        installation_id: objectId,
                        center_date: centerDate,
                        days: days
                    }
                )

                if (response.data.success) {
                    this.analysisData = response.data
                }
                return response.data
            } catch (error) {
                throw error
            } finally {
                this.analysisLoading = false
            }
        },

        // Generate analysis with specific center date (for date picker)
        async generateAnalysisWithDate(objectId, centerDate, days = 21) {
            this.analysisLoading = true
            
            try {
                const response = await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/predict/period'),
                    {
                        mode: 'historical',
                        installation_id: objectId,
                        center_date: centerDate,
                        days: days
                    }
                )

            if (response.data.success) {
                    this.analysisData = response.data
                }
                return response.data
            } catch (error) {
                throw error
            } finally {
                this.analysisLoading = false
            }
        },

        // Generate analysis with specific center date and mode (for Historical/Predicted toggle)
        async generateAnalysisWithMode(objectId, centerDate, days = 21, mode = 'historical') {
            this.analysisLoading = true
            // Clear previous mode payload so UI never mixes Historical metrics into Predicted
            this.analysisData = null

            try {
                const obj = this.objects.find(o => o.id === objectId)
                
                // Prefer NC db id for ops stations (including virtual_* list ids).
                const installationKey = obj?.customData?.dbId
                    || (String(objectId).startsWith('virtual_') ? String(objectId).slice('virtual_'.length) : objectId)
                const hasNcDb = !!obj?.customData?.dbId || /^\d+$/.test(String(installationKey))
                // Historical with NC rows must use mode=historical (NC SoT).
                // Only force ML 'custom' for predicted/sim when station is virtual AND has no db id.
                const isVirtual = obj?.customData?.isVirtual || String(objectId).startsWith('virtual_')
                let effectiveMode = mode
                if (mode === 'historical' && hasNcDb) {
                    effectiveMode = 'historical'
                } else if (isVirtual && mode !== 'historical') {
                    effectiveMode = 'custom'
                }
                
                const response = await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/predict/period'),
                    {
                        mode: effectiveMode,
                        installation_id: installationKey,
                        center_date: centerDate,
                        days: days,
                        // Include location/capacity/coords for ML custom/simulated path
                        location: obj?.location,
                        capacity_kwp: obj?.capacity_kwp,
                        latitude: obj?.latitude ?? obj?.coordinates?.lat,
                        longitude: obj?.longitude ?? obj?.coordinates?.lng,
                    }
                )

                if (response.data.success) {
                    const data = { ...response.data, mode: mode }
                    // Normalize hour on every hourly point for chart labels (0:00 bug)
                    if (Array.isArray(data.hourly_data)) {
                        data.hourly_data = data.hourly_data.map((h) => {
                            let hour = h.hour
                            if (hour === undefined || hour === null || hour === '') {
                                const ts = h.timestamp || ''
                                const m = ts.match(/T(\d{1,2})/) || ts.match(/\s(\d{2}):/)
                                hour = m ? parseInt(m[1], 10) : 0
                            }
                            return { ...h, hour: Number(hour) }
                        })
                    }
                    // Predicted badge always SIMULATED
                    if (mode === 'simulated' || mode === 'custom' || mode === 'predicted') {
                        data.series_label = data.series_label || 'SIMULATED'
                        data.data_mode_label = data.data_mode_label || 'SIMULATED'
                    }
                    this.analysisData = data
                }
                return response.data
            } catch (error) {
                throw error
            } finally {
                this.analysisLoading = false
            }
        },

        // Update map view
        setMapView(center, zoom) {
            this.mapCenter = center
            this.mapZoom = zoom
        },

        // Analytics Modal actions
        openAnalyticsModal(objectId = null) {
            if (objectId) {
                this.selectObject(objectId)
            }
            this.analyticsModalOpen = true
        },

        closeAnalyticsModal() {
            this.analyticsModalOpen = false
        },

        setAnalyticsTimeframe(tf) {
            this.analyticsTimeframe = tf
        },

        // Virtual Installation Modal actions
        openCreateVirtualModal() {
            this.createVirtualModalOpen = true
        },

        closeCreateVirtualModal() {
            this.createVirtualModalOpen = false
        },

        openEditStationModal() {
            this.editStationModalOpen = true
        },
        closeEditStationModal() {
            this.editStationModalOpen = false
        },
        openLifecycleModal() {
            this.lifecycleModalOpen = true
        },
        closeLifecycleModal() {
            this.lifecycleModalOpen = false
        },


        stationApiKey(objOrId) {
            if (objOrId && typeof objOrId === 'object') {
                const obj = objOrId
                if (obj.customData?.dbId) {
                    return String(obj.customData.dbId)
                }
                if (obj.installation_id) {
                    return String(obj.installation_id)
                }
                return String(obj.id || '')
            }
            const id = String(objOrId || '')
            const obj = this.objects.find(o => o.id === id || o.installation_id === id)
            if (obj?.customData?.dbId) {
                return String(obj.customData.dbId)
            }
            if (obj?.installation_id) {
                return String(obj.installation_id)
            }
            // virtual_123 -> 123
            if (id.startsWith('virtual_')) {
                return id.slice('virtual_'.length)
            }
            return id
        },

        lifecycleKey(obj) {
            return this.stationApiKey(obj)
        },

        async promotePlanned(objectId) {
            const obj = this.objects.find(o => o.id === objectId)
            const key = this.stationApiKey(objectId)
            try {
                const response = await axios.post(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${encodeURIComponent(key)}/promote-planned`),
                    {},
                )
                if (!response.data?.success) {
                    throw new Error(response.data?.error || 'Promote failed')
                }
                await this.fetchObjects()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Promote failed'
                throw error
            }
        },

        async markInstalled(objectId) {
            const obj = this.objects.find(o => o.id === objectId)
            const key = this.stationApiKey(objectId)
            try {
                const response = await axios.post(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${encodeURIComponent(key)}/mark-installed`),
                    {},
                )
                if (!response.data?.success) {
                    throw new Error(response.data?.error || 'Mark installed failed')
                }
                await this.fetchObjects()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Mark installed failed'
                throw error
            }
        },

        async softRemoveStation(objectId) {
            const obj = this.objects.find(o => o.id === objectId)
            const key = this.stationApiKey(objectId)
            try {
                const response = await axios.post(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${encodeURIComponent(key)}/soft-remove`),
                    {},
                )
                if (!response.data?.success) {
                    throw new Error(response.data?.error || 'Soft-remove failed')
                }
                await this.fetchObjects()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Soft-remove failed'
                throw error
            }
        },

        async setLifecycle(objectId, lifecycleState) {
            const obj = this.objects.find(o => o.id === objectId)
            const key = this.stationApiKey(objectId)
            try {
                const response = await axios.post(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${encodeURIComponent(key)}/set-lifecycle`),
                    { lifecycle_state: lifecycleState },
                )
                if (!response.data?.success) {
                    throw new Error(response.data?.error || 'Lifecycle update failed')
                }
                await this.fetchObjects()
                // reselect same logical station if possible
                if (this.selectedObjectId) {
                    const still = this.objects.find(o => o.id === objectId || o.installation_id === key)
                    if (still) this.selectedObjectId = still.id
                }
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Lifecycle update failed'
                throw error
            }
        },

        async updateStation(objectId, fields) {
            const obj = this.objects.find(o => o.id === objectId)
            const key = this.stationApiKey(objectId)
            try {
                const response = await axios.put(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${encodeURIComponent(key)}`),
                    fields,
                )
                if (!response.data?.success) {
                    throw new Error(response.data?.error || 'Update failed')
                }
                await this.fetchObjects()
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Update failed'
                throw error
            }
        },

        async importHistoricalReadings(objectId, readings) {
            const key = this.stationApiKey(objectId)
            try {
                const response = await axios.post(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${encodeURIComponent(key)}/import`),
                    { readings },
                )
                return response.data
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Import failed'
                throw error
            }
        },

        // Create a new virtual installation
        async createVirtualInstallation(data) {
            const virtualObj = {
                id: `virtual_${Date.now()}`,
                name: data.name,
                status: 'warning', // Virtual installations start as warning
                location: data.location,
                metrics: {
                    powerOutput: data.capacityKwp,
                    efficiency: 0.85
                },
                customData: {
                    serialNumber: `VIRTUAL-${Date.now()}`,
                    isVirtual: true
                },
                coordinates: { lat: data.latitude, lng: data.longitude },
                capacity_kwp: data.capacityKwp,
                latitude: data.latitude,
                longitude: data.longitude,
                lastUpdate: new Date().toISOString()
            }
            
            try {
                // Try to persist to database
                const response = await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/installations'),
                    {
                        name: data.name,
                        location: data.location,
                        latitude: data.latitude,
                        longitude: data.longitude,
                        capacityKwp: data.capacityKwp,
                        gridPriceKwh: data.gridPriceKwh || 0.15,
                        isVirtual: true
                    }
                )

                if (response.data.success) {
                    // Use backend-assigned ID if available
                    const newInst = response.data.installation
                    virtualObj.id = `virtual_${newInst.id || Date.now()}`
                }
            } catch (error) {
                // If backend fails, still add locally (virtual mode)
                this.objects.push(virtualObj)
                return { success: true, installation: virtualObj }
            }

            await this.fetchObjects()
            return { success: true }
        },

        // Simulate energy production for an installation using weather API
        async simulateForInstallation(objectId, days = 21) {
            this.analysisLoading = true
            
            try {
                const obj = this.objects.find(o => o.id === objectId)
                if (!obj) throw new Error('Installation not found')

                // Use today as center date for simulation
                const centerDate = new Date().toISOString().split('T')[0]
                
                const response = await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/predict/period'),
                    {
                        mode: 'simulated',
                        installation_id: objectId,
                        center_date: centerDate,
                        days: days,
                        location: obj.location,
                        capacity_kwp: obj.capacity_kwp
                    }
                )

                if (response.data.success) {
                    this.analysisData = {
                        ...response.data,
                        mode: 'simulated'
                    }
                }
                return response.data
            } catch (error) {
                throw error
            } finally {
                this.analysisLoading = false
            }
        },

        // Export installation data to Nextcloud Files
        async exportInstallationData(objectId) {
            try {
                const response = await axios.post(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${objectId}/export`)
                )
                
                if (response.data.success) {
                    // Open Nextcloud Files to the export folder
                    const filesUrl = generateUrl('/apps/files/?dir=/' + encodeURIComponent(response.data.path))
                    window.open(filesUrl, '_blank')
                    return response.data
                } else {
                    const errorMsg = response.data.error || 'Export failed'
                    alert('Export failed: ' + errorMsg)
                    throw new Error(errorMsg)
                }
            } catch (error) {
                if (error.response) {
                    alert('Export failed: ' + (error.response.data?.error || error.message))
                } else {
                    alert('Export failed: ' + error.message)
                }
                throw error
            }
        },

        // Hard-delete station from Nextcloud DB (ops fleet/user/crm). Not a map hide.
        async deleteInstallation(objectId) {
            const obj = this.objects.find(o => o.id === objectId)
            if (!obj) return

            const key = this.stationApiKey(objectId)
            try {
                const response = await axios.delete(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${encodeURIComponent(key)}`),
                )
                if (response.data && response.data.success === false) {
                    throw new Error(response.data.error || 'Delete failed')
                }
            } catch (error) {
                this.error = error.response?.data?.error || error.message || 'Delete failed'
                throw error
            }

            // Drop from client state immediately, then refresh for truth
            this.objects = this.objects.filter(o => o.id !== objectId)
            if (this.selectedObjectId === objectId) {
                this.selectedObjectId = null
            }
            // Clear legacy localStorage hide entry if present
            if (this.hiddenObjectIds.includes(objectId)) {
                this.hiddenObjectIds = this.hiddenObjectIds.filter(id => id !== objectId)
                localStorage.setItem('fs_hidden_installations', JSON.stringify(this.hiddenObjectIds))
            }
            await this.fetchObjects()
        },

        // Add a dataset installation to the user's dashboard (bookmark)
        async addDatasetInstallation(obj) {
            try {
                await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/installations'),
                    {
                        name: obj.name,
                        location: obj.location,
                        latitude: obj.latitude || obj.coordinates?.lat,
                        longitude: obj.longitude || obj.coordinates?.lng,
                        capacityKwp: obj.capacity_kwp,
                        serialNumber: obj.customData?.serialNumber || null,
                        isVirtual: false
                    }
                )
            } catch (error) {
                // Best-effort persistence
            }
        },

        // Restore dashboard: unhide all hidden installations and re-fetch
        async restoreDashboard() {
            this.hiddenObjectIds = []
            localStorage.removeItem('fs_hidden_installations')
            // Re-fetch all installations
            await this.fetchObjects()
        },

        // Export analysis report as CSV for the selected timeframe
        async exportAnalysisReport(installation, analysisData, centerDate, days) {
            try {
                // Build CSV content from analysis data
                const hourlyData = analysisData.hourly_data || []
                const dailyData = analysisData.daily_data || []
                const stats = analysisData.period_statistics || {}
                
                // Header with metadata
                let csv = `# FilantropiaSolar Analysis Report\n`
                csv += `# Installation: ${installation.name}\n`
                csv += `# Location: ${installation.location}\n`
                csv += `# Capacity: ${installation.capacity_kwp} kWp\n`
                csv += `# Center Date: ${centerDate}\n`
                csv += `# Analysis Period: ${days} days\n`
                csv += `# Generated: ${new Date().toISOString()}\n`
                csv += `#\n`
                csv += `# PERIOD STATISTICS\n`
                csv += `# Total Energy: ${(stats.total_energy_kwh || 0).toFixed(2)} kWh\n`
                csv += `# Avg Daily: ${(stats.avg_daily_kwh || 0).toFixed(2)} kWh/day\n`
                csv += `#\n\n`
                
                // Daily summary section
                csv += `DAILY SUMMARY\n`
                csv += `Date,Energy_kWh,Peak_kWh,Avg_Temp_C,Avg_Cloud_Pct\n`
                
                if (dailyData.length > 0) {
                    dailyData.forEach(d => {
                        csv += `${d.date || ''},${(d.total_production_kwh || 0).toFixed(2)},`
                        csv += `${(d.peak_production_kwh || 0).toFixed(2)},`
                        csv += `${(d.avg_temperature || 0).toFixed(1)},`
                        csv += `${(d.avg_cloud_cover || 0).toFixed(0)}\n`
                    })
                } else {
                    // Calculate from hourly data
                    const byDate = {}
                    hourlyData.forEach(h => {
                        const date = (h.timestamp || '').split('T')[0]
                        if (!byDate[date]) {
                            byDate[date] = { energy: 0, peak: 0, temps: [], clouds: [] }
                        }
                        byDate[date].energy += h.production_kwh || 0
                        byDate[date].peak = Math.max(byDate[date].peak, h.production_kwh || 0)
                        byDate[date].temps.push(h.temperature || 0)
                        byDate[date].clouds.push(h.cloud_cover || 0)
                    })
                    
                    Object.entries(byDate).sort().forEach(([date, data]) => {
                        const avgTemp = data.temps.reduce((a, b) => a + b, 0) / data.temps.length
                        const avgCloud = data.clouds.reduce((a, b) => a + b, 0) / data.clouds.length
                        csv += `${date},${data.energy.toFixed(2)},${data.peak.toFixed(2)},`
                        csv += `${avgTemp.toFixed(1)},${avgCloud.toFixed(0)}\n`
                    })
                }
                
                csv += `\nHOURLY DATA\n`
                csv += `Timestamp,Hour,Energy_kWh,Temperature_C,Cloud_Cover_Pct,Humidity_Pct\n`
                
                hourlyData.forEach(h => {
                    csv += `${h.timestamp || ''},${h.hour || ''},`
                    csv += `${(h.production_kwh || 0).toFixed(3)},`
                    csv += `${(h.temperature || 0).toFixed(1)},`
                    csv += `${(h.cloud_cover || 0).toFixed(0)},`
                    csv += `${(h.humidity || 0).toFixed(0)}\n`
                })
                
                // Create download
                const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
                const url = URL.createObjectURL(blob)
                const link = document.createElement('a')
                link.href = url
                const filename = `${installation.name.replace(/[^a-zA-Z0-9]/g, '_')}_${centerDate}_${days}day_report.csv`
                link.download = filename
                document.body.appendChild(link)
                link.click()
                document.body.removeChild(link)
                URL.revokeObjectURL(url)
                
                return { success: true, filename }
                
            } catch (error) {
                alert('Export failed: ' + error.message)
                throw error
            }
        }
    }
})
