<template>
	<div v-if="isOpen && selectedObject" class="modal-overlay" @click.self="close">
		<div class="modal-card">
			<header class="modal-head">
				<h3>Set lifecycle</h3>
				<button type="button" class="x" @click="close">Close</button>
			</header>
			<div class="modal-body">
				<p class="hint">{{ selectedObject.name }} — current: <strong>{{ current }}</strong></p>
				<div class="choices">
					<button
						v-for="s in states"
						:key="s"
						type="button"
						class="choice"
						:class="{ active: current === s }"
						:disabled="busy || selectedObject.soft_removed"
						@click="choose(s)"
					>
						{{ label(s) }}
					</button>
				</div>
				<p v-if="error" class="err">{{ error }}</p>
			</div>
		</div>
	</div>
</template>

<script>
import { computed, ref } from 'vue'
import { useAppStore } from '../store/app.js'

export default {
	name: 'LifecycleModal',
	setup() {
		const store = useAppStore()
		const isOpen = computed(() => store.lifecycleModalOpen)
		const selectedObject = computed(() => store.selectedObject)
		const busy = ref(false)
		const error = ref('')
		const states = ['virtual', 'planned', 'running']
		const current = computed(() =>
			selectedObject.value?.lifecycle_state
			|| selectedObject.value?.customData?.lifecycleState
			|| 'running',
		)
		const label = (s) => s.charAt(0).toUpperCase() + s.slice(1)
		const close = () => store.closeLifecycleModal()
		const choose = async (s) => {
			if (!selectedObject.value || s === current.value) {
				close()
				return
			}
			busy.value = true
			error.value = ''
			try {
				await store.setLifecycle(selectedObject.value.id, s)
				close()
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Failed'
			} finally {
				busy.value = false
			}
		}
		return { isOpen, selectedObject, states, current, busy, error, label, close, choose }
	},
}
</script>

<style scoped>
.modal-overlay {
	position: fixed; inset: 0; background: rgba(0,0,0,.45);
	display: flex; align-items: center; justify-content: center; z-index: 11000; padding: 20px;
}
.modal-card {
	width: 100%; max-width: 360px; background: #fff; border-radius: 10px; overflow: hidden;
}
.modal-head {
	display: flex; justify-content: space-between; align-items: center;
	padding: 12px 16px; border-bottom: 1px solid #eee;
}
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-body { padding: 16px; }
.hint { margin: 0 0 12px; font-size: 13px; color: #555; }
.choices { display: grid; gap: 8px; }
.choice {
	border: 1px solid #d8d8d8; background: #fff; border-radius: 8px;
	padding: 12px; font-weight: 600; cursor: pointer;
}
.choice.active { border-color: #A89D3F; background: #FDFBF5; }
.choice:disabled { opacity: .5; cursor: not-allowed; }
.x { border: none; background: transparent; cursor: pointer; }
.err { color: #c62828; font-size: 12px; }
</style>
