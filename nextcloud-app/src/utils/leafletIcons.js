/**
 * Leaflet default marker icons break under webpack (wrong image paths).
 * Provide CDN-backed defaults + a simple pin for edit/pick maps.
 */
import L from 'leaflet'

const LEAFLET_IMG = 'https://unpkg.com/leaflet@1.9.4/dist/images'

let defaultsFixed = false

export function fixLeafletDefaultIcons() {
	if (defaultsFixed) return
	// Drop webpack-broken prototype URLs
	// eslint-disable-next-line no-underscore-dangle
	delete L.Icon.Default.prototype._getIconUrl
	L.Icon.Default.mergeOptions({
		iconRetinaUrl: `${LEAFLET_IMG}/marker-icon-2x.png`,
		iconUrl: `${LEAFLET_IMG}/marker-icon.png`,
		shadowUrl: `${LEAFLET_IMG}/marker-shadow.png`,
	})
	defaultsFixed = true
}

/** Draggable location pin used on edit/create maps. */
export function createLocationPinIcon() {
	fixLeafletDefaultIcons()
	const svg = encodeURIComponent(`
		<svg xmlns="http://www.w3.org/2000/svg" width="28" height="40" viewBox="0 0 28 40">
			<path d="M14 0C6.3 0 0 6.3 0 14c0 10.5 14 26 14 26s14-15.5 14-26C28 6.3 21.7 0 14 0z"
				fill="#0082c9" stroke="#ffffff" stroke-width="1.5"/>
			<circle cx="14" cy="14" r="5" fill="#ffffff"/>
		</svg>
	`.trim())
	return L.icon({
		iconUrl: `data:image/svg+xml,${svg}`,
		iconSize: [28, 40],
		iconAnchor: [14, 40],
		popupAnchor: [0, -36],
	})
}
