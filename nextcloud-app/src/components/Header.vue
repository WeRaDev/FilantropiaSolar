<template>
	<header class="app-header">
		<div class="header-branding">
			<span class="app-logo">
				<svg width="28" height="28" viewBox="0 0 32 32" fill="none">
					<defs>
						<radialGradient id="sunGlow" cx="50%" cy="50%" r="50%">
							<stop offset="0%" stop-color="#FFF9E6"/>
							<stop offset="50%" stop-color="#F5D547"/>
							<stop offset="100%" stop-color="#C4A000"/>
						</radialGradient>
					</defs>
					<circle cx="16" cy="16" r="8" fill="url(#sunGlow)"/>
				</svg>
			</span>
			<div class="app-title-group">
				<h1 class="app-title">FilantropiaSolar</h1>
				<span class="app-tagline">built by <span class="wera-we">we</span><span class="wera-ra">ra</span></span>
			</div>
			<span class="app-version">v3.2.4</span>
		</div>

		<div class="kpi-container">
			<div class="kpi-card" :class="{ active: activeFilter === 'all' }" @click="setFilter('all')">
				<span class="kpi-value">{{ totalObjects }}</span>
				<span class="kpi-label">Total stations</span>
			</div>
			<div class="kpi-card kpi-online" :class="{ active: activeFilter === 'online' }" @click="setFilter('online')">
				<span class="kpi-value">{{ onlineCount }}</span>
				<span class="kpi-label">Online</span>
			</div>
			<div class="kpi-card kpi-offline" :class="{ active: activeFilter === 'offline' }" @click="setFilter('offline')">
				<span class="kpi-value">{{ offlineCount }}</span>
				<span class="kpi-label">Offline</span>
			</div>
			<div class="kpi-card kpi-planned" :class="{ active: activeFilter === 'planned' }" @click="setFilter('planned')">
				<span class="kpi-value">{{ plannedCount }}</span>
				<span class="kpi-label">Planned</span>
			</div>
			<div class="kpi-card">
				<span class="kpi-value">{{ formatKwp(totalCapacity) }}</span>
				<span class="kpi-label">Total kWp</span>
			</div>
			<div class="kpi-card">
				<span class="kpi-value">{{ formatEnergy(totalEnergy) }}</span>
				<span class="kpi-label">Total energy</span>
			</div>
			<div class="kpi-card">
				<span class="kpi-value">{{ formatMoney(totalSavings) }}</span>
				<span class="kpi-label">Total savings</span>
			</div>
		</div>
	</header>
</template>

<script>
import { computed, ref } from 'vue'
import { useAppStore } from '../store/app.js'

export default {
	name: 'Header',
	setup() {
		const store = useAppStore()
		const activeFilter = ref('all')

		const totalObjects = computed(() => store.totalObjects)
		const onlineCount = computed(() => store.onlineCount)
		const offlineCount = computed(() => store.offlineRunningCount)
		const plannedCount = computed(() => store.plannedCount)
		const totalCapacity = computed(() => store.totalCapacity)
		const totalEnergy = computed(() => store.totalEnergyKwh)
		const totalSavings = computed(() => store.totalSavingsEur)

		const setFilter = (key) => {
			if (key === 'all' || activeFilter.value === key) {
				activeFilter.value = 'all'
				store.setLifecycleFilter([])
				store.setStatusFilter([])
				return
			}
			activeFilter.value = key
			store.setStatusFilter([])
			if (key === 'online' || key === 'offline' || key === 'planned') {
				store.setLifecycleFilter([key])
			} else {
				store.setLifecycleFilter([])
			}
		}

		const formatKwp = (n) => Number(n || 0).toFixed(1)
		const formatEnergy = (n) => {
			const v = Number(n || 0)
			if (v >= 1e6) return (v / 1e6).toFixed(1) + ' GWh'
			if (v >= 1e3) return (v / 1e3).toFixed(0) + ' MWh'
			return v.toFixed(0) + ' kWh'
		}
		const formatMoney = (n) => {
			const v = Number(n || 0)
			if (v >= 1e6) return '€' + (v / 1e6).toFixed(1) + 'M'
			if (v >= 1e3) return '€' + (v / 1e3).toFixed(0) + 'k'
			return '€' + v.toFixed(0)
		}

		return {
			totalObjects,
			onlineCount,
			offlineCount,
			plannedCount,
			totalCapacity,
			totalEnergy,
			totalSavings,
			activeFilter,
			setFilter,
			formatKwp,
			formatEnergy,
			formatMoney,
		}
	},
}
</script>

<style scoped>
.app-header {
	min-height: 88px;
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 10px 20px;
	background: var(--color-main-background, #fff);
	border-bottom: 1px solid var(--color-border, #e0e0e0);
	gap: 16px;
	flex-wrap: wrap;
}
.header-branding {
	display: flex;
	align-items: center;
	gap: 12px;
	flex-shrink: 0;
}
.app-title {
	font-family: Georgia, 'Times New Roman', serif;
	font-style: italic;
	font-size: 20px;
	font-weight: 400;
	margin: 0;
	line-height: 1.1;
}
.app-tagline { font-size: 10px; color: #767676; }
.wera-we { color: #A89D3F; font-weight: 500; }
.wera-ra { color: #E8A020; font-weight: 500; }
.app-version {
	font-size: 11px;
	color: #767676;
	padding: 2px 6px;
	background: #f5f5f5;
	border-radius: 4px;
}
.kpi-container {
	display: flex;
	gap: 10px;
	flex: 1;
	justify-content: flex-end;
	flex-wrap: wrap;
}
.kpi-card {
	min-width: 88px;
	padding: 6px 10px;
	background: #f5f5f5;
	border-radius: 8px;
	text-align: center;
	cursor: pointer;
	border: 2px solid transparent;
}
.kpi-card:hover { background: #ededed; }
.kpi-card.active { border-color: #A89D3F; background: #FDFBF5; }
.kpi-value {
	display: block;
	font-size: 20px;
	font-weight: 700;
	line-height: 1.15;
}
.kpi-label {
	display: block;
	font-size: 10px;
	color: #666;
	text-transform: uppercase;
	letter-spacing: 0.02em;
}
.kpi-online .kpi-value { color: #22A559; }
.kpi-offline .kpi-value { color: #CC2020; }
.kpi-planned .kpi-value { color: #ef6c00; }
</style>
