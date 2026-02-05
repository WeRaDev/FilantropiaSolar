<template>
  <div class="energy-chart">
    <h3>Hourly Energy Production</h3>
    <div v-if="hourlyData && hourlyData.length" class="chart-container">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
    <div v-else class="no-data">
      <p>No hourly data available</p>
    </div>
    <div class="legend">
      <span class="legend-item"><span class="dot rank-5"></span> Excellent (5)</span>
      <span class="legend-item"><span class="dot rank-4"></span> Good (4)</span>
      <span class="legend-item"><span class="dot rank-3"></span> Average (3)</span>
      <span class="legend-item"><span class="dot rank-2"></span> Below Avg (2)</span>
      <span class="legend-item"><span class="dot rank-1"></span> Poor (1)</span>
    </div>
  </div>
</template>

<script>
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

// Performance ranking colors from v1.2.3
const RANK_COLORS = {
  5: '#2ecc71', // Excellent - green
  4: '#27ae60', // Good - darker green
  3: '#f39c12', // Average - orange
  2: '#e67e22', // Below Avg - darker orange
  1: '#e74c3c', // Poor - red
  0: '#bdc3c7'  // No data - gray
}

export default {
  name: 'EnergyChart',
  components: { Bar },
  props: {
    hourlyData: {
      type: Array,
      default: () => []
    },
    dayIndex: {
      type: Number,
      default: 0
    }
  },
  computed: {
    filteredData() {
      // Filter hourly data for the selected day (24 hours per day)
      const startIdx = this.dayIndex * 24
      const endIdx = startIdx + 24
      return this.hourlyData.slice(startIdx, endIdx)
    },
    chartData() {
      const data = this.filteredData
      return {
        labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
        datasets: [{
          label: 'Production (kWh)',
          data: data.map(h => h.production_kwh || 0),
          backgroundColor: data.map(h => this.getRankColor(h.rank || 0)),
          borderColor: data.map(h => this.getRankBorderColor(h.rank || 0)),
          borderWidth: 1
        }]
      }
    },
    chartOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              afterLabel: (context) => {
                const dataPoint = this.filteredData[context.dataIndex]
                if (dataPoint) {
                  return `Rank: ${dataPoint.rank || 'N/A'}`
                }
                return ''
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Energy (kWh)'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Hour'
            }
          }
        }
      }
    }
  },
  methods: {
    getRankColor(rank) {
      return RANK_COLORS[rank] || RANK_COLORS[0]
    },
    getRankBorderColor(rank) {
      const colors = {
        5: '#27ae60',
        4: '#1e8449',
        3: '#d68910',
        2: '#ca6f1e',
        1: '#c0392b',
        0: '#95a5a6'
      }
      return colors[rank] || colors[0]
    }
  }
}
</script>

<style scoped>
.energy-chart {
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.energy-chart h3 {
  margin: 0 0 16px 0;
  color: #2d2d2d;
  font-size: 16px;
}

.chart-container {
  height: 300px;
  position: relative;
}

.no-data {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #7f8c8d;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.rank-5 { background: #2ecc71; }
.rank-4 { background: #27ae60; }
.rank-3 { background: #f39c12; }
.rank-2 { background: #e67e22; }
.rank-1 { background: #e74c3c; }
</style>
