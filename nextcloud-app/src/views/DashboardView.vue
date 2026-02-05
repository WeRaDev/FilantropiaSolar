<template>
    <div class="dashboard-view">
        <!-- Metrics Cards -->
        <section class="metrics-section">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-icon">
                        <span class="icon-text">PV</span>
                    </div>
                    <div class="metric-content">
                        <span class="metric-value">{{ formatCapacity(overview.total_capacity_kwp) }}</span>
                        <span class="metric-label">Network Capacity</span>
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-icon online">
                        <span class="icon-text">ON</span>
                    </div>
                    <div class="metric-content">
                        <span class="metric-value">
                            {{ overview.online_count }} / {{ overview.total_count }}
                        </span>
                        <span class="metric-label">Systems Online</span>
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-icon energy">
                        <span class="icon-text">kW</span>
                    </div>
                    <div class="metric-content">
                        <span class="metric-value">{{ formatEnergy(overview.monthly_generation_kwh) }}</span>
                        <span class="metric-label">Monthly Generation</span>
                    </div>
                </div>

                <div class="metric-card highlight">
                    <div class="metric-icon savings">
                        <span class="icon-text">EUR</span>
                    </div>
                    <div class="metric-content">
                        <span class="metric-value golden">{{ formatCurrency(overview.total_savings_eur) }}</span>
                        <span class="metric-label">Total Savings</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- Map Overview -->
        <section class="map-section">
            <h2>Installation Network</h2>
            <div ref="dashboardMap" class="dashboard-map"></div>
        </section>

        <!-- Quick Stats -->
        <section class="quick-stats">
            <h2>Performance Summary</h2>
            <div class="stats-table">
                <div class="stats-row header">
                    <span>Location</span>
                    <span>Installations</span>
                    <span>Capacity</span>
                    <span>Avg. Performance</span>
                </div>
                <div
                    v-for="location in locationStats"
                    :key="location.name"
                    class="stats-row"
                >
                    <span class="location-name">{{ location.name }}</span>
                    <span>{{ location.count }}</span>
                    <span>{{ location.capacity_kwp }} kWp</span>
                    <span class="performance" :class="performanceClass(location.performance)">
                        {{ formatPercent(location.performance) }}
                    </span>
                </div>
            </div>
        </section>

        <!-- Recent Activity -->
        <section class="activity-section">
            <h2>Recent Activity</h2>
            <div class="activity-list">
                <div
                    v-for="activity in recentActivity"
                    :key="activity.id"
                    class="activity-item"
                >
                    <span class="activity-icon" :class="activity.type"></span>
                    <div class="activity-content">
                        <span class="activity-text">{{ activity.message }}</span>
                        <span class="activity-time">{{ formatTime(activity.timestamp) }}</span>
                    </div>
                </div>
                <div v-if="recentActivity.length === 0" class="empty-activity">
                    No recent activity
                </div>
            </div>
        </section>
    </div>
</template>

<script>
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default {
    name: 'DashboardView',
    data() {
        return {
            overview: {
                total_capacity_kwp: 0,
                online_count: 0,
                total_count: 0,
                monthly_generation_kwh: 0,
                total_savings_eur: 0,
            },
            locationStats: [],
            recentActivity: [],
            map: null,
        }
    },
    mounted() {
        this.fetchDashboardData()
        this.initMap()
    },
    beforeUnmount() {
        if (this.map) {
            this.map.remove()
        }
    },
    methods: {
        async fetchDashboardData() {
            try {
                // Fetch from PHP API (which proxies to ML service)
                const url = generateUrl('/apps/filantropia_solar/api/v1/dashboard')
                const response = await axios.get(url)
                const data = response.data

                this.overview = {
                    total_capacity_kwp: data.total_capacity_kwp || 0,
                    online_count: data.total_installations || 0,
                    total_count: data.total_installations || 0,
                    monthly_generation_kwh: (data.total_production_kwh || 0) / 48,
                    total_savings_eur: data.total_savings_eur || 0,
                }
                this.locationStats = data.locations || []
                this.recentActivity = []

                this.updateMapMarkers()
            } catch (error) {
                console.error('Failed to fetch dashboard data:', error)
            }
        },

        initMap() {
            this.map = L.map(this.$refs.dashboardMap, {
                zoomControl: false,
            }).setView([39.5, -8.0], 6)

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OSM',
                maxZoom: 18,
            }).addTo(this.map)
        },

        updateMapMarkers() {
            // Add cluster markers for each location
            this.locationStats.forEach(location => {
                if (location.lat && location.lon) {
                    const size = Math.min(60, 20 + location.count * 5)
                    const icon = L.divIcon({
                        html: `
                            <div class="cluster-marker" style="width:${size}px;height:${size}px;">
                                <span>${location.count}</span>
                            </div>
                        `,
                        className: 'cluster-icon',
                        iconSize: [size, size],
                    })

                    L.marker([location.lat, location.lon], { icon })
                        .addTo(this.map)
                        .bindPopup(`
                            <strong>${location.name}</strong><br/>
                            ${location.count} installations<br/>
                            ${location.capacity_kwp} kWp total
                        `)
                }
            })
        },

        formatCapacity(value) {
            if (value === null || value === undefined) return '-- kWp'
            if (value >= 1000) return `${(value / 1000).toFixed(1)} MWp`
            return `${parseFloat(value).toFixed(1)} kWp`
        },

        formatEnergy(value) {
            if (value === null || value === undefined) return '-- kWh'
            if (value >= 1000) return `${(value / 1000).toFixed(1)} MWh`
            return `${parseFloat(value).toFixed(0)} kWh`
        },

        formatCurrency(value) {
            if (value === null || value === undefined) return '-- EUR'
            if (value >= 1000) return `${(value / 1000).toFixed(1)}k EUR`
            return `${parseFloat(value).toFixed(0)} EUR`
        },

        formatPercent(value) {
            if (value === null || value === undefined) return '--%'
            return `${(parseFloat(value) * 100).toFixed(0)}%`
        },

        formatTime(timestamp) {
            if (!timestamp) return ''
            const date = new Date(timestamp)
            const now = new Date()
            const diff = now - date

            if (diff < 3600000) return 'Just now'
            if (diff < 86400000) return 'Today'
            return date.toLocaleDateString()
        },

        performanceClass(value) {
            if (!value) return ''
            if (value >= 0.9) return 'excellent'
            if (value >= 0.7) return 'good'
            if (value >= 0.5) return 'fair'
            return 'poor'
        },
    },
}
</script>

<style lang="scss" scoped>
@import '../style/_golden-brand.scss';

.dashboard-view {
    width: 100%;
    height: 100%;
    max-width: 100%;
    padding: 16px;
    box-sizing: border-box;
    overflow-y: auto;
}

.metrics-section {
    margin-bottom: 24px;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;

    @media (max-width: 1000px) {
        grid-template-columns: repeat(2, 1fr);
    }
}

.metric-card {
    @include golden-card;
    display: flex;
    align-items: center;
    gap: 16px;

    &.highlight {
        background: linear-gradient(135deg, rgba($golden-primary, 0.15), rgba($golden-secondary, 0.05));
        border-color: $golden-primary;
    }
}

.metric-icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba($golden-primary, 0.1);
    color: $golden-olive;

    .icon-text {
        font-weight: 700;
        font-size: 0.85rem;
    }

    &.online {
        background: rgba(76, 175, 80, 0.1);
        color: #4CAF50;
    }

    &.energy {
        background: rgba($warm-orange, 0.1);
        color: $warm-orange;
    }

    &.savings {
        background: rgba($golden-primary, 0.2);
        color: $golden-primary;
    }
}

.metric-content {
    flex: 1;
}

.metric-value {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: $charcoal;

    &.golden {
        color: $golden-primary;
    }
}

.metric-label {
    font-size: 0.85rem;
    color: #888;
}

.map-section {
    @include golden-card;
    margin-bottom: 24px;

    h2 {
        @include golden-heading;
        font-size: 1.1rem;
        margin: 0 0 16px;
    }
}

.dashboard-map {
    height: 300px;
    border-radius: 8px;
    overflow: hidden;
}

.quick-stats {
    @include golden-card;
    margin-bottom: 24px;

    h2 {
        @include golden-heading;
        font-size: 1.1rem;
        margin: 0 0 16px;
    }
}

.stats-table {
    display: table;
    width: 100%;
}

.stats-row {
    display: table-row;

    &.header {
        font-weight: 600;
        color: #888;
        font-size: 0.85rem;

        span {
            padding-bottom: 8px;
            border-bottom: 1px solid $golden-border;
        }
    }

    span {
        display: table-cell;
        padding: 12px 8px;
        border-bottom: 1px solid rgba($golden-border, 0.5);
    }
}

.location-name {
    font-weight: 500;
}

.performance {
    font-weight: 600;

    &.excellent {
        color: #4CAF50;
    }

    &.good {
        color: $golden-primary;
    }

    &.fair {
        color: $warm-orange;
    }

    &.poor {
        color: #F44336;
    }
}

.activity-section {
    @include golden-card;

    h2 {
        @include golden-heading;
        font-size: 1.1rem;
        margin: 0 0 16px;
    }
}

.activity-list {
    max-height: 300px;
    overflow-y: auto;
}

.activity-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 0;
    border-bottom: 1px solid rgba($golden-border, 0.5);

    &:last-child {
        border-bottom: none;
    }
}

.activity-icon {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-top: 6px;
    background: #ccc;

    &.production {
        background: $golden-primary;
    }

    &.alert {
        background: $warm-orange;
    }

    &.system {
        background: #6B9BC3;
    }
}

.activity-content {
    flex: 1;
}

.activity-text {
    display: block;
    color: $charcoal;
}

.activity-time {
    font-size: 0.75rem;
    color: #888;
}

.empty-activity {
    text-align: center;
    padding: 24px;
    color: #888;
}

// Cluster marker styles
:global(.cluster-icon) {
    background: none !important;
    border: none !important;
}

:global(.cluster-marker) {
    background: $golden-primary;
    border: 3px solid white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);

    span {
        color: white;
        font-weight: 700;
        font-size: 14px;
    }
}
</style>
