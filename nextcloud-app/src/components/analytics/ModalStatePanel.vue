<template>
    <!-- Loading state -->
    <div v-if="state === 'loading'" class="loading-overlay">
        <div class="spinner"></div>
        <p>{{ loadingMessage }}</p>
    </div>

    <!-- No data state -->
    <div v-else class="no-data-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M3 3v18h18"/>
            <path d="m19 9-5 5-4-4-3 3"/>
        </svg>
        <h3>No Analysis Data</h3>
        <p>Click below to generate analysis for this installation.</p>
        <button class="btn-primary" @click="$emit('generate')">
            Generate analysis
        </button>
    </div>
</template>

<script>
export default {
    name: 'ModalStatePanel',
    props: {
        state: {
            type: String,
            required: true,
            validator: (v) => ['loading', 'no-data'].includes(v),
        },
        loadingMessage: { type: String, default: 'Generating analysis...' },
        timeframeDays: { type: Number, required: true },
    },
    emits: ['generate'],
}
</script>

<style scoped>
/* Loading Overlay */
.loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.9);
    gap: 16px;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--color-border, #e0e0e0);
    border-top-color: var(--color-primary, #0082c9);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* No Data State */
.no-data-state {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--color-text-lighter, #666);
    gap: 16px;
}

.no-data-state h3 {
    margin: 0;
    font-size: 20px;
    color: var(--color-main-text, #333);
}

.btn-primary {
    padding: 12px 24px;
    background: var(--color-primary, #0082c9);
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
}

.btn-primary:hover {
    background: var(--color-primary-hover, #0070b0);
}
</style>
