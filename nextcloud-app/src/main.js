/**
 * FilantropiaSolar - Vue.js Entry Point
 *
 * Initializes the Vue 3 application with Pinia state management
 * and Vue Router for navigation.
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'

import { generateUrl } from '@nextcloud/router'
import { getRequestToken } from '@nextcloud/auth'

import App from './App.vue'
import Dashboard from './views/Dashboard.vue'

// CSRF token setup for Nextcloud
__webpack_nonce__ = btoa(getRequestToken())

// Vue Router configuration - Single dashboard following layout.specs.md
const routes = [
    {
        path: '/',
        name: 'dashboard',
        component: Dashboard,
        meta: { title: 'FilantropiaSolar Dashboard' },
    },
]

const router = createRouter({
    history: createWebHashHistory(generateUrl('/apps/filantropia_solar')),
    routes,
})

// Update document title on navigation
router.afterEach((to) => {
    const baseTitle = 'FilantropiaSolar'
    document.title = to.meta.title
        ? `${to.meta.title} - ${baseTitle}`
        : baseTitle
})

// Pinia store
const pinia = createPinia()

// Create Vue app
const app = createApp(App)

// Register plugins
app.use(pinia)
app.use(router)

// Golden brand colors as global properties (for programmatic use)
app.config.globalProperties.$goldenColors = {
    primary: '#C4B552',
    secondary: '#D4C563',
    olive: '#A89D3F',
    warmOrange: '#E8A94B',
    creamBg: '#FDFBF5',
    charcoal: '#2D2D2D',
}

// Default grid price (inherited from Python v1.2.x)
app.config.globalProperties.$defaultGridPrice = 0.15

// Portuguese locations (inherited from Python v1.2.x)
app.config.globalProperties.$locations = {
    Lisbon: { lat: 38.7223, lon: -9.1393 },
    Setubal: { lat: 38.5244, lon: -8.8882 },
    Faro: { lat: 37.0194, lon: -7.9304 },
    Braga: { lat: 41.5454, lon: -8.4265 },
    Tavira: { lat: 37.1279, lon: -7.6486 },
    Loule: { lat: 37.1376, lon: -8.0197 },
}

// Mount application
const container = document.getElementById('filantropia-solar-app')
if (container) {
    app.mount(container)
}

export { app, router, pinia }
