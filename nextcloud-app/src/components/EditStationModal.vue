<template>
	<div v-if="isOpen && selectedObject" class="modal-overlay" @click.self="close">
		<div class="modal-card">
			<header class="modal-head">
				<h3>Edit station</h3>
				<button type="button" class="x" @click="close">Close</button>
			</header>
			<div class="modal-body">
				<label>Location *
					<select v-model="form.locationChoice">
						<option value="">Select a location...</option>
						<option v-for="loc in locations" :key="loc.name" :value="loc.name">
							{{ loc.name }} ({{ loc.lat.toFixed(2) }}, {{ loc.lng.toFixed(2) }})
						</option>
						<option value="custom">Custom Location...</option>
					</select>
				</label>

				<div v-if="form.locationChoice === 'custom'" class="custom-location-section">
					<p class="map-hint">Click on the map to select location, or enter coordinates manually:</p>
					<div ref="mapContainer" class="location-map"></div>
					<div class="coord-row">
						<label>Latitude *
							<input
								v-model.number="form.latitude"
								type="number"
								step="0.0001"
								min="-90"
								max="90"
								placeholder="e.g., 38.72"
								@input="updateMapMarker"
							>
						</label>
						<label>Longitude *
							<input
								v-model.number="form.longitude"
								type="number"
								step="0.0001"
								min="-180"
								max="180"
								placeholder="e.g., -9.14"
								@input="updateMapMarker"
							>
						</label>
					</div>
					<label>Location label
						<input
							v-model="form.locationLabel"
							type="text"
							placeholder="Optional display name for this place"
						>
					</label>
				</div>

				<label>Capacity (kWp)
					<input v-model.number="form.capacity_kwp" type="number" min="0.01" step="0.01">
				</label>
				<label>Energy price (€/kWh)
					<input v-model.number="form.grid_price_kwh" type="number" min="0" step="0.001">
				</label>
				<label>Grid connection
					<select v-model="form.grid_connection_type">
						<option value="on_grid">On-grid (factor 0.4)</option>
						<option value="off_grid">Off-grid (factor 1.0)</option>
					</select>
				</label>
				<label>Website
					<input v-model="form.website" type="url" placeholder="https://...">
				</label>
				<label>Short description
					<textarea v-model="form.short_description" rows="3" placeholder="As shown on the public site" />
				</label>
				<label>Installation date (dataset start)
					<input v-model="form.installation_date" type="date">
				</label>
				<div class="dataset-box">
					<div class="dataset-label">Series / dataset range</div>
					<div class="dataset-value">{{ seriesRangeLabel }}</div>
					<div class="dataset-actions">
						<button type="button" class="btn" :disabled="busy" @click="viewDataset">View dataset</button>
						<button type="button" class="btn primary" :disabled="busy" @click="populateDataset">Populate dataset</button>
					</div>
					<p class="hint">Populate fills missing hours with ML simulation from installation date to now. Measured hours are never overwritten.</p>
				</div>
				<p v-if="error" class="err">{{ error }}</p>
				<p v-if="info" class="ok">{{ info }}</p>
			</div>
			<footer class="modal-foot">
				<button type="button" class="btn" :disabled="busy" @click="close">Cancel</button>
				<button type="button" class="btn primary" :disabled="busy" @click="save">Save</button>
			</footer>
		</div>
	</div>
</template>

<script>
import { computed, nextTick, onUnmounted, reactive, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useAppStore } from '../store/app.js'
import { createLocationPinIcon, fixLeafletDefaultIcons } from '../utils/leafletIcons.js'

const LOCATIONS = [
	{ name: 'Lisbon', lat: 38.7223, lng: -9.1393 },
	{ name: 'Setubal', lat: 38.5244, lng: -8.8882 },
	{ name: 'Faro', lat: 37.0194, lng: -7.9304 },
	{ name: 'Braga', lat: 41.5454, lng: -8.4265 },
	{ name: 'Tavira', lat: 37.1279, lng: -7.6486 },
	{ name: 'Loule', lat: 37.1376, lng: -8.0197 },
	{ name: 'Porto', lat: 41.1579, lng: -8.6291 },
	{ name: 'Coimbra', lat: 40.2033, lng: -8.4103 },
	{ name: 'Evora', lat: 38.5714, lng: -7.9094 },
]

function nearlyEqual(a, b, eps = 0.02) {
	return Math.abs(Number(a) - Number(b)) <= eps
}

function resolveLocationChoice(locationName, lat, lng) {
	const name = (locationName || '').trim()
	const knownByName = LOCATIONS.find((l) => l.name === name)
	if (knownByName) {
		return { choice: knownByName.name, label: knownByName.name }
	}
	if (lat != null && lng != null && !Number.isNaN(Number(lat)) && !Number.isNaN(Number(lng))) {
		const knownByCoords = LOCATIONS.find(
			(l) => nearlyEqual(l.lat, lat) && nearlyEqual(l.lng, lng),
		)
		if (knownByCoords) {
			return { choice: knownByCoords.name, label: knownByCoords.name }
		}
	}
	if (name || (lat != null && lng != null)) {
		return { choice: 'custom', label: name }
	}
	return { choice: '', label: '' }
}

export default {
	name: 'EditStationModal',
	setup() {
		const store = useAppStore()
		const isOpen = computed(() => store.editStationModalOpen)
		const selectedObject = computed(() => store.selectedObject)
		const busy = ref(false)
		const error = ref('')
		const info = ref('')
		const mapContainer = ref(null)
		let map = null
		let marker = null

		const form = reactive({
			locationChoice: '',
			locationLabel: '',
			latitude: null,
			longitude: null,
			capacity_kwp: 0,
			grid_price_kwh: 0.15,
			grid_connection_type: 'on_grid',
			website: '',
			short_description: '',
			installation_date: new Date().toISOString().slice(0, 10),
		})

		const seriesRangeLabel = computed(() => {
			const o = selectedObject.value
			if (!o) return '—'
			// Series bounds only (not installation date)
			const from = (o.series_from_date || o.customData?.seriesFromDate || '').toString().slice(0, 10)
			const to = (o.series_to_date || o.customData?.seriesToDate || '').toString().slice(0, 10)
			if (from && to) return `${from} → ${to}`
			if (from) return `from ${from} (no series end yet)`
			const n = Number(o.readings_count || 0)
			if (n > 0) return `${n} hours (bounds pending)`
			return 'No series yet — use Populate dataset'
		})

		const destroyMap = () => {
			if (map) {
				map.remove()
				map = null
				marker = null
			}
		}

		const addMarker = (lat, lng) => {
			if (!map) return
			const icon = createLocationPinIcon()
			if (marker) {
				marker.setLatLng([lat, lng])
				marker.setIcon(icon)
				return
			}
			marker = L.marker([lat, lng], { draggable: true, icon }).addTo(map)
			marker.on('dragend', (e) => {
				const pos = e.target.getLatLng()
				form.latitude = parseFloat(pos.lat.toFixed(4))
				form.longitude = parseFloat(pos.lng.toFixed(4))
			})
		}

		const initMap = () => {
			if (!mapContainer.value || map) return
			fixLeafletDefaultIcons()
			const defaultLat = form.latitude != null ? Number(form.latitude) : 39.5
			const defaultLng = form.longitude != null ? Number(form.longitude) : -8.0
			map = L.map(mapContainer.value, {
				zoomControl: true,
				attributionControl: false,
			}).setView([defaultLat, defaultLng], form.latitude != null ? 10 : 7)

			L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
				maxZoom: 18,
			}).addTo(map)

			if (form.latitude != null && form.longitude != null) {
				addMarker(Number(form.latitude), Number(form.longitude))
			}

			map.on('click', (e) => {
				form.latitude = parseFloat(e.latlng.lat.toFixed(4))
				form.longitude = parseFloat(e.latlng.lng.toFixed(4))
				addMarker(form.latitude, form.longitude)
			})

			// Leaflet needs a size pass after the container becomes visible
			setTimeout(() => map && map.invalidateSize(), 50)
		}

		const updateMapMarker = () => {
			if (!map || form.latitude == null || form.longitude == null) return
			const lat = Number(form.latitude)
			const lng = Number(form.longitude)
			if (Number.isNaN(lat) || Number.isNaN(lng)) return
			addMarker(lat, lng)
			map.panTo([lat, lng])
		}

		watch([isOpen, selectedObject], async () => {
			if (!isOpen.value || !selectedObject.value) {
				destroyMap()
				return
			}
			const o = selectedObject.value
			const lat = o.latitude ?? o.coordinates?.lat ?? null
			const lng = o.longitude ?? o.coordinates?.lng ?? null
			const resolved = resolveLocationChoice(o.location, lat, lng)
			form.locationChoice = resolved.choice
			form.locationLabel = resolved.label
			form.latitude = lat != null ? Number(lat) : null
			form.longitude = lng != null ? Number(lng) : null
			form.capacity_kwp = Number(o.capacity_kwp || 0)
			form.grid_connection_type = o.grid_connection_type || 'on_grid'
			form.grid_price_kwh = Number(o.grid_price_kwh ?? o.customData?.gridPriceKwh ?? 0.15)
			form.website = o.website || o.customData?.website || ''
			form.short_description = o.short_description || o.customData?.shortDescription || ''
			form.installation_date = (
				o.installation_date
				|| o.customData?.installationDate
				|| (o.installed_at || o.customData?.installedAt || '').toString().slice(0, 10)
				|| new Date().toISOString().slice(0, 10)
			)
			error.value = ''
			info.value = ''

			if (form.locationChoice === 'custom') {
				await nextTick()
				destroyMap()
				initMap()
			} else {
				destroyMap()
			}
		})

		watch(() => form.locationChoice, async (choice) => {
			if (!isOpen.value) return
			if (choice && choice !== 'custom') {
				const loc = LOCATIONS.find((l) => l.name === choice)
				if (loc) {
					form.latitude = loc.lat
					form.longitude = loc.lng
					form.locationLabel = loc.name
				}
				destroyMap()
			} else if (choice === 'custom') {
				const isKnownLabel = LOCATIONS.some((l) => l.name === form.locationLabel)
				if (!form.locationLabel || isKnownLabel) {
					const lat = form.latitude
					const lng = form.longitude
					if (lat != null && lng != null) {
						form.locationLabel = `Custom (${Number(lat).toFixed(2)}, ${Number(lng).toFixed(2)})`
					}
				}
				await nextTick()
				destroyMap()
				initMap()
			}
		})

		onUnmounted(() => {
			destroyMap()
		})

		const close = () => {
			destroyMap()
			store.closeEditStationModal()
		}

		const save = async () => {
			if (!selectedObject.value) return
			if (!form.locationChoice) {
				error.value = 'Please select a location'
				return
			}
			if (
				form.locationChoice === 'custom'
				&& (form.latitude == null || form.longitude == null
					|| Number.isNaN(Number(form.latitude))
					|| Number.isNaN(Number(form.longitude)))
			) {
				error.value = 'Please enter latitude and longitude'
				return
			}

			const locationName = form.locationChoice === 'custom'
				? (form.locationLabel?.trim()
					|| `Custom (${Number(form.latitude).toFixed(2)}, ${Number(form.longitude).toFixed(2)})`)
				: form.locationChoice

			busy.value = true
			error.value = ''
			try {
				await store.updateStation(selectedObject.value.id, {
					location: locationName,
					latitude: Number(form.latitude),
					longitude: Number(form.longitude),
					capacity_kwp: form.capacity_kwp,
					grid_price_kwh: form.grid_price_kwh,
					grid_connection_type: form.grid_connection_type,
					website: form.website,
					short_description: form.short_description,
					installation_date: form.installation_date,
				})
				close()
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Save failed'
			} finally {
				busy.value = false
			}
		}

		const viewDataset = () => {
			if (!selectedObject.value) return
			// Full series table for manual validation (not Analysis charts)
			store.openViewDatasetModal()
		}

		const populateDataset = async () => {
			if (!selectedObject.value) return
			if (!confirm('Populate missing series hours with ML simulation from installation date to now?\nMeasured hours will not be overwritten.')) {
				return
			}
			busy.value = true
			error.value = ''
			info.value = ''
			try {
				// Persist install date first so populate uses the correct start
				if (form.installation_date) {
					await store.updateStation(selectedObject.value.id, {
						installation_date: form.installation_date,
					})
				}
				const res = await store.populateStationSeries(selectedObject.value.id, {
					from: form.installation_date || undefined,
				})
				const r = res?.result || {}
				info.value = `Populate done: inserted ${r.inserted ?? 0}, skipped existing ${r.skipped_existing ?? 0}, skipped measured ${r.skipped_measured ?? 0}. Range ${res?.series_from_date || '?'} → ${res?.series_to_date || '?'}`
				await store.fetchObjects()
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Populate failed'
			} finally {
				busy.value = false
			}
		}

		return {
			isOpen,
			selectedObject,
			form,
			busy,
			error,
			info,
			seriesRangeLabel,
			locations: LOCATIONS,
			mapContainer,
			close,
			save,
			viewDataset,
			populateDataset,
			updateMapMarker,
		}
	},
}
</script>

<style scoped>
.modal-overlay {
	position: fixed; inset: 0; background: rgba(0,0,0,.55);
	display: flex; align-items: center; justify-content: center; z-index: 11000; padding: 20px;
}
.modal-card {
	width: 100%; max-width: 520px;
	max-height: 90vh;
	background: #ffffff;
	color: #1a1a1a;
	border-radius: 12px;
	overflow: hidden;
	box-shadow: 0 16px 48px rgba(0,0,0,.4);
	display: flex;
	flex-direction: column;
}
.modal-head, .modal-foot {
	display: flex; align-items: center; justify-content: space-between;
	padding: 12px 16px;
	background: #fafafa;
	flex-shrink: 0;
}
.modal-head { border-bottom: 1px solid #e6e6e6; }
.modal-foot { border-top: 1px solid #e6e6e6; justify-content: flex-end; gap: 8px; }
.modal-head h3 { margin: 0; font-size: 16px; font-weight: 700; color: #111; }
.modal-body {
	padding: 16px;
	display: grid;
	gap: 10px;
	background: #fff;
	overflow-y: auto;
}
label { display: grid; gap: 4px; font-size: 12px; color: #333; font-weight: 600; }
.dataset-box {
	border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px 12px; background: #fafafa;
	display: grid; gap: 8px;
}
.dataset-label { font-size: 12px; font-weight: 700; color: #333; }
.dataset-value { font-size: 13px; color: #111; font-family: ui-monospace, monospace; }
.dataset-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.hint { margin: 0; font-size: 11px; color: #666; font-weight: 400; line-height: 1.35; }
.ok { color: #2e7d32; font-size: 12px; margin: 0; }
input, textarea, select {
	border: 1px solid #cfcfcf;
	border-radius: 6px;
	padding: 8px 10px;
	font-size: 13px;
	background: #fff;
	color: #111;
	width: 100%;
	box-sizing: border-box;
}
.custom-location-section {
	display: grid;
	gap: 8px;
	padding: 10px;
	border: 1px solid #e6e6e6;
	border-radius: 8px;
	background: #fafafa;
}
.map-hint {
	margin: 0;
	font-size: 12px;
	color: #555;
	font-weight: 500;
}
.location-map {
	width: 100%;
	height: 200px;
	border-radius: 8px;
	border: 1px solid #cfcfcf;
	z-index: 1;
}
.coord-row {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 8px;
}
.btn {
	border: 1px solid #cfcfcf;
	background: #fff;
	color: #111;
	border-radius: 6px;
	padding: 8px 12px;
	cursor: pointer;
	font-weight: 600;
}
.btn.primary { background: #0082c9; color: #fff; border-color: #0082c9; }
.btn:disabled { opacity: .6; cursor: not-allowed; }
.x {
	border: 1px solid #ddd;
	background: #fff;
	color: #333;
	border-radius: 6px;
	padding: 4px 10px;
	cursor: pointer;
	font-size: 12px;
}
.err { color: #b71c1c; margin: 0; font-size: 12px; }
</style>
