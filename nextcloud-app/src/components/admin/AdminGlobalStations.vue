<template>
	<section class="admin-section">
		<div class="section-header">
			<div>
				<h3>Stations &amp; lifecycle</h3>
				<p class="section-sub">
					Promote Virtual → Planned, mark Planned installed (Running/Existing), soft-remove from public.
					Hard delete remains dataset-only.
				</p>
			</div>
			<div class="section-actions">
				<button class="btn-action" @click="$emit('create')">Add Dataset Station</button>
				<button class="btn-action" @click="$emit('reimport')">Re-import Dataset</button>
			</div>
		</div>

		<div class="filters-row">
			<label class="filter-field">
				<span>Lifecycle</span>
				<select
					:value="lifecycleFilter"
					:disabled="disabled"
					@change="$emit('filter-lifecycle', $event.target.value)"
				>
					<option value="all">All states</option>
					<option value="virtual">Virtual</option>
					<option value="planned">Planned</option>
					<option value="running">Running</option>
				</select>
			</label>
			<label class="filter-field">
				<span>Source</span>
				<select
					:value="sourceFilter"
					:disabled="disabled"
					@change="$emit('filter-source', $event.target.value)"
				>
					<option value="all">All sources</option>
					<option value="dataset">Dataset</option>
					<option value="user">User</option>
					<option value="crm">CRM</option>
				</select>
			</label>
			<label class="filter-check">
				<input
					type="checkbox"
					:checked="includeSoftRemoved"
					:disabled="disabled"
					@change="$emit('filter-soft-removed', $event.target.checked)"
				>
				<span>Show soft-removed</span>
			</label>
			<div v-if="counts" class="counts">
				<span>All {{ counts.all ?? 0 }}</span>
				<span>V {{ counts.virtual ?? 0 }}</span>
				<span>P {{ counts.planned ?? 0 }}</span>
				<span>R {{ counts.running ?? 0 }}</span>
				<span>SR {{ counts.soft_removed ?? 0 }}</span>
			</div>
		</div>

		<div class="table-wrap">
			<table class="stations-table">
				<thead>
					<tr>
						<th>Name</th>
						<th>Location</th>
						<th>Capacity (kWp)</th>
						<th>Source</th>
						<th>Lifecycle</th>
						<th>Public</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="station in stations"
						:key="station.id"
						:class="{ 'row-soft-removed': station.soft_removed }"
					>
						<td>
							<div class="name-cell">
								<span>{{ station.name }}</span>
								<small v-if="station.serial_number">{{ station.serial_number }}</small>
							</div>
						</td>
						<td>{{ station.location }}</td>
						<td>{{ Number(station.capacity_kwp || 0).toFixed(2) }}</td>
						<td>
							<span class="badge source">{{ station.source || '—' }}</span>
						</td>
						<td>
							<span
								class="badge lifecycle"
								:class="lifecycleClass(station)"
							>
								{{ lifecycleLabel(station) }}
							</span>
						</td>
						<td>
							<span
								class="badge public"
								:class="publicClass(station)"
							>
								{{ publicLabel(station) }}
							</span>
						</td>
						<td class="actions-cell">
							<button
								class="btn-link"
								:disabled="disabled || !canPromote(station)"
								title="Virtual → Planned"
								@click="$emit('promote', station)"
							>
								Promote
							</button>
							<button
								class="btn-link"
								:disabled="disabled || !canInstall(station)"
								title="Planned → Running (Existing on public map)"
								@click="$emit('install', station)"
							>
								Install
							</button>
							<button
								class="btn-link warn"
								:disabled="disabled || !canSoftRemove(station)"
								title="Hide from public listing"
								@click="$emit('soft-remove', station)"
							>
								Soft-remove
							</button>
							<button
								v-if="station.source === 'dataset'"
								class="btn-link"
								:disabled="disabled"
								@click="$emit('edit', station)"
							>
								Edit
							</button>
							<button
								v-if="station.source === 'dataset'"
								class="btn-link"
								:disabled="disabled"
								@click="$emit('train', station)"
							>
								Train
							</button>
							<button
								v-if="station.source === 'dataset'"
								class="btn-link danger"
								:disabled="disabled"
								@click="$emit('delete', station)"
							>
								Delete
							</button>
						</td>
					</tr>
					<tr v-if="stations.length === 0">
						<td colspan="7" class="empty-cell">No stations match the current filters.</td>
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
		lifecycleFilter: {
			type: String,
			default: 'all',
		},
		sourceFilter: {
			type: String,
			default: 'all',
		},
		includeSoftRemoved: {
			type: Boolean,
			default: true,
		},
		counts: {
			type: Object,
			default: null,
		},
		disabled: {
			type: Boolean,
			default: false,
		},
	},
	emits: [
		'create',
		'edit',
		'delete',
		'reimport',
		'train',
		'promote',
		'install',
		'soft-remove',
		'filter-lifecycle',
		'filter-source',
		'filter-soft-removed',
	],
	methods: {
		lifecycleLabel(station) {
			if (station.soft_removed) {
				return `${station.lifecycle_state || '—'} (removed)`
			}
			return station.lifecycle_state || '—'
		},
		lifecycleClass(station) {
			const state = station.lifecycle_state || 'running'
			return {
				virtual: state === 'virtual',
				planned: state === 'planned',
				running: state === 'running',
				removed: Boolean(station.soft_removed),
			}
		},
		publicLabel(station) {
			if (station.soft_removed || station.public_category === 'none') {
				return 'hidden'
			}
			return station.public_category || '—'
		},
		publicClass(station) {
			const cat = station.soft_removed ? 'none' : (station.public_category || 'none')
			return {
				planned: cat === 'planned',
				existing: cat === 'existing',
				none: cat === 'none',
			}
		},
		canPromote(station) {
			if (station.soft_removed) {
				return false
			}
			return station.lifecycle_state === 'virtual'
		},
		canInstall(station) {
			if (station.soft_removed) {
				return false
			}
			return station.lifecycle_state === 'planned'
		},
		canSoftRemove(station) {
			return !station.soft_removed
		},
	},
}
</script>

<style scoped>
.section-header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
	margin-bottom: 12px;
}

.section-sub {
	margin: 4px 0 0;
	font-size: 12px;
	color: var(--color-text-lighter, #757575);
	max-width: 520px;
}

.section-actions {
	display: flex;
	gap: 8px;
	flex-shrink: 0;
}

.filters-row {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 12px 16px;
	margin-bottom: 12px;
	padding: 10px 12px;
	background: var(--color-background-dark, #f6f6f6);
	border-radius: 8px;
}

.filter-field {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 12px;
}

.filter-field select {
	border: 1px solid var(--color-border, #d8d8d8);
	border-radius: 6px;
	padding: 5px 8px;
	background: #fff;
}

.filter-check {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 12px;
	cursor: pointer;
}

.counts {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	margin-left: auto;
	font-size: 11px;
	color: var(--color-text-lighter, #666);
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
	vertical-align: top;
}

.row-soft-removed {
	opacity: 0.65;
}

.name-cell {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.name-cell small {
	color: var(--color-text-lighter, #888);
	font-size: 11px;
}

.badge {
	display: inline-block;
	padding: 2px 8px;
	border-radius: 999px;
	font-size: 11px;
	font-weight: 600;
	text-transform: lowercase;
	background: #eee;
	color: #444;
}

.badge.source {
	background: #e3f2fd;
	color: #1565c0;
}

.badge.lifecycle.virtual {
	background: #f3e5f5;
	color: #7b1fa2;
}

.badge.lifecycle.planned {
	background: #fff3e0;
	color: #ef6c00;
}

.badge.lifecycle.running {
	background: #e8f5e9;
	color: #2e7d32;
}

.badge.lifecycle.removed {
	text-decoration: line-through;
}

.badge.public.planned {
	background: #fff8e1;
	color: #f9a825;
}

.badge.public.existing {
	background: #e0f2f1;
	color: #00695c;
}

.badge.public.none {
	background: #eceff1;
	color: #607d8b;
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
	font-size: 12px;
}

.btn-link:disabled {
	color: #9e9e9e;
	cursor: not-allowed;
}

.btn-link.warn {
	color: #ef6c00;
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
