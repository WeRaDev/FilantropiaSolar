<template>
  <div class="daily-overview-chart">
    <h3>21-Day Overview</h3>
    <div class="navigation">
      <button @click="previousDay" :disabled="selectedDay <= 0" class="nav-btn">
        Previous
      </button>
      <span class="current-day">{{ currentDayLabel }}</span>
      <button @click="nextDay" :disabled="selectedDay >= totalDays - 1" class="nav-btn">
        Next
      </button>
    </div>
    <div v-if="dailyData && dailyData.length" class="chart-container">
      <Bar :data="chartData" :options="chartOptions" @click="onChartClick" />
    </div>
    <div v-else class="no-data">
      <p>No daily data available</p>
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

export default {
  name: 'DailyOverviewChart',
  components: { Bar },
  props: {
    dailyData: {
      type: Array,
      default: () => []
    },
    selectedDay: {
      type: Number,
      default: 0
    }
  },
  emits: ['dayChange'],
  computed: {
    totalDays() {
      return this.dailyData.length
    },
    currentDayLabel() {
      if (this.dailyData.length === 0) return 'No data'
      const day = this.dailyData[this.selectedDay]
      if (!day) return 'Day ' + (this.selectedDay + 1)
      return day.date || 'Day ' + (this.selectedDay + 1)
    },
    chartData() {
      const data = this.dailyData
      // Create background colors with selected day highlighted
      const bgColors = data.map((_, idx) => {
        if (idx === this.selectedDay) {
          return 'rgba(196, 181, 82, 0.9)' // Golden highlight for selected
        }
        return 'rgba(196, 181, 82, 0.5)' // Semi-transparent for others
      })
      
      const borderColors = data.map((_, idx) => {
        if (idx === this.selectedDay) {
          return '#c0392b' // Red frame for selected (from v1.2.3)
        }
        return '#A89D3F' // Golden border
      })
      
      const borderWidths = data.map((_, idx) => {
        return idx === this.selectedDay ? 3 : 1
      })
      
      return {
        labels: data.map(d => this.formatDateLabel(d.date)),
        datasets: [{
          label: 'Daily Production (kWh)',
          data: data.map(d => d.total_kwh || 0),
          backgroundColor: bgColors,
          borderColor: borderColors,
          borderWidth: borderWidths
        }]
      }
    },
    chartOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        onClick: (event, elements) => {
          if (elements.length > 0) {
            const idx = elements[0].index
            this.$emit('dayChange', idx)
          }
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              title: (items) => {
                if (items.length === 0) return ''
                const idx = items[0].dataIndex
                const day = this.dailyData[idx]
                return day ? day.date : ''
              },
              afterLabel: (context) => {
                const day = this.dailyData[context.dataIndex]
                if (day && day.savings_eur !== undefined) {
                  return `Savings: ${day.savings_eur.toFixed(2)} EUR`
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
              text: 'Date'
            },
            ticks: {
              maxRotation: 45,
              minRotation: 45
            }
          }
        }
      }
    }
  },
  methods: {
    formatDateLabel(dateStr) {
      if (!dateStr) return ''
      // Format as MM/DD for compactness
      const parts = dateStr.split('-')
      if (parts.length === 3) {
        return `${parts[1]}/${parts[2]}`
      }
      return dateStr
    },
    previousDay() {
      if (this.selectedDay > 0) {
        this.$emit('dayChange', this.selectedDay - 1)
      }
    },
    nextDay() {
      if (this.selectedDay < this.totalDays - 1) {
        this.$emit('dayChange', this.selectedDay + 1)
      }
    },
    onChartClick(event) {
      // Click handling is done via chartOptions.onClick
    }
  }
}
</script>

<style scoped>
.daily-overview-chart {
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.daily-overview-chart h3 {
  margin: 0 0 12px 0;
  color: #2d2d2d;
  font-size: 16px;
}

.navigation {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 12px;
}

.nav-btn {
  padding: 6px 16px;
  background: #C4B552;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background: #A89D3F;
}

.nav-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.current-day {
  font-weight: 600;
  color: #2d2d2d;
  min-width: 120px;
  text-align: center;
}

.chart-container {
  height: 250px;
  position: relative;
}

.no-data {
  height: 250px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #7f8c8d;
}
</style>
