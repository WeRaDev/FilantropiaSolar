<template>
    <div class="main-view">
        <div class="content-split">
            <!-- Map Panel (70%) -->
            <div class="map-panel">
                <div ref="mapContainer" class="map-container"></div>
            </div>

            <!-- Sidebar (30%) -->
            <aside class="sidebar">
                <div class="sidebar-header">
                    <h2>Installations</h2>
                    <button class="btn btn-primary" @click="showAddDialog = true">
                        + Add
                    </button>
                </div>

                <div class="search-bar">
                    <input
                        v-model="searchQuery"
                        type="text"
                        class="search-input"
                        placeholder="Search installations..."
                    />
                </div>

                <div class="installations-list">
                    <div
                        v-for="installation in filteredInstallations"
                        :key="installation.id"
                        class="installation-card"
                        :class="{ selected: selectedId === installation.id }"
                        @click="selectInstallation(installation)"
                        @dblclick="navigateToDetail(installation.id)"
                    >
                        <div class="card-header">
                            <span class="installation-name">{{ installation.name }}</span>
                            <span class="capacity-badge">{{ installation.capacity_kwp }} kWp</span>
                        </div>
                        <div class="card-body">
                            <div class="metric production">
                                <span class="label">Production</span>
                                <span class="value golden">{{ formatEnergy(installation.current_production) }}</span>
                            </div>
                            <div class="metric consumption">
                                <span class="label">Consumption</span>
                                <span class="value orange">{{ formatEnergy(installation.current_consumption) }}</span>
                            </div>
                        </div>
                        <div class="card-footer">
                            <span
                                class="status-indicator"
                                :class="installation.status || 'unknown'"
                            ></span>
                            <span class="location-text">{{ installation.location || 'Unknown' }}</span>
                        </div>
                    </div>

                    <div v-if="filteredInstallations.length === 0" class="empty-state">
                        <p>No installations found</p>
                    </div>
                </div>

                <div class="sidebar-footer">
                    <span class="total-capacity">
                        Total: {{ totalCapacity }} kWp
                    </span>
                </div>
            </aside>
        </div>

        <!-- Add Installation Dialog -->
        <div v-if="showAddDialog" class="dialog-overlay" @click.self="showAddDialog = false">
            <div class="dialog">
                <div class="dialog-header">
                    <h3>Add Installation</h3>
                    <button class="close-btn" @click="showAddDialog = false">X</button>
                </div>
                <form @submit.prevent="createInstallation">
                    <div class="form-group">
                        <label>Name</label>
                        <input v-model="newInstallation.name" type="text" required />
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Latitude</label>
                            <input v-model.number="newInstallation.latitude" type="number" step="0.0001" required />
                        </div>
                        <div class="form-group">
                            <label>Longitude</label>
                            <input v-model.number="newInstallation.longitude" type="number" step="0.0001" required />
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Capacity (kWp)</label>
                        <input v-model.number="newInstallation.capacity_kwp" type="number" step="0.01" required />
                    </div>
                    <div class="form-group">
                        <label>Grid Price (EUR/kWh)</label>
                        <input v-model.number="newInstallation.grid_price_kwh" type="number" step="0.01" />
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" @click="showAddDialog = false">Cancel</button>
                        <button type="submit" class="btn btn-primary" :disabled="saving">Create</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</template>

<script>
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Golden solar panel marker SVG
const goldenMarkerSvg = `
<svg width="32" height="40" viewBox="0 0 32 40" xmlns="http://www.w3.org/2000/svg">
  <path d="M16 0C7.2 0 0 7.2 0 16c0 12 16 24 16 24s16-12 16-24C32 7.2 24.8 0 16 0z" fill="#C4B552"/>
  <circle cx="16" cy="14" r="8" fill="#FDFBF5"/>
  <rect x="10" y="10" width="12" height="8" rx="1" fill="#A89D3F"/>
  <line x1="13" y1="10" x2="13" y2="18" stroke="#FDFBF5" stroke-width="0.5"/>
  <line x1="16" y1="10" x2="16" y2="18" stroke="#FDFBF5" stroke-width="0.5"/>
  <line x1="19" y1="10" x2="19" y2="18" stroke="#FDFBF5" stroke-width="0.5"/>
  <line x1="10" y1="14" x2="22" y2="14" stroke="#FDFBF5" stroke-width="0.5"/>
</svg>
`

const goldenIcon = L.divIcon({
    html: goldenMarkerSvg,
    className: 'golden-marker',
    iconSize: [32, 40],
    iconAnchor: [16, 40],
    popupAnchor: [0, -40],
})

export default {
    name: 'MainView',
    data() {
        return {
            installations: [],
            selectedId: null,
            searchQuery: '',
            showAddDialog: false,
            saving: false,
            map: null,
            markers: {},
            newInstallation: {
                name: '',
                latitude: 38.7223, // Default to Lisbon
                longitude: -9.1393,
                capacity_kwp: 5.0,
                grid_price_kwh: 0.15,
            },
        }
    },
    computed: {
        filteredInstallations() {
            if (!this.searchQuery) {
                return this.installations
            }
            const query = this.searchQuery.toLowerCase()
            return this.installations.filter(
                (i) => i.name.toLowerCase().includes(query)
            )
        },
        totalCapacity() {
            return this.installations
                .reduce((sum, i) => sum + parseFloat(i.capacity_kwp || 0), 0)
                .toFixed(1)
        },
    },
    mounted() {
        this.initMap()
        this.fetchInstallations()
    },
    beforeUnmount() {
        if (this.map) {
            this.map.remove()
        }
    },
    methods: {
        initMap() {
            // Center on Portugal
            this.map = L.map(this.$refs.mapContainer).setView([39.5, -8.0], 7)

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 18,
            }).addTo(this.map)
        },

        async fetchInstallations() {
            try {
                // Fetch from PHP API (which proxies to ML service)
                const url = generateUrl('/apps/filantropia_solar/api/v1/installations')
                const response = await axios.get(url)
                this.installations = response.data.installations || []
                this.updateMarkers()
            } catch (error) {
                console.error('Failed to fetch installations:', error)
                this.installations = []
            }
        },

        updateMarkers() {
            // Clear existing markers
            Object.values(this.markers).forEach((marker) => {
                this.map.removeLayer(marker)
            })
            this.markers = {}

            // Add new markers
            this.installations.forEach((installation) => {
                const lat = parseFloat(installation.latitude)
                const lon = parseFloat(installation.longitude)

                if (!isNaN(lat) && !isNaN(lon)) {
                    const marker = L.marker([lat, lon], { icon: goldenIcon })
                        .addTo(this.map)
                        .bindPopup(`
                            <strong>${installation.name}</strong><br/>
                            ${installation.capacity_kwp} kWp
                        `)

                    marker.on('click', () => {
                        this.selectInstallation(installation)
                    })

                    this.markers[installation.id] = marker
                }
            })

            // Fit bounds if we have installations
            if (Object.keys(this.markers).length > 0) {
                const group = L.featureGroup(Object.values(this.markers))
                this.map.fitBounds(group.getBounds().pad(0.1))
            }
        },

        selectInstallation(installation) {
            this.selectedId = installation.id

            // Pan to marker
            const marker = this.markers[installation.id]
            if (marker) {
                this.map.setView(marker.getLatLng(), 10)
                marker.openPopup()
            }
        },

        navigateToDetail(id) {
            this.$router.push({ name: 'detail', params: { id } })
        },

        async createInstallation() {
            this.saving = true
            try {
                const response = await axios.post(
                    generateUrl('/apps/filantropia_solar/api/v1/installations'),
                    this.newInstallation
                )
                this.installations.push(response.data.installation)
                this.updateMarkers()
                this.showAddDialog = false
                this.resetNewInstallation()
            } catch (error) {
                console.error('Failed to create installation:', error)
            } finally {
                this.saving = false
            }
        },

        resetNewInstallation() {
            this.newInstallation = {
                name: '',
                latitude: 38.7223,
                longitude: -9.1393,
                capacity_kwp: 5.0,
                grid_price_kwh: 0.15,
            }
        },

        formatEnergy(value) {
            if (value === null || value === undefined) {
                return '-- kWh'
            }
            return `${parseFloat(value).toFixed(1)} kWh`
        },
    },
}
</script>

<style lang="scss" scoped>
@import '../style/_golden-brand.scss';

.main-view {
    height: 100%;
}

.content-split {
    display: flex;
    height: 100%;
    gap: 0;
}

.map-panel {
    flex: 1;
    min-width: 0;
    position: relative;
}

.map-container {
    width: 100%;
    height: 100%;
    border-radius: 0;
    overflow: hidden;
}

.sidebar {
    flex: 0 0 320px;
    max-width: 400px;
    display: flex;
    flex-direction: column;
    background: white;
    border-left: 1px solid $golden-border;
    overflow: hidden;
}

.sidebar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid $golden-border;

    h2 {
        @include golden-heading;
        font-size: 1.1rem;
        margin: 0;
    }
}

.search-bar {
    padding: 12px 16px;
    border-bottom: 1px solid $golden-border;
}

.installations-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

.installation-card {
    @include golden-card;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba($golden-olive, 0.15);
    }

    &.selected {
        border-color: $golden-primary;
        background: rgba($golden-primary, 0.05);
    }
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.installation-name {
    font-weight: 600;
    color: $charcoal;
}

.capacity-badge {
    @include golden-badge;
}

.card-body {
    display: flex;
    gap: 16px;
    margin-bottom: 8px;
}

.metric {
    flex: 1;

    .label {
        display: block;
        font-size: 0.75rem;
        color: #888;
        margin-bottom: 2px;
    }

    .value {
        font-weight: 600;
        font-size: 0.9rem;

        &.golden {
            color: $golden-primary;
        }

        &.orange {
            color: $warm-orange;
        }
    }
}

.card-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.75rem;
    color: #888;
}

.status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ccc;

    &.online {
        background: #4CAF50;
    }

    &.offline {
        background: #F44336;
    }

    &.warning {
        background: $warm-orange;
    }
}

.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: #888;
}

.sidebar-footer {
    padding: 12px 16px;
    border-top: 1px solid $golden-border;
    background: rgba($golden-primary, 0.05);

    .total-capacity {
        font-weight: 600;
        color: $golden-olive;
    }
}

// Form styles
.form-group {
    margin-bottom: 16px;

    label {
        display: block;
        font-weight: 500;
        margin-bottom: 4px;
    }
}

.form-row {
    display: flex;
    gap: 16px;

    .form-group {
        flex: 1;
    }
}

.form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 24px;
}

// Global marker style
:global(.golden-marker) {
    background: none !important;
    border: none !important;
}
</style>
