import { describe, expect, it, vi } from 'vitest'
import { addOpenStreetMapLayer } from '../../../src/utils/openStreetMap.js'

describe('OpenStreetMap tile layer', () => {
    it('uses the canonical endpoint, a valid referrer policy, and linked attribution', () => {
        const map = { addLayer: vi.fn() }
        const layer = addOpenStreetMapLayer(map, { maxZoom: 18 })

        expect(layer._url).toBe('https://tile.openstreetmap.org/{z}/{x}/{y}.png')
        expect(layer.options.referrerPolicy).toBe('strict-origin-when-cross-origin')
        expect(layer.options.attribution).toContain(
            '<a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        )
        expect(layer.options.maxZoom).toBe(18)
        expect(map.addLayer).toHaveBeenCalledWith(layer)
    })
})
