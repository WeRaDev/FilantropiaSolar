<template>
	<div v-if="open" class="view-data-overlay" @click.self="$emit('close')">
		<div class="view-data-modal" role="dialog" aria-labelledby="view-data-title">
			<header class="view-data-header">
				<div>
					<h3 id="view-data-title">Station data</h3>
					<p class="view-data-sub">
						{{ stationName }}
						<span v-if="rangeLabel"> · {{ rangeLabel }}</span>
						<span v-if="modeLabel"> · {{ modeLabel }}</span>
						<span> · {{ rows.length }} rows</span>
					</p>
				</div>
				<div class="view-data-actions">
					<button type="button" class="btn-secondary" :disabled="!rows.length" @click="copyCsv">
						Copy CSV
					</button>
					<button type="button" class="btn-close" title="Close" @click="$emit('close')">
						<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M18 6 6 18M6 6l12 12" />
						</svg>
					</button>
				</div>
			</header>
			<div class="view-data-body">
				<p v-if="!rows.length" class="empty">No rows in the current analysis window.</p>
				<table v-else class="data-table">
					<thead>
						<tr>
							<th>Timestamp (UTC)</th>
							<th>Hour</th>
							<th>Production (kWh)</th>
							<th>Source</th>
							<th>Temp (°C)</th>
							<th>Cloud (%)</th>
							<th>Humidity (%)</th>
							<th>Wind (m/s)</th>
							<th>Radiation</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="(row, idx) in rows" :key="idx">
							<td class="mono">{{ row.timestamp }}</td>
							<td>{{ row.hourLabel }}</td>
							<td class="num">{{ row.productionLabel }}</td>
							<td>
								<span class="prov" :class="row.provenanceClass">{{ row.provenanceLabel }}</span>
							</td>
							<td class="num">{{ row.tempLabel }}</td>
							<td class="num">{{ row.cloudLabel }}</td>
							<td class="num">{{ row.humidityLabel }}</td>
							<td class="num">{{ row.windLabel }}</td>
							<td class="num">{{ row.radiationLabel }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
	</div>
</template>

<script>
import { computed } from 'vue'

function rowHour(h) {
	if (h?.hour !== undefined && h?.hour !== null && h?.hour !== '') {
		const n = Number(h.hour)
		if (!Number.isNaN(n)) return n
	}
	const ts = String(h?.timestamp || '')
	const m = ts.match(/T(\d{1,2})/) || ts.match(/\s(\d{2}):/)
	return m ? parseInt(m[1], 10) : null
}

function fmt(v, digits = 2) {
	if (v === null || v === undefined || v === '') return '—'
	const n = Number(v)
	if (Number.isNaN(n)) return '—'
	return n.toFixed(digits)
}

function provenanceOf(h, analysisMode) {
	if (analysisMode === 'predicted') {
		return { label: 'SIMULATED', cls: 'simulated' }
	}
	const p = (h?.provenance || '').toLowerCase()
	if (p === 'measured') return { label: 'HISTORICAL', cls: 'historical' }
	if (p === 'simulated') return { label: 'SIMULATED', cls: 'simulated' }
	if (h?.production_kwh == null || h?.production_kwh === '') {
		return { label: '—', cls: 'none' }
	}
	return { label: 'SIMULATED', cls: 'simulated' }
}

export default {
	name: 'ViewDataTable',
	props: {
		open: { type: Boolean, default: false },
		hourlyData: { type: Array, default: () => [] },
		stationName: { type: String, default: '' },
		rangeLabel: { type: String, default: '' },
		modeLabel: { type: String, default: '' },
		analysisMode: { type: String, default: 'historical' },
	},
	emits: ['close'],
	setup(props) {
		const rows = computed(() => {
			const list = Array.isArray(props.hourlyData) ? [...props.hourlyData] : []
			list.sort((a, b) => String(a.timestamp || '').localeCompare(String(b.timestamp || '')))
			return list.map((h) => {
				const hour = rowHour(h)
				const prov = provenanceOf(h, props.analysisMode)
				return {
					timestamp: h.timestamp || '—',
					hourLabel: hour === null ? '—' : `${hour}:00`,
					productionLabel: fmt(h.production_kwh, 4),
					provenanceLabel: prov.label,
					provenanceClass: prov.cls,
					tempLabel: fmt(h.temperature ?? h.temperature_2m, 1),
					cloudLabel: fmt(h.cloud_cover, 0),
					humidityLabel: fmt(h.humidity ?? h.relative_humidity_2m, 0),
					windLabel: fmt(h.wind_speed ?? h.wind_speed_10m, 1),
					radiationLabel: fmt(h.radiation ?? h.shortwave_radiation, 1),
				}
			})
		})

		const copyCsv = async () => {
			const header = [
				'timestamp_utc',
				'hour',
				'production_kwh',
				'source',
				'temperature_c',
				'cloud_cover_pct',
				'humidity_pct',
				'wind_speed_ms',
				'radiation',
			]
			const lines = [header.join(',')]
			for (const r of rows.value) {
				lines.push([
					r.timestamp,
					r.hourLabel,
					r.productionLabel,
					r.provenanceLabel,
					r.tempLabel,
					r.cloudLabel,
					r.humidityLabel,
					r.windLabel,
					r.radiationLabel,
				].map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
			}
			const csv = lines.join('\n')
			try {
				await navigator.clipboard.writeText(csv)
			} catch {
				const ta = document.createElement('textarea')
				ta.value = csv
				document.body.appendChild(ta)
				ta.select()
				document.execCommand('copy')
				document.body.removeChild(ta)
			}
		}

		return { rows, copyCsv }
	},
}
</script>

<style scoped>
.view-data-overlay {
	position: fixed;
	inset: 0;
	z-index: 12000;
	background: rgba(0, 0, 0, 0.45);
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 24px;
}

.view-data-modal {
	width: min(1100px, 96vw);
	max-height: 85vh;
	background: #fff;
	border-radius: 12px;
	box-shadow: 0 16px 48px rgba(0, 0, 0, 0.28);
	display: flex;
	flex-direction: column;
	overflow: hidden;
	color: #1a1a1a;
}

.view-data-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 16px;
	padding: 14px 16px;
	border-bottom: 1px solid #e6e6e6;
	background: #fafafa;
}

.view-data-header h3 {
	margin: 0 0 4px;
	font-size: 16px;
	font-weight: 700;
}

.view-data-sub {
	margin: 0;
	font-size: 12px;
	color: #666;
}

.view-data-actions {
	display: flex;
	align-items: center;
	gap: 8px;
}

.btn-secondary {
	border: 1px solid #ccc;
	background: #fff;
	border-radius: 6px;
	padding: 6px 10px;
	font-size: 12px;
	cursor: pointer;
}

.btn-secondary:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}

.btn-close {
	border: none;
	background: transparent;
	cursor: pointer;
	padding: 4px;
	display: flex;
}

.view-data-body {
	overflow: auto;
	padding: 0;
}

.empty {
	padding: 24px;
	margin: 0;
	color: #666;
}

.data-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 12px;
}

.data-table th,
.data-table td {
	padding: 8px 10px;
	border-bottom: 1px solid #eee;
	text-align: left;
	white-space: nowrap;
}

.data-table th {
	position: sticky;
	top: 0;
	background: #f5f5f5;
	font-weight: 600;
	z-index: 1;
}

.data-table tbody tr:hover {
	background: #fafafa;
}

.num {
	font-variant-numeric: tabular-nums;
	text-align: right;
}

.mono {
	font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
	font-size: 11px;
}

.prov {
	display: inline-block;
	padding: 2px 8px;
	border-radius: 4px;
	font-size: 10px;
	font-weight: 600;
	text-transform: uppercase;
}

.prov.historical {
	background: #e8f5e9;
	color: #2e7d32;
}

.prov.simulated {
	background: #fff3e0;
	color: #ef6c00;
}

.prov.none {
	background: #f0f0f0;
	color: #757575;
}
</style>
