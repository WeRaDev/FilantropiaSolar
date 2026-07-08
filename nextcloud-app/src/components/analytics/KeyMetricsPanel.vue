<template>
    <div class="metrics-card">
        <h3>Key Metrics ({{ totalDays }}-day)</h3>
        <div class="metrics-grid">
            <div class="metric">
                <span class="metric-value">{{ periodStats.totalEnergy.toFixed(1) }}</span>
                <span class="metric-label">Total kWh</span>
            </div>
            <div class="metric">
                <span class="metric-value">{{ periodStats.avgDaily.toFixed(1) }}</span>
                <span class="metric-label">Avg Daily kWh</span>
            </div>
            <div class="metric metric-highlight">
                <span class="metric-value">&euro;{{ periodStats.lightSaved.toFixed(2) }}</span>
                <span class="metric-label">Light Saved</span>
            </div>
            <div class="metric">
                <span class="metric-value">{{ periodStats.peakHourEnergy.toFixed(2) }}</span>
                <span class="metric-label">Peak kWh/kWp</span>
            </div>
            <div class="metric">
                <span class="metric-value">{{ periodStats.avgTemperature.toFixed(1) }}</span>
                <span class="metric-label">Avg Temp C</span>
            </div>
            <div class="metric">
                <span class="metric-value">{{ periodStats.avgCloudCover.toFixed(0) }}</span>
                <span class="metric-label">Avg Cloud %</span>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'KeyMetricsPanel',
    props: {
        periodStats: {
            type: Object,
            required: true,
        },
        totalDays: {
            type: Number,
            default: 0,
        },
    },
}
</script>

<style scoped>
.metrics-card {
    background: var(--color-background-dark, #f8f8f8);
    border-radius: 8px;
    padding: 16px;
}

.metrics-card h3 {
    margin: 0 0 16px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-lighter, #666);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}

.metric {
    text-align: center;
}

.metric-value {
    display: block;
    font-size: 24px;
    font-weight: 700;
    color: var(--color-main-text, #333);
}

.metric-label {
    display: block;
    font-size: 11px;
    color: var(--color-text-lighter, #888);
    margin-top: 4px;
}

.metric-highlight .metric-value {
    color: #22A559;
}
</style>
