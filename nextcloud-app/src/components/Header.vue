<template>
    <header class="app-header">
        <!-- Left: App title and logo -->
        <div class="header-branding">
            <span class="app-logo">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="5" fill="#F5A623"/>
                    <path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" 
                          stroke="#F5A623" stroke-width="2" stroke-linecap="round"/>
                </svg>
            </span>
            <h1 class="app-title">FilantropiaSolar</h1>
            <span class="app-version">v3.0.3</span>
        </div>

        <!-- Center: KPI cards -->
        <div class="kpi-container">
            <div class="kpi-card" :class="{ active: !activeFilter || activeFilter === 'all' }" @click="setFilter('all')">
                <span class="kpi-value">{{ totalObjects }}</span>
                <span class="kpi-label">Total Plants</span>
            </div>
            <div class="kpi-card kpi-active" :class="{ active: activeFilter === 'active' }" @click="setFilter('active')">
                <span class="kpi-value">{{ activeCount }}</span>
                <span class="kpi-label">Active</span>
            </div>
            <div class="kpi-card kpi-warning" :class="{ active: activeFilter === 'warning' }" @click="setFilter('warning')">
                <span class="kpi-value">{{ warningCount }}</span>
                <span class="kpi-label">Warnings</span>
            </div>
            <div class="kpi-card kpi-offline" :class="{ active: activeFilter === 'offline' }" @click="setFilter('offline')">
                <span class="kpi-value">{{ offlineCount }}</span>
                <span class="kpi-label">Offline</span>
            </div>
            <div class="kpi-card kpi-capacity">
                <span class="kpi-value">{{ totalCapacity.toFixed(1) }}</span>
                <span class="kpi-label">kWp Total</span>
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
        const activeFilter = ref(null)

        // Computed values from store
        const totalObjects = computed(() => store.totalObjects)
        const activeCount = computed(() => store.activeObjectsCount)
        const warningCount = computed(() => store.warningObjectsCount)
        const offlineCount = computed(() => store.offlineObjectsCount)
        const totalCapacity = computed(() => store.totalCapacity)

        // Filter by status via KPI card click (FR2.3)
        const setFilter = (status) => {
            if (status === 'all' || activeFilter.value === status) {
                activeFilter.value = null
                store.setStatusFilter([])
            } else {
                activeFilter.value = status
                store.setStatusFilter([status])
            }
        }

        return {
            totalObjects,
            activeCount,
            warningCount,
            offlineCount,
            totalCapacity,
            activeFilter,
            setFilter
        }
    }
}
</script>

<style scoped>
/* Header: 80px height per spec Section 5.1 */
.app-header {
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    background: var(--color-main-background, #fff);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    gap: 24px;
}

/* Branding */
.header-branding {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
}

.app-logo {
    display: flex;
}

.app-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--color-main-text, #1a1a1a);
    margin: 0;
}

.app-version {
    font-size: 12px;
    color: var(--color-text-lighter, #767676);
    padding: 2px 8px;
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 4px;
}

/* KPI Container - cards 120px wide per spec */
.kpi-container {
    display: flex;
    gap: 16px;
    flex: 1;
    justify-content: center;
}

.kpi-card {
    min-width: 100px;
    width: 120px;
    padding: 8px 16px;
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 8px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 2px solid transparent;
}

.kpi-card:hover {
    background: var(--color-background-hover, #ededed);
}

.kpi-card.active {
    border-color: var(--color-primary, #0082c9);
}

/* KPI Values - 28px bold per spec */
.kpi-value {
    display: block;
    font-size: 28px;
    font-weight: 700;
    line-height: 1.2;
}

.kpi-label {
    display: block;
    font-size: 11px;
    color: var(--color-text-lighter, #767676);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Status-specific colors per spec Section 5.2 */
.kpi-active .kpi-value { color: #22A559; }
.kpi-warning .kpi-value { color: #F5A623; }
.kpi-offline .kpi-value { color: #CC2020; }
.kpi-capacity .kpi-value { color: var(--color-primary, #0082c9); }

/* Responsive */
@media (max-width: 1200px) {
    .kpi-card {
        min-width: 80px;
        width: 100px;
        padding: 6px 12px;
    }
    .kpi-value {
        font-size: 22px;
    }
}

@media (max-width: 768px) {
    .app-header {
        height: auto;
        flex-wrap: wrap;
        padding: 12px 16px;
    }
    .kpi-container {
        order: 3;
        width: 100%;
        justify-content: space-between;
        margin-top: 12px;
    }
    .kpi-card {
        flex: 1;
        min-width: auto;
    }
}
</style>
