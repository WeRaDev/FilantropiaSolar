/**
 * Mock for @nextcloud/auth
 */

export function getRequestToken() {
    return 'mock-csrf-token'
}

export function getCurrentUser() {
    return {
        uid: 'testuser',
        displayName: 'Test User',
        isAdmin: false,
    }
}

export function onRequestTokenUpdate(callback) {
    // No-op
}
