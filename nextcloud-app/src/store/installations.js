/**
 * Installations Store (Pinia)
 *
 * State management for PV installations.
 */

import { defineStore } from 'pinia'
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

export const useInstallationsStore = defineStore('installations', {
    state: () => ({
        installations: [],
        selectedId: null,
        loading: false,
        error: null,
    }),

    getters: {
        selectedInstallation: (state) => {
            return state.installations.find(i => i.id === state.selectedId) || null
        },

        totalCapacity: (state) => {
            return state.installations.reduce(
                (sum, i) => sum + parseFloat(i.capacity_kwp || 0),
                0
            )
        },

        installationsByLocation: (state) => {
            const grouped = {}
            state.installations.forEach(inst => {
                const loc = inst.nearest_location || 'Unknown'
                if (!grouped[loc]) {
                    grouped[loc] = []
                }
                grouped[loc].push(inst)
            })
            return grouped
        },

        onlineCount: (state) => {
            return state.installations.filter(i => i.status === 'online').length
        },
    },

    actions: {
        async fetchInstallations() {
            this.loading = true
            this.error = null

            try {
                const response = await axios.get(
                    generateUrl('/apps/filantropia_solar/api/v1/installations')
                )
                // Handle both 'installations' and 'data' keys for compatibility
                this.installations = response.data.installations || response.data.data || []
            } catch (error) {
                console.error('Failed to fetch installations:', error)
                this.error = error.message || 'Failed to load installations'
            } finally {
                this.loading = false
            }
        },

        async fetchInstallation(id) {
            try {
                const response = await axios.get(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${id}`)
                )
                // Handle both 'installation' and 'data' keys for compatibility
                const installation = response.data.installation || response.data.data

                // Update in list if exists
                const index = this.installations.findIndex(i => i.id === id)
                if (index >= 0) {
                    this.installations[index] = installation
                } else {
                    this.installations.push(installation)
                }

                return installation
            } catch (error) {
                console.error('Failed to fetch installation:', error)
                throw error
            }
        },

        async createInstallation(data) {
            try {
                const response = await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/installations'),
                    data
                )
                // Handle both 'installation' and 'data' keys for compatibility
                const installation = response.data.installation || response.data.data
                this.installations.push(installation)
                return installation
            } catch (error) {
                console.error('Failed to create installation:', error)
                throw error
            }
        },

        async updateInstallation(id, data) {
            try {
                const response = await axios.put(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${id}`),
                    data
                )
                // Handle both 'installation' and 'data' keys for compatibility
                const installation = response.data.installation || response.data.data

                const index = this.installations.findIndex(i => i.id === id)
                if (index >= 0) {
                    this.installations[index] = installation
                }

                return installation
            } catch (error) {
                console.error('Failed to update installation:', error)
                throw error
            }
        },

        async deleteInstallation(id) {
            try {
                await axios.delete(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${id}`)
                )
                this.installations = this.installations.filter(i => i.id !== id)

                if (this.selectedId === id) {
                    this.selectedId = null
                }
            } catch (error) {
                console.error('Failed to delete installation:', error)
                throw error
            }
        },

        selectInstallation(id) {
            this.selectedId = id
        },

        clearSelection() {
            this.selectedId = null
        },
    },
})
