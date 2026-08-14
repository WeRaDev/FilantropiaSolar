<template>
	<div v-if="isOpen && selectedObject" class="modal-overlay" @click.self="close">
		<div class="modal-card">
			<header class="modal-head">
				<div>
					<h3>Dataset — {{ selectedObject.name }}</h3>
					<p class="sub">
						NC series SoT (measured + populated). Installation date:
						<strong>{{ installDate || '—' }}</strong>
						· Series range:
						<strong>{{ seriesRange || 'no series' }}</strong>
					</p>
				</div>
				<button type="button" class="x" @click="close">Close</button>
			</header>

			<div class="toolbar">
				<label>
					From
					<input v-model="from" type="date" @change="load">
				</label>
				<label>
					To
					<input v-model="to" type="date" @change="load">
				</label>
				<label>
					Limit
					<input v-model.number="limit" type="number" min="100" max="20000" step="100" @change="load">
				</label>
				<button type="button" class="btn" :disabled="busy" @click="load">Reload</button>
				<button type="button" class="btn" :disabled="busy || !rows.length" @click="exportCsv">Export CSV</button>
			</div>

			<p v-if="error" class="err">{{ error }}</p>
			<p v-if="busy" class="muted">Loading series…</p>
			<p v-else class="muted">{{ rows.length }} rows · source {{ source }}</p>

			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th>Timestamp</th>
							<th>Production kWh</th>
							<th>Savings €</th>
							<th>Temp °C</th>
							<th>Cloud %</th>
							<th>Radiation</th>
							<th>Provenance</th>
							<th>Capacity</th>
							<th>Price</th>
							<th>Grid</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(r, i) in rows" :key="i">
							<td class="mono">{{ r.timestamp }}</td>
							<td>{{ fmt(r.production_kwh, 3) }}</td>
							<td>{{ fmt(r.savings_eur, 4) }}</td>
							<td>{{ fmt(r.temperature_c, 1) }}</td>
							<td>{{ r.cloud_cover_pct ?? '—' }}</td>
							<td>{{ fmt(r.solar_radiation_wm2, 0) }}</td>
							<td>
								<span class="prov" :class="r.provenance">{{ r.provenance || '—' }}</span>
							</td>
							<td>{{ fmt(r.capacity_kwp, 2) }}</td>
							<td>{{ fmt(r.grid_price_kwh, 3) }}</td>
							<td>{{ r.grid_connection_type || '—' }}</td>
						</tr>
						<tr v-if="!busy && !rows.length">
							<td colspan="10" class="empty">No series rows. Use Edit → Populate dataset.</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useAppStore } from '../store/app.js'

export default {
	name: 'ViewDatasetModal',
	setup() {
		const store = useAppStore()
		const isOpen = computed(() => store.viewDatasetModalOpen)
		const selectedObject = computed(() => store.selectedObject)
		const busy = ref(false)
		const error = ref('')
		const rows = ref([])
		const source = ref('')
		const from = ref('')
		const to = ref('')
		const limit = ref(5000)

		const installDate = computed(() => {
			const o = selectedObject.value
			return (o?.installation_date || o?.customData?.installationDate || '').toString().slice(0, 10)
		})
		const seriesRange = computed(() => {
			const o = selectedObject.value
			const a = (o?.series_from_date || o?.customData?.seriesFromDate || '').toString().slice(0, 10)
			const b = (o?.series_to_date || o?.customData?.seriesToDate || '').toString().slice(0, 10)
			if (a && b) return `${a} → ${b}`
			return ''
		})

		const fmt = (v, d = 2) => {
			if (v === null || v === undefined || v === '') return '—'
			const n = Number(v)
			return Number.isFinite(n) ? n.toFixed(d) : '—'
		}

		const close = () => store.closeViewDatasetModal()

		const load = async () => {
			if (!selectedObject.value) return
			busy.value = true
			error.value = ''
			try {
				const data = await store.fetchStationSeries(selectedObject.value.id, {
					from: from.value || undefined,
					to: to.value || undefined,
					limit: limit.value,
				})
				rows.value = Array.isArray(data?.readings) ? data.readings : []
				source.value = data?.source || 'unknown'
				// Prefer server series bounds for display refresh
				if (data?.series_from_date && selectedObject.value) {
					// no mutation required; label uses store object
				}
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Failed to load series'
				rows.value = []
			} finally {
				busy.value = false
			}
		}

		const exportCsv = () => {
			if (!rows.value.length) return
			const cols = [
				'timestamp', 'production_kwh', 'savings_eur', 'temperature_c', 'cloud_cover_pct',
				'solar_radiation_wm2', 'provenance', 'capacity_kwp', 'grid_price_kwh',
				'grid_connection_type', 'self_consumption_factor',
			]
			const lines = [cols.join(',')]
			for (const r of rows.value) {
				lines.push(cols.map((c) => {
					const v = r[c]
					if (v === null || v === undefined) return ''
					const s = String(v)
					return s.includes(',') ? `"${s}"` : s
				}).join(','))
			}
			const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
			const url = URL.createObjectURL(blob)
			const a = document.createElement('a')
			const name = String(selectedObject.value?.name || 'station').replace(/[^a-zA-Z0-9_-]+/g, '_')
			a.href = url
			a.download = `${name}_series.csv`
			document.body.appendChild(a)
			a.click()
			document.body.removeChild(a)
			URL.revokeObjectURL(url)
		}

		watch([isOpen, selectedObject], async ([open]) => {
			if (!open || !selectedObject.value) {
				rows.value = []
				return
			}
			const o = selectedObject.value
			from.value = (o.series_from_date || o.customData?.seriesFromDate || o.installation_date || o.customData?.installationDate || '').toString().slice(0, 10)
			to.value = (o.series_to_date || o.customData?.seriesToDate || '').toString().slice(0, 10)
			await load()
		})

		return {
			isOpen,
			selectedObject,
			busy,
			error,
			rows,
			source,
			from,
			to,
			limit,
			installDate,
			seriesRange,
			fmt,
			close,
			load,
			exportCsv,
		}
	},
}
</script>

<style scoped>
.modal-overlay {
	position: fixed; inset: 0; background: rgba(0, 0, 0, 0.55);
	display: flex; align-items: center; justify-content: center;
	z-index: 12000; padding: 16px;
}
.modal-card {
	width: min(1100px, 96vw); height: min(85vh, 900px);
	background: #fff; color: #111; border-radius: 12px;
	display: flex; flex-direction: column; overflow: hidden;
	box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
}
.modal-head {
	display: flex; justify-content: space-between; gap: 12px;
	padding: 12px 16px; border-bottom: 1px solid #e6e6e6; background: #fafafa;
}
.modal-head h3 { margin: 0 0 4px; font-size: 16px; }
.sub { margin: 0; font-size: 12px; color: #555; }
.x, .btn {
	border: 1px solid #ccc; background: #fff; border-radius: 6px;
	padding: 6px 10px; cursor: pointer; font-size: 12px;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.toolbar {
	display: flex; flex-wrap: wrap; gap: 10px; align-items: end;
	padding: 10px 16px; border-bottom: 1px solid #eee;
}
.toolbar label { display: grid; gap: 2px; font-size: 11px; font-weight: 600; color: #444; }
.toolbar input { border: 1px solid #ccc; border-radius: 6px; padding: 6px 8px; font-size: 12px; }
.table-wrap { flex: 1; overflow: auto; padding: 0 0 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { border-bottom: 1px solid #eee; padding: 6px 8px; text-align: left; white-space: nowrap; }
th { position: sticky; top: 0; background: #f7f7f7; z-index: 1; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.prov { padding: 1px 6px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.prov.measured { background: #e8f5e9; color: #2e7d32; }
.prov.simulated { background: #fff8e1; color: #f9a825; }
.err { color: #c62828; padding: 0 16px; font-size: 12px; }
.muted { color: #777; padding: 0 16px 8px; font-size: 12px; margin: 0; }
.empty { text-align: center; color: #888; padding: 24px !important; }
</style>
