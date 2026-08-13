<template>
	<div class="dashboard-layout">
		<Header />

		<main class="main-content">
			<ListPanel class="list-section" />
			<MapPanel class="map-section" />
		</main>

		<AnalyticsModal />
		<CreateVirtualModal />
		<EditStationModal />
		<UploadHistoricalModal />
		<LifecycleModal />
	</div>
</template>

<script>
import { onMounted, defineAsyncComponent } from 'vue'
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
const EditStationModal = defineAsyncComponent(() =>
	import('../components/EditStationModal.vue'),
)
const UploadHistoricalModal = defineAsyncComponent(() =>
	import('../components/UploadHistoricalModal.vue'),
)
const LifecycleModal = defineAsyncComponent(() =>
	import('../components/LifecycleModal.vue'),
)

export default {
	name: 'Dashboard',
	components: {
		Header,
		ListPanel,
		MapPanel,
		AnalyticsModal,
		CreateVirtualModal,
		EditStationModal,
		UploadHistoricalModal,
		LifecycleModal,
	},
	setup() {
		const store = useAppStore()

		onMounted(async () => {
			await store.fetchObjects()
		})

		return {}
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
	width: 34%;
	min-width: 300px;
	max-width: 440px;
	flex-shrink: 0;
}

.map-section {
	flex: 1;
	min-width: 0;
}

@media (max-width: 1200px) {
	.list-section {
		width: 38%;
		max-width: 380px;
	}
}

@media (max-width: 768px) {
	.main-content {
		flex-direction: column;
	}

	.list-section {
		width: 100%;
		max-width: none;
		height: 240px;
		min-width: auto;
	}

	.map-section {
		flex: 1;
	}
}
</style>
