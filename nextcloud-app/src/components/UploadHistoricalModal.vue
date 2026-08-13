<template>
	<teleport to="body">
		<div
			v-if="isOpen"
			class="modal-overlay upload-historical-overlay"
			@click.self="close"
		>
			<div
				class="modal-card upload-historical-card"
				role="dialog"
				aria-modal="true"
				aria-labelledby="upload-hist-title"
			>
			<header class="modal-head">
				<div>
					<h3 id="upload-hist-title">Add historical data</h3>
					<p class="sub">
						{{ selectedObject?.name || 'Station' }}
						— measured rows win over simulated hours
					</p>
				</div>
				<button type="button" class="x" @click="close">Close</button>
			</header>
			<div class="modal-body">
				<p class="hint">
					CSV columns:
					<code>timestamp</code> (or Date) and
					<code>production_kwh</code> (or Produced Energy).
					Hours use Europe/Lisbon measured provenance.
				</p>

				<div class="source-tabs">
					<button
						type="button"
						class="tab"
						:class="{ active: source === 'computer' }"
						@click="source = 'computer'"
					>
						From computer
					</button>
					<button
						type="button"
						class="tab"
						:class="{ active: source === 'nextcloud' }"
						@click="source = 'nextcloud'"
					>
						From Nextcloud Files
					</button>
				</div>

				<div v-if="source === 'computer'">
					<div
						class="file-upload-area"
						@click="triggerFile"
						@dragover.prevent
						@drop.prevent="onDrop"
					>
						<input
							ref="fileInput"
							type="file"
							accept=".csv,.xlsx,.xls,text/csv"
							hidden
							@change="onFile"
						>
						<span v-if="!fileName">Drop CSV or click to browse your computer</span>
						<span v-else>{{ fileName }} ({{ readings.length }} rows parsed)</span>
					</div>
				</div>

				<div v-else class="nc-files-block">
					<button type="button" class="btn" :disabled="busy" @click="pickFromNextcloud">
						Choose file in Nextcloud…
					</button>
					<p v-if="ncPath" class="path-line">Selected: <code>{{ ncPath }}</code></p>
					<p class="hint-sm">
						Or paste a path under your Files home (e.g. <code>Reports/station.csv</code>):
					</p>
					<input v-model="ncPathManual" type="text" class="path-input" placeholder="path/to/file.csv">
				</div>

				<p v-if="error" class="err">{{ error }}</p>
				<p v-if="result" class="ok">
					Imported {{ result.imported }} measured
					<span v-if="result.overwritten_simulated">
						(overwrote {{ result.overwritten_simulated }} simulated)
					</span>
					<span v-if="result.skipped">, skipped {{ result.skipped }}</span>
				</p>
			</div>
			<footer class="modal-foot">
				<button type="button" class="btn" :disabled="busy" @click="close">Cancel</button>
				<button
					type="button"
					class="btn primary"
					:disabled="busy || !canSubmit"
					@click="submit"
				>
					{{ busy ? 'Uploading…' : 'Import measured' }}
				</button>
			</footer>
			</div>
		</div>
	</teleport>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useAppStore } from '../store/app.js'

function parseCsv(text) {
	const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
	if (lines.length < 2) return []
	const split = (line) => {
		const out = []
		let cur = ''
		let q = false
		for (let i = 0; i < line.length; i++) {
			const c = line[i]
			if (c === '"') {
				q = !q
				continue
			}
			if (c === ',' && !q) {
				out.push(cur.trim())
				cur = ''
				continue
			}
			cur += c
		}
		out.push(cur.trim())
		return out
	}
	const header = split(lines[0]).map((h) => h.toLowerCase().replace(/[^a-z0-9]+/g, '_'))
	const tsIdx = header.findIndex((h) => h.includes('timestamp') || h === 'date' || h.includes('time'))
	const pIdx = header.findIndex((h) => h.includes('production') || h.includes('produced') || h.includes('energy') || h.includes('kwh'))
	if (tsIdx < 0 || pIdx < 0) {
		throw new Error('CSV needs timestamp/date and production_kwh columns')
	}
	const rows = []
	for (let i = 1; i < lines.length; i++) {
		const cols = split(lines[i])
		const ts = cols[tsIdx]
		const prod = parseFloat(String(cols[pIdx]).replace(',', '.'))
		if (!ts || Number.isNaN(prod)) continue
		rows.push({ timestamp: ts, production_kwh: prod })
	}
	return rows
}

export default {
	name: 'UploadHistoricalModal',
	setup() {
		const store = useAppStore()
		const isOpen = computed(() => store.uploadHistoricalModalOpen)
		const selectedObject = computed(() => store.selectedObject)
		const fileInput = ref(null)
		const fileName = ref('')
		const readings = ref([])
		const error = ref('')
		const result = ref(null)
		const busy = ref(false)
		const source = ref('computer')
		const ncPath = ref('')
		const ncPathManual = ref('')

		const canSubmit = computed(() => {
			if (source.value === 'computer') return readings.value.length > 0
			return Boolean((ncPath.value || ncPathManual.value || '').trim())
		})

		watch(isOpen, (open) => {
			if (open) {
				fileName.value = ''
				readings.value = []
				error.value = ''
				result.value = null
				source.value = 'computer'
				ncPath.value = ''
				ncPathManual.value = ''
			}
		})

		const close = () => store.closeUploadHistoricalModal()
		const triggerFile = () => fileInput.value?.click()

		const loadText = async (file) => {
			const name = (file.name || '').toLowerCase()
			if (name.endsWith('.xlsx') || name.endsWith('.xls')) {
				throw new Error('Please export Excel as CSV for upload (xlsx parsing not bundled here).')
			}
			return file.text()
		}

		const handleFile = async (file) => {
			error.value = ''
			result.value = null
			fileName.value = file.name
			try {
				const text = await loadText(file)
				readings.value = parseCsv(text)
				if (!readings.value.length) {
					error.value = 'No valid rows found in file'
				}
			} catch (e) {
				readings.value = []
				error.value = e.message || String(e)
			}
		}

		const onFile = (e) => {
			const f = e.target.files?.[0]
			if (f) handleFile(f)
		}
		const onDrop = (e) => {
			const f = e.dataTransfer?.files?.[0]
			if (f) handleFile(f)
		}

		const pickFromNextcloud = async () => {
			error.value = ''
			// Prefer OC.dialogs.filepicker when available (no extra webpack graph).
			try {
				const OC = window.OC
				if (OC?.dialogs?.filepicker) {
					await new Promise((resolve) => {
						OC.dialogs.filepicker(
							'Select measured CSV',
							(path) => {
								if (path) {
									const clean = String(path).replace(/^\/+/, '')
									ncPath.value = clean
									ncPathManual.value = clean
								}
								resolve()
							},
							false,
							['text/csv', 'text/plain'],
							true,
						)
					})
					return
				}
			} catch (e) {
				// fall through to path paste
			}
			error.value = 'File picker unavailable in this view — paste a path under your Files home below.'
		}

		const submit = async () => {
			if (!selectedObject.value) return
			busy.value = true
			error.value = ''
			result.value = null
			try {
				if (source.value === 'nextcloud') {
					const path = (ncPathManual.value || ncPath.value || '').trim()
					if (!path) throw new Error('Choose or enter a Nextcloud Files path')
					const data = await store.importMeasuredFromFiles(selectedObject.value.id, path)
					result.value = data
				} else {
					if (!readings.value.length) throw new Error('No rows to import')
					const data = await store.uploadMeasuredReadings(
						selectedObject.value.id,
						readings.value,
					)
					result.value = data
				}
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Upload failed'
			} finally {
				busy.value = false
			}
		}

		return {
			isOpen,
			selectedObject,
			fileInput,
			fileName,
			readings,
			error,
			result,
			busy,
			source,
			ncPath,
			ncPathManual,
			canSubmit,
			close,
			triggerFile,
			onFile,
			onDrop,
			pickFromNextcloud,
			submit,
		}
	},
}
</script>

<style scoped>
/* Above analytics modal (z-index 10000) and View data (12000) */
.upload-historical-overlay {
	position: fixed;
	inset: 0;
	z-index: 20050;
	background: rgba(0, 0, 0, 0.55);
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
	box-sizing: border-box;
}
.upload-historical-card,
.upload-historical-card * {
	box-sizing: border-box;
}
.upload-historical-card {
	width: min(560px, 96vw);
	background: #ffffff;
	border-radius: 12px;
	box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35);
	color: #000000;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}
.modal-head {
	display: flex;
	justify-content: space-between;
	align-items: flex-start;
	gap: 12px;
	padding: 14px 16px;
	border-bottom: 1px solid #e0e0e0;
	background: #f5f5f5;
	color: #000000;
}
.modal-head h3 {
	margin: 0 0 4px;
	font-size: 16px;
	font-weight: 700;
	color: #000000;
}
.sub {
	margin: 0;
	font-size: 12px;
	color: #000000;
}
.x {
	border: 1px solid #ccc;
	background: #fff;
	border-radius: 6px;
	cursor: pointer;
	font-size: 13px;
	color: #000000;
	padding: 4px 10px;
}
.modal-body {
	padding: 16px;
	display: flex;
	flex-direction: column;
	gap: 12px;
	color: #000000;
	background: #ffffff;
}
.hint {
	margin: 0;
	font-size: 13px;
	color: #000000;
	line-height: 1.45;
}
.hint code,
.path-line code {
	color: #000000;
	background: #f0f0f0;
	padding: 1px 4px;
	border-radius: 3px;
}
.hint-sm {
	margin: 8px 0 0;
	font-size: 12px;
	color: #000000;
}
.source-tabs {
	display: flex;
	gap: 8px;
}
.tab {
	flex: 1;
	border: 1px solid #999;
	background: #f0f0f0;
	border-radius: 6px;
	padding: 8px 10px;
	cursor: pointer;
	font-size: 13px;
	color: #000000;
}
.tab.active {
	background: #0082c9;
	border-color: #0082c9;
	color: #ffffff;
}
.file-upload-area {
	border: 1px dashed #666;
	border-radius: 8px;
	padding: 28px 12px;
	text-align: center;
	cursor: pointer;
	background: #fafafa;
	font-size: 13px;
	color: #000000;
}
.file-upload-area:hover {
	border-color: #000;
	background: #f5f5f5;
}
.nc-files-block {
	display: flex;
	flex-direction: column;
	gap: 8px;
	color: #000000;
}
.path-line {
	margin: 0;
	font-size: 12px;
	word-break: break-all;
	color: #000000;
}
.path-input {
	width: 100%;
	padding: 8px 10px;
	border: 1px solid #666;
	border-radius: 6px;
	font-size: 13px;
	color: #000000;
	background: #ffffff;
}
.err {
	color: #b71c1c;
	margin: 0;
	font-size: 13px;
}
.ok {
	color: #1b5e20;
	margin: 0;
	font-size: 13px;
}
.modal-foot {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
	padding: 12px 16px;
	border-top: 1px solid #e0e0e0;
	background: #fafafa;
}
.btn {
	border: 1px solid #666;
	background: #ffffff;
	border-radius: 6px;
	padding: 8px 14px;
	cursor: pointer;
	font-size: 13px;
	color: #000000;
}
.btn.primary {
	background: #0082c9;
	border-color: #0082c9;
	color: #ffffff;
}
.btn:disabled {
	opacity: 0.5;
	cursor: not-allowed;
}
</style>
