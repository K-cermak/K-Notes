import { defineStore } from 'pinia'
import { liveQuery, type Subscription } from 'dexie'
import { computed, ref } from 'vue'
import { api, call, isFailure } from '@/api/client'
import type { components } from '@/api/schema'
import { deviceId, deviceSettings, getMeta, setMeta } from '@/db/meta'
import { db } from '@/db/schema'
import { BlobSync } from '@/sync/blobs'
import { SyncEngine, type SyncState } from '@/sync/engine'
import { apiTransport, blobApi } from '@/sync/transport'
import { i18n } from '@/i18n'
import { useSessionStore } from './session'
import { useSnackbarStore } from './snackbar'

type StorageStatus = components['schemas']['StorageStatus']

export const useSyncStore = defineStore('sync', () => {
  const state = ref<SyncState>('idle')
  const unsent = ref(0)
  const rejected = ref(0)
  // Kept on the device, so an offline start can still tell when the notes last reached the server.
  const lastSynced = ref<number | null>(null)
  // The quota as of the last sync, kept for an offline start (SPEC 7, Storage quotas).
  const storage = ref<StorageStatus | null>(null)
  const storageFull = computed(() => storage.value?.full ?? false)
  const snackbar = useSnackbarStore()

  async function refreshStorage(): Promise<void> {
    try {
      const status = await call(() => api.GET('/api/v1/me/storage'))
      storage.value = status
      // The plain object: IndexedDB cannot store Vue's reactive proxy that storage.value returns.
      await setMeta(db, 'storage', status)
    } catch (e) {
      if (!isFailure(e)) throw e
    }
  }

  /** For actions that add data: false, with a message, while the user is over the quota. */
  function hasRoom(): boolean {
    if (!storageFull.value) return true
    snackbar.show(i18n.global.t('storage.full'))
    return false
  }
  let engine: SyncEngine | null = null
  const blobs = new BlobSync(db, blobApi, {
    onDemand: async () => (await deviceSettings(db)).downloadOnDemand,
    onRefused: (count) => {
      rejected.value += count
    },
  })
  let outboxCount: Subscription | null = null

  async function start(): Promise<void> {
    if (engine) return
    const session = useSessionStore()
    engine = new SyncEngine({
      db,
      transport: apiTransport,
      blobs,
      deviceId: await deviceId(db),
      onState: (value) => {
        state.value = value
        if (value === 'synced') {
          lastSynced.value = Date.now()
          void setMeta(db, 'lastSynced', lastSynced.value)
          void refreshStorage()
        }
        if (value === 'unauthorized') session.expired = true
      },
      onRejected: (results) => {
        rejected.value += results.length
      },
    })
    storage.value = (await getMeta<StorageStatus>(db, 'storage')) ?? null
    lastSynced.value = (await getMeta<number>(db, 'lastSynced')) ?? null
    outboxCount = liveQuery(() => db.outbox.count()).subscribe((count) => {
      unsent.value = count
    })
    await engine.start()
  }

  function stop(): void {
    storage.value = null
    lastSynced.value = null
    engine?.stop()
    engine = null
    outboxCount?.unsubscribe()
    outboxCount = null
    state.value = 'idle'
  }

  async function resume(): Promise<void> {
    await engine?.resume()
  }

  function syncNow(): void {
    engine?.request()
  }

  /** Runs a cycle now and resolves with the state it ended in. */
  async function syncAndWait(): Promise<SyncState> {
    await engine?.sync()
    return state.value
  }

  /** Fetches one note's images now, for a device that downloads images on demand. */
  async function downloadImages(noteId: string): Promise<void> {
    await blobs.downloadNote(noteId)
  }

  return {
    state,
    unsent,
    rejected,
    lastSynced,
    storage,
    storageFull,
    hasRoom,
    start,
    stop,
    resume,
    syncNow,
    syncAndWait,
    downloadImages,
  }
})
