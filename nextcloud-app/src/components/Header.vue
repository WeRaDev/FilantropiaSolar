<template>
    <header class="app-header">
        <!-- Left: App title and logo -->
        <div class="header-branding">
            <span class="app-logo">
                <!-- Sun icon with glow effect matching brand -->
                <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
                    <defs>
                        <radialGradient id="sunGlow" cx="50%" cy="50%" r="50%">
                            <stop offset="0%" stop-color="#FFF9E6"/>
                            <stop offset="50%" stop-color="#F5D547"/>
                            <stop offset="100%" stop-color="#C4A000"/>
                        </radialGradient>
                        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                            <feGaussianBlur stdDeviation="1.5" result="blur"/>
                            <feMerge>
                                <feMergeNode in="blur"/>
                                <feMergeNode in="SourceGraphic"/>
                            </feMerge>
                        </filter>
                    </defs>
                    <circle cx="16" cy="16" r="8" fill="url(#sunGlow)" filter="url(#glow)"/>
                    <circle cx="16" cy="16" r="5" fill="none" stroke="#C4A000" stroke-width="1" opacity="0.5"/>
                </svg>
            </span>
            <div class="app-title-group">
                <h1 class="app-title">FilantropiaSolar</h1>
                <span class="app-tagline">built by <span class="wera-we">we</span><span class="wera-ra">ra</span></span>
            </div>
            <span class="app-version">v3.0.5</span>
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

.app-title-group {
    display: flex;
    flex-direction: column;
    gap: 0;
}

.app-title {
    font-family: Georgia, 'Times New Roman', serif;
    font-style: italic;
    font-size: 22px;
    font-weight: 400;
    color: var(--color-main-text, #1a1a1a);
    margin: 0;
    line-height: 1.1;
}

.app-tagline {
    font-size: 10px;
    color: var(--color-text-lighter, #767676);
    margin-left: 2px;
}

.wera-we {
    color: #A89D3F;
    font-weight: 500;
}

.wera-ra {
    color: #E8A020;
    font-weight: 500;
}

.app-version {
    font-size: 11px;
    color: var(--color-text-lighter, #767676);
    padding: 2px 6px;
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 4px;
    align-self: flex-start;
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
