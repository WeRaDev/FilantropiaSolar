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
	position: fixed; inset: 0; background: rgba(0,0,0,.45);
	display: flex; align-items: center; justify-content: center; z-index: 11000; padding: 20px;
}
.modal-card {
	width: 100%; max-width: 420px; background: #fff; border-radius: 10px; overflow: hidden;
	box-shadow: 0 12px 40px rgba(0,0,0,.2);
}
.modal-head, .modal-foot {
	display: flex; align-items: center; justify-content: space-between;
	padding: 12px 16px; border-bottom: 1px solid #eee;
}
.modal-foot { border-bottom: 0; border-top: 1px solid #eee; justify-content: flex-end; gap: 8px; }
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-body { padding: 16px; display: grid; gap: 10px; }
label { display: grid; gap: 4px; font-size: 12px; color: #555; }
input, textarea {
	border: 1px solid #d8d8d8; border-radius: 6px; padding: 8px 10px; font-size: 13px;
}
.btn { border: 1px solid #d8d8d8; background: #fff; border-radius: 6px; padding: 8px 12px; cursor: pointer; }
.btn.primary { background: #0082c9; color: #fff; border-color: #0082c9; }
.btn:disabled { opacity: .6; cursor: not-allowed; }
.x { border: none; background: transparent; cursor: pointer; }
.err { color: #c62828; margin: 0; font-size: 12px; }
</style>
