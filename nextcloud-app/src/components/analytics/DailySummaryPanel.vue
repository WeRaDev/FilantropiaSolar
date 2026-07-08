<template>
    <div class="daily-card">
        <h3>Daily Summary</h3>
        <div class="daily-table-wrapper">
            <table class="daily-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Date</th>
                        <th>kWh</th>
                        <th>&euro;</th>
                        <th>Temp</th>
                        <th>Rating</th>
                    </tr>
                </thead>
                <tbody>
                    <tr
                        v-for="(day, idx) in dailySummary"
                        :key="idx"
                        :class="{ active: idx === currentDayIndex }"
                        @click="$emit('select-day', idx)">
                        <td>{{ idx + 1 }}</td>
                        <td>{{ day.date }}</td>
                        <td>{{ day.energy.toFixed(1) }}</td>
                        <td>&euro;{{ (day.energy * 0.15).toFixed(2) }}</td>
                        <td>{{ day.temp.toFixed(0) }}</td>
                        <td>
                            <span class="rating" :class="'rank-' + day.rank">
                                {{ getRatingLabel(day.rank) }}
                            </span>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script>
import { getRatingLabel } from '../../utils/ranking.js'

export default {
    name: 'DailySummaryPanel',
    props: {
        dailySummary: {
            type: Array,
            default: () => [],
        },
        currentDayIndex: {
            type: Number,
            default: 0,
        },
    },
    emits: ['select-day'],
    methods: {
        getRatingLabel,
    },
}
</script>

<style scoped>
.daily-card {
    background: var(--color-background-dark, #f8f8f8);
    border-radius: 8px;
    padding: 16px;
}

.daily-card h3 {
    margin: 0 0 16px 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-lighter, #666);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.daily-table-wrapper {
    max-height: 300px;
    overflow-y: auto;
}

.daily-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}

.daily-table th,
.daily-table td {
    padding: 8px 6px;
    text-align: left;
    border-bottom: 1px solid var(--color-border, #e0e0e0);
}

.daily-table th {
    font-weight: 600;
    color: var(--color-text-lighter, #666);
    position: sticky;
    top: 0;
    background: var(--color-background-dark, #f8f8f8);
}

.daily-table tr.active {
    background: var(--color-primary-light, #e3f2fd);
}

.daily-table tr:hover {
    background: var(--color-background-hover, #f0f0f0);
    cursor: pointer;
}

.rating {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
}

.rating.rank-0 { background: #B0B0B0; color: white; }
.rating.rank-1 { background: #DC143C; color: white; }
.rating.rank-2 { background: #FF8C00; color: white; }
.rating.rank-3 { background: #FFD700; color: #333; }
.rating.rank-4 { background: #32CD32; color: white; }
.rating.rank-5 { background: #87CEEB; color: #333; }
</style>
