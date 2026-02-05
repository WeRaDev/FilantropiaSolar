/**
 * Vitest Configuration for FilantropiaSolar Vue Tests
 */

import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
    plugins: [vue()],

    test: {
        globals: true,
        environment: 'jsdom',
        include: ['tests/js/**/*.{test,spec}.{js,ts}'],
        coverage: {
            provider: 'v8',
            reporter: ['text', 'html'],
            include: ['src/**/*.{js,vue}'],
            exclude: ['src/main.js'],
        },
        setupFiles: ['tests/js/setup.js'],
    },

    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src'),
            // Mock Nextcloud modules
            '@nextcloud/router': path.resolve(__dirname, 'tests/js/mocks/router.js'),
            '@nextcloud/axios': path.resolve(__dirname, 'tests/js/mocks/axios.js'),
            '@nextcloud/auth': path.resolve(__dirname, 'tests/js/mocks/auth.js'),
            '@nextcloud/l10n': path.resolve(__dirname, 'tests/js/mocks/l10n.js'),
        },
    },
})
