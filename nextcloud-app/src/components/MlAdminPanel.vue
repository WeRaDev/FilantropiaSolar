<template>
    <teleport v-if="!embedded" to="body">
        <div v-if="isOpen" class="admin-modal-overlay" @click.self="close">
            <div class="admin-modal">
                <div class="panel-content">
                    <header class="modal-header">
                        <h2>FilantropiaSolar Admin Dashboard</h2>
                        <button class="btn-close" @click="close">✕</button>
                    </header>
                    <AdminPanelBody />
                </div>
            </div>
        </div>
    </teleport>

    <div v-else class="embedded-container">
        <div class="panel-content embedded">
            <header class="modal-header">
                <h2>FilantropiaSolar Admin Dashboard</h2>
            </header>
            <AdminPanelBody />
        </div>
    </div>
</template>

<script>
import { computed, defineComponent, onMounted, reactive, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAdminStore } from '../store/admin.js'
import AdminMlControls from './admin/AdminMlControls.vue'
import AdminGlobalStations from './admin/AdminGlobalStations.vue'

export default {
    name: 'MlAdminPanel',
    components: {
        AdminMlControls,
        AdminGlobalStations,
        AdminPanelBody: defineComponent({
            name: 'AdminPanelBody',
            setup() {
                const store = useAdminStore()
                const { loading, actionLoading, stations, cacheStatus, modelInfo, settings, message, error } = storeToRefs(store)
                const form = reactive({
                    id: null,
                    name: '',
                    location: '',
                    latitude: '',
                    longitude: '',
                    capacity_kwp: '',
                    serial_number: '',
                })
                const showForm = reactive({ value: false })

                const resetForm = () => {
                    form.id = null
                    form.name = ''
                    form.location = ''
                    form.latitude = ''
                    form.longitude = ''
                    form.capacity_kwp = ''
                    form.serial_number = ''
                }

                const openCreate = () => {
                    resetForm()
                    showForm.value = true
                }

                const openEdit = (station) => {
                    form.id = station.id
                    form.name = station.name || ''
                    form.location = station.location || ''
                    form.latitude = String(station.latitude ?? '')
                    form.longitude = String(station.longitude ?? '')
                    form.capacity_kwp = String(station.capacity_kwp ?? '')
                    form.serial_number = station.serial_number || ''
                    showForm.value = true
                }

                const submitStation = async () => {
                    await store.saveStation({
                        id: form.id,
                        name: form.name,
                        location: form.location,
                        latitude: Number(form.latitude),
                        longitude: Number(form.longitude),
                        capacity_kwp: Number(form.capacity_kwp),
                        serial_number: form.serial_number,
                    })
                    showForm.value = false
                }

                const removeStation = async (station) => {
                    if (!confirm(`Delete ${station.name}?`)) {
                        return
                    }
                    await store.deleteStation(station.id)
                }

                const trainStation = async (station) => {
                    await store.trainStation(station.installation_id || station.serial_number || String(station.id))
                }

                const refreshAll = async () => {
                    await Promise.all([
                        store.fetchStations(),
                        store.fetchModelInfo(),
                        store.fetchCacheStatus(),
                    ])
                }

                onMounted(async () => {
                    await store.loadAll()
                })

                return {
                    loading,
                    actionLoading,
                    stations,
                    cacheStatus,
                    modelInfo,
                    settings,
                    message,
                    error,
                    form,
                    showForm,
                    openCreate,
                    openEdit,
                    submitStation,
                    removeStation,
                    trainStation,
                    refreshAll,
                    saveSettings: store.saveSettings,
                    clearCache: store.clearCache,
                    trainAll: store.trainAll,
                    reimportDataset: store.reimportDataset,
                }
            },
            template: `
                <div class="modal-body">
                    <div v-if="loading" class="loading-state">
                        <div class="spinner"></div>
                        <span>Loading admin dashboard…</span>
                    </div>
                    <template v-else>
                        <section class="admin-section">
                            <h3>Settings</h3>
                            <div class="settings-row">
                                <label for="ml-service-url">ML Service URL</label>
                                <input id="ml-service-url" v-model="settings.ml_service_url" type="url" />
                                <button class="btn-action" :disabled="actionLoading" @click="saveSettings">Save</button>
                            </div>
                        </section>

                        <AdminMlControls
                            :modelInfo="modelInfo"
                            :cacheStatus="cacheStatus"
                            @refresh="refreshAll"
                            @clear-cache="clearCache"
                            @train-all="trainAll"
                        />

                        <AdminGlobalStations
                            :stations="stations"
                            @create="openCreate"
                            @edit="openEdit"
                            @delete="removeStation"
                            @train="trainStation"
                            @reimport="reimportDataset"
                        />

                        <section v-if="showForm.value" class="admin-section station-form">
                            <h3>{{ form.id ? 'Edit Global Station' : 'Create Global Station' }}</h3>
                            <div class="form-grid">
                                <input v-model="form.name" placeholder="Name" />
                                <input v-model="form.location" placeholder="Location" />
                                <input v-model="form.serial_number" placeholder="Serial Number" />
                                <input v-model="form.capacity_kwp" placeholder="Capacity kWp" type="number" step="0.01" />
                                <input v-model="form.latitude" placeholder="Latitude" type="number" step="0.000001" />
                                <input v-model="form.longitude" placeholder="Longitude" type="number" step="0.000001" />
                            </div>
                            <div class="section-actions">
                                <button class="btn-action" :disabled="actionLoading" @click="submitStation">Save Station</button>
                                <button class="btn-action" @click="showForm.value = false">Cancel</button>
                            </div>
                        </section>

                        <p v-if="message" class="feedback success">{{ message }}</p>
                        <p v-if="error" class="feedback error">{{ error }}</p>
                    </template>
                </div>
            `,
        }),
    },
    props: {
        isOpen: {
            type: Boolean,
            default: false,
        },
        embedded: {
            type: Boolean,
            default: false,
        },
    },
    emits: ['close'],
    setup(props, { emit }) {
        const visible = computed(() => props.embedded || props.isOpen)
        watch(visible, () => {
            // reactive placeholder for potential future side-effects
        })
        const close = () => emit('close')
        return { close }
    },
}
</script>

<style scoped>
.embedded-container {
    width: 100%;
}

.admin-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    padding: 24px;
}

.admin-modal {
    width: 100%;
    max-width: 1080px;
    max-height: 92vh;
}

.panel-content {
    background: var(--color-main-background, #fff);
    border-radius: 12px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
    overflow: hidden;
}

.panel-content.embedded {
    box-shadow: none;
    border: 1px solid var(--color-border, #e5e5e5);
}

.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--color-border, #ececec);
}

.modal-header h2 {
    margin: 0;
    font-size: 20px;
}

.btn-close {
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 18px;
}

.modal-body {
    padding: 16px 20px 24px;
    max-height: calc(92vh - 64px);
    overflow-y: auto;
}

.admin-section {
    margin-bottom: 18px;
}

.admin-section h3 {
    margin: 0 0 10px;
    font-size: 14px;
    text-transform: uppercase;
}

.loading-state {
    display: flex;
    gap: 10px;
    align-items: center;
    justify-content: center;
    min-height: 140px;
}

.spinner {
    width: 26px;
    height: 26px;
    border: 3px solid #ddd;
    border-top-color: #0082c9;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

.settings-row {
    display: grid;
    grid-template-columns: 130px 1fr auto;
    gap: 10px;
    align-items: center;
}

.settings-row input,
.form-grid input {
    border: 1px solid var(--color-border, #d9d9d9);
    border-radius: 6px;
    padding: 7px 10px;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(120px, 1fr));
    gap: 10px;
    margin-bottom: 10px;
}

.section-actions {
    display: flex;
    gap: 8px;
}

.btn-action {
    border: 1px solid var(--color-border, #d9d9d9);
    border-radius: 6px;
    background: #fff;
    padding: 7px 10px;
    cursor: pointer;
}

.feedback {
    margin: 8px 0 0;
    padding: 8px 10px;
    border-radius: 6px;
}

.feedback.success {
    color: #2e7d32;
    background: #e8f5e9;
}

.feedback.error {
    color: #c62828;
    background: #ffebee;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}
</style>