<template>
    <div class="list-panel">
        <!-- Search Box (FR2.2) -->
        <div class="search-container">
            <input
                v-model="searchTerm"
                type="text"
                class="search-input"
                placeholder="Search installations..."
                @input="onSearch"
            />
            <span class="search-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="m21 21-4.35-4.35"/>
                </svg>
            </span>
        </div>

        <!-- Station filters -->
        <div class="filter-chips lifecycle-chips">
            <button class="chip" :class="{ active: lifecycleFilters.length === 0 }" @click="clearLifecycleFilters">All</button>
            <button class="chip chip-virtual" :class="{ active: lifecycleFilters.includes('virtual') }" @click="toggleLifecycle('virtual')">Virtual</button>
            <button class="chip chip-planned" :class="{ active: lifecycleFilters.includes('planned') }" @click="toggleLifecycle('planned')">Planned</button>
            <button class="chip chip-running" :class="{ active: lifecycleFilters.includes('running') }" @click="toggleLifecycle('running')">Running</button>
            <button class="chip chip-archived" :class="{ active: lifecycleFilters.includes('archived') }" @click="toggleLifecycle('archived')">Archived</button>
            <button class="chip chip-offline" :class="{ active: lifecycleFilters.includes('offline') }" @click="toggleLifecycle('offline')">Offline</button>
            <button class="chip chip-online" :class="{ active: lifecycleFilters.includes('online') }" @click="toggleLifecycle('online')">Online</button>
        </div>

        <!-- Object List (FR2.1) -->
        <div class="object-list" ref="listRef">
            <div v-if="isLoading" class="loading-state">
                <div class="spinner"></div>
                <span>Loading installations...</span>
            </div>
            
            <div v-else-if="filteredObjects.length === 0" class="empty-state">
                <span class="empty-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <path d="M12 8v8M8 12h8"/>
                    </svg>
                </span>
                <p>No installations found</p>
                <button v-if="activeFilters.length > 0 || searchTerm" class="btn-clear" @click="clearAll">
                    Clear filters
                </button>
            </div>

            <div 
                v-else
                v-for="obj in filteredObjects" 
                :key="obj.id"
                class="list-item"
                :class="{ selected: obj.id === selectedId, [obj.status || 'active']: true, 'soft-removed': obj.soft_removed }"
                @click="selectObject(obj.id)">
                
                <div class="item-status">
                    <span class="status-dot-lg" :class="onlineClass(obj)"></span>
                </div>
                <div class="item-content">
                    <div class="item-primary">
                        <span class="item-name">{{ obj.name || obj.id }}</span>
                        <span class="item-capacity">{{ Number(obj.capacity_kwp || 0).toFixed(1) }} kWp</span>
                    </div>
                    <div class="item-secondary">
                        <span class="item-location">{{ obj.location || 'Unknown' }}</span>
                        <span class="lifecycle-badge" :class="[lifecycleOf(obj), { removed: obj.soft_removed, archived: obj.public_archived }]">
                            {{ lifecycleLabel(obj) }}
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- List footer with count and actions -->
        <div class="list-footer">
            <span>{{ filteredObjects.length }} of {{ totalObjects }} installations</span>
            <div class="footer-actions">
                <button v-if="hasHiddenInstallations" class="btn-restore" @click="restoreAll" title="Restore hidden installations">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M23 4v6h-6M1 20v-6h6"/>
                        <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
                    </svg>
                    Restore
                </button>
                <button class="btn-add-virtual" @click="openCreateVirtual" title="Add Virtual Installation">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 5v14M5 12h14"/>
                    </svg>
                    Add Virtual
                </button>
            </div>
        </div>
    </div>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useAppStore } from '../store/app.js'

export default {
    name: 'ListPanel',
    setup() {
        const store = useAppStore()
        const searchTerm = ref('')
        const listRef = ref(null)

        // Computed from store
        const filteredObjects = computed(() => store.filteredObjects)
        const totalObjects = computed(() => store.totalObjects)
        const activeCount = computed(() => store.activeObjectsCount)
        const warningCount = computed(() => store.warningObjectsCount)
        const offlineCount = computed(() => store.offlineObjectsCount)
        const virtualCount = computed(() => store.virtualCount)
        const plannedCount = computed(() => store.plannedCount)
        const runningCount = computed(() => store.runningCount)
        const selectedId = computed(() => store.selectedObjectId)
        const isLoading = computed(() => store.isLoadingObjects)
        const activeFilters = computed(() => store.filters.status)
        const lifecycleFilters = computed(() => store.filters.lifecycle || [])

        // Search handler with debounce
        let searchTimeout = null
        const onSearch = () => {
            clearTimeout(searchTimeout)
            searchTimeout = setTimeout(() => {
                store.setSearchTerm(searchTerm.value)
            }, 300)
        }

        // Toggle filter (FR2.3)
        const toggleFilter = (status) => {
            const current = [...store.filters.status]
            const index = current.indexOf(status)
            if (index >= 0) {
                current.splice(index, 1)
            } else {
                current.push(status)
            }
            store.setStatusFilter(current)
        }

        // Clear all filters (FR2.4)
        const clearFilters = () => {
            store.clearFilters()
        }

        const clearAll = () => {
            searchTerm.value = ''
            store.clearFilters()
        }

        // Select object (FR2.5) - now shows info card in MapPanel
        const selectObject = (objectId) => {
            store.selectObject(objectId)
        }

        // View analysis - opens modal
        const viewAnalysis = (objectId) => {
            store.openAnalyticsModal(objectId)
        }

        // Open create virtual modal
        const openCreateVirtual = () => {
            store.openCreateVirtualModal()
        }

        // Whether there are hidden installations that can be restored
        const hasHiddenInstallations = computed(() => store.hiddenObjectIds.length > 0)

        // Hard-delete station with confirmation
        const confirmDelete = async (obj) => {
            const msg = `Permanently delete "${obj.name}" from Nextcloud? This removes the station and its readings. This cannot be undone.`
            if (confirm(msg)) {
                try {
                    await store.deleteInstallation(obj.id)
                } catch (e) {
                    alert(e.response?.data?.error || e.message || 'Failed to delete')
                }
            }
        }

        // Restore all hidden installations
        const restoreAll = async () => {
            await store.restoreDashboard()
        }

        // Scroll selected item into view (FR2.6)
        watch(selectedId, (newId) => {
            if (newId && listRef.value) {
                const item = listRef.value.querySelector(`[class*="selected"]`)
                if (item) {
                    item.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
                }
            }
        })


        const lifecycleOf = (obj) =>
            obj.lifecycle_state || obj.customData?.lifecycleState || 'running'

        const onlineClass = (obj) => {
            const lc = lifecycleOf(obj)
            if (lc !== 'running' || obj.soft_removed) return 'neutral'
            return (obj.status || 'active') === 'active' ? 'online' : 'offline'
        }


        const lifecycleLabel = (obj) => {
            let label = lifecycleOf(obj)
            if (obj.public_archived) {
                label = `${label} (archived)`
            }
            if (obj.soft_removed) {
                label = `${label} (removed)`
            }
            return label
        }

        const publicLabel = (obj) => {
            if (obj.soft_removed) return 'hidden'
            if (obj.public_archived) return 'archived'
            const cat = obj.public_category || obj.customData?.publicCategory
            if (cat === 'archived') return 'archived'
            if (!cat || cat === 'none') return 'hidden'
            return cat
        }

        const publicClass = (obj) => {
            const label = publicLabel(obj)
            return {
                planned: label === 'planned',
                existing: label === 'existing',
                none: label === 'hidden',
            }
        }

        const toggleLifecycle = (state) => {
            const current = [...(store.filters.lifecycle || [])]
            const index = current.indexOf(state)
            if (index >= 0) {
                current.splice(index, 1)
            } else {
                current.push(state)
            }
            store.setLifecycleFilter(current)
        }

        const clearLifecycleFilters = () => {
            store.setLifecycleFilter([])
        }

        return {
            searchTerm,
            listRef,
            filteredObjects,
            totalObjects,
            activeCount,
            warningCount,
            offlineCount,
            virtualCount,
            plannedCount,
            runningCount,
            selectedId,
            isLoading,
            activeFilters,
            lifecycleFilters,
            onSearch,
            toggleFilter,
            clearFilters,
            clearAll,
            selectObject,
            viewAnalysis,
            openCreateVirtual,
            confirmDelete,
            hasHiddenInstallations,
            restoreAll,
            lifecycleOf,
            onlineClass,
            lifecycleLabel,
            publicLabel,
            publicClass,
            toggleLifecycle,
            clearLifecycleFilters,
        }
    }
}
</script>

<style scoped>
/* List Panel - 30-35% width per spec */
.list-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--color-main-background, #fff);
    border-right: 1px solid var(--color-border, #e0e0e0);
}

/* Search Container */
.search-container {
    position: relative;
    padding: 16px;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.search-input {
    width: 100%;
    height: 40px;
    padding: 0 16px 0 40px;
    border: 1px solid var(--color-border, #e0e0e0);
    border-radius: 8px;
    font-size: 14px;
    background: var(--color-background-dark, #f5f5f5);
    transition: all 0.2s ease;
}

.search-input:focus {
    outline: none;
    border-color: var(--color-primary, #0082c9);
    background: var(--color-main-background, #fff);
    box-shadow: 0 0 0 2px rgba(0, 130, 201, 0.1);
}

.search-icon {
    position: absolute;
    left: 28px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--color-text-lighter, #767676);
}

/* Filter Chips */
.filter-chips {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    overflow-x: auto;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border: 1px solid var(--color-border, #e0e0e0);
    border-radius: 16px;
    background: var(--color-main-background, #fff);
    font-size: 12px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
}

.chip:hover {
    background: var(--color-background-hover, #f5f5f5);
}

.chip.active {
    background: var(--color-primary, #0082c9);
    color: #fff;
    border-color: var(--color-primary, #0082c9);
}

.chip-archived.active {
    background: #6d6d6d;
    border-color: #6d6d6d;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.status-dot.active { background: #22A559; }
.status-dot.warning { background: #F5A623; }
.status-dot.offline { background: #CC2020; }

/* Object List */
.object-list {
    flex: 1;
    overflow-y: auto;
}

/* List Item - 56px height per spec */
.list-item {
    display: flex;
    align-items: center;
    height: 56px;
    padding: 0 16px;
    cursor: pointer;
    border-bottom: 1px solid var(--color-border-dark, #ebebeb);
    transition: all 0.15s ease;
    border-left: 4px solid transparent;
}

.list-item:hover {
    background: var(--color-background-hover, #f5f5f5);
}

/* Selected state - 4px left border per spec */
.list-item.selected {
    background: rgba(0, 130, 201, 0.08);
    border-left-color: var(--color-primary, #0082c9);
}

/* Status border colors */
.list-item.active.selected { border-left-color: #22A559; }
.list-item.warning.selected { border-left-color: #F5A623; }
.list-item.offline.selected { border-left-color: #CC2020; }

/* Status Badge - 20px per spec */
.item-status {
    margin-right: 12px;
}

.status-badge {
    display: block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

.status-badge.active { background: #22A559; }
.status-badge.warning { background: #F5A623; }
.status-badge.offline { background: #CC2020; }

/* Item Content */
.item-content {
    flex: 1;
    min-width: 0;
}

.item-primary {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
}

.item-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--color-main-text, #1a1a1a);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.item-capacity {
    font-size: 12px;
    font-weight: 600;
    color: var(--color-primary, #0082c9);
    flex-shrink: 0;
}

.item-secondary {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    margin-top: 2px;
}

.item-location {
    font-size: 12px;
    color: var(--color-text-lighter, #767676);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.item-metric {
    font-size: 11px;
    color: var(--color-text-lighter, #767676);
    flex-shrink: 0;
}

/* View Analysis Action Button */
.item-action {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    margin-left: 8px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    color: var(--color-text-lighter, #767676);
    opacity: 0.4;
    transition: all 0.2s ease;
}

.list-item:hover .item-action {
    opacity: 1;
}

.item-action:hover {
    background: var(--color-primary, #0082c9);
    color: white;
    border-color: var(--color-primary, #0082c9);
}

.item-delete:hover {
    background: #CC2020;
    border-color: #CC2020;
}

/* Loading State */
.loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--color-text-lighter, #767676);
    gap: 12px;
}

.spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--color-border, #e0e0e0);
    border-top-color: var(--color-primary, #0082c9);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* Empty State */
.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--color-text-lighter, #767676);
    text-align: center;
    padding: 24px;
}

.empty-icon {
    opacity: 0.5;
    margin-bottom: 8px;
}

.btn-clear {
    margin-top: 12px;
    padding: 8px 16px;
    border: 1px solid var(--color-border, #e0e0e0);
    border-radius: 4px;
    background: var(--color-main-background, #fff);
    cursor: pointer;
}

.btn-clear:hover {
    background: var(--color-background-hover, #f5f5f5);
}

/* List Footer */
.list-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    font-size: 12px;
    color: var(--color-text-lighter, #767676);
    border-top: 1px solid var(--color-border, #e0e0e0);
}

.footer-actions {
    display: flex;
    align-items: center;
    gap: 6px;
}

.btn-restore {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    background: var(--color-main-background, #fff);
    color: var(--color-primary, #0082c9);
    border: 1px solid var(--color-primary, #0082c9);
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-restore:hover {
    background: rgba(0, 130, 201, 0.08);
}

/* Add Virtual Button */
.btn-add-virtual {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    background: var(--color-primary, #0082c9);
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
}

.btn-add-virtual:hover {
    background: var(--color-primary-hover, #0070b0);
}

.lifecycle-chips {
    border-bottom: 1px solid var(--color-border, #eee);
}

.chip-virtual.active {
    border-color: #7b1fa2;
    background: #f3e5f5;
}

.chip-planned.active {
    border-color: #ef6c00;
    background: #fff3e0;
}

.chip-running.active {
    border-color: #2e7d32;
    background: #e8f5e9;
}

.list-item.soft-removed {
    opacity: 0.65;
}

.lifecycle-badge,
.public-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    text-transform: lowercase;
    padding: 1px 6px;
    border-radius: 999px;
    background: #eee;
    color: #444;
}

.lifecycle-badge.virtual { background: #f3e5f5; color: #7b1fa2; }
.lifecycle-badge.planned { background: #fff3e0; color: #ef6c00; }
.lifecycle-badge.running { background: #e8f5e9; color: #2e7d32; }
.lifecycle-badge.removed { text-decoration: line-through; }
.lifecycle-badge.archived { opacity: 0.85; border-style: dashed; }

.public-badge.planned { background: #fff8e1; color: #f9a825; }
.public-badge.existing { background: #e0f2f1; color: #00695c; }
.public-badge.none { background: #eceff1; color: #607d8b; }





.item-secondary {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
}

.status-dot-lg {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    display: inline-block;
    margin-top: 4px;
}
.status-dot-lg.online { background: #22A559; }
.status-dot-lg.offline { background: #CC2020; }
.status-dot-lg.neutral { background: #bdbdbd; }
.chip-online.active { border-color: #22A559; background: #e8f5e9; }
.chip-offline.active { border-color: #CC2020; background: #ffebee; }
.item-content { flex: 1; min-width: 0; }
</style>
