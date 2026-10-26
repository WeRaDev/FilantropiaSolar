import L from 'leaflet'

const TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const REFERRER_POLICY = 'strict-origin-when-cross-origin'

export function addOpenStreetMapLayer(map, options = {}) {
    return L.tileLayer(TILE_URL, {
        ...options,
        attribution: ATTRIBUTION,
        referrerPolicy: REFERRER_POLICY,
    }).addTo(map)
}
