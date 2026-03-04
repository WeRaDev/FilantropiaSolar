<template>
    <teleport to="body">
        <transition name="modal-fade">
            <div v-if="isOpen" class="admin-modal-overlay" @click.self="close">
                <div class="admin-modal">
                    <header class="modal-header">
                        <h2>ML Service Admin</h2>
                        <button class="btn-close" @click="close" title="Close">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M18 6 6 18M6 6l12 12"/>
                            </svg>
                        </button>
                    </header>

                    <div class="modal-body">
                        <!-- Loading state -->
                        <div v-if="loading" class="loading-state">
                            <div class="spinner"></div>
                            <span>Loading cache status...</span>
                        </div>

                        <template v-else>
                            <!-- Cache Overview -->
                            <section class="admin-section">
                                <h3>Cache Status</h3>
                                <div class="stats-grid">
                                    <div class="stat-card">
                                        <span class="stat-value">{{ cacheData?.models?.count || 0 }}</span>
                                        <span class="stat-label">Models Loaded</span>
                                    </div>
                                    <div class="stat-card">
                                        <span class="stat-value">{{ cacheData?.installations_loaded || 0 }}</span>
                                        <span class="stat-label">Installations</span>
                                    </div>
                                    <div class="stat-card">
                                        <span class="stat-value">{{ cacheData?.energy_data?.count || 0 }}</span>
                                        <span class="stat-label">Energy Datasets</span>
                                    </div>
                                    <div class="stat-card">
                                        <span class="stat-value">{{ formatBytes(cacheData?.total_memory_bytes || 0) }}</span>
                                        <span class="stat-label">Memory Usage</span>
                                    </div>
                                </div>
                            </section>

                            <!-- Models List -->
                            <section class="admin-section">
                                <h3>Model Details</h3>
                                <div v-if="modelInfo" class="model-list">
                                    <div class="model-summary">
                                        {{ modelInfo.models_available }} of {{ modelInfo.total_installations }}
                                        installations have trained ML models
                                    </div>
                                    <div v-for="model in modelInfo.models" :key="model.id" class="model-item">
                                        <span class="model-id">{{ model.id }}</span>
                                        <span class="model-type">{{ model.model_type }}</span>
                                        <span class="model-features">{{ model.feature_count }} features</span>
                                    </div>
                                    <div v-if="modelInfo.missing_ids?.length" class="missing-models">
                                        <strong>Missing models:</strong>
                                        {{ modelInfo.missing_ids.join(', ') }}
                                    </div>
                                </div>
                            </section>

                            <!-- Actions -->
                            <section class="admin-section">
                                <h3>Actions</h3>
                                <div class="action-buttons">
                                    <button class="btn-action" @click="refreshCache" :disabled="actionLoading">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M23 4v6h-6M1 20v-6h6"/>
                                            <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
                                        </svg>
                                        Refresh Status
                                    </button>
                                    <button class="btn-action btn-danger" @click="clearCache" :disabled="actionLoading">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                        </svg>
                                        Clear All Caches
                                    </button>
                                </div>
                                <div v-if="actionMessage" class="action-message" :class="{ error: actionError }">
                                    {{ actionMessage }}
                                </div>
                            </section>

                            <!-- Dataset Citation -->
                            <section class="admin-section citation-section">
                                <h3>Dataset</h3>
                                <div v-if="modelInfo?.dataset_citation" class="citation">
                                    <p>{{ modelInfo.dataset_citation.authors }} ({{ modelInfo.dataset_citation.year }})</p>
                                    <p><em>{{ modelInfo.dataset_citation.title }}</em></p>
                                    <p>{{ modelInfo.dataset_citation.publisher }} - DOI: {{ modelInfo.dataset_citation.doi }}</p>
                                </div>
                            </section>
                        </template>
                    </div>
                </div>
            </div>
        </transition>
    </teleport>
</template>

<script>
import { ref, watch } from 'vue'
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

export default {
    name: 'MlAdminPanel',
    props: {
        isOpen: { type: Boolean, default: false }
    },
    emits: ['close'],
    setup(props, { emit }) {
        const loading = ref(false)
        const actionLoading = ref(false)
        const cacheData = ref(null)
        const modelInfo = ref(null)
        const actionMessage = ref('')
        const actionError = ref(false)

        const ML_BASE = '/apps/filantropia_solar/api/v1'

        const fetchData = async () => {
            loading.value = true
            try {
                // Fetch cache status and model info in parallel
                const [cacheRes, modelRes] = await Promise.allSettled([
                    axios.get(generateUrl(`${ML_BASE}/predict/period`).replace('/predict/period', '') + '/../ml-admin/cache'),
                    axios.get(generateUrl(`${ML_BASE}/predict/period`).replace('/predict/period', '') + '/../ml-admin/model-info'),
                ])

                // For now, direct ML service calls may not work through PHP proxy
                // Use a simpler approach: call the ML service endpoints through an admin proxy
                // or directly if CORS allows
                cacheData.value = cacheRes.status === 'fulfilled' ? cacheRes.value.data : null
                modelInfo.value = modelRes.status === 'fulfilled' ? modelRes.value.data : null
            } catch (e) {
                // Expected: admin endpoints may not be proxied yet
                cacheData.value = { models: { count: 0 }, installations_loaded: 0, energy_data: { count: 0 }, total_memory_bytes: 0 }
                modelInfo.value = null
            } finally {
                loading.value = false
            }
        }

        const refreshCache = async () => {
            actionLoading.value = true
            actionMessage.value = ''
            await fetchData()
            actionMessage.value = 'Status refreshed'
            actionError.value = false
            actionLoading.value = false
        }

        const clearCache = async () => {
            if (!confirm('Clear all ML caches? Models will be reloaded on next request.')) return

            actionLoading.value = true
            actionMessage.value = ''
            try {
                await axios.post(generateUrl(`${ML_BASE}/predict/period`).replace('/predict/period', '') + '/../ml-admin/cache/clear')
                actionMessage.value = 'Caches cleared successfully'
                actionError.value = false
                await fetchData()
            } catch (e) {
                actionMessage.value = 'Failed to clear caches: ' + (e.message || 'Unknown error')
                actionError.value = true
            } finally {
                actionLoading.value = false
            }
        }

        const formatBytes = (bytes) => {
            if (bytes < 1024) return bytes + ' B'
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
        }

        const close = () => emit('close')

        // Load data when modal opens
        watch(() => props.isOpen, (newVal) => {
            if (newVal) fetchData()
        })

        return {
            loading,
            actionLoading,
            cacheData,
            modelInfo,
            actionMessage,
            actionError,
            refreshCache,
            clearCache,
            formatBytes,
            close,
        }
    }
}
</script>

<style scoped>
.admin-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    padding: 24px;
}

.admin-modal {
    background: var(--color-main-background, #fff);
    border-radius: 12px;
    width: 100%;
    max-width: 600px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25);
}

.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: var(--color-background-dark, #f5f5f5);
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.modal-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}

.btn-close {
    background: none;
    border: none;
    cursor: pointer;
    padding: 4px;
    color: var(--color-text-lighter, #666);
    border-radius: 4px;
}

.btn-close:hover {
    background: var(--color-background-hover, #e8e8e8);
}

.modal-body {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
}

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

@keyframes spin { to { transform: rotate(360deg); } }

.admin-section {
    margin-bottom: 24px;
}

.admin-section h3 {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--color-text-lighter, #767676);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}

.stat-card {
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 8px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}

.stat-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--color-primary, #0082c9);
}

.stat-label {
    font-size: 12px;
    color: var(--color-text-lighter, #767676);
}

.model-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.model-summary {
    font-size: 13px;
    color: var(--color-text-lighter, #767676);
    margin-bottom: 4px;
}

.model-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 6px;
    font-size: 13px;
}

.model-id {
    flex: 1;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.model-type {
    color: var(--color-primary, #0082c9);
    font-size: 12px;
}

.model-features {
    color: var(--color-text-lighter, #767676);
    font-size: 12px;
    flex-shrink: 0;
}

.missing-models {
    font-size: 12px;
    color: var(--color-text-lighter, #767676);
    padding: 8px;
    background: #fff3e0;
    border-radius: 6px;
    word-break: break-all;
}

.action-buttons {
    display: flex;
    gap: 12px;
}

.btn-action {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 6px;
    background: var(--color-main-background, #fff);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
}

.btn-action:hover:not(:disabled) {
    background: var(--color-background-hover, #f5f5f5);
}

.btn-action:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.btn-danger {
    color: #c62828;
    border-color: #e57373;
}

.btn-danger:hover:not(:disabled) {
    background: #ffebee;
}

.action-message {
    margin-top: 12px;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    background: #e8f5e9;
    color: #2e7d32;
}

.action-message.error {
    background: #ffebee;
    color: #c62828;
}

.citation-section .citation {
    font-size: 13px;
    line-height: 1.6;
    color: var(--color-text-lighter, #555);
    padding: 12px;
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 8px;
}

.citation p {
    margin: 0;
}

/* Transitions */
.modal-fade-enter-active,
.modal-fade-leave-active {
    transition: opacity 0.2s ease;
}

.modal-fade-enter-active .admin-modal,
.modal-fade-leave-active .admin-modal {
    transition: transform 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
    opacity: 0;
}

.modal-fade-enter-from .admin-modal,
.modal-fade-leave-to .admin-modal {
    transform: scale(0.95) translateY(-10px);
}
</style>
