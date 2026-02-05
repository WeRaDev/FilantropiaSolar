<template>
    <div class="configuration-view">
        <header class="config-header">
            <h1>Solar Energy Analysis Configuration</h1>
        </header>

        <div class="config-content">
            <!-- Analysis Mode Selection -->
            <section class="config-section">
                <h2>Analysis Mode</h2>
                <div class="mode-options">
                    <label class="mode-option" :class="{ active: mode === 'historical' }">
                        <input
                            type="radio"
                            v-model="mode"
                            value="historical"
                            @change="onModeChange"
                        />
                        <span class="mode-icon">&#128200;</span>
                        <div class="mode-text">
                            <strong>Historical Analysis</strong>
                            <span>Analyze existing data</span>
                        </div>
                    </label>
                    <label class="mode-option" :class="{ active: mode === 'simulation' }">
                        <input
                            type="radio"
                            v-model="mode"
                            value="simulation"
                            @change="onModeChange"
                        />
                        <span class="mode-icon">&#128302;</span>
                        <div class="mode-text">
                            <strong>Future Simulation</strong>
                            <span>Predict any date</span>
                        </div>
                    </label>
                </div>
            </section>

            <!-- Installation Selection -->
            <section class="config-section">
                <h2>Installation Selection</h2>
                <div class="installation-row">
                    <div class="installation-select">
                        <label>Choose Installation:</label>
                        <select v-model="selectedInstallation" @change="onInstallationChange">
                            <option value="">-- Select Installation --</option>
                            <option
                                v-for="inst in installations"
                                :key="inst.id"
                                :value="inst.id"
                            >
                                {{ inst.name }} - {{ inst.location }} ({{ inst.capacity_kwp }} kWp)
                            </option>
                        </select>
                    </div>

                    <!-- Custom Station Panel (Simulation mode only) -->
                    <div class="custom-station" v-if="mode === 'simulation'">
                        <h3>Custom Station (Optional)</h3>
                        <label class="checkbox-label">
                            <input type="checkbox" v-model="useCustomStation" />
                            Simulate as new station
                        </label>
                        <div class="custom-fields" v-if="useCustomStation">
                            <div class="field">
                                <label>Location:</label>
                                <select v-model="customLocation">
                                    <option v-for="loc in locations" :key="loc" :value="loc">
                                        {{ loc }}
                                    </option>
                                </select>
                            </div>
                            <div class="field">
                                <label>Capacity (kWp):</label>
                                <input
                                    type="number"
                                    v-model.number="customCapacity"
                                    step="0.1"
                                    min="0.1"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Date Selection -->
            <section class="config-section">
                <h2>Date Selection</h2>

                <!-- Historical Mode: Date Dropdown -->
                <div v-if="mode === 'historical'" class="date-selection">
                    <div class="date-range-info" v-if="dateRange">
                        <span class="label">Available Data Range:</span>
                        <span class="range golden">
                            {{ dateRange.from_date }} to {{ dateRange.to_date }}
                        </span>
                    </div>
                    <div class="field">
                        <label>Select Historical Date:</label>
                        <select v-model="selectedDate">
                            <option value="">-- Select Date --</option>
                            <option
                                v-for="date in availableDates"
                                :key="date"
                                :value="date"
                            >
                                {{ date }}
                            </option>
                        </select>
                    </div>
                </div>

                <!-- Simulation Mode: Date Input -->
                <div v-else class="date-selection">
                    <div class="field">
                        <label>Enter Date for Simulation:</label>
                        <input
                            type="date"
                            v-model="simulationDate"
                        />
                    </div>
                    <p class="hint">Format: YYYY-MM-DD</p>
                </div>
            </section>

            <!-- Action Buttons -->
            <section class="config-section actions">
                <button
                    class="btn btn-primary"
                    @click="generateAnalysis"
                    :disabled="!canGenerate || loading"
                >
                    <span v-if="loading">Generating...</span>
                    <span v-else>&#128640; Generate 21-Day Analysis</span>
                </button>
                <span class="status" :class="statusClass">{{ statusMessage }}</span>
            </section>
        </div>
    </div>
</template>

<script>
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

export default {
    name: 'ConfigurationView',
    data() {
        return {
            // Mode
            mode: 'historical',

            // Installations
            installations: [],
            selectedInstallation: '',

            // Custom station (simulation only)
            useCustomStation: false,
            customLocation: 'Lisbon',
            customCapacity: 5.0,
            locations: ['Lisbon', 'Setubal', 'Faro', 'Braga', 'Tavira', 'Loule'],

            // Date selection
            dateRange: null,
            availableDates: [],
            selectedDate: '',
            simulationDate: new Date().toISOString().split('T')[0],

            // Status
            loading: false,
            statusMessage: 'Ready to generate analysis',
            statusClass: '',

            // Results
            analysisResults: null,
        }
    },
    computed: {
        canGenerate() {
            if (this.mode === 'historical') {
                return this.selectedInstallation && this.selectedDate
            } else {
                if (this.useCustomStation) {
                    return this.customLocation && this.customCapacity > 0 && this.simulationDate
                }
                return this.selectedInstallation && this.simulationDate
            }
        },
    },
    mounted() {
        this.fetchInstallations()
    },
    methods: {
        async fetchInstallations() {
            try {
                const url = generateUrl('/apps/filantropia_solar/api/v1/installations')
                const response = await axios.get(url)
                this.installations = response.data.installations || []

                // Auto-select first installation
                if (this.installations.length > 0) {
                    this.selectedInstallation = this.installations[0].id
                    this.onInstallationChange()
                }
            } catch (error) {
                console.error('Failed to fetch installations:', error)
                this.statusMessage = 'Error loading installations'
                this.statusClass = 'error'
            }
        },

        async onInstallationChange() {
            if (!this.selectedInstallation) {
                this.dateRange = null
                this.availableDates = []
                return
            }

            // Find selected installation for date range
            const inst = this.installations.find(i => i.id === this.selectedInstallation)
            if (inst) {
                this.dateRange = {
                    from_date: inst.from_date?.split('T')[0] || '2019-01-01',
                    to_date: inst.to_date?.split('T')[0] || '2022-12-31',
                }

                // Generate sample dates (every 30 days)
                this.generateAvailableDates()
            }
        },

        generateAvailableDates() {
            if (!this.dateRange) return

            const dates = []
            const start = new Date(this.dateRange.from_date)
            const end = new Date(this.dateRange.to_date)
            const step = 30 // Days between options

            let current = new Date(start)
            while (current <= end) {
                dates.push(current.toISOString().split('T')[0])
                current.setDate(current.getDate() + step)
            }

            // Ensure end date is included
            const endStr = end.toISOString().split('T')[0]
            if (!dates.includes(endStr)) {
                dates.push(endStr)
            }

            this.availableDates = dates
            // Default to most recent
            this.selectedDate = dates[dates.length - 1]
        },

        onModeChange() {
            // Reset custom station when switching to historical
            if (this.mode === 'historical') {
                this.useCustomStation = false
            }
            this.statusMessage = 'Ready to generate analysis'
            this.statusClass = ''
        },

        async generateAnalysis() {
            this.loading = true
            this.statusMessage = 'Generating analysis...'
            this.statusClass = 'loading'

            try {
                const url = generateUrl('/apps/filantropia_solar/api/v1/predict/period')

                let requestData = {}

                if (this.mode === 'simulation' && this.useCustomStation) {
                    // Custom station simulation
                    requestData = {
                        mode: 'custom',
                        location: this.customLocation,
                        capacity_kwp: this.customCapacity,
                        center_date: this.simulationDate,
                        days: 21,
                    }
                } else {
                    // Standard analysis
                    requestData = {
                        mode: this.mode,
                        installation_id: this.selectedInstallation,
                        center_date: this.mode === 'historical' ? this.selectedDate : this.simulationDate,
                        days: 21,
                    }
                }

                const response = await axios.post(url, requestData)

                if (response.data.success) {
                    this.analysisResults = response.data
                    this.statusMessage = `Analysis completed for ${requestData.center_date}`
                    this.statusClass = 'success'

                    // Store analysis data in sessionStorage for ResultsView
                    sessionStorage.setItem('analysisData', JSON.stringify(response.data))

                    // Navigate to results view
                    this.$router.push({ name: 'results' })
                } else {
                    throw new Error(response.data.error || 'Analysis failed')
                }
            } catch (error) {
                console.error('Analysis failed:', error)
                this.statusMessage = `Error: ${error.message || 'Analysis failed'}`
                this.statusClass = 'error'
            } finally {
                this.loading = false
            }
        },
    },
}
</script>

<style lang="scss" scoped>
@import '../style/_golden-brand.scss';

.configuration-view {
    max-width: 900px;
    margin: 0 auto;
}

.config-header {
    margin-bottom: 24px;

    h1 {
        @include golden-heading;
        font-size: 1.5rem;
        margin: 0;
    }
}

.config-section {
    @include golden-card;
    margin-bottom: 20px;

    h2 {
        font-size: 1.1rem;
        font-weight: 600;
        color: $charcoal;
        margin: 0 0 16px;
        padding-bottom: 8px;
        border-bottom: 2px solid $golden-primary;
    }

    h3 {
        font-size: 0.95rem;
        font-weight: 600;
        color: $golden-olive;
        margin: 0 0 12px;
    }
}

.mode-options {
    display: flex;
    gap: 16px;
}

.mode-option {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    border: 2px solid $golden-border;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;

    input[type="radio"] {
        display: none;
    }

    &:hover {
        border-color: $golden-secondary;
        background: rgba($golden-primary, 0.05);
    }

    &.active {
        border-color: $golden-primary;
        background: rgba($golden-primary, 0.1);
    }
}

.mode-icon {
    font-size: 24px;
}

.mode-text {
    display: flex;
    flex-direction: column;

    strong {
        color: $charcoal;
    }

    span {
        font-size: 0.85rem;
        color: #888;
    }
}

.installation-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.installation-select,
.custom-station {
    display: flex;
    flex-direction: column;
}

.custom-station {
    padding: 16px;
    background: rgba($golden-primary, 0.05);
    border-radius: 8px;
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    margin-bottom: 12px;
}

.custom-fields {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.field {
    display: flex;
    flex-direction: column;
    gap: 4px;

    label {
        font-weight: 500;
        font-size: 0.9rem;
        color: $charcoal;
    }

    select,
    input {
        padding: 10px 12px;
        border: 1px solid $golden-border;
        border-radius: 6px;
        font-size: 0.95rem;
        background: white;

        &:focus {
            outline: none;
            border-color: $golden-primary;
            box-shadow: 0 0 0 2px rgba($golden-primary, 0.2);
        }
    }
}

.date-selection {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.date-range-info {
    display: flex;
    gap: 8px;
    align-items: center;

    .label {
        color: #888;
    }

    .range {
        font-weight: 600;
    }

    .golden {
        color: $golden-primary;
    }
}

.hint {
    font-size: 0.85rem;
    color: #888;
    margin: 0;
}

.actions {
    display: flex;
    align-items: center;
    gap: 16px;
}

.btn {
    padding: 12px 24px;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;

    &:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
}

.btn-primary {
    background: $golden-primary;
    color: white;

    &:hover:not(:disabled) {
        background: $golden-olive;
    }
}

.status {
    font-size: 0.9rem;

    &.loading {
        color: $golden-olive;
    }

    &.success {
        color: #4CAF50;
    }

    &.error {
        color: #F44336;
    }
}
</style>
