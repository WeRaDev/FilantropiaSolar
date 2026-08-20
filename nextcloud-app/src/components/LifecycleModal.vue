<template>
	<div v-if="isOpen && selectedObject" class="modal-overlay" @click.self="close">
		<div class="modal-card">
			<header class="modal-head">
				<h3>Set lifecycle</h3>
				<button type="button" class="x" @click="close">Close</button>
			</header>
			<div class="modal-body">
				<p class="hint">
					{{ selectedObject.name }} — current:
					<strong>{{ currentLabel }}</strong>
				</p>
				<div class="choices">
					<button
						v-for="s in states"
						:key="s"
						type="button"
						class="choice"
						:class="{ active: current === s && !isArchived }"
						:disabled="busy || selectedObject.soft_removed"
						@click="choose(s)"
					>
						{{ label(s) }}
					</button>
				</div>
				<div v-if="canToggleArchive" class="archive-block">
					<p class="archive-hint">
						Public map: hide running stations from the website while keeping them in stats.
					</p>
					<button
						type="button"
						class="choice choice-archive"
						:class="{ active: isArchived }"
						:disabled="busy || selectedObject.soft_removed"
						@click="toggleArchive"
					>
						{{ isArchived ? 'Unarchive (show on public map)' : 'Archive (hide from public map)' }}
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
		const isArchived = computed(() => Boolean(
			selectedObject.value?.public_archived
			|| selectedObject.value?.customData?.publicArchived
			|| selectedObject.value?.public_category === 'archived'
			|| selectedObject.value?.customData?.publicCategory === 'archived',
		))
		const canToggleArchive = computed(() =>
			current.value === 'running' && !selectedObject.value?.soft_removed,
		)
		const currentLabel = computed(() => {
			const base = label(current.value)
			return isArchived.value ? `${base} (archived)` : base
		})
		const label = (s) => s.charAt(0).toUpperCase() + s.slice(1)
		const close = () => store.closeLifecycleModal()
		const choose = async (s) => {
			if (!selectedObject.value || (s === current.value && !isArchived.value)) {
				close()
				return
			}
			busy.value = true
			error.value = ''
			try {
				// Leaving archive via lifecycle change: unarchive first when staying running.
				if (isArchived.value && s === 'running') {
					await store.setPublicArchived(selectedObject.value.id, false)
				} else {
					await store.setLifecycle(selectedObject.value.id, s)
				}
				close()
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Failed'
			} finally {
				busy.value = false
			}
		}
		const toggleArchive = async () => {
			if (!selectedObject.value || !canToggleArchive.value) {
				return
			}
			busy.value = true
			error.value = ''
			try {
				await store.setPublicArchived(selectedObject.value.id, !isArchived.value)
				close()
			} catch (e) {
				error.value = e.response?.data?.error || e.message || 'Failed'
			} finally {
				busy.value = false
			}
		}
		return {
			isOpen,
			selectedObject,
			states,
			current,
			currentLabel,
			isArchived,
			canToggleArchive,
			busy,
			error,
			label,
			close,
			choose,
			toggleArchive,
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
	width: 100%; max-width: 380px;
	background: #ffffff;
	color: #1a1a1a;
	border-radius: 12px;
	overflow: hidden;
	box-shadow: 0 16px 48px rgba(0,0,0,.4);
}
.modal-head {
	display: flex; justify-content: space-between; align-items: center;
	padding: 14px 16px; border-bottom: 1px solid #e6e6e6;
	background: #fafafa;
}
.modal-head h3 {
	margin: 0; font-size: 16px; font-weight: 700; color: #111;
}
.modal-body { padding: 16px; background: #fff; }
.hint { margin: 0 0 14px; font-size: 13px; color: #333; }
.hint strong { color: #111; }
.choices { display: grid; gap: 8px; }
.archive-block {
	margin-top: 14px;
	padding-top: 12px;
	border-top: 1px solid #ececec;
}
.archive-hint {
	margin: 0 0 8px;
	font-size: 12px;
	color: #555;
	line-height: 1.35;
}
.choice {
	border: 1px solid #cfcfcf;
	background: #fff;
	color: #111;
	border-radius: 8px;
	padding: 12px;
	font-size: 14px;
	font-weight: 600;
	cursor: pointer;
}
.choice-archive.active {
	border-color: #6d6d6d;
	background: #f0f0f0;
	box-shadow: inset 0 0 0 1px #6d6d6d;
}
.choice:hover:not(:disabled) {
	background: #f7f7f7;
	border-color: #A89D3F;
}
.choice.active {
	border-color: #A89D3F;
	background: #FDFBF5;
	color: #111;
	box-shadow: inset 0 0 0 1px #A89D3F;
}
.choice:disabled {
	opacity: .55;
	cursor: not-allowed;
}
.x {
	border: 1px solid #ddd;
	background: #fff;
	color: #333;
	border-radius: 6px;
	padding: 4px 10px;
	cursor: pointer;
	font-size: 12px;
}
.err { color: #b71c1c; font-size: 12px; margin: 10px 0 0; }
</style>
