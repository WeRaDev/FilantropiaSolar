<template>
    <div class="chart-section">
        <div class="chart-header">
            <h3>{{ chartTitle }}</h3>
            <div class="chart-header-actions">
                <button
                    type="button"
                    class="view-data-btn"
                    title="View station dataset table"
                    @click="$emit('view-data')"
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 5h18M3 12h18M3 19h18"/>
                        <path d="M8 5v14M16 5v14"/>
                    </svg>
                    View data
                </button>
            <!-- Day navigation only for 'day' timeframe -->
            <div v-if="currentTimeframe === 'day'" class="day-nav">
                <button class="nav-btn" :disabled="currentDayIndex <= 0" @click="$emit('prev-day')">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="m15 18-6-6 6-6"/>
                    </svg>
                </button>
                <span class="day-label">{{ currentDayLabel }}</span>
                <button class="nav-btn" :disabled="currentDayIndex >= totalDays - 1" @click="$emit('next-day')">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="m9 18 6-6-6-6"/>
                    </svg>
                </button>
            </div>
            <div v-else class="timeframe-info">
                <span>{{ totalDays }} days: {{ dateRangeLabel }}</span>
            </div>
            </div>
        </div>
        <div class="chart-container">
            <canvas ref="canvasEl"></canvas>
        </div>
        <!-- Data mode indicator -->
        <div class="data-mode-badge" :class="dataMode">
            {{ dataModeLabel }}
        </div>
    </div>
</template>

<script>
import { ref, onMounted, onUpdated, watch } from 'vue'

export default {
    name: 'ChartSection',
    props: {
        chartTitle: { type: String, required: true },
        currentTimeframe: { type: String, required: true },
        currentDayIndex: { type: Number, required: true },
        totalDays: { type: Number, required: true },
        currentDayLabel: { type: String, required: true },
        dateRangeLabel: { type: String, default: '' },
        dataMode: { type: String, required: true },
        dataModeLabel: { type: String, required: true },
    },
    emits: ['prev-day', 'next-day', 'canvas-el', 'view-data'],
    setup(props, { emit }) {
        const canvasEl = ref(null)

        const emitCanvas = () => {
            if (canvasEl.value) {
                emit('canvas-el', canvasEl.value)
            }
        }

        // Hand the canvas element to the parent so the chart composable can render into it
        onMounted(emitCanvas)
        onUpdated(emitCanvas)
        // Mode/data changes can leave canvas at 0x0 until layout; re-emit for parent re-render
        watch(
            () => [props.dataMode, props.currentDayLabel, props.currentTimeframe],
            () => emitCanvas(),
        )

        return { canvasEl }
    },
}
</script>

<style scoped>
/* Chart Section - Left */
.chart-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
    border-right: 1px solid var(--color-border, #e0e0e0);
    position: relative;
}

.chart-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
}

.chart-header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    justify-content: flex-end;
}

.view-data-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--color-border, #ddd);
    background: var(--color-background-dark, #f7f7f7);
    color: inherit;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
}

.view-data-btn:hover {
    background: var(--color-background-hover, #ececec);
}

.chart-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}

.day-nav {
    display: flex;
    align-items: center;
    gap: 8px;
}

.nav-btn {
    background: var(--color-background-dark, #f5f5f5);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 4px;
    padding: 4px 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
}

.nav-btn:hover:not(:disabled) {
    background: var(--color-background-hover, #e8e8e8);
}

.nav-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.day-label {
    font-size: 13px;
    min-width: 100px;
    text-align: center;
}

.chart-container {
    flex: 1;
    min-height: 0;
    position: relative;
}

.chart-container canvas {
    width: 100% !important;
    height: 100% !important;
}

.data-mode-badge {
    position: absolute;
    bottom: 20px;
    left: 20px;
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
}

.data-mode-badge.historical {
    background: #e8f5e9;
    color: #2e7d32;
}

.data-mode-badge.simulated {
    background: #fff3e0;
    color: #ef6c00;
}

.data-mode-badge.mixed {
    background: #e3f2fd;
    color: #1565c0;
}

.data-mode-badge.none {
    background: #f5f5f5;
    color: #616161;
}

/* Responsive */
@media (max-width: 1000px) {
    .chart-section {
        border-right: none;
        border-bottom: 1px solid var(--color-border, #e0e0e0);
        height: 50%;
    }
}
</style>
