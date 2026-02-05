<template>
  <div class="weather-chart">
    <h3>Hourly Weather Conditions</h3>
    <div v-if="hourlyData && hourlyData.length" class="chart-container">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
    <div v-else class="no-data">
      <p>No weather data available</p>
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
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
)

export default {
  name: 'WeatherChart',
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
      const startIdx = this.dayIndex * 24
      const endIdx = startIdx + 24
      return this.hourlyData.slice(startIdx, endIdx)
    },
    chartData() {
      const data = this.filteredData
      return {
        labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
        datasets: [
          {
            type: 'line',
            label: 'Temperature (C)',
            data: data.map(h => h.temperature || 0),
            borderColor: '#e74c3c',
            backgroundColor: 'rgba(231, 76, 60, 0.1)',
            yAxisID: 'y-temp',
            tension: 0.3,
            pointRadius: 2
          },
          {
            type: 'line',
            label: 'Humidity (%)',
            data: data.map(h => h.humidity || 0),
            borderColor: '#3498db',
            backgroundColor: 'rgba(52, 152, 219, 0.1)',
            yAxisID: 'y-percent',
            tension: 0.3,
            pointRadius: 2
          },
          {
            type: 'bar',
            label: 'Cloud Cover (%)',
            data: data.map(h => h.cloud_cover || 0),
            backgroundColor: 'rgba(149, 165, 166, 0.5)',
            borderColor: '#95a5a6',
            yAxisID: 'y-percent'
          },
          {
            type: 'line',
            label: 'Wind Speed (m/s)',
            data: data.map(h => h.wind_speed || 0),
            borderColor: '#9b59b6',
            backgroundColor: 'rgba(155, 89, 182, 0.1)',
            yAxisID: 'y-wind',
            tension: 0.3,
            pointRadius: 2
          }
        ]
      }
    },
    chartOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            position: 'top'
          }
        },
        scales: {
          'y-temp': {
            type: 'linear',
            position: 'left',
            title: {
              display: true,
              text: 'Temperature (C)'
            },
            grid: {
              drawOnChartArea: true
            }
          },
          'y-percent': {
            type: 'linear',
            position: 'right',
            min: 0,
            max: 100,
            title: {
              display: true,
              text: 'Percentage (%)'
            },
            grid: {
              drawOnChartArea: false
            }
          },
          'y-wind': {
            type: 'linear',
            position: 'right',
            title: {
              display: false
            },
            grid: {
              drawOnChartArea: false
            },
            display: false // Hidden axis, uses same visual space
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
  }
}
</script>

<style scoped>
.weather-chart {
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.weather-chart h3 {
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
</style>
