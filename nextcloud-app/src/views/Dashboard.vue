<template>
	<div class="dashboard-layout">
		<Header
			:active-view="activeView"
			@set-view="setView"
		/>

		<main class="main-content">
			<template v-if="activeView === 'map'">
				<ListPanel class="list-section" />
				<MapPanel class="map-section" />
			</template>

			<section v-else class="admin-section-view">
				<MlAdminPanel embedded :is-open="true" />
			</section>
		</main>

		<AnalyticsModal />
		<CreateVirtualModal />
	</div>
</template>

<script>
import { onMounted, ref, defineAsyncComponent } from 'vue'
import { useAppStore } from '../store/app.js'
import Header from '../components/Header.vue'
import ListPanel from '../components/ListPanel.vue'
import MapPanel from '../components/MapPanel.vue'

const AnalyticsModal = defineAsyncComponent(() =>
	import('../components/AnalyticsModal.vue'),
)
const CreateVirtualModal = defineAsyncComponent(() =>
	import('../components/CreateVirtualModal.vue'),
)
const MlAdminPanel = defineAsyncComponent(() =>
	import('../components/MlAdminPanel.vue'),
)

export default {
	name: 'Dashboard',
	components: {
		Header,
		ListPanel,
		MapPanel,
		AnalyticsModal,
		CreateVirtualModal,
		MlAdminPanel,
	},
	setup() {
		const store = useAppStore()
		// Default to admin: this app is the ops dashboard (D2)
		const activeView = ref('admin')

		const setView = (view) => {
			activeView.value = view === 'map' ? 'map' : 'admin'
		}

		onMounted(async () => {
			await store.fetchObjects()
		})

		return {
			activeView,
			setView,
		}
	},
}
</script>

<style scoped>
.dashboard-layout {
	display: flex;
	flex-direction: column;
	height: 100%;
	width: 100%;
	overflow: hidden;
	background: var(--color-main-background, #fff);
}

.main-content {
	display: flex;
	flex: 1;
	min-height: 0;
	overflow: hidden;
}

.list-section {
	width: 32%;
	min-width: 280px;
	max-width: 400px;
	flex-shrink: 0;
}

.map-section {
	flex: 1;
	min-width: 0;
}

.admin-section-view {
	flex: 1;
	min-width: 0;
	min-height: 0;
	overflow: hidden;
	display: flex;
	flex-direction: column;
}

@media (max-width: 1200px) {
	.list-section {
		width: 35%;
		max-width: 350px;
	}
}

@media (max-width: 768px) {
	.main-content {
		flex-direction: column;
	}

	.list-section {
		width: 100%;
		max-width: none;
		height: 200px;
		min-width: auto;
	}

	.map-section {
		flex: 1;
	}
}
</style>
