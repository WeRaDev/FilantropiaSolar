<template>
    <section class="admin-section">
        <div class="section-header">
            <h3>Global Dataset Stations</h3>
            <div class="section-actions">
                <button class="btn-action" @click="$emit('create')">Add Station</button>
                <button class="btn-action" @click="$emit('reimport')">Re-import Dataset</button>
            </div>
        </div>

        <div class="table-wrap">
            <table class="stations-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Location</th>
                        <th>Capacity (kWp)</th>
                        <th>Serial</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="station in stations" :key="station.id">
                        <td>{{ station.name }}</td>
                        <td>{{ station.location }}</td>
                        <td>{{ Number(station.capacity_kwp || 0).toFixed(2) }}</td>
                        <td>{{ station.serial_number }}</td>
                        <td class="actions-cell">
                            <button class="btn-link" @click="$emit('edit', station)">Edit</button>
                            <button class="btn-link" @click="$emit('train', station)">Train</button>
                            <button class="btn-link danger" @click="$emit('delete', station)">Delete</button>
                        </td>
                    </tr>
                    <tr v-if="stations.length === 0">
                        <td colspan="5" class="empty-cell">No global dataset stations found.</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </section>
</template>

<script>
export default {
    name: 'AdminGlobalStations',
    props: {
        stations: {
            type: Array,
            default: () => [],
        },
    },
    emits: ['create', 'edit', 'delete', 'reimport', 'train'],
}
</script>

<style scoped>
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
}

.section-actions {
    display: flex;
    gap: 8px;
}

.table-wrap {
    overflow-x: auto;
}

.stations-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.stations-table th,
.stations-table td {
    padding: 10px;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
    text-align: left;
}

.actions-cell {
    white-space: nowrap;
}

.btn-link {
    background: none;
    border: none;
    color: #2962ff;
    cursor: pointer;
    padding: 0 6px 0 0;
}

.btn-link.danger {
    color: #c62828;
}

.btn-action {
    border: 1px solid var(--color-border, #d8d8d8);
    border-radius: 6px;
    background: #fff;
    padding: 7px 10px;
    cursor: pointer;
    font-size: 12px;
}

.empty-cell {
    color: var(--color-text-lighter, #757575);
    text-align: center;
}
</style>
