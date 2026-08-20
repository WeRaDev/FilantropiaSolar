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
						v-for="opt in options"
						:key="opt.id"
						type="button"
						class="choice"
						:class="{ active: opt.active, archive: opt.id === 'archived' }"
						:disabled="busy || selectedObject.soft_removed || opt.disabled"
						:title="opt.title || ''"
						@click="choose(opt.id)"
					>
						<span class="choice-title">{{ opt.label }}</span>
						<span v-if="opt.hint" class="choice-sub">{{ opt.hint }}</span>
					</button>
				</div>
				<p class="archive-hint">
					Archived keeps the station in stats but hides it from the public website map.
					Only available for Running stations.
				</p>
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
		const lifecycle = computed(() =>
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
		const canArchive = computed(() =>
			lifecycle.value === 'running' && !selectedObject.value?.soft_removed,
		)
		const currentLabel = computed(() => {
			const base = lifecycle.value.charAt(0).toUpperCase() + lifecycle.value.slice(1)
			return isArchived.value ? `${base} (archived)` : base
		})
		const options = computed(() => {
			const lc = lifecycle.value
			const archived = isArchived.value
			return [
				{
					id: 'virtual',
					label: 'Virtual',
					active: lc === 'virtual' && !archived,
					disabled: false,
				},
				{
					id: 'planned',
					label: 'Planned',
					active: lc === 'planned' && !archived,
					disabled: false,
				},
				{
					id: 'running',
					label: 'Running',
					hint: archived ? 'On public map' : '',
					active: lc === 'running' && !archived,
					disabled: false,
				},
				{
					id: 'archived',
					label: 'Archived',
					hint: 'Hidden from public map, still in stats',
					active: archived,
					disabled: !canArchive.value && !archived,
					title: (!canArchive.value && !archived)
						? 'Set lifecycle to Running first'
						: '',
				},
			]
		})
		const close = () => store.closeLifecycleModal()
		const choose = async (id) => {
			if (!selectedObject.value) {
				return
			}
			const opt = options.value.find((o) => o.id === id)
			if (!opt || opt.disabled || opt.active) {
				if (opt?.active) close()
				return
			}
			busy.value = true
			error.value = ''
			try {
				const sid = selectedObject.value.id
				if (id === 'archived') {
					// Ensure running, then archive from public map.
					if (lifecycle.value !== 'running') {
						await store.setLifecycle(sid, 'running')
					}
					await store.setPublicArchived(sid, true)
				} else if (id === 'running') {
					if (isArchived.value) {
						await store.setPublicArchived(sid, false)
					} else if (lifecycle.value !== 'running') {
						await store.setLifecycle(sid, 'running')
					}
				} else {
					// virtual / planned — demote and clear archive if needed
					await store.setLifecycle(sid, id)
				}
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
			options,
			currentLabel,
			busy,
			error,
			close,
			choose,
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
.archive-hint {
	margin: 12px 0 0;
	font-size: 12px;
	color: #555;
	line-height: 1.35;
}
.choice {
	display: flex;
	flex-direction: column;
	align-items: flex-start;
	gap: 2px;
	border: 1px solid #cfcfcf;
	background: #fff;
	color: #111;
	border-radius: 8px;
	padding: 12px;
	font-size: 14px;
	font-weight: 600;
	cursor: pointer;
	text-align: left;
}
.choice-title { font-size: 14px; font-weight: 600; }
.choice-sub {
	font-size: 11px;
	font-weight: 500;
	color: #666;
	line-height: 1.3;
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
.choice.archive.active {
	border-color: #6d6d6d;
	background: #f0f0f0;
	box-shadow: inset 0 0 0 1px #6d6d6d;
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
