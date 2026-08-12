<template>
	<div class="admin-shell" :class="{ embedded, modal: !embedded }">
		<div v-if="!embedded && isOpen" class="admin-modal-overlay" @click.self="close">
			<div class="admin-modal">
				<div class="panel-content">
					<header class="modal-header">
						<h2>Admin</h2>
						<button type="button" class="btn-close" @click="close">Close</button>
					</header>
					<AdminPanelBody />
				</div>
			</div>
		</div>

		<div v-else-if="embedded" class="embedded-container">
			<div class="panel-content embedded">
				<AdminPanelBody />
			</div>
		</div>
	</div>
</template>

<script>
import AdminPanelBody from './admin/AdminPanelBody.vue'

export default {
	name: 'MlAdminPanel',
	components: {
		AdminPanelBody,
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
		const close = () => emit('close')
		return { close }
	},
}
</script>

<style scoped>
.embedded-container,
.panel-content.embedded {
	width: 100%;
	height: 100%;
	min-height: 0;
}

.panel-content.embedded {
	background: var(--color-main-background, #fff);
	overflow: hidden;
	display: flex;
	flex-direction: column;
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
	max-height: 92vh;
	display: flex;
	flex-direction: column;
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
	border: 1px solid var(--color-border, #d8d8d8);
	background: #fff;
	border-radius: 6px;
	cursor: pointer;
	padding: 6px 10px;
}
</style>
