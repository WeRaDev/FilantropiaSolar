<template>
    <div class="dashboard-layout">
        <!-- Header Section - 80px height -->
        <Header />
        
        <!-- Main Content - List (30-35%) + Map (65-70%) -->
        <main class="main-content">
            <ListPanel class="list-section" />
            <MapPanel class="map-section" />
        </main>
        
        <!-- Analytics Modal (full-screen overlay) -->
        <AnalyticsModal />
        
        <!-- Create Virtual Installation Modal -->
        <CreateVirtualModal />
        
        <!-- ML Admin Panel -->
        <MlAdminPanel :isOpen="showAdminPanel" @close="showAdminPanel = false" />
    </div>
</template>

<script>
import { onMounted, ref, defineAsyncComponent } from 'vue'
import { useAppStore } from '../store/app.js'
import Header from '../components/Header.vue'
import ListPanel from '../components/ListPanel.vue'
import MapPanel from '../components/MapPanel.vue'

// Lazy load modals for better initial bundle size
const AnalyticsModal = defineAsyncComponent(() =>
    import('../components/AnalyticsModal.vue')
)
const CreateVirtualModal = defineAsyncComponent(() =>
    import('../components/CreateVirtualModal.vue')
)
const MlAdminPanel = defineAsyncComponent(() =>
    import('../components/MlAdminPanel.vue')
)

export default {
    name: 'Dashboard',
    components: {
        Header,
        ListPanel,
        MapPanel,
        AnalyticsModal,
        CreateVirtualModal,
        MlAdminPanel
    },
    setup() {
        const store = useAppStore()
        const showAdminPanel = ref(false)

        onMounted(async () => {
            // Fetch installations on mount
            await store.fetchObjects()
        })

        return { showAdminPanel }
    }
}
</script>

<style scoped>
/* Dashboard Layout - Full viewport minus Nextcloud header */
.dashboard-layout {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    overflow: hidden;
    background: var(--color-main-background, #fff);
}

/* Main Content Area - Takes remaining space */
.main-content {
    display: flex;
    flex: 1;
    min-height: 0; /* Important for flex children to scroll */
    overflow: hidden;
}

/* List Section - 30-35% width per spec */
.list-section {
    width: 32%;
    min-width: 280px;
    max-width: 400px;
    flex-shrink: 0;
}

/* Map Section - 65-70% width per spec */
.map-section {
    flex: 1;
    min-width: 0;
}

/* Responsive breakpoints per spec Section 5.5 */
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
