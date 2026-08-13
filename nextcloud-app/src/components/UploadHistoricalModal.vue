<template>
	<div v-if="isOpen" class="modal-overlay" @click.self="close">
		<div class="modal-card" role="dialog" aria-labelledby="upload-hist-title">
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
					Upload CSV/Excel with columns
					<code>timestamp</code> (or Date) and
					<code>production_kwh</code> (or Produced Energy).
					Hours are stored as Europe/Lisbon measured provenance.
				</p>
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
					<span v-if="!fileName">Drop file or click to browse</span>
					<span v-else>{{ fileName }} ({{ readings.length }} rows parsed)</span>
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
					:disabled="busy || !readings.length"
					@click="submit"
				>
					{{ busy ? 'Uploading…' : 'Upload measured' }}
				</button>
			</footer>
		</div>
	</div>
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

		watch(isOpen, (open) => {
			if (open) {
				fileName.value = ''
				readings.value = []
				error.value = ''
				result.value = null
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

		const submit = async () => {
			if (!selectedObject.value || !readings.value.length) return
			busy.value = true
			error.value = ''
			result.value = null
			try {
				const data = await store.uploadMeasuredReadings(
					selectedObject.value.id,
					readings.value,
				)
				result.value = data
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
			close,
			triggerFile,
			onFile,
			onDrop,
			submit,
		}
	},
}
</script>

<style scoped>
.modal-overlay {
	position: fixed;
	inset: 0;
	z-index: 13000;
	background: rgba(0, 0, 0, 0.45);
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
}
.modal-card {
	width: min(520px, 96vw);
	background: #fff;
	border-radius: 12px;
	box-shadow: 0 16px 48px rgba(0, 0, 0, 0.28);
	color: #1a1a1a;
	display: flex;
	flex-direction: column;
	overflow: hidden;
}
.modal-head {
	display: flex;
	justify-content: space-between;
	gap: 12px;
	padding: 14px 16px;
	border-bottom: 1px solid #e6e6e6;
	background: #fafafa;
}
.modal-head h3 { margin: 0 0 4px; font-size: 16px; }
.sub { margin: 0; font-size: 12px; color: #666; }
.x {
	border: none;
	background: transparent;
	cursor: pointer;
	font-size: 13px;
}
.modal-body { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.hint { margin: 0; font-size: 13px; color: #444; line-height: 1.4; }
.file-upload-area {
	border: 1px dashed #bbb;
	border-radius: 8px;
	padding: 28px 12px;
	text-align: center;
	cursor: pointer;
	background: #fafafa;
	font-size: 13px;
}
.file-upload-area:hover { border-color: #888; }
.err { color: #c62828; margin: 0; font-size: 13px; }
.ok { color: #2e7d32; margin: 0; font-size: 13px; }
.modal-foot {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
	padding: 12px 16px;
	border-top: 1px solid #eee;
}
.btn {
	border: 1px solid #ccc;
	background: #fff;
	border-radius: 6px;
	padding: 8px 14px;
	cursor: pointer;
	font-size: 13px;
}
.btn.primary {
	background: #0082c9;
	border-color: #0082c9;
	color: #fff;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
