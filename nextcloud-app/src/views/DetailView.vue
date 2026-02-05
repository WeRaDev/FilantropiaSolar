<template>
    <div class="detail-view">
        <header class="detail-header">
            <div class="header-left">
                <button class="btn" @click="$router.push({ name: 'main' })">
                    &larr; Back
                </button>
                <div class="title-section">
                    <h1>{{ installation?.name || 'Loading...' }}</h1>
                <span class="location-badge">{{ installation?.location || '' }}</span>
                </div>
            </div>
            <div class="header-right">
                <span class="capacity-display">{{ installation?.capacity_kwp || 0 }} kWp</span>
            </div>
        </header>

        <div class="detail-content" v-if="installation">
            <!-- Energy Chart -->
            <section class="chart-section">
                <h2>24-Hour Energy Profile</h2>
                <div class="chart-wrapper">
                    <canvas ref="energyChart"></canvas>
                </div>
            </section>

            <!-- Statistics Grid -->
            <section class="stats-section">
                <div class="stats-grid">
                    <div class="stat-card">
                        <span class="stat-label">Today</span>
                        <span class="stat-value golden">{{ formatEnergy(stats.today_kwh) }}</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">This Month</span>
                        <span class="stat-value golden">{{ formatEnergy(stats.month_kwh) }}</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">This Year</span>
                        <span class="stat-value golden">{{ formatEnergy(stats.year_kwh) }}</span>
                    </div>
                    <div class="stat-card highlight">
                        <span class="stat-label">Total Savings</span>
                        <span class="stat-value">{{ formatCurrency(stats.total_savings_eur) }}</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Performance Ratio</span>
                        <span class="stat-value">{{ formatPercent(stats.performance_ratio) }}</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Grid Price</span>
                        <span class="stat-value">{{ installation.grid_price_kwh || 0.15 }} EUR/kWh</span>
                    </div>
                </div>
            </section>

            <!-- Weather Correlation -->
            <section class="weather-section" v-if="weatherData">
                <h2>Weather Conditions</h2>
                <div class="weather-grid">
                    <div class="weather-card">
                        <span class="weather-value">{{ weatherData.temperature }}C</span>
                        <span class="weather-label">Temperature</span>
                    </div>
                    <div class="weather-card">
                        <span class="weather-value">{{ weatherData.radiation }} W/m2</span>
                        <span class="weather-label">Radiation</span>
                    </div>
                    <div class="weather-card">
                        <span class="weather-value">{{ weatherData.cloud_cover }}%</span>
                        <span class="weather-label">Cloud Cover</span>
                    </div>
                </div>
            </section>
        </div>

        <div class="loading-state" v-else>
            <div class="golden-spinner"></div>
            <p>Loading installation data...</p>
        </div>
    </div>
</template>

<script>
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

import {
    Chart,
    LineController,
    LineElement,
    PointElement,
    BarController,
    BarElement,
    LinearScale,
    CategoryScale,
    Tooltip,
    Legend,
    Filler,
} from 'chart.js'

Chart.register(
    LineController,
    LineElement,
    PointElement,
    BarController,
    BarElement,
    LinearScale,
    CategoryScale,
    Tooltip,
    Legend,
    Filler
)

export default {
    name: 'DetailView',
    props: {
        id: {
            type: [String, Number],
            required: true,
        },
    },
    data() {
        return {
            installation: null,
            readings: [],
            stats: {
                today_kwh: 0,
                month_kwh: 0,
                year_kwh: 0,
                total_savings_eur: 0,
                performance_ratio: 0,
            },
            weatherData: null,
            chart: null,
        }
    },
    mounted() {
        this.fetchData()
    },
    beforeUnmount() {
        if (this.chart) {
            this.chart.destroy()
        }
    },
    methods: {
        async fetchData() {
            try {
                // Fetch installation details from PHP API (proxied to ML service)
                const installUrl = generateUrl(`/apps/filantropia_solar/api/v1/installations/${this.id}`)
                const installationRes = await axios.get(installUrl)
                this.installation = installationRes.data

                // Fetch readings for chart
                const readingsUrl = generateUrl(`/apps/filantropia_solar/api/v1/installations/${this.id}/readings`)
                const readingsRes = await axios.get(readingsUrl, { params: { limit: 168 } })
                this.readings = readingsRes.data.readings || []

                // Fetch statistics
                const statsUrl = generateUrl(`/apps/filantropia_solar/api/v1/installations/${this.id}/stats`)
                const statsRes = await axios.get(statsUrl)
                const statsData = statsRes.data
                this.stats = {
                    today_kwh: statsData.avg_daily_production_kwh || 0,
                    month_kwh: (statsData.avg_daily_production_kwh || 0) * 30,
                    year_kwh: statsData.total_production_kwh || 0,
                    total_savings_eur: statsData.total_savings_eur || 0,
                    performance_ratio: 0.85,
                }

                // Update chart
                this.$nextTick(() => {
                    this.initChart()
                })
            } catch (error) {
                console.error('Failed to fetch installation data:', error)
            }
        },

        initChart() {
            const ctx = this.$refs.energyChart?.getContext('2d')
            if (!ctx) return

            // Group readings by hour for aggregation
            const hourlyData = {}
            this.readings.forEach(r => {
                const date = new Date(r.timestamp)
                const hour = date.getHours()
                if (!hourlyData[hour]) {
                    hourlyData[hour] = { total: 0, count: 0 }
                }
                hourlyData[hour].total += r.produced_kwh || 0
                hourlyData[hour].count += 1
            })

            // Generate 24-hour labels
            const labels = Array.from({ length: 24 }, (_, i) => `${i}:00`)

            // Calculate average production per hour
            const productionData = labels.map((_, hour) => {
                const data = hourlyData[hour]
                return data && data.count > 0 ? (data.total / data.count) : 0
            })

            // Placeholder for other data (would need weather data)
            const consumptionData = Array(24).fill(0)
            const radiationData = Array(24).fill(0)

            this.chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Production (kWh)',
                            data: productionData,
                            borderColor: '#C4B552',
                            backgroundColor: 'rgba(196, 181, 82, 0.1)',
                            fill: true,
                            tension: 0.3,
                        },
                        {
                            label: 'Consumption (kWh)',
                            data: consumptionData,
                            borderColor: '#E8A94B',
                            backgroundColor: 'rgba(232, 169, 75, 0.1)',
                            fill: true,
                            tension: 0.3,
                        },
                        {
                            label: 'Radiation (x10 W/m2)',
                            data: radiationData,
                            type: 'bar',
                            backgroundColor: 'rgba(107, 155, 195, 0.3)',
                            borderColor: '#6B9BC3',
                            borderWidth: 1,
                            yAxisID: 'radiation',
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'kWh',
                            },
                        },
                        radiation: {
                            position: 'right',
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'W/m2 (x10)',
                            },
                            grid: {
                                drawOnChartArea: false,
                            },
                        },
                    },
                    plugins: {
                        legend: {
                            position: 'bottom',
                        },
                    },
                },
            })
        },

        formatEnergy(value) {
            if (value === null || value === undefined) return '-- kWh'
            if (value >= 1000) return `${(value / 1000).toFixed(1)} MWh`
            return `${parseFloat(value).toFixed(1)} kWh`
        },

        formatCurrency(value) {
            if (value === null || value === undefined) return '-- EUR'
            return `${parseFloat(value).toFixed(2)} EUR`
        },

        formatPercent(value) {
            if (value === null || value === undefined) return '-- %'
            return `${(parseFloat(value) * 100).toFixed(1)}%`
        },
    },
}
</script>

<style lang="scss" scoped>
@import '../style/_golden-brand.scss';

.detail-view {
    max-width: 1200px;
    margin: 0 auto;
}

.detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 0;
    border-bottom: 2px solid $golden-primary;
    margin-bottom: 24px;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 16px;
}

.title-section {
    h1 {
        @include golden-heading;
        font-size: 1.5rem;
        margin: 0 0 4px;
    }
}

.location-badge {
    @include golden-badge;
    font-size: 0.75rem;
}

.capacity-display {
    font-size: 1.5rem;
    font-weight: 700;
    color: $golden-primary;
}

.chart-section {
    @include golden-card;
    margin-bottom: 24px;

    h2 {
        @include golden-heading;
        font-size: 1.1rem;
        margin: 0 0 16px;
    }
}

.chart-wrapper {
    height: 300px;
    position: relative;
}

.stats-section {
    margin-bottom: 24px;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
}

.stat-card {
    @include golden-card;
    text-align: center;

    &.highlight {
        background: linear-gradient(135deg, rgba($golden-primary, 0.1), rgba($golden-secondary, 0.05));
        border-color: $golden-primary;

        .stat-value {
            color: $golden-primary;
            font-size: 1.5rem;
        }
    }
}

.stat-label {
    display: block;
    font-size: 0.75rem;
    color: #888;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.stat-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: $charcoal;

    &.golden {
        color: $golden-primary;
    }
}

.weather-section {
    @include golden-card;

    h2 {
        @include golden-heading;
        font-size: 1.1rem;
        margin: 0 0 16px;
    }
}

.weather-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}

.weather-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px;
    background: rgba($golden-primary, 0.05);
    border-radius: 8px;
}

.weather-icon {
    color: $golden-olive;
    margin-bottom: 8px;
}

.weather-value {
    font-size: 1.25rem;
    font-weight: 600;
    color: $charcoal;
}

.weather-label {
    font-size: 0.75rem;
    color: #888;
    margin-top: 4px;
}

.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 50vh;
    color: #888;

    .golden-spinner {
        width: 48px;
        height: 48px;
        border: 4px solid #f0ecd8;
        border-top-color: $golden-primary;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 16px;
    }
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
</style>
