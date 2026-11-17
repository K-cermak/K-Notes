import type { components } from '@/api/schema'
import { Failure } from '@/api/client'
import { applyChanges, removeLocal, resetSyncedData } from '@/db/apply'
import { getMeta } from '@/db/meta'
import { localWrites } from '@/db/outbox'
import type { NotesDatabase, OutboxEntry } from '@/db/schema'

type Schemas = components['schemas']
export type PushRequest = Schemas['PushRequest']
export type PushResponse = Schemas['PushResponse']
export type PullResponse = Schemas['PullResponse']
export type OpResult = Schemas['OpResult']

export interface SyncTransport {
  push(body: PushRequest): Promise<PushResponse>
  pull(since: number): Promise<PullResponse>
}

/** Images move in the first and last step of a cycle. */
export interface BlobTransfer {
  upload(): Promise<void>
  download(): Promise<void>
  /** Attachment ops wait until their image is on the server. */
  holdsBack(entry: OutboxEntry): Promise<boolean>
  /** The server answered blob_missing for an op that was not held back; true if it will upload. */
  missing(entry: OutboxEntry): Promise<boolean>
}

export type SyncState = 'idle' | 'syncing' | 'synced' | 'offline' | 'error' | 'unauthorized'

export interface EngineOptions {
  db: NotesDatabase
  transport: SyncTransport
  deviceId: string
  blobs?: BlobTransfer
  onState?: (state: SyncState) => void
  onRejected?: (results: OpResult[]) => void
  /** Opens the change stream; null where EventSource does not exist (tests). */
  openEvents?: (() => EventSource) | null
  maxOps?: number
  maxBatchBytes?: number
  writeDelayMs?: number
}

export const MAX_OPS = 200
export const MAX_BATCH_BYTES = 1_000_000
const WRITE_DELAY_MS = 500
const MAX_BACKOFF_MS = 60_000

const noBlobs: BlobTransfer = {
  upload: () => Promise.resolve(),
  download: () => Promise.resolve(),
  holdsBack: () => Promise.resolve(false),
  missing: () => Promise.resolve(false),
}

/**
 * Runs sync cycles (SPEC 5.6): upload blobs, push the outbox, pull until up to date, download blobs.
 * One cycle at a time; a request during a cycle runs another one right after it.
 */
export class SyncEngine {
  private readonly db: NotesDatabase
  private readonly transport: SyncTransport
  private readonly blobs: BlobTransfer
  private readonly options: EngineOptions
  private running: Promise<void> | null = null
  private again = false
  private stopped = true
  private failures = 0
  private timer: ReturnType<typeof setTimeout> | null = null
  private events: EventSource | null = null
  private eventsClosed = false
  private detach: (() => void)[] = []
  state: SyncState = 'idle'

  constructor(options: EngineOptions) {
    this.options = options
    this.db = options.db
    this.transport = options.transport
    this.blobs = options.blobs ?? noBlobs
  }

  async start(): Promise<void> {
    this.stopped = false
    // Ops left in flight by a closed tab are sent again; their op_id makes that safe.
    await this.db.outbox.toCollection().modify({ inFlight: 0 })
    this.listen()
    this.openEvents()
    await this.sync()
  }

  /** Continues after the user signed in again following a 401. */
  async resume(): Promise<void> {
    this.failures = 0
    this.setState('idle')
    this.openEvents()
    await this.sync()
  }

  stop(): void {
    this.stopped = true
    this.clearTimer()
    for (const off of this.detach) off()
    this.detach = []
    this.events?.close()
    this.events = null
  }

  /** Runs a cycle after the delay, replacing any cycle already scheduled. */
  request(delayMs = 0): void {
    if (this.stopped || this.state === 'unauthorized') return
    this.clearTimer()
    this.timer = setTimeout(() => {
      this.timer = null
      void this.sync()
    }, delayMs)
  }

  /** Runs a cycle now, or right after the one under way, and resolves when it is done. */
  async sync(): Promise<void> {
    if (this.stopped) return
    if (this.running) {
      this.again = true
      return this.running
    }
    this.running = (async () => {
      do {
        this.again = false
        await this.cycle()
      } while (this.again && !this.stopped && this.state !== 'unauthorized')
    })().finally(() => {
      this.running = null
    })
    return this.running
  }

  private setState(state: SyncState): void {
    this.state = state
    this.options.onState?.(state)
  }

  private clearTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer)
    this.timer = null
  }

  private async cycle(): Promise<void> {
    this.setState('syncing')
    try {
      await this.blobs.upload()
      await this.push()
      await this.pull()
      await this.blobs.download()
    } catch (e) {
      if (e instanceof Failure && e.status === 401) {
        // Keep everything local and stop until the user signs in again (SPEC 5.6).
        this.setState('unauthorized')
        this.clearTimer()
        return
      }
      if (!(e instanceof Failure)) console.error('Sync failed', e)
      this.setState(e instanceof Failure && e.status === null ? 'offline' : 'error')
      const delay = Math.min(1000 * 2 ** this.failures, MAX_BACKOFF_MS)
      this.failures += 1
      this.request(delay)
      return
    }
    this.failures = 0
    this.setState('synced')
    if (this.eventsClosed) this.openEvents()
  }

  private async nextBatch(skip: Set<string>): Promise<OutboxEntry[]> {
    const maxOps = this.options.maxOps ?? MAX_OPS
    const maxBytes = this.options.maxBatchBytes ?? MAX_BATCH_BYTES
    const batch: OutboxEntry[] = []
    let bytes = 0
    for (const entry of await this.db.outbox.orderBy('seq').toArray()) {
      if (entry.inFlight || skip.has(entry.opId) || (await this.blobs.holdsBack(entry))) continue
      const size = JSON.stringify(entry.fields).length + 200
      // A single op larger than the limit still goes, on its own.
      if (batch.length > 0 && (batch.length >= maxOps || bytes + size > maxBytes)) break
      batch.push(entry)
      bytes += size
    }
    return batch
  }

  private async push(): Promise<void> {
    const skip = new Set<string>()
    for (;;) {
      const batch = await this.nextBatch(skip)
      if (batch.length === 0) return
      const keys = batch.map((e) => e.seq!)
      await this.db.outbox.where('seq').anyOf(keys).modify({ inFlight: 1 })
      let response: PushResponse
      try {
        response = await this.transport.push({
          device_id: this.options.deviceId,
          ops: batch.map((e) => ({
            op_id: e.opId,
            entity: e.entity,
            id: e.entityId,
            kind: e.kind,
            fields: e.fields,
            base_seq: e.baseSeq,
            edited_at: e.editedAt,
          })),
        })
      } catch (e) {
        await this.db.outbox.where('seq').anyOf(keys).modify({ inFlight: 0 })
        throw e
      }
      const byOp = new Map(batch.map((e) => [e.opId, e]))
      const rejected: OpResult[] = []
      const missing: OutboxEntry[] = []
      await this.db.transaction('rw', [this.db.outbox, ...this.db.syncedTables], async () => {
        for (const result of response.results) {
          const entry = byOp.get(result.op_id)
          if (!entry) continue
          if (result.status === 'rejected' && result.error === 'blob_missing') {
            // Kept and retried after the image is uploaded, in a later cycle.
            skip.add(entry.opId)
            missing.push(entry)
            await this.db.outbox.update(entry.seq, { inFlight: 0 })
            continue
          }
          if (result.status === 'rejected') rejected.push(result)
          if (result.status === 'gone' && entry.kind === 'upsert') {
            // The row, or the note or label it belongs to, is deleted on the server. A row made
            // here would otherwise stay for good: no tombstone ever comes for it.
            await removeLocal(this.db, entry.entity, entry.entityId)
          }
          if (result.status === 'applied' && entry.kind === 'upsert' && entry.baseSeq === 0) {
            // The server has the new row now. Until the pull brings its real seq, a serverSeq of 0
            // would make a delete look like one of a row the server never saw, and it would be
            // dropped. No other device can have changed a row created up to response.seq.
            const table = this.db.syncedTable(entry.entity)
            const row = await table.get(entry.entityId)
            if (row?.serverSeq === 0)
              await table.update(entry.entityId, { serverSeq: response.seq })
          }
          await this.db.outbox.delete(entry.seq)
        }
      })
      for (const entry of missing) {
        if (await this.blobs.missing(entry)) this.again = true
      }
      if (rejected.length > 0) {
        console.warn('Sync rejected ops', rejected)
        this.options.onRejected?.(rejected)
      }
    }
  }

  private async pull(): Promise<void> {
    let since = (await getMeta<number>(this.db, 'cursor')) ?? 0
    for (;;) {
      const response = await this.transport.pull(since)
      if (response.seq < since) {
        // The server is behind this device, as after restoring a backup: start over from it.
        await resetSyncedData(this.db)
        since = 0
        continue
      }
      await applyChanges(this.db, response.changes, response.seq)
      since = response.seq
      if (!response.has_more) return
    }
  }

  private listen(): void {
    const on = (target: EventTarget, type: string, handler: () => void) => {
      target.addEventListener(type, handler)
      this.detach.push(() => target.removeEventListener(type, handler))
    }
    on(localWrites, 'write', () => this.request(this.options.writeDelayMs ?? WRITE_DELAY_MS))
    if (typeof window !== 'undefined') {
      on(window, 'online', () => {
        this.failures = 0
        this.request()
      })
      on(window, 'offline', () => this.setState('offline'))
      on(document, 'visibilitychange', () => {
        if (document.visibilityState === 'visible') this.request()
      })
    }
  }

  private openEvents(): void {
    const open =
      this.options.openEvents === undefined
        ? () => new EventSource('/api/v1/sync/events')
        : this.options.openEvents
    if (!open || this.stopped) return
    this.events?.close()
    this.eventsClosed = false
    const events = open()
    events.addEventListener('change', (event) => {
      void this.onChange(Number((event as MessageEvent<string>).data))
    })
    // EventSource reconnects by itself, except after an error response such as 401; then it is
    // reopened after the next successful cycle.
    events.addEventListener('error', () => {
      if (events.readyState === EventSource.CLOSED) this.eventsClosed = true
    })
    this.events = events
  }

  private async onChange(seq: number): Promise<void> {
    const cursor = (await getMeta<number>(this.db, 'cursor')) ?? 0
    if (seq > cursor) this.request()
  }
}
