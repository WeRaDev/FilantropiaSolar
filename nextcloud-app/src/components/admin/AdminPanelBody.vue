<template>
	<div class="admin-body">
		<div v-if="loading" class="loading-state">
			<div class="spinner" />
			<span>Loading admin dashboard…</span>
		</div>
		<template v-else>
			<section class="admin-section">
				<h3>Settings</h3>
				<div class="settings-row">
					<label for="ml-service-url">ML Service URL</label>
					<input id="ml-service-url" v-model="settings.ml_service_url" type="url">
					<button class="btn-action" :disabled="actionLoading" @click="saveSettings">Save</button>
				</div>
			</section>

			<AdminMlControls
				:model-info="modelInfo"
				:cache-status="cacheStatus"
				@refresh="refreshAll"
				@clear-cache="clearCache"
				@train-all="trainAll"
			/>

			<AdminGlobalStations
				:stations="stations"
				:lifecycle-filter="stationFilters.lifecycle_state"
				:source-filter="stationFilters.source"
				:include-soft-removed="stationFilters.include_soft_removed"
				:counts="lifecycleCounts"
				:disabled="actionLoading"
				@create="openCreate"
				@edit="openEdit"
				@delete="removeStation"
				@train="trainStation"
				@reimport="reimportDataset"
				@promote="promoteStation"
				@install="installStation"
				@soft-remove="softRemoveStation"
				@public-archive="archiveStation"
				@public-unarchive="unarchiveStation"
				@filter-lifecycle="onFilterLifecycle"
				@filter-source="onFilterSource"
				@filter-soft-removed="onFilterSoftRemoved"
			/>

			<section v-if="showForm" class="admin-section station-form">
				<h3>{{ form.id ? 'Edit Global Station' : 'Create Global Station' }}</h3>
				<div class="form-grid">
					<input v-model="form.name" placeholder="Name">
					<input v-model="form.location" placeholder="Location">
					<input v-model="form.serial_number" placeholder="Serial Number">
					<input v-model="form.capacity_kwp" placeholder="Capacity kWp" type="number" step="0.01">
					<input v-model="form.latitude" placeholder="Latitude" type="number" step="0.000001">
					<input v-model="form.longitude" placeholder="Longitude" type="number" step="0.000001">
				</div>
				<div class="section-actions">
					<button class="btn-action" :disabled="actionLoading" @click="submitStation">Save Station</button>
					<button class="btn-action" @click="showForm = false">Cancel</button>
				</div>
			</section>

			<p v-if="message" class="feedback success">{{ message }}</p>
			<p v-if="error" class="feedback error">{{ error }}</p>
		</template>
	</div>
</template>

<script>
import { onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAdminStore } from '../../store/admin.js'
import AdminMlControls from './AdminMlControls.vue'
import AdminGlobalStations from './AdminGlobalStations.vue'

export default {
	name: 'AdminPanelBody',
	components: {
		AdminMlControls,
		AdminGlobalStations,
	},
	setup() {
		const store = useAdminStore()
		const {
			loading,
			actionLoading,
			stations,
			stationFilters,
			cacheStatus,
			modelInfo,
			settings,
			message,
			error,
			lifecycleCounts,
		} = storeToRefs(store)

		const form = reactive({
			id: null,
			name: '',
			location: '',
			latitude: '',
			longitude: '',
			capacity_kwp: '',
			serial_number: '',
		})
		const showForm = ref(false)

		const resetForm = () => {
			form.id = null
			form.name = ''
			form.location = ''
			form.latitude = ''
			form.longitude = ''
			form.capacity_kwp = ''
			form.serial_number = ''
		}

		const openCreate = () => {
			resetForm()
			showForm.value = true
		}

		const openEdit = (station) => {
			form.id = station.id
			form.name = station.name || ''
			form.location = station.location || ''
			form.latitude = String(station.latitude ?? '')
			form.longitude = String(station.longitude ?? '')
			form.capacity_kwp = String(station.capacity_kwp ?? '')
			form.serial_number = station.serial_number || ''
			showForm.value = true
		}

		const submitStation = async () => {
			await store.saveStation({
				id: form.id,
				name: form.name,
				location: form.location,
				latitude: Number(form.latitude),
				longitude: Number(form.longitude),
				capacity_kwp: Number(form.capacity_kwp),
				serial_number: form.serial_number,
			})
			showForm.value = false
		}

		const removeStation = async (station) => {
			if (!confirm(`Delete ${station.name}?`)) {
				return
			}
			await store.deleteStation(station.id)
		}

		const trainStation = async (station) => {
			await store.trainStation(station.installation_id || station.serial_number || String(station.id))
		}

		const promoteStation = async (station) => {
			if (!confirm(`Promote "${station.name}" to Planned (public map)?`)) {
				return
			}
			await store.promotePlanned(station)
		}

		const installStation = async (station) => {
			if (!confirm(`Mark "${station.name}" as installed (Running / Existing on public map)?\nWon in CRM is not enough — this is the ops install step.`)) {
				return
			}
			await store.markInstalled(station)
		}

		const softRemoveStation = async (station) => {
			if (!confirm(`Soft-remove "${station.name}" from public listing?\nRow is kept; hard delete remains dataset-only.`)) {
				return
			}
			await store.softRemove(station)
		}

		const archiveStation = async (station) => {
			if (!confirm(`Archive "${station.name}" from the public map?\nIt stays Running and still counts in stats.`)) {
				return
			}
			await store.setPublicArchived(station, true)
		}

		const unarchiveStation = async (station) => {
			await store.setPublicArchived(station, false)
		}

		const onFilterLifecycle = async (value) => {
			await store.setLifecycleFilter(value)
		}

		const onFilterSource = async (value) => {
			await store.setSourceFilter(value)
		}

		const onFilterSoftRemoved = async (value) => {
			await store.setIncludeSoftRemoved(value)
		}

		const refreshAll = async () => {
			await Promise.all([
				store.fetchStations(),
				store.fetchModelInfo(),
				store.fetchCacheStatus(),
			])
		}

		onMounted(async () => {
			await store.loadAll()
		})

		return {
			loading,
			actionLoading,
			stations,
			stationFilters,
			lifecycleCounts,
			cacheStatus,
			modelInfo,
			settings,
			message,
			error,
			form,
			showForm,
			openCreate,
			openEdit,
			submitStation,
			removeStation,
			trainStation,
			promoteStation,
			installStation,
			softRemoveStation,
			archiveStation,
			unarchiveStation,
			onFilterLifecycle,
			onFilterSource,
			onFilterSoftRemoved,
			refreshAll,
			saveSettings: () => store.saveSettings(),
			clearCache: () => store.clearCache(),
			trainAll: () => store.trainAll(),
			reimportDataset: () => store.reimportDataset(),
		}
	},
}
</script>

<style scoped>
.admin-body {
	padding: 16px 20px 24px;
	height: 100%;
	overflow-y: auto;
	box-sizing: border-box;
}

.admin-section {
	margin-bottom: 18px;
}

.admin-section h3 {
	margin: 0 0 10px;
	font-size: 14px;
	text-transform: uppercase;
}

.loading-state {
	display: flex;
	gap: 10px;
	align-items: center;
	justify-content: center;
	min-height: 140px;
}

.spinner {
	width: 26px;
	height: 26px;
	border: 3px solid #ddd;
	border-top-color: #0082c9;
	border-radius: 50%;
	animation: spin 1s linear infinite;
}

.settings-row {
	display: grid;
	grid-template-columns: 130px 1fr auto;
	gap: 10px;
	align-items: center;
}

.settings-row input,
.form-grid input {
	border: 1px solid var(--color-border, #d9d9d9);
	border-radius: 6px;
	padding: 7px 10px;
}

.form-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(120px, 1fr));
	gap: 10px;
	margin-bottom: 10px;
}

.section-actions {
	display: flex;
	gap: 8px;
}

.btn-action {
	border: 1px solid var(--color-border, #d9d9d9);
	border-radius: 6px;
	background: #fff;
	padding: 7px 10px;
	cursor: pointer;
}

.feedback {
	margin: 8px 0 0;
	padding: 8px 10px;
	border-radius: 6px;
}

.feedback.success {
	color: #2e7d32;
	background: #e8f5e9;
}

.feedback.error {
	color: #c62828;
	background: #ffebee;
}

@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}
</style>
