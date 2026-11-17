import { defineStore } from 'pinia'
import { liveQuery, type Subscription } from 'dexie'
import { ref } from 'vue'
import { deviceId, deviceSettings } from '@/db/meta'
import { db } from '@/db/schema'
import { BlobSync } from '@/sync/blobs'
import { SyncEngine, type SyncState } from '@/sync/engine'
import { apiTransport, blobApi } from '@/sync/transport'
import { useSessionStore } from './session'

export const useSyncStore = defineStore('sync', () => {
  const state = ref<SyncState>('idle')
  const unsent = ref(0)
  const rejected = ref(0)
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
        if (value === 'unauthorized') session.expired = true
      },
      onRejected: (results) => {
        rejected.value += results.length
      },
    })
    outboxCount = liveQuery(() => db.outbox.count()).subscribe((count) => {
      unsent.value = count
    })
    await engine.start()
  }

  function stop(): void {
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

  /** Fetches one note's images now, for a device that downloads images on demand. */
  async function downloadImages(noteId: string): Promise<void> {
    await blobs.downloadNote(noteId)
  }

  return { state, unsent, rejected, start, stop, resume, syncNow, downloadImages }
})
