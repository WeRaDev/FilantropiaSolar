<template>
  <div class="results-view">
    <!-- Header -->
    <div class="results-header">
      <button @click="goBack" class="back-btn">Back to Configuration</button>
      <h2 v-if="installationInfo">{{ installationInfo.name }}</h2>
      <h2 v-else>Analysis Results</h2>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Generating analysis...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button @click="goBack" class="retry-btn">Go Back</button>
    </div>

    <!-- Results Content -->
    <div v-else-if="hasData" class="results-content">
      <!-- Statistics Panel -->
      <div class="stats-panel">
        <h3>Period Statistics</h3>
        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-label">Installation</span>
            <span class="stat-value">{{ installationInfo?.name || 'N/A' }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Location</span>
            <span class="stat-value">{{ installationInfo?.location || 'N/A' }}</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Capacity</span>
            <span class="stat-value">{{ installationInfo?.capacity_kwp || 0 }} kWp</span>
          </div>
          <div class="stat-card highlight">
            <span class="stat-label">Total Energy</span>
            <span class="stat-value">{{ formatNumber(periodStats?.total_energy_kwh) }} kWh</span>
          </div>
          <div class="stat-card">
            <span class="stat-label">Daily Average</span>
            <span class="stat-value">{{ formatNumber(periodStats?.avg_daily_kwh) }} kWh</span>
          </div>
          <div class="stat-card highlight golden">
            <span class="stat-label">Total Savings</span>
            <span class="stat-value">{{ formatNumber(periodStats?.total_savings_eur) }} EUR</span>
          </div>
        </div>
      </div>

      <!-- Charts Section -->
      <div class="charts-section">
        <!-- Daily Overview Chart -->
        <DailyOverviewChart
          :daily-data="dailyData"
          :selected-day="selectedDayIndex"
          @day-change="onDayChange"
        />

        <!-- Hourly Charts Row -->
        <div class="hourly-charts">
          <EnergyChart
            :hourly-data="hourlyData"
            :day-index="selectedDayIndex"
          />
          <WeatherChart
            :hourly-data="hourlyData"
            :day-index="selectedDayIndex"
          />
        </div>
      </div>

      <!-- Daily Breakdown Table -->
      <div class="daily-breakdown">
        <h3>Daily Breakdown</h3>
        <table class="breakdown-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Production (kWh)</th>
              <th>Savings (EUR)</th>
              <th>Avg Temp (C)</th>
              <th>Avg Cloud (%)</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(day, idx) in dailyData"
              :key="day.date"
              :class="{ selected: idx === selectedDayIndex }"
              @click="onDayChange(idx)"
            >
              <td>{{ day.date }}</td>
              <td>{{ formatNumber(day.total_kwh) }}</td>
              <td>{{ formatNumber(day.savings_eur) }}</td>
              <td>{{ formatNumber(day.avg_temperature) }}</td>
              <td>{{ formatNumber(day.avg_cloud_cover) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- No Data State -->
    <div v-else class="no-data-state">
      <p>No analysis data available. Please generate an analysis first.</p>
      <button @click="goBack" class="action-btn">Go to Configuration</button>
    </div>
  </div>
</template>

<script>
import EnergyChart from '../components/charts/EnergyChart.vue'
import WeatherChart from '../components/charts/WeatherChart.vue'
import DailyOverviewChart from '../components/charts/DailyOverviewChart.vue'

export default {
  name: 'ResultsView',
  components: {
    EnergyChart,
    WeatherChart,
    DailyOverviewChart
  },
  data() {
    return {
      loading: false,
      error: null,
      analysisData: null,
      selectedDayIndex: 0
    }
  },
  computed: {
    hasData() {
      return this.analysisData !== null
    },
    installationInfo() {
      return this.analysisData?.installation_info || null
    },
    periodStats() {
      return this.analysisData?.period_statistics || null
    },
    dailyData() {
      return this.analysisData?.daily_data || []
    },
    hourlyData() {
      return this.analysisData?.hourly_data || []
    }
  },
  mounted() {
    this.loadAnalysisData()
  },
  methods: {
    loadAnalysisData() {
      // Check for data passed via sessionStorage (from ConfigurationView)
      const storedData = sessionStorage.getItem('analysisData')
      if (storedData) {
        try {
          this.analysisData = JSON.parse(storedData)
          // Center on middle day (day 11 of 21)
          if (this.dailyData.length > 0) {
            this.selectedDayIndex = Math.floor(this.dailyData.length / 2)
          }
        } catch (e) {
          console.error('Failed to parse analysis data:', e)
          this.error = 'Failed to load analysis data'
        }
      }
    },
    onDayChange(newIndex) {
      this.selectedDayIndex = newIndex
    },
    goBack() {
      this.$router.push('/analysis')
    },
    formatNumber(value) {
      if (value === null || value === undefined) return 'N/A'
      return Number(value).toFixed(2)
    }
  }
}
</script>

<style scoped>
.results-view {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.results-header {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #C4B552;
}

.results-header h2 {
  margin: 0;
  color: #2d2d2d;
  flex: 1;
}

.back-btn {
  padding: 8px 16px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.back-btn:hover {
  background: #eee;
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #C4B552;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Error State */
.error-state, .no-data-state {
  text-align: center;
  padding: 60px;
  color: #666;
}

.retry-btn, .action-btn {
  margin-top: 16px;
  padding: 10px 24px;
  background: #C4B552;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.retry-btn:hover, .action-btn:hover {
  background: #A89D3F;
}

/* Stats Panel */
.stats-panel {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.stats-panel h3 {
  margin: 0 0 16px 0;
  color: #2d2d2d;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.stat-card {
  background: #f9f9f9;
  padding: 16px;
  border-radius: 6px;
  text-align: center;
}

.stat-card.highlight {
  background: #f0f4f8;
}

.stat-card.golden {
  background: rgba(196, 181, 82, 0.15);
  border: 1px solid #C4B552;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 18px;
  font-weight: 600;
  color: #2d2d2d;
}

.stat-card.golden .stat-value {
  color: #A89D3F;
}

/* Charts Section */
.charts-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 24px;
}

.hourly-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
  gap: 20px;
}

/* Daily Breakdown Table */
.daily-breakdown {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.daily-breakdown h3 {
  margin: 0 0 16px 0;
  color: #2d2d2d;
}

.breakdown-table {
  width: 100%;
  border-collapse: collapse;
}

.breakdown-table th,
.breakdown-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.breakdown-table th {
  background: #f5f5f5;
  font-weight: 600;
  color: #444;
}

.breakdown-table tr:hover {
  background: #fafafa;
  cursor: pointer;
}

.breakdown-table tr.selected {
  background: rgba(196, 181, 82, 0.15);
  border-left: 3px solid #C4B552;
}

.breakdown-table tr.selected td:first-child {
  padding-left: 9px;
}

@media (max-width: 768px) {
  .hourly-charts {
    grid-template-columns: 1fr;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
