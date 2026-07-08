<template>
    <section class="admin-section">
        <div class="section-header">
            <h3>ML Controls</h3>
            <div class="section-actions">
                <button class="btn-action" @click="$emit('refresh')">Refresh</button>
                <button class="btn-action" @click="$emit('train-all')">Train All</button>
                <button class="btn-action danger" @click="$emit('clear-cache')">Clear Cache</button>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <span class="stat-value">{{ modelInfo?.models_available || 0 }}</span>
                <span class="stat-label">Models Available</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{{ modelInfo?.total_installations || 0 }}</span>
                <span class="stat-label">Total Installations</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{{ cacheStatus?.models?.count || 0 }}</span>
                <span class="stat-label">Cached Models</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{{ cacheStatus?.installations_loaded || 0 }}</span>
                <span class="stat-label">Loaded Installations</span>
            </div>
        </div>

        <div class="model-list" v-if="modelInfo?.models?.length">
            <div class="model-item" v-for="model in modelInfo.models" :key="model.id">
                <div class="model-main">
                    <strong>{{ model.id }}</strong>
                    <span>{{ model.model_type }}</span>
                </div>
                <div class="model-metrics">
                    <span>features: {{ model.feature_count }}</span>
                    <span v-if="model.r2 !== undefined">R²: {{ Number(model.r2).toFixed(3) }}</span>
                    <span v-if="model.mae !== undefined">MAE: {{ Number(model.mae).toFixed(3) }}</span>
                </div>
            </div>
        </div>
    </section>
</template>

<script>
export default {
    name: 'AdminMlControls',
    props: {
        modelInfo: {
            type: Object,
            default: null,
        },
        cacheStatus: {
            type: Object,
            default: null,
        },
    },
    emits: ['refresh', 'train-all', 'clear-cache'],
}
</script>

<style scoped>
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 12px;
}

.section-actions {
    display: flex;
    gap: 8px;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(120px, 1fr));
    gap: 10px;
}

.stat-card {
    background: var(--color-background-dark, #f5f5f5);
    border-radius: 8px;
    padding: 10px;
}

.stat-value {
    display: block;
    font-size: 22px;
    font-weight: 700;
}

.stat-label {
    font-size: 11px;
    color: var(--color-text-lighter, #757575);
}

.btn-action {
    border: 1px solid var(--color-border, #d8d8d8);
    border-radius: 6px;
    background: #fff;
    padding: 7px 10px;
    cursor: pointer;
    font-size: 12px;
}

.btn-action.danger {
    border-color: #ef9a9a;
    color: #c62828;
}

.model-list {
    margin-top: 12px;
    display: grid;
    gap: 8px;
}

.model-item {
    border: 1px solid var(--color-border, #ececec);
    border-radius: 8px;
    padding: 10px;
}

.model-main {
    display: flex;
    justify-content: space-between;
}

.model-metrics {
    display: flex;
    gap: 12px;
    margin-top: 4px;
    font-size: 12px;
    color: var(--color-text-lighter, #666);
}
</style>
