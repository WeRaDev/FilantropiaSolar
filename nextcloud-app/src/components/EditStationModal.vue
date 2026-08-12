<template>
	<div v-if="isOpen && selectedObject" class="modal-overlay" @click.self="close">
		<div class="modal-card">
			<header class="modal-head">
				<h3>Edit station</h3>
				<button type="button" class="x" @click="close">Close</button>
			</header>
			<div class="modal-body">
				<label>Capacity (kWp)
					<input v-model.number="form.capacity_kwp" type="number" min="0.01" step="0.01">
				</label>
				<label>Energy price (€/kWh)
					<input v-model.number="form.grid_price_kwh" type="number" min="0" step="0.001">
				</label>
				<label>Website
					<input v-model="form.website" type="url" placeholder="https://...">
				</label>
				<label>Short description
					<textarea v-model="form.short_description" rows="3" placeholder="As shown on the public site" />
				</label>
				<label>Effective date
					<input v-model="form.effective_date" type="date">
				</label>
				<p v-if="error" class="err">{{ error }}</p>
			</div>
			<footer class="modal-foot">
				<button type="button" class="btn" :disabled="busy" @click="close">Cancel</button>
				<button type="button" class="btn primary" :disabled="busy" @click="save">Save</button>
			</footer>
		</div>
	</div>
</template>

<script>
import { computed, reactive, ref, watch } from 'vue'
import { useAppStore } from '../store/app.js'

export default {
	name: 'EditStationModal',
	setup() {
		const store = useAppStore()
		const isOpen = computed(() => store.editStationModalOpen)
		const selectedObject = computed(() => store.selectedObject)
		const busy = ref(false)
		const error = ref('')
		const form = reactive({
			capacity_kwp: 0,
			grid_price_kwh: 0.15,
			website: '',
			short_description: '',
			effective_date: new Date().toISOString().slice(0, 10),
		})

		watch([isOpen, selectedObject], () => {
			if (!isOpen.value || !selectedObject.value) return
			const o = selectedObject.value
			form.capacity_kwp = Number(o.capacity_kwp || 0)
			form.grid_price_kwh = Number(o.grid_price_kwh ?? o.customData?.gridPriceKwh ?? 0.15)
			form.website = o.website || o.customData?.website || ''
			form.short_description = o.short_description || o.customData?.shortDescription || ''
			form.effective_date = new Date().toISOString().slice(0, 10)
			error.value = ''
		})

		const close = () => store.closeEditStationModal()
		const save = async () => {
			if (!selectedObject.value) return
			busy.value = true
			error.value = ''
			try {
				await store.updateStation(selectedObject.value.id, {
					capacity_kwp: form.capacity_kwp,
					grid_price_kwh: form.grid_price_kwh,
					website: form.website,
					short_description: form.short_description,
					effective_date: form.effective_date,
				})
				close()
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Save failed'
			} finally {
				busy.value = false
			}
		}

		return { isOpen, selectedObject, form, busy, error, close, save }
	},
}
</script>

<style scoped>
.modal-overlay {
	position: fixed; inset: 0; background: rgba(0,0,0,.55);
	display: flex; align-items: center; justify-content: center; z-index: 11000; padding: 20px;
}
.modal-card {
	width: 100%; max-width: 440px;
	background: #ffffff;
	color: #1a1a1a;
	border-radius: 12px;
	overflow: hidden;
	box-shadow: 0 16px 48px rgba(0,0,0,.4);
}
.modal-head, .modal-foot {
	display: flex; align-items: center; justify-content: space-between;
	padding: 12px 16px;
	background: #fafafa;
}
.modal-head { border-bottom: 1px solid #e6e6e6; }
.modal-foot { border-top: 1px solid #e6e6e6; justify-content: flex-end; gap: 8px; }
.modal-head h3 { margin: 0; font-size: 16px; font-weight: 700; color: #111; }
.modal-body { padding: 16px; display: grid; gap: 10px; background: #fff; }
label { display: grid; gap: 4px; font-size: 12px; color: #333; font-weight: 600; }
input, textarea {
	border: 1px solid #cfcfcf;
	border-radius: 6px;
	padding: 8px 10px;
	font-size: 13px;
	background: #fff;
	color: #111;
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
