<template>
    <header class="modal-header">
        <div class="header-left">
            <span class="status-badge" :class="selectedObject?.status || 'offline'"></span>
            <h2>{{ selectedObject?.name || 'Installation Analysis' }}</h2>
            <span class="location-badge">{{ selectedObject?.location }}</span>
            <span class="capacity-badge">{{ selectedObject?.capacity_kwp }} kWp</span>
        </div>
        <div class="header-center">
            <!-- Historical/Predicted Toggle -->
            <div class="mode-toggle">
                <span
                    class="mode-label"
                    :class="{ active: analysisMode === 'historical' }"
                    @click="$emit('set-analysis-mode', 'historical')">
                    Historical
                </span>
                <label class="toggle-switch">
                    <input
                        type="checkbox"
                        :checked="analysisMode === 'predicted'"
                        @change="$emit('toggle-analysis-mode')"
                    />
                    <span class="toggle-slider"></span>
                </label>
                <span
                    class="mode-label"
                    :class="{ active: analysisMode === 'predicted' }"
                    @click="$emit('set-analysis-mode', 'predicted')">
                    Predicted
                </span>
            </div>
            <!-- Date picker -->
            <div class="date-picker-group">
                <label for="center-date">Center Date:</label>
                <input
                    id="center-date"
                    ref="dateInput"
                    type="date"
                    :value="centerDate"
                    :max="effectiveMaxDate"
                    class="date-input"
                    @input="$emit('update:centerDate', $event.target.value)"
                    @change="$emit('date-change')"
                />
                <button class="calendar-btn" title="Open calendar" @click="openCalendar">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                        <line x1="16" y1="2" x2="16" y2="6"/>
                        <line x1="8" y1="2" x2="8" y2="6"/>
                        <line x1="3" y1="10" x2="21" y2="10"/>
                    </svg>
                </button>
            </div>
            <!-- Timeframe buttons -->
            <div class="timeframe-buttons">
                <button
                    v-for="tf in timeframes"
                    :key="tf.value"
                    class="tf-btn"
                    :class="{ active: currentTimeframe === tf.value }"
                    @click="$emit('set-timeframe', tf.value)">
                    {{ tf.label }}
                </button>
            </div>
            <!-- Weather data toggle -->
            <div class="weather-toggle">
                <button class="weather-toggle-btn" title="Weather layers" @click="showWeatherDropdown = !showWeatherDropdown">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M3 15h4v6H3zM9 11h4v10H9zM15 7h4v14h-4z"/>
                    </svg>
                    <span>Weather</span>
                </button>
                <div v-if="showWeatherDropdown" class="weather-dropdown">
                    <label class="weather-option">
                        <input type="checkbox" :checked="weatherLayers.temperature" @change="onWeatherToggle('temperature')" />
                        <span class="weather-color" style="background: #FFA500;"></span>
                        Temperature
                    </label>
                    <label class="weather-option">
                        <input type="checkbox" :checked="weatherLayers.cloudCover" @change="onWeatherToggle('cloudCover')" />
                        <span class="weather-color" style="background: #888888;"></span>
                        Cloud Cover
                    </label>
                    <label class="weather-option">
                        <input type="checkbox" :checked="weatherLayers.humidity" @change="onWeatherToggle('humidity')" />
                        <span class="weather-color" style="background: #4169E1;"></span>
                        Humidity
                    </label>
                    <label class="weather-option">
                        <input type="checkbox" :checked="weatherLayers.windSpeed" @change="onWeatherToggle('windSpeed')" />
                        <span class="weather-color" style="background: #9B59B6;"></span>
                        Wind Speed
                    </label>
                </div>
            </div>
        </div>
        <div class="header-right">
            <!-- ML Module Info button -->
            <div class="ml-info-wrapper">
                <button class="btn-info" title="ML Module Info" @click="showMlInfo = !showMlInfo">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 16v-4M12 8h.01"/>
                    </svg>
                    <span>ML Info</span>
                </button>
                <div v-if="showMlInfo" class="ml-info-popover">
                    <h4>Data Source & Model Info</h4>
                    <div class="ml-info-row"><span class="ml-info-label">PV Data:</span> Sarmas et al. (2025)</div>
                    <div class="ml-info-row">Photovoltaic Power Production Dataset</div>
                    <div class="ml-info-row"><span class="ml-info-label">DOI:</span> 10.17632/dbh93b6vp8.3</div>
                    <div class="ml-info-row"><span class="ml-info-label">Weather Source:</span> {{ analysisData?.weather_source || 'synthetic' }}</div>
                    <div class="ml-info-row"><span class="ml-info-label">Data points:</span> {{ analysisData?.hourly_data?.length || 0 }} hourly, {{ analysisData?.daily_data?.length || 0 }} daily</div>
                    <div class="ml-info-row"><span class="ml-info-label">Prediction Method:</span> {{ analysisData?.weather_source === 'measured' ? 'Measured Data' : (analysisData?.model_info?.name || 'Physics-based Estimation') }}</div>
                    <div class="ml-info-row"><span class="ml-info-label">Model R&sup2;:</span> {{ analysisData?.model_info?.r2 != null ? analysisData.model_info.r2.toFixed(4) : 'N/A (physics-based)' }}</div>
                    <div class="ml-info-row"><span class="ml-info-label">Model MAE:</span> {{ analysisData?.model_info?.mae != null ? analysisData.model_info.mae.toFixed(4) : 'N/A (physics-based)' }}</div>
                </div>
            </div>
            <!-- Export Data button -->
            <button
                class="btn-export"
                :disabled="isExporting || !analysisData"
                title="Export to Files"
                @click="$emit('export')">
                <span v-if="isExporting" class="spinner-sm"></span>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                <span>Export</span>
            </button>
            <button class="btn-close" title="Close (Esc)" @click="$emit('close')">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
            </button>
        </div>
    </header>
</template>

<script>
export default {
    name: 'AnalyticsHeader',
    props: {
        selectedObject: {
            type: Object,
            default: null,
        },
        analysisMode: {
            type: String,
            default: 'predicted',
        },
        centerDate: {
            type: String,
            default: '',
        },
        effectiveMaxDate: {
            type: String,
            default: '',
        },
        timeframes: {
            type: Array,
            default: () => [],
        },
        currentTimeframe: {
            type: String,
            default: 'week',
        },
        weatherLayers: {
            type: Object,
            default: () => ({}),
        },
        analysisData: {
            type: Object,
            default: null,
        },
        isExporting: {
            type: Boolean,
            default: false,
        },
    },
    emits: [
        'set-analysis-mode',
        'toggle-analysis-mode',
        'update:centerDate',
        'date-change',
        'set-timeframe',
        'update:weatherLayers',
        'weather-change',
        'export',
        'close',
    ],
    data() {
        return {
            showMlInfo: false,
            showWeatherDropdown: false,
        }
    },
    methods: {
        openCalendar() {
            const el = this.$refs.dateInput
            if (el && el.showPicker) el.showPicker()
        },
        onWeatherToggle(layer) {
            const next = { ...this.weatherLayers, [layer]: !this.weatherLayers[layer] }
            this.$emit('update:weatherLayers', next)
            this.$emit('weather-change')
        },
    },
}
</script>

<style scoped>
.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: var(--color-background-dark, #f5f5f5);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    gap: 16px;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.status-badge {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}
.status-badge.active { background: #22A559; }
.status-badge.warning { background: #F5A623; }
.status-badge.offline { background: #CC2020; }

.modal-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}

.location-badge, .capacity-badge {
    font-size: 12px;
    padding: 4px 8px;
    background: var(--color-background-hover, #e8e8e8);
    border-radius: 4px;
    color: var(--color-text-lighter, #666);
}

.header-center {
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
}

/* Mode Toggle Switch */
.mode-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px;
    background: var(--color-background-hover, #e8e8e8);
    border-radius: 20px;
}

.mode-label {
    font-size: 12px;
    color: var(--color-text-lighter, #888);
    cursor: pointer;
    transition: color 0.2s;
}

.mode-label.active {
    color: var(--color-primary, #0082c9);
    font-weight: 600;
}

.toggle-switch {
    position: relative;
    display: inline-block;
    width: 40px;
    height: 20px;
}

.toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #32CD32;
    transition: 0.3s;
    border-radius: 20px;
}

.toggle-slider:before {
    position: absolute;
    content: "";
    height: 14px;
    width: 14px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: 0.3s;
    border-radius: 50%;
}

input:checked + .toggle-slider {
    background-color: #F5A623;
}

input:checked + .toggle-slider:before {
    transform: translateX(20px);
}

.date-picker-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.date-picker-group label {
    font-size: 13px;
    color: var(--color-text-lighter, #666);
}

.date-input {
    padding: 6px 10px;
    border: 1px solid var(--color-border, #ccc);
    border-radius: 6px;
    font-size: 13px;
    background: var(--color-main-background, #fff);
}

.date-input:hover {
    border-color: var(--color-primary, #0082c9);
}

.calendar-btn {
    padding: 6px 8px;
    border: 1px solid var(--color-border, #ccc);
    background: var(--color-main-background, #fff);
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.calendar-btn:hover {
    background: var(--color-background-hover, #f0f0f0);
    border-color: var(--color-primary, #0082c9);
}

.timeframe-buttons {
    display: flex;
    gap: 8px;
}

.tf-btn {
    padding: 8px 16px;
    border: 1px solid var(--color-border, #ccc);
    background: var(--color-main-background, #fff);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.tf-btn:hover {
    background: var(--color-background-hover, #f0f0f0);
}

.tf-btn.active {
    background: var(--color-primary, #0082c9);
    color: white;
    border-color: var(--color-primary, #0082c9);
}

/* Weather Toggle Dropdown */
.weather-toggle {
    position: relative;
}

.weather-toggle-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    border: 1px solid var(--color-border, #ccc);
    background: var(--color-main-background, #fff);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.weather-toggle-btn:hover {
    background: var(--color-background-hover, #f0f0f0);
    border-color: var(--color-primary, #0082c9);
}

.weather-dropdown {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 4px;
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #ccc);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 100;
    min-width: 160px;
    padding: 8px 0;
}

.weather-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 13px;
    transition: background 0.2s;
}

.weather-option:hover {
    background: var(--color-background-hover, #f5f5f5);
}

.weather-option input {
    cursor: pointer;
}

.weather-color {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    flex-shrink: 0;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 12px;
}

/* ML Info Button & Popover */
.ml-info-wrapper {
    position: relative;
}

.btn-info {
    padding: 8px 12px;
    background: var(--color-background-dark, #f0f0f0);
    color: var(--color-main-text, #333);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
}

.btn-info:hover {
    background: var(--color-background-hover, #e8e8e8);
    border-color: var(--color-primary, #0082c9);
}

.ml-info-popover {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 8px;
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #ccc);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    z-index: 200;
    min-width: 320px;
    padding: 16px;
}

.ml-info-popover h4 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-main-text, #333);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    padding-bottom: 8px;
}

.ml-info-row {
    font-size: 12px;
    color: var(--color-text-lighter, #666);
    padding: 3px 0;
    line-height: 1.5;
}

.ml-info-label {
    font-weight: 600;
    color: var(--color-main-text, #333);
}

.btn-export {
    padding: 8px 12px;
    background: var(--color-background-dark, #f0f0f0);
    color: var(--color-main-text, #333);
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
}

.btn-export:hover:not(:disabled) {
    background: var(--color-background-hover, #e8e8e8);
    border-color: var(--color-border-dark, #ccc);
}

.btn-export:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-close {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    color: var(--color-text-lighter, #666);
    border-radius: 4px;
}

.btn-close:hover {
    background: var(--color-background-hover, #e8e8e8);
    color: var(--color-main-text, #333);
}

.spinner-sm {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
</style>
