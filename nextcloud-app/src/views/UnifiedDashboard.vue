<template>
  <div class="unified-dashboard">
    <!-- Top Metrics Row -->
    <div class="metrics-row">
      <div class="metric-card">
        <span class="metric-icon pv">PV</span>
        <div class="metric-content">
          <span class="metric-value">{{ totalCapacity.toFixed(1) }} kWp</span>
          <span class="metric-label">Network Capacity</span>
        </div>
      </div>
      <div class="metric-card">
        <span class="metric-icon on">ON</span>
        <div class="metric-content">
          <span class="metric-value">{{ installations.length }} / {{ installations.length }}</span>
          <span class="metric-label">Systems Online</span>
        </div>
      </div>
      <div class="metric-card">
        <span class="metric-icon kw">kW</span>
        <div class="metric-content">
          <span class="metric-value">{{ totalMonthlyGeneration.toFixed(1) }} MWh</span>
          <span class="metric-label">Monthly Generation</span>
        </div>
      </div>
      <div class="metric-card highlight">
        <span class="metric-icon eur">EUR</span>
        <div class="metric-content">
          <span class="metric-value golden">{{ totalSavings.toFixed(1) }}k EUR</span>
          <span class="metric-label">Total Savings</span>
        </div>
      </div>
    </div>

    <!-- Main Content: Map + List + Analysis -->
    <div class="main-content">
      <!-- Left: Map -->
      <div class="map-section">
        <div id="dashboard-map" class="map-container"></div>
      </div>

      <!-- Right: Installation List + Analysis Panel -->
      <div class="side-panel">
        <!-- Installation List -->
        <div class="installations-list" :class="{ collapsed: selectedInstallation }">
          <div class="list-header">
            <h3>Installations</h3>
            <input v-model="searchQuery" placeholder="Search..." class="search-input" />
          </div>
          <div class="list-content">
            <div
              v-for="inst in filteredInstallations"
              :key="inst.id"
              class="installation-card"
              :class="{ selected: selectedInstallation?.id === inst.id }"
              @click="selectInstallation(inst)"
            >
              <div class="card-header">
                <span class="card-name">{{ inst.name }}</span>
                <span class="card-capacity">{{ inst.capacity_kwp }} kWp</span>
              </div>
              <div class="card-location">{{ inst.location }}</div>
            </div>
          </div>
          <div class="list-footer">
            <span>Total: {{ totalCapacity.toFixed(1) }} kWp</span>
          </div>
        </div>

        <!-- Analysis Panel (shown when installation selected) -->
        <div v-if="selectedInstallation" class="analysis-panel">
          <div class="analysis-header">
            <button @click="closeAnalysis" class="close-btn">X</button>
            <h3>{{ selectedInstallation.name }}</h3>
            <span class="location-badge">{{ selectedInstallation.location }}</span>
          </div>

          <!-- Analysis Controls -->
          <div class="analysis-controls">
            <div class="control-row">
              <label>Center Date:</label>
              <input type="date" v-model="analysisDate" class="date-input" />
            </div>
            <div class="control-row">
              <label>Timeframe:</label>
              <div class="timeframe-buttons">
                <button
                  v-for="tf in timeframes"
                  :key="tf.days"
                  :class="{ active: selectedTimeframe === tf.days }"
                  @click="selectedTimeframe = tf.days"
                >
                  {{ tf.label }}
                </button>
              </div>
            </div>
            <button
              class="generate-btn"
              @click="generateAnalysis"
              :disabled="analysisLoading"
            >
              {{ analysisLoading ? 'Generating...' : 'Generate Analysis' }}
            </button>
          </div>

          <!-- Analysis Results -->
          <div v-if="analysisData" class="analysis-results">
            <!-- Stats Summary -->
            <div class="stats-row">
              <div class="stat">
                <span class="stat-value">{{ analysisData.period_statistics?.total_energy_kwh?.toFixed(1) || 0 }}</span>
                <span class="stat-label">kWh Total</span>
              </div>
              <div class="stat">
                <span class="stat-value">{{ analysisData.period_statistics?.avg_daily_kwh?.toFixed(1) || 0 }}</span>
                <span class="stat-label">kWh/day Avg</span>
              </div>
              <div class="stat highlight">
                <span class="stat-value golden">{{ analysisData.period_statistics?.total_savings_eur?.toFixed(2) || 0 }}</span>
                <span class="stat-label">EUR Savings</span>
              </div>
            </div>

            <!-- Daily Overview Chart -->
            <div class="chart-section">
              <h4>Daily Overview</h4>
              <div class="day-nav">
                <button @click="prevDay" :disabled="selectedDayIndex <= 0">Prev</button>
                <span>{{ currentDayLabel }}</span>
                <button @click="nextDay" :disabled="selectedDayIndex >= (analysisData.daily_data?.length || 1) - 1">Next</button>
              </div>
              <div class="chart-container" ref="dailyChartContainer">
                <canvas ref="dailyChart"></canvas>
              </div>
            </div>

            <!-- Hourly Energy Chart -->
            <div class="chart-section">
              <h4>Hourly Energy Production</h4>
              <div class="chart-container" ref="hourlyChartContainer">
                <canvas ref="hourlyChart"></canvas>
              </div>
              <div class="rank-legend">
                <span><span class="dot r5"></span>Excellent</span>
                <span><span class="dot r4"></span>Good</span>
                <span><span class="dot r3"></span>Average</span>
                <span><span class="dot r2"></span>Below</span>
                <span><span class="dot r1"></span>Poor</span>
              </div>
            </div>

            <!-- Weather Chart -->
            <div class="chart-section">
              <h4>Weather Conditions</h4>
              <div class="chart-container" ref="weatherChartContainer">
                <canvas ref="weatherChart"></canvas>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import {
  Chart,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

Chart.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Title, Tooltip, Legend)

const RANK_COLORS = {
  5: '#2ecc71',
  4: '#27ae60',
  3: '#f39c12',
  2: '#e67e22',
  1: '#e74c3c',
  0: '#bdc3c7'
}

export default {
  name: 'UnifiedDashboard',
  data() {
    return {
      installations: [],
      searchQuery: '',
      selectedInstallation: null,
      analysisDate: new Date().toISOString().split('T')[0],
      selectedTimeframe: 21,
      timeframes: [
        { days: 1, label: '1 Day' },
        { days: 7, label: '7 Days' },
        { days: 21, label: '21 Days' },
        { days: 28, label: '28 Days' }
      ],
      analysisLoading: false,
      analysisData: null,
      selectedDayIndex: 0,
      map: null,
      markers: [],
      dailyChartInstance: null,
      hourlyChartInstance: null,
      weatherChartInstance: null
    }
  },
  computed: {
    filteredInstallations() {
      if (!this.searchQuery) return this.installations
      const q = this.searchQuery.toLowerCase()
      return this.installations.filter(i =>
        i.name.toLowerCase().includes(q) ||
        i.location.toLowerCase().includes(q)
      )
    },
    totalCapacity() {
      return this.installations.reduce((sum, i) => sum + (i.capacity_kwp || 0), 0)
    },
    totalMonthlyGeneration() {
      // Estimate based on capacity (4 hours peak sun * 30 days * 0.8 efficiency / 1000)
      return this.totalCapacity * 4 * 30 * 0.8 / 1000
    },
    totalSavings() {
      // Rough estimate: monthly generation * 12 months * 0.15 EUR/kWh / 1000
      return this.totalMonthlyGeneration * 12 * 0.15
    },
    currentDayLabel() {
      if (!this.analysisData?.daily_data?.length) return ''
      const day = this.analysisData.daily_data[this.selectedDayIndex]
      return day?.date || ''
    }
  },
  mounted() {
    this.fetchInstallations()
    this.$nextTick(() => this.initMap())
  },
  beforeUnmount() {
    this.destroyCharts()
    if (this.map) this.map.remove()
  },
  methods: {
    async fetchInstallations() {
      try {
        const url = generateUrl('/apps/filantropia_solar/api/v1/installations')
        const response = await axios.get(url)
        this.installations = response.data.installations || []
        this.updateMapMarkers()
      } catch (error) {
        console.error('Failed to fetch installations:', error)
      }
    },

    initMap() {
      const container = document.getElementById('dashboard-map')
      if (!container || this.map) return

      this.map = L.map(container).setView([39.5, -8.0], 6)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: 'Leaflet | OpenStreetMap'
      }).addTo(this.map)

      this.updateMapMarkers()
    },

    updateMapMarkers() {
      if (!this.map) return

      // Clear existing markers
      this.markers.forEach(m => m.remove())
      this.markers = []

      // Add markers for each installation
      const locations = {
        'Lisbon': [38.7223, -9.1393],
        'Setubal': [38.5244, -8.8882],
        'Faro': [37.0194, -7.9304],
        'Braga': [41.5454, -8.4265],
        'Tavira': [37.1279, -7.6486],
        'Loule': [37.1376, -8.0197]
      }

      // Group by location
      const grouped = {}
      this.installations.forEach(inst => {
        const loc = inst.location || 'Unknown'
        if (!grouped[loc]) grouped[loc] = []
        grouped[loc].push(inst)
      })

      Object.entries(grouped).forEach(([loc, insts]) => {
        const coords = locations[loc] || [38.7, -9.1]
        const count = insts.length
        const totalKwp = insts.reduce((s, i) => s + (i.capacity_kwp || 0), 0)

        const icon = L.divIcon({
          className: 'golden-marker',
          html: `<div class="marker-inner">${count}</div>`,
          iconSize: [32, 32]
        })

        const marker = L.marker(coords, { icon })
          .bindPopup(`<b>${loc}</b><br>${count} installations<br>${totalKwp.toFixed(1)} kWp`)
          .on('click', () => {
            if (insts.length === 1) {
              this.selectInstallation(insts[0])
            }
          })
          .addTo(this.map)

        this.markers.push(marker)
      })
    },

    selectInstallation(inst) {
      this.selectedInstallation = inst
      this.analysisData = null
      this.selectedDayIndex = 0

      // Set default date based on installation data range
      if (inst.to_date) {
        this.analysisDate = inst.to_date.split('T')[0]
      }
    },

    closeAnalysis() {
      this.selectedInstallation = null
      this.analysisData = null
      this.destroyCharts()
    },

    async generateAnalysis() {
      if (!this.selectedInstallation) return

      this.analysisLoading = true
      this.destroyCharts()

      try {
        const url = generateUrl('/apps/filantropia_solar/api/v1/predict/period')
        const response = await axios.post(url, {
          mode: 'historical',
          installation_id: this.selectedInstallation.id,
          center_date: this.analysisDate,
          days: this.selectedTimeframe
        })

        if (response.data.success) {
          this.analysisData = response.data
          this.selectedDayIndex = Math.floor((this.analysisData.daily_data?.length || 0) / 2)
          this.$nextTick(() => this.renderCharts())
        } else {
          console.error('Analysis failed:', response.data.error)
        }
      } catch (error) {
        console.error('Failed to generate analysis:', error)
      } finally {
        this.analysisLoading = false
      }
    },

    destroyCharts() {
      if (this.dailyChartInstance) {
        this.dailyChartInstance.destroy()
        this.dailyChartInstance = null
      }
      if (this.hourlyChartInstance) {
        this.hourlyChartInstance.destroy()
        this.hourlyChartInstance = null
      }
      if (this.weatherChartInstance) {
        this.weatherChartInstance.destroy()
        this.weatherChartInstance = null
      }
    },

    renderCharts() {
      this.renderDailyChart()
      this.renderHourlyChart()
      this.renderWeatherChart()
    },

    renderDailyChart() {
      const canvas = this.$refs.dailyChart
      if (!canvas || !this.analysisData?.daily_data) return

      const data = this.analysisData.daily_data
      const bgColors = data.map((_, idx) =>
        idx === this.selectedDayIndex ? 'rgba(196, 181, 82, 0.9)' : 'rgba(196, 181, 82, 0.5)'
      )
      const borderColors = data.map((_, idx) =>
        idx === this.selectedDayIndex ? '#c0392b' : '#A89D3F'
      )

      this.dailyChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
          labels: data.map(d => d.date?.slice(5) || ''),
          datasets: [{
            label: 'kWh',
            data: data.map(d => d.total_kwh || 0),
            backgroundColor: bgColors,
            borderColor: borderColors,
            borderWidth: data.map((_, idx) => idx === this.selectedDayIndex ? 3 : 1)
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          onClick: (e, elements) => {
            if (elements.length > 0) {
              this.selectedDayIndex = elements[0].index
              this.updateCharts()
            }
          },
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'kWh' } }
          }
        }
      })
    },

    renderHourlyChart() {
      const canvas = this.$refs.hourlyChart
      if (!canvas || !this.analysisData?.hourly_data) return

      const hourlyData = this.getSelectedDayHourly()

      this.hourlyChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
          labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
          datasets: [{
            label: 'Production (kWh)',
            data: hourlyData.map(h => h.production_kwh || 0),
            backgroundColor: hourlyData.map(h => RANK_COLORS[h.rank] || RANK_COLORS[0]),
            borderColor: hourlyData.map(h => RANK_COLORS[h.rank] || RANK_COLORS[0]),
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'kWh' } }
          }
        }
      })
    },

    renderWeatherChart() {
      const canvas = this.$refs.weatherChart
      if (!canvas || !this.analysisData?.hourly_data) return

      const hourlyData = this.getSelectedDayHourly()

      this.weatherChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
          labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
          datasets: [
            {
              type: 'line',
              label: 'Temp (C)',
              data: hourlyData.map(h => h.temperature || 0),
              borderColor: '#e74c3c',
              tension: 0.3,
              pointRadius: 1,
              yAxisID: 'y'
            },
            {
              type: 'bar',
              label: 'Cloud (%)',
              data: hourlyData.map(h => h.cloud_cover || 0),
              backgroundColor: 'rgba(149, 165, 166, 0.5)',
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'top' } },
          scales: {
            y: { position: 'left', title: { display: true, text: 'Temp (C)' } },
            y1: { position: 'right', min: 0, max: 100, title: { display: true, text: '%' }, grid: { drawOnChartArea: false } }
          }
        }
      })
    },

    getSelectedDayHourly() {
      if (!this.analysisData?.hourly_data) return []
      const start = this.selectedDayIndex * 24
      return this.analysisData.hourly_data.slice(start, start + 24)
    },

    prevDay() {
      if (this.selectedDayIndex > 0) {
        this.selectedDayIndex--
        this.updateCharts()
      }
    },

    nextDay() {
      if (this.selectedDayIndex < (this.analysisData?.daily_data?.length || 1) - 1) {
        this.selectedDayIndex++
        this.updateCharts()
      }
    },

    updateCharts() {
      this.destroyCharts()
      this.$nextTick(() => this.renderCharts())
    }
  }
}
</script>

<style scoped>
.unified-dashboard {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 50px);
  background: #f5f5f5;
}

/* Metrics Row */
.metrics-row {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: white;
  border-bottom: 1px solid #eee;
}

.metric-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: #fafafa;
  border-radius: 8px;
  flex: 1;
}

.metric-card.highlight {
  background: rgba(196, 181, 82, 0.1);
  border: 1px solid #C4B552;
}

.metric-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  color: white;
}

.metric-icon.pv { background: #C4B552; }
.metric-icon.on { background: #27ae60; }
.metric-icon.kw { background: #3498db; }
.metric-icon.eur { background: #C4B552; }

.metric-value {
  font-size: 20px;
  font-weight: 600;
  color: #2d2d2d;
}

.metric-value.golden {
  color: #A89D3F;
}

.metric-label {
  font-size: 12px;
  color: #666;
}

/* Main Content */
.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.map-section {
  flex: 1;
  min-width: 0;
}

.map-container {
  width: 100%;
  height: 100%;
}

/* Side Panel */
.side-panel {
  width: 380px;
  display: flex;
  flex-direction: column;
  background: white;
  border-left: 1px solid #eee;
  overflow: hidden;
}

.installations-list {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: max-height 0.3s;
}

.installations-list.collapsed {
  max-height: 200px;
}

.list-header {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.list-header h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
}

.search-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
}

.list-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.installation-card {
  padding: 12px;
  border: 1px solid #eee;
  border-radius: 6px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.installation-card:hover {
  border-color: #C4B552;
  background: #fafafa;
}

.installation-card.selected {
  border-color: #C4B552;
  background: rgba(196, 181, 82, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.card-name {
  font-weight: 500;
}

.card-capacity {
  color: #C4B552;
  font-weight: 600;
}

.card-location {
  font-size: 12px;
  color: #666;
}

.list-footer {
  padding: 8px 16px;
  border-top: 1px solid #eee;
  font-size: 13px;
  color: #C4B552;
  font-weight: 600;
}

/* Analysis Panel */
.analysis-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-top: 2px solid #C4B552;
}

.analysis-header {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
  position: relative;
}

.analysis-header h3 {
  margin: 0;
  padding-right: 30px;
}

.close-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border: none;
  background: #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.location-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #eee;
  border-radius: 4px;
  font-size: 11px;
  margin-top: 4px;
}

.analysis-controls {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
}

.control-row {
  margin-bottom: 10px;
}

.control-row label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.date-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.timeframe-buttons {
  display: flex;
  gap: 6px;
}

.timeframe-buttons button {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.timeframe-buttons button.active {
  background: #C4B552;
  color: white;
  border-color: #C4B552;
}

.generate-btn {
  width: 100%;
  padding: 10px;
  background: #C4B552;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.generate-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

/* Analysis Results */
.analysis-results {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.stats-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.stat {
  flex: 1;
  text-align: center;
  padding: 10px;
  background: #fafafa;
  border-radius: 6px;
}

.stat.highlight {
  background: rgba(196, 181, 82, 0.1);
}

.stat-value {
  display: block;
  font-size: 16px;
  font-weight: 600;
}

.stat-value.golden {
  color: #A89D3F;
}

.stat-label {
  font-size: 10px;
  color: #666;
}

.chart-section {
  margin-bottom: 16px;
  padding: 12px;
  background: white;
  border: 1px solid #eee;
  border-radius: 6px;
}

.chart-section h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #444;
}

.day-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 8px;
}

.day-nav button {
  padding: 4px 12px;
  background: #C4B552;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.day-nav button:disabled {
  background: #ccc;
}

.chart-container {
  height: 150px;
  position: relative;
}

.rank-legend {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
  font-size: 10px;
  color: #666;
}

.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 2px;
}

.r5 { background: #2ecc71; }
.r4 { background: #27ae60; }
.r3 { background: #f39c12; }
.r2 { background: #e67e22; }
.r1 { background: #e74c3c; }

/* Golden Marker Style */
:deep(.golden-marker) {
  background: none;
  border: none;
}

:deep(.marker-inner) {
  width: 32px;
  height: 32px;
  background: #C4B552;
  border: 2px solid white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  font-size: 14px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}
</style>
