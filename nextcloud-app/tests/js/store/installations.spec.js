/**
 * Tests for Installations Pinia Store
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useInstallationsStore } from '@/store/installations'
import axios from '@nextcloud/axios'

describe('Installations Store', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
    })

    describe('Initial State', () => {
        it('should have empty installations array', () => {
            const store = useInstallationsStore()
            expect(store.installations).toEqual([])
        })

        it('should have null selectedId', () => {
            const store = useInstallationsStore()
            expect(store.selectedId).toBeNull()
        })

        it('should not be loading initially', () => {
            const store = useInstallationsStore()
            expect(store.loading).toBe(false)
        })

        it('should have no error initially', () => {
            const store = useInstallationsStore()
            expect(store.error).toBeNull()
        })
    })

    describe('Getters', () => {
        it('should calculate totalCapacity correctly', () => {
            const store = useInstallationsStore()
            store.installations = [
                { id: 1, capacity_kwp: '5.5' },
                { id: 2, capacity_kwp: '10.0' },
                { id: 3, capacity_kwp: '7.25' },
            ]

            expect(store.totalCapacity).toBeCloseTo(22.75, 2)
        })

        it('should return 0 totalCapacity for empty installations', () => {
            const store = useInstallationsStore()
            expect(store.totalCapacity).toBe(0)
        })

        it('should return selectedInstallation correctly', () => {
            const store = useInstallationsStore()
            store.installations = [
                { id: 1, name: 'Solar A' },
                { id: 2, name: 'Solar B' },
            ]
            store.selectedId = 2

            expect(store.selectedInstallation).toEqual({ id: 2, name: 'Solar B' })
        })

        it('should return null for selectedInstallation when no selection', () => {
            const store = useInstallationsStore()
            store.installations = [{ id: 1, name: 'Solar A' }]

            expect(store.selectedInstallation).toBeNull()
        })

        it('should group installations by location', () => {
            const store = useInstallationsStore()
            store.installations = [
                { id: 1, nearest_location: 'Lisbon' },
                { id: 2, nearest_location: 'Faro' },
                { id: 3, nearest_location: 'Lisbon' },
            ]

            const grouped = store.installationsByLocation
            expect(grouped['Lisbon']).toHaveLength(2)
            expect(grouped['Faro']).toHaveLength(1)
        })

        it('should count online installations', () => {
            const store = useInstallationsStore()
            store.installations = [
                { id: 1, status: 'online' },
                { id: 2, status: 'offline' },
                { id: 3, status: 'online' },
            ]

            expect(store.onlineCount).toBe(2)
        })
    })

    describe('Actions', () => {
        it('should fetch installations successfully', async () => {
            const store = useInstallationsStore()
            const mockInstallations = [
                { id: 1, name: 'Solar A', capacity_kwp: '5.0' },
                { id: 2, name: 'Solar B', capacity_kwp: '10.0' },
            ]

            axios.get.mockResolvedValueOnce({
                data: { installations: mockInstallations },
            })

            await store.fetchInstallations()

            expect(store.installations).toEqual(mockInstallations)
            expect(store.loading).toBe(false)
            expect(store.error).toBeNull()
        })

        it('should handle fetch error', async () => {
            const store = useInstallationsStore()
            axios.get.mockRejectedValueOnce(new Error('Network error'))

            await store.fetchInstallations()

            expect(store.installations).toEqual([])
            expect(store.error).toBe('Network error')
        })

        it('should select installation', () => {
            const store = useInstallationsStore()
            store.selectInstallation(42)

            expect(store.selectedId).toBe(42)
        })

        it('should clear selection', () => {
            const store = useInstallationsStore()
            store.selectedId = 42
            store.clearSelection()

            expect(store.selectedId).toBeNull()
        })

        it('should create installation', async () => {
            const store = useInstallationsStore()
            const newInstallation = {
                id: 3,
                name: 'New Solar',
                capacity_kwp: '7.5',
            }

            axios.post.mockResolvedValueOnce({
                data: { installation: newInstallation },
            })

            const result = await store.createInstallation({
                name: 'New Solar',
                capacity_kwp: 7.5,
            })

            expect(store.installations).toContainEqual(newInstallation)
            expect(result).toEqual(newInstallation)
        })

        it('should delete installation', async () => {
            const store = useInstallationsStore()
            store.installations = [
                { id: 1, name: 'Solar A' },
                { id: 2, name: 'Solar B' },
            ]
            store.selectedId = 1

            axios.delete.mockResolvedValueOnce({})

            await store.deleteInstallation(1)

            expect(store.installations).toHaveLength(1)
            expect(store.installations[0].id).toBe(2)
            expect(store.selectedId).toBeNull()
        })

        it('should update installation', async () => {
            const store = useInstallationsStore()
            store.installations = [
                { id: 1, name: 'Solar A', capacity_kwp: '5.0' },
            ]

            const updated = { id: 1, name: 'Solar A Updated', capacity_kwp: '6.0' }
            axios.put.mockResolvedValueOnce({
                data: { installation: updated },
            })

            const result = await store.updateInstallation(1, { name: 'Solar A Updated' })

            expect(store.installations[0].name).toBe('Solar A Updated')
            expect(result).toEqual(updated)
        })
    })

    describe('Portuguese Locations', () => {
        it('should handle installations in all Portuguese locations', () => {
            const store = useInstallationsStore()
            store.installations = [
                { id: 1, nearest_location: 'Lisbon' },
                { id: 2, nearest_location: 'Setubal' },
                { id: 3, nearest_location: 'Faro' },
                { id: 4, nearest_location: 'Braga' },
                { id: 5, nearest_location: 'Tavira' },
                { id: 6, nearest_location: 'Loule' },
            ]

            const grouped = store.installationsByLocation
            expect(Object.keys(grouped)).toHaveLength(6)
        })
    })
})
