<template>
    <div v-if="isVisible" class="installation-popup-overlay" @click.self="close">
        <div class="installation-popup">
            <div class="popup-header">
                <span class="popup-status" :class="installation?.status || 'active'"></span>
                <h3>{{ installation?.name || installation?.id }}</h3>
                <button class="popup-close" @click="close">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6 6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>

            <div class="popup-body">
                <!-- Loading State -->
                <div v-if="loading" class="popup-loading">
                    <div class="spinner"></div>
                    <span>Loading statistics...</span>
                </div>

                <!-- Stats Display -->
                <template v-else>
                    <div class="stat-row">
                        <span class="stat-label">Location</span>
                        <span class="stat-value">{{ installation?.location || 'Unknown' }}</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Capacity</span>
                        <span class="stat-value">{{ installation?.capacity_kwp || 0 }} kWp</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Avg. Yearly Production</span>
                        <span class="stat-value highlight">{{ formatNumber(stats.avgYearlyProduction) }} kWh</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Efficiency</span>
                        <span class="stat-value" :class="getEfficiencyClass(stats.efficiency)">
                            {{ formatPercent(stats.efficiency) }}
                        </span>
                    </div>
                    <div v-if="stats.totalDays > 0" class="stat-note">
                        Based on {{ stats.totalDays }} days of historical data
                    </div>
                </template>
            </div>

            <div class="popup-footer">
                <button class="btn-secondary" @click="close">Close</button>
                <button class="btn-primary" @click="openAnalysis">View Analysis</button>
            </div>
        </div>
    </div>
</template>

<script>
import { ref, computed, watch } from 'vue'
import { useAppStore } from '../store/app.js'
import axios from '@nextcloud/axios'
import { generateUrl } from '@nextcloud/router'

export default {
    name: 'InstallationPopup',
    setup() {
        const store = useAppStore()
        const loading = ref(false)
        const stats = ref({
            avgYearlyProduction: 0,
            efficiency: 0,
            totalDays: 0
        })

        // Computed from store
        const isVisible = computed(() => store.installationPopupOpen)
        const installation = computed(() => {
            const id = store.installationPopupId
            return store.objects.find(o => o.id === id)
        })

        // Fetch statistics when popup opens
        watch(isVisible, async (visible) => {
            if (visible && installation.value) {
                await fetchStats()
            }
        })

        const fetchStats = async () => {
            loading.value = true
            try {
                const response = await axios.get(
                    generateUrl(`/apps/filantropia_solar/api/v1/installations/${store.installationPopupId}/stats`)
                )
                if (response.data.success) {
                    stats.value = {
                        avgYearlyProduction: response.data.avg_yearly_production_kwh || 0,
                        efficiency: response.data.efficiency_kwh_kwp || 0,
                        totalDays: response.data.total_days || 0
                    }
                } else {
                    // Fallback: calculate from local data if available
                    calculateLocalStats()
                }
            } catch (error) {
                console.error('Failed to fetch installation stats:', error)
                // Fallback to local calculation
                calculateLocalStats()
            } finally {
                loading.value = false
            }
        }

        const calculateLocalStats = () => {
            const inst = installation.value
            if (inst) {
                // Simple fallback estimate: capacity * 4 hours/day * 365 * 0.8 efficiency
                const estimated = (inst.capacity_kwp || 0) * 4 * 365 * 0.8
                stats.value = {
                    avgYearlyProduction: estimated,
                    efficiency: inst.metrics?.efficiency || 0.85,
                    totalDays: 0
                }
            }
        }

        const formatNumber = (num) => {
            if (num === null || num === undefined) return '0'
            return num.toLocaleString('en-US', { maximumFractionDigits: 1 })
        }

        const formatPercent = (num) => {
            if (num === null || num === undefined) return '0%'
            return (num * 100).toFixed(1) + '%'
        }

        const getEfficiencyClass = (efficiency) => {
            if (efficiency >= 0.9) return 'efficiency-high'
            if (efficiency >= 0.7) return 'efficiency-medium'
            return 'efficiency-low'
        }

        const close = () => {
            store.closeInstallationPopup()
        }

        const openAnalysis = () => {
            const id = store.installationPopupId
            store.closeInstallationPopup()
            store.openAnalyticsModal(id)
        }

        return {
            isVisible,
            installation,
            loading,
            stats,
            formatNumber,
            formatPercent,
            getEfficiencyClass,
            close,
            openAnalysis
        }
    }
}
</script>

<style scoped>
.installation-popup-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
}

.installation-popup {
    width: 360px;
    max-width: 90vw;
    background: var(--color-main-background, #fff);
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    overflow: hidden;
}

.popup-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px;
    background: var(--color-background-dark, #f5f5f5);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.popup-status {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}

.popup-status.active { background: #22A559; }
.popup-status.warning { background: #F5A623; }
.popup-status.offline { background: #CC2020; }

.popup-header h3 {
    flex: 1;
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.popup-close {
    padding: 6px;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-text-lighter, #767676);
    border-radius: 6px;
    transition: all 0.2s ease;
}

.popup-close:hover {
    background: var(--color-border, #e0e0e0);
}

.popup-body {
    padding: 20px;
}

.popup-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 0;
    color: var(--color-text-lighter, #767676);
    gap: 12px;
}

.spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--color-border, #e0e0e0);
    border-top-color: var(--color-primary, #0082c9);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid var(--color-border-dark, #ebebeb);
}

.stat-row:last-of-type {
    border-bottom: none;
}

.stat-label {
    font-size: 13px;
    color: var(--color-text-lighter, #767676);
}

.stat-value {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-main-text, #1a1a1a);
}

.stat-value.highlight {
    color: var(--color-primary, #0082c9);
}

.stat-value.efficiency-high {
    color: #22A559;
}

.stat-value.efficiency-medium {
    color: #F5A623;
}

.stat-value.efficiency-low {
    color: #CC2020;
}

.stat-note {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--color-border, #e0e0e0);
    font-size: 11px;
    color: var(--color-text-lighter, #767676);
    text-align: center;
    font-style: italic;
}

.popup-footer {
    display: flex;
    gap: 12px;
    padding: 16px 20px;
    background: var(--color-background-dark, #f5f5f5);
    border-top: 1px solid var(--color-border, #e0e0e0);
}

.popup-footer button {
    flex: 1;
    padding: 10px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-secondary {
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #e0e0e0);
    color: var(--color-main-text, #1a1a1a);
}

.btn-secondary:hover {
    background: var(--color-background-hover, #f5f5f5);
}

.btn-primary {
    background: var(--color-primary, #0082c9);
    border: 1px solid var(--color-primary, #0082c9);
    color: #fff;
}

.btn-primary:hover {
    background: var(--color-primary-hover, #0070b0);
}
</style>
