<template>
    <div class="map-panel">
        <div ref="mapContainer" class="map-container"></div>
        
        <!-- Map Controls Overlay -->
        <div class="map-controls">
            <button class="map-btn" @click="zoomIn" title="Zoom in">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 5v14M5 12h14"/>
                </svg>
            </button>
            <button class="map-btn" @click="zoomOut" title="Zoom out">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 12h14"/>
                </svg>
            </button>
            <button class="map-btn" @click="resetView" title="Reset view">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <circle cx="12" cy="12" r="1"/>
                </svg>
            </button>
        </div>

        <!-- Legend -->
        <div class="map-legend">
            <div class="legend-item">
                <span class="legend-dot active"></span>
                <span>Active</span>
            </div>
            <div class="legend-item">
                <span class="legend-dot warning"></span>
                <span>Warning</span>
            </div>
            <div class="legend-item">
                <span class="legend-dot offline"></span>
                <span>Offline</span>
            </div>
        </div>

        <!-- Enhanced info card (shows full details like popup used to) -->
        <div v-if="selectedObject" class="info-card">
            <div class="info-header">
                <span class="info-status" :class="selectedObject.status || 'active'"></span>
                <h3>{{ selectedObject.name || selectedObject.id }}</h3>
                <button class="info-close" @click="clearSelection">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6 6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
            <div class="info-body">
                <div class="info-row">
                    <span class="info-label">Location</span>
                    <span class="info-value">{{ selectedObject.location }}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Capacity</span>
                    <span class="info-value">{{ selectedObject.capacity_kwp }} kWp</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Avg. Yearly Production</span>
                    <span class="info-value highlight">{{ formatNumber(estimatedYearlyProduction) }} kWh</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Efficiency</span>
                    <span class="info-value" :class="getEfficiencyClass(selectedObject.metrics?.efficiency || 0.85)">
                        {{ formatPercent(selectedObject.metrics?.efficiency || 0.85) }}
                    </span>
                </div>
                <div v-if="selectedObject.customData?.isVirtual" class="info-row">
                    <span class="info-label">Type</span>
                    <span class="info-value virtual-badge">Virtual</span>
                </div>
            </div>
            <div class="info-actions">
                <button class="info-action" @click="viewDetails">View Analysis</button>
                <button class="info-action-secondary" @click="hideInstallation" title="Remove from dashboard">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6 6 18M6 6l12 12"/>
                    </svg>
                    Hide
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useAppStore } from '../store/app.js'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default {
    name: 'MapPanel',
    setup() {
        const store = useAppStore()
        const mapContainer = ref(null)
        let map = null
        let markers = []

        // Computed
        const objects = computed(() => store.objects)
        const selectedObject = computed(() => store.selectedObject)
        const mapCenter = computed(() => store.mapCenter)
        const mapZoom = computed(() => store.mapZoom)
        
        // Estimated yearly production (capacity * 1500 kWh/kWp for Portugal)
        const estimatedYearlyProduction = computed(() => {
            if (!selectedObject.value) return 0
            return (selectedObject.value.capacity_kwp || 0) * 1500
        })

        // Status colors per spec
        const statusColors = {
            active: '#22A559',
            warning: '#F5A623',
            offline: '#CC2020'
        }

        // Create custom marker icon
        const createMarkerIcon = (status, isSelected = false) => {
            const color = statusColors[status] || statusColors.active
            const size = isSelected ? 34 : 28 // 28px base per spec
            const borderWidth = isSelected ? 4 : 2
            
            return L.divIcon({
                className: 'custom-marker',
                html: `
                    <div style="
                        width: ${size}px;
                        height: ${size}px;
                        background: ${color};
                        border: ${borderWidth}px solid ${isSelected ? '#fff' : 'rgba(255,255,255,0.8)'};
                        border-radius: 50%;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                        transform: translate(-50%, -50%);
                        cursor: pointer;
                        ${isSelected ? 'animation: pulse 1.5s ease-in-out infinite;' : ''}
                    "></div>
                `,
                iconSize: [size, size],
                iconAnchor: [size / 2, size / 2]
            })
        }

        // Initialize map
        const initMap = () => {
            if (!mapContainer.value || map) return

            map = L.map(mapContainer.value, {
                zoomControl: false, // Use custom controls
                attributionControl: true
            }).setView(mapCenter.value, mapZoom.value)

            // Add tile layer (OpenStreetMap)
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 18
            }).addTo(map)

            // Add markers for objects
            updateMarkers()
        }

        // Update markers on map
        const updateMarkers = () => {
            if (!map) return

            // Clear existing markers
            markers.forEach(m => map.removeLayer(m))
            markers = []

            // Add markers for each object
            objects.value.forEach(obj => {
                if (!obj.coordinates) return

                const isSelected = obj.id === store.selectedObjectId
                const marker = L.marker(
                    [obj.coordinates.lat, obj.coordinates.lng],
                    { icon: createMarkerIcon(obj.status || 'active', isSelected) }
                )

                // Click handler - select installation (v3.0.5: uses info card instead of popup)
                marker.on('click', () => {
                    store.selectObject(obj.id)
                })

                // Tooltip
                marker.bindTooltip(`
                    <strong>${obj.name || obj.id}</strong><br/>
                    ${obj.capacity_kwp} kWp - ${obj.location}
                `, { 
                    direction: 'top', 
                    offset: [0, -16] 
                })

                marker.addTo(map)
                markers.push(marker)
            })
        }

        // Map controls
        const zoomIn = () => {
            if (map) map.zoomIn()
        }

        const zoomOut = () => {
            if (map) map.zoomOut()
        }

        const resetView = () => {
            if (map) {
                map.setView([39.5, -8.0], 7)
                store.setMapView([39.5, -8.0], 7)
            }
        }

        // Clear selection
        const clearSelection = () => {
            store.clearSelection()
        }

        // View details - opens analytics modal
        const viewDetails = () => {
            if (store.selectedObjectId) {
                store.openAnalyticsModal(store.selectedObjectId)
            }
        }

        // Hide installation from dashboard
        const hideInstallation = async () => {
            const obj = store.selectedObject
            if (!obj) return
            const msg = obj.customData?.isVirtual
                ? `Delete "${obj.name}" permanently?`
                : `Hide "${obj.name}" from your dashboard? You can restore it later.`
            if (confirm(msg)) {
                try {
                    await store.deleteInstallation(obj.id)
                } catch (e) {
                    alert(e.message || 'Failed to remove')
                }
            }
        }
        
        // Format helpers for info card
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

        // Watch for object changes
        watch(objects, () => {
            updateMarkers()
        }, { deep: true })

        // Watch for selection changes
        watch(() => store.selectedObjectId, () => {
            updateMarkers()
            
            // Pan to selected object
            const obj = store.selectedObject
            if (obj && obj.coordinates && map) {
                map.panTo([obj.coordinates.lat, obj.coordinates.lng], { animate: true })
            }
        })

        // Watch for map view changes
        watch([mapCenter, mapZoom], ([newCenter, newZoom]) => {
            if (map) {
                map.setView(newCenter, newZoom, { animate: true })
            }
        })

        onMounted(() => {
            // Delay init to ensure container is rendered
            setTimeout(initMap, 100)
        })

        onUnmounted(() => {
            if (map) {
                map.remove()
                map = null
            }
        })

        return {
            mapContainer,
            selectedObject,
            estimatedYearlyProduction,
            zoomIn,
            zoomOut,
            resetView,
            clearSelection,
            viewDetails,
            hideInstallation,
            formatNumber,
            formatPercent,
            getEfficiencyClass
        }
    }
}
</script>

<style scoped>
/* Map Panel - 65-70% width per spec */
.map-panel {
    position: relative;
    flex: 1;
    height: 100%;
    min-height: 400px;
}

.map-container {
    width: 100%;
    height: 100%;
    background: #f0f0f0;
}

/* Custom marker styles */
:deep(.custom-marker) {
    background: transparent !important;
    border: none !important;
}

/* Pulse animation for selected marker */
@keyframes pulse {
    0%, 100% { transform: translate(-50%, -50%) scale(1); }
    50% { transform: translate(-50%, -50%) scale(1.1); }
}

/* Map Controls */
.map-controls {
    position: absolute;
    top: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    z-index: 1000;
}

.map-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #e0e0e0);
    border-radius: 6px;
    cursor: pointer;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    transition: all 0.2s ease;
}

.map-btn:hover {
    background: var(--color-background-hover, #f5f5f5);
}

/* Legend */
.map-legend {
    position: absolute;
    bottom: 16px;
    left: 16px;
    display: flex;
    gap: 16px;
    padding: 8px 16px;
    background: var(--color-main-background, #fff);
    border-radius: 6px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
    z-index: 1000;
    font-size: 12px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
}

.legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.legend-dot.active { background: #22A559; }
.legend-dot.warning { background: #F5A623; }
.legend-dot.offline { background: #CC2020; }

/* Info Card for selected object */
.info-card {
    position: absolute;
    top: 16px;
    left: 16px;
    width: 280px;
    background: var(--color-main-background, #fff);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 1000;
    overflow: hidden;
}

.info-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: var(--color-background-dark, #f5f5f5);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.info-status {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

.info-status.active { background: #22A559; }
.info-status.warning { background: #F5A623; }
.info-status.offline { background: #CC2020; }

.info-header h3 {
    flex: 1;
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.info-close {
    padding: 4px;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-text-lighter, #767676);
    border-radius: 4px;
    transition: background 0.2s ease;
}

.info-close:hover {
    background: var(--color-border, #e0e0e0);
}

.info-body {
    padding: 12px 16px;
}

.info-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    font-size: 13px;
}

.info-row:not(:last-child) {
    border-bottom: 1px solid var(--color-border-dark, #ebebeb);
}

.info-label {
    color: var(--color-text-lighter, #767676);
}

.info-value {
    font-weight: 500;
}

.info-value.highlight {
    color: var(--color-primary, #0082c9);
}

.info-value.efficiency-high {
    color: #22A559;
}

.info-value.efficiency-medium {
    color: #F5A623;
}

.info-value.efficiency-low {
    color: #CC2020;
}

.virtual-badge {
    color: #9B59B6;
    font-style: italic;
}

.info-actions {
    display: flex;
}

.info-action {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 12px;
    background: var(--color-primary, #0082c9);
    color: #fff;
    border: none;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s ease;
}

.info-action:hover {
    background: #006ba7;
}

.info-action-secondary {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 12px 16px;
    background: var(--color-background-dark, #f5f5f5);
    color: #CC2020;
    border: none;
    border-left: 1px solid var(--color-border, #e0e0e0);
    font-size: 12px;
    cursor: pointer;
    transition: background 0.2s ease;
}

.info-action-secondary:hover {
    background: #fce8e8;
}
</style>
