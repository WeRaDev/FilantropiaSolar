<template>
    <teleport to="body">
        <transition name="modal-fade">
            <div v-if="isOpen" class="virtual-modal-overlay" @click.self="closeModal">
                <div class="virtual-modal">
                    <!-- Modal Header -->
                    <header class="modal-header">
                        <h2>Create Virtual Installation</h2>
                        <button class="btn-close" @click="closeModal" title="Close">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M18 6 6 18M6 6l12 12"/>
                            </svg>
                        </button>
                    </header>

                    <!-- Modal Body -->
                    <div class="modal-body">
                        <p class="description">
                            Create a virtual PV installation to simulate energy production based on weather data. 
                            Virtual installations use real-time weather API data.
                        </p>

                        <form @submit.prevent="handleSubmit" class="form">
                            <!-- Name -->
                            <div class="form-group">
                                <label for="name">Installation Name *</label>
                                <input 
                                    id="name"
                                    v-model="form.name"
                                    type="text"
                                    placeholder="e.g., My Virtual Plant"
                                    required
                                />
                            </div>

                            <!-- Location Selection -->
                            <div class="form-group">
                                <label for="location">Location *</label>
                                <select id="location" v-model="form.location" required>
                                    <option value="">Select a location...</option>
                                    <option v-for="loc in locations" :key="loc.name" :value="loc.name">
                                        {{ loc.name }} ({{ loc.lat.toFixed(2) }}, {{ loc.lng.toFixed(2) }})
                                    </option>
                                    <option value="custom">Custom Location...</option>
                                </select>
                            </div>

                            <!-- Custom coordinates with map picker (v3.0.4) -->
                            <div v-if="form.location === 'custom'" class="custom-location-section">
                                <p class="map-hint">Click on the map to select location, or enter coordinates manually:</p>
                                <div ref="mapContainer" class="location-map"></div>
                                <div class="form-row">
                                    <div class="form-group">
                                        <label for="latitude">Latitude *</label>
                                        <input 
                                            id="latitude"
                                            v-model.number="form.latitude"
                                            type="number"
                                            step="0.0001"
                                            min="-90"
                                            max="90"
                                            placeholder="e.g., 38.72"
                                            required
                                            @input="updateMapMarker"
                                        />
                                    </div>
                                    <div class="form-group">
                                        <label for="longitude">Longitude *</label>
                                        <input 
                                            id="longitude"
                                            v-model.number="form.longitude"
                                            type="number"
                                            step="0.0001"
                                            min="-180"
                                            max="180"
                                            placeholder="e.g., -9.14"
                                            required
                                            @input="updateMapMarker"
                                        />
                                    </div>
                                </div>
                            </div>

                            <!-- Capacity -->
                            <div class="form-group">
                                <label for="capacity">Capacity (kWp) *</label>
                                <input 
                                    id="capacity"
                                    v-model.number="form.capacityKwp"
                                    type="number"
                                    step="0.1"
                                    min="0.1"
                                    max="10000"
                                    placeholder="e.g., 5.5"
                                    required
                                />
                                <span class="input-hint">Peak power capacity in kilowatts</span>
                            </div>

                            <!-- Grid Price (optional) -->
                            <div class="form-group">
                                <label for="gridPrice">Grid Price (EUR/kWh)</label>
                                <input 
                                    id="gridPrice"
                                    v-model.number="form.gridPriceKwh"
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    max="1"
                                    placeholder="0.15"
                                />
                                <span class="input-hint">Used for savings calculations</span>
                            </div>

                            <!-- Historical Data Upload (optional) -->
                            <div class="form-group">
                                <label for="dataFile">Historical Data (optional)</label>
                                <div class="file-upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="handleFileDrop">
                                    <input
                                        ref="fileInput"
                                        id="dataFile"
                                        type="file"
                                        accept=".csv,.xlsx"
                                        style="display: none;"
                                        @change="handleFileSelect"
                                    />
                                    <span v-if="!form.dataFile" class="upload-placeholder">
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                                        </svg>
                                        Drop CSV/Excel or click to browse
                                    </span>
                                    <span v-else class="upload-selected">
                                        {{ form.dataFile.name }} ({{ formatFileSize(form.dataFile.size) }})
                                        <button type="button" class="btn-remove-file" @click.stop="form.dataFile = null">
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                                <path d="M18 6 6 18M6 6l12 12"/>
                                            </svg>
                                        </button>
                                    </span>
                                </div>
                                <span class="input-hint">CSV with columns: Date, Produced Energy (kWh). Optional.</span>
                            </div>

                            <!-- Error message -->
                            <div v-if="error" class="error-message">
                                {{ error }}
                            </div>

                            <!-- Actions -->
                            <div class="form-actions">
                                <button type="button" class="btn-secondary" @click="closeModal">
                                    Cancel
                                </button>
                                <button type="submit" class="btn-primary" :disabled="isSubmitting">
                                    <span v-if="isSubmitting" class="spinner-sm"></span>
                                    <span v-else>Create Virtual Installation</span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </transition>
    </teleport>
</template>

<script>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useAppStore } from '../store/app.js'
import { generateUrl } from '@nextcloud/router'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default {
    name: 'CreateVirtualModal',
    setup() {
        const store = useAppStore()
        const mapContainer = ref(null)
        let map = null
        let marker = null
        
        // Form state
        const form = ref({
            name: '',
            location: '',
            latitude: null,
            longitude: null,
            capacityKwp: null,
            gridPriceKwh: 0.15
        })
        
        const isSubmitting = ref(false)
        const error = ref(null)
        const fileInput = ref(null)

        // Known locations with coordinates
        const locations = [
            { name: 'Lisbon', lat: 38.7223, lng: -9.1393 },
            { name: 'Setubal', lat: 38.5244, lng: -8.8882 },
            { name: 'Faro', lat: 37.0194, lng: -7.9304 },
            { name: 'Braga', lat: 41.5454, lng: -8.4265 },
            { name: 'Tavira', lat: 37.1279, lng: -7.6486 },
            { name: 'Loule', lat: 37.1376, lng: -8.0197 },
            { name: 'Porto', lat: 41.1579, lng: -8.6291 },
            { name: 'Coimbra', lat: 40.2033, lng: -8.4103 },
            { name: 'Evora', lat: 38.5714, lng: -7.9094 }
        ]

        // Computed
        const isOpen = computed(() => store.createVirtualModalOpen)

        // Watch location selection to auto-fill coordinates and init map
        watch(() => form.value.location, (newLoc) => {
            if (newLoc && newLoc !== 'custom') {
                const loc = locations.find(l => l.name === newLoc)
                if (loc) {
                    form.value.latitude = loc.lat
                    form.value.longitude = loc.lng
                }
                // Destroy map when switching away from custom
                destroyMap()
            } else if (newLoc === 'custom') {
                // Initialize map for custom location
                nextTick(() => {
                    initMap()
                })
            }
        })

        // Initialize Leaflet map for location picking (v3.0.4)
        const initMap = () => {
            if (!mapContainer.value || map) return

            // Default to Portugal center
            const defaultLat = form.value.latitude || 39.5
            const defaultLng = form.value.longitude || -8.0

            map = L.map(mapContainer.value, {
                zoomControl: true,
                attributionControl: false
            }).setView([defaultLat, defaultLng], 7)

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 18
            }).addTo(map)

            // Add marker if coordinates exist
            if (form.value.latitude && form.value.longitude) {
                addMarker(form.value.latitude, form.value.longitude)
            }

            // Click handler to set coordinates
            map.on('click', (e) => {
                const { lat, lng } = e.latlng
                form.value.latitude = parseFloat(lat.toFixed(4))
                form.value.longitude = parseFloat(lng.toFixed(4))
                addMarker(lat, lng)
            })
        }

        // Custom star icon for virtual installations (v3.0.5)
        const createCustomIcon = () => {
            // Create SVG star icon as data URL
            const starSvg = `
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="%239B59B6" stroke="%23fff" stroke-width="1.5">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
            `
            const encodedSvg = encodeURIComponent(starSvg.trim())
            
            return L.icon({
                iconUrl: `data:image/svg+xml,${encodedSvg}`,
                iconSize: [32, 32],
                iconAnchor: [16, 16],  // Center of icon (star should be centered)
                popupAnchor: [0, -16]
            })
        }

        // Add or move marker on map
        const addMarker = (lat, lng) => {
            if (marker) {
                marker.setLatLng([lat, lng])
            } else if (map) {
                marker = L.marker([lat, lng], {
                    draggable: true,
                    icon: createCustomIcon()
                }).addTo(map)

                // Drag handler to update coordinates
                marker.on('dragend', (e) => {
                    const pos = e.target.getLatLng()
                    form.value.latitude = parseFloat(pos.lat.toFixed(4))
                    form.value.longitude = parseFloat(pos.lng.toFixed(4))
                })
            }
        }

        // Update marker when coordinates are manually entered
        const updateMapMarker = () => {
            if (map && form.value.latitude && form.value.longitude) {
                const lat = parseFloat(form.value.latitude)
                const lng = parseFloat(form.value.longitude)
                if (!isNaN(lat) && !isNaN(lng)) {
                    addMarker(lat, lng)
                    map.panTo([lat, lng])
                }
            }
        }

        // Destroy map instance
        const destroyMap = () => {
            if (map) {
                map.remove()
                map = null
                marker = null
            }
        }

        // Cleanup on unmount
        onUnmounted(() => {
            destroyMap()
        })

        // Methods
        const closeModal = () => {
            store.closeCreateVirtualModal()
            destroyMap()
            resetForm()
        }

        const resetForm = () => {
            form.value = {
                name: '',
                location: '',
                latitude: null,
                longitude: null,
                capacityKwp: null,
                gridPriceKwh: 0.15,
                dataFile: null
            }
            error.value = null
        }

        // File handling
        const triggerFileInput = () => {
            fileInput.value?.click()
        }

        const handleFileSelect = (event) => {
            const file = event.target.files[0]
            if (file) {
                form.value.dataFile = file
            }
        }

        const handleFileDrop = (event) => {
            const file = event.dataTransfer.files[0]
            if (file && (file.name.endsWith('.csv') || file.name.endsWith('.xlsx'))) {
                form.value.dataFile = file
            }
        }

        const formatFileSize = (bytes) => {
            if (bytes < 1024) return bytes + ' B'
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
        }

        const handleSubmit = async () => {
            error.value = null

            // Validation
            if (!form.value.name.trim()) {
                error.value = 'Please enter a name'
                return
            }
            if (!form.value.location) {
                error.value = 'Please select a location'
                return
            }
            if (form.value.location === 'custom' && (!form.value.latitude || !form.value.longitude)) {
                error.value = 'Please enter latitude and longitude'
                return
            }
            if (!form.value.capacityKwp || form.value.capacityKwp <= 0) {
                error.value = 'Please enter a valid capacity'
                return
            }

            isSubmitting.value = true

            try {
                // Determine final location name and coordinates
                const locationName = form.value.location === 'custom' 
                    ? `Custom (${form.value.latitude.toFixed(2)}, ${form.value.longitude.toFixed(2)})`
                    : form.value.location

                await store.createVirtualInstallation({
                    name: form.value.name.trim(),
                    location: locationName,
                    latitude: form.value.latitude,
                    longitude: form.value.longitude,
                    capacityKwp: form.value.capacityKwp,
                    gridPriceKwh: form.value.gridPriceKwh || 0.15
                })

                closeModal()
            } catch (e) {
                error.value = e.message || 'Failed to create installation'
            } finally {
                isSubmitting.value = false
            }
        }

        return {
            isOpen,
            form,
            locations,
            isSubmitting,
            error,
            mapContainer,
            fileInput,
            closeModal,
            handleSubmit,
            updateMapMarker,
            triggerFileInput,
            handleFileSelect,
            handleFileDrop,
            formatFileSize
        }
    }
}
</script>

<style scoped>
/* Modal Overlay */
.virtual-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    padding: 24px;
}

/* Modal Container */
.virtual-modal {
    background: var(--color-main-background, #fff);
    border-radius: 12px;
    width: 100%;
    max-width: 500px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25);
}

/* Modal Header */
.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: var(--color-background-dark, #f5f5f5);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.modal-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
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
}

/* Modal Body */
.modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
}

.description {
    margin: 0 0 24px 0;
    color: var(--color-text-lighter, #666);
    font-size: 14px;
    line-height: 1.5;
}

/* Form */
.form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.form-group label {
    font-size: 13px;
    font-weight: 500;
    color: var(--color-main-text, #333);
}

.form-group input,
.form-group select {
    padding: 10px 12px;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    font-size: 14px;
    background: var(--color-main-background, #fff);
    transition: border-color 0.2s, box-shadow 0.2s;
}

.form-group input:focus,
.form-group select:focus {
    outline: none;
    border-color: var(--color-primary, #0082c9);
    box-shadow: 0 0 0 2px rgba(0, 130, 201, 0.15);
}

.input-hint {
    font-size: 11px;
    color: var(--color-text-lighter, #888);
}

.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

/* Custom Location Section with Map (v3.0.4) */
.custom-location-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.map-hint {
    margin: 0;
    font-size: 12px;
    color: var(--color-text-lighter, #666);
}

.location-map {
    width: 100%;
    height: 200px;
    border-radius: 8px;
    border: 1px solid var(--color-border, #ddd);
    overflow: hidden;
    background: #f0f0f0;
}

/* Fix Leaflet marker icon issue */
:deep(.leaflet-default-icon-path) {
    background-image: url('https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png');
}

/* File Upload Area */
.file-upload-area {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 60px;
    padding: 12px;
    border: 2px dashed var(--color-border, #ddd);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    background: var(--color-background-dark, #f9f9f9);
}

.file-upload-area:hover {
    border-color: var(--color-primary, #0082c9);
    background: rgba(0, 130, 201, 0.04);
}

.upload-placeholder {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--color-text-lighter, #888);
    font-size: 13px;
}

.upload-selected {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--color-main-text, #333);
}

.btn-remove-file {
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px;
    color: var(--color-text-lighter, #888);
    border-radius: 4px;
}

.btn-remove-file:hover {
    background: #ffebee;
    color: #c62828;
}

/* Error Message */
.error-message {
    padding: 12px;
    background: #ffebee;
    color: #c62828;
    border-radius: 6px;
    font-size: 13px;
}

/* Form Actions */
.form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 8px;
}

.btn-secondary,
.btn-primary {
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.btn-secondary {
    background: var(--color-main-background, #fff);
    border: 1px solid var(--color-border, #ddd);
    color: var(--color-main-text, #333);
}

.btn-secondary:hover {
    background: var(--color-background-hover, #f5f5f5);
}

.btn-primary {
    background: var(--color-primary, #0082c9);
    border: none;
    color: white;
}

.btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover, #0070b0);
}

.btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.spinner-sm {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Modal Transitions */
.modal-fade-enter-active,
.modal-fade-leave-active {
    transition: opacity 0.2s ease;
}

.modal-fade-enter-active .virtual-modal,
.modal-fade-leave-active .virtual-modal {
    transition: transform 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
    opacity: 0;
}

.modal-fade-enter-from .virtual-modal,
.modal-fade-leave-to .virtual-modal {
    transform: scale(0.95) translateY(-10px);
}
</style>
