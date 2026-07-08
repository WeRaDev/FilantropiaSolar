import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { getRequestToken } from '@nextcloud/auth'
import MlAdminPanel from './components/MlAdminPanel.vue'

__webpack_nonce__ = btoa(getRequestToken())

const container = document.getElementById('filantropia_solar_admin_vue')
if (container) {
    const app = createApp({
        render: () => h(MlAdminPanel, { embedded: true, isOpen: true }),
    })
    app.use(createPinia())
    app.mount(container)
}
