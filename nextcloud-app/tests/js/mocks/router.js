/**
 * Mock for @nextcloud/router
 */

export function generateUrl(path) {
    return `/apps/filantropia_solar${path}`
}

export function generateOcsUrl(path) {
    return `/ocs/v2.php/apps/filantropia_solar${path}`
}

export function generateFilePath(app, type, path) {
    return `/${app}/${type}/${path}`
}

export function imagePath(app, image) {
    return `/apps/${app}/img/${image}`
}

export function getRootUrl() {
    return ''
}
