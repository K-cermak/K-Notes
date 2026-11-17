import { afterEach, describe, expect, it, vi } from 'vitest'
import { Failure } from '@/api/client'
import { getMeta } from '@/db/meta'
import { createNote, purgeNote, updateNote } from '@/db/notes'
import { testDatabase } from '@/db/testing'
import type { NotesDatabase } from '@/db/schema'
import {
  SyncEngine,
  type BlobTransfer,
  type PullResponse,
  type PushRequest,
  type PushResponse,
  type SyncState,
} from './engine'

const emptyChanges = () => ({
  notes: [],
  checklist_items: [],
  labels: [],
  note_labels: [],
  attachments: [],
})

/** A scripted server that records what it was asked. */
class FakeServer {
  log: string[] = []
  pushes: PushRequest[] = []
  seq = 0
  failNext: Failure | null = null
  results: (op: PushRequest['ops'][number]) => PushResponse['results'][number] = (op) => ({
    op_id: op.op_id,
    status: 'applied',
  })
  pages: PullResponse[] = []

  push = (body: PushRequest): Promise<PushResponse> => {
    this.log.push(`push:${body.ops.length}`)
    if (this.failNext) return Promise.reject(this.take())
    this.pushes.push(body)
    this.seq += body.ops.length
    return Promise.resolve({ seq: this.seq, results: body.ops.map((op) => this.results(op)) })
  }

  pull = (since: number): Promise<PullResponse> => {
    this.log.push(`pull:${since}`)
    if (this.failNext) return Promise.reject(this.take())
    return Promise.resolve(
      this.pages.shift() ?? {
        seq: Math.max(since, this.seq),
        has_more: false,
        changes: emptyChanges(),
      },
    )
  }

  private take(): Failure {
    const failure = this.failNext!
    this.failNext = null
    return failure
  }
}

const engines: SyncEngine[] = []

function makeEngine(
  db: NotesDatabase,
  server: FakeServer,
  extra: Partial<ConstructorParameters<typeof SyncEngine>[0]> = {},
) {
  const states: SyncState[] = []
  const engine = new SyncEngine({
    db,
    transport: server,
    deviceId: 'device-1',
    openEvents: null,
    onState: (s) => states.push(s),
    writeDelayMs: 60_000,
    ...extra,
  })
  engines.push(engine)
  return { engine, states }
}

afterEach(() => {
  for (const engine of engines.splice(0)) engine.stop()
})

describe('sync cycle', () => {
  it('runs blob upload, push, pull and blob download in that order', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    const blobs: BlobTransfer = {
      upload: () => Promise.resolve(void server.log.push('upload')),
      download: () => Promise.resolve(void server.log.push('download')),
      holdsBack: () => Promise.resolve(false),
    }
    await createNote({ title: 'x' }, db)
    const { engine, states } = makeEngine(db, server, { blobs })
    await engine.start()
    expect(server.log).toEqual(['upload', 'push:1', 'pull:0', 'download'])
    expect(states.at(-1)).toBe('synced')
    expect(await db.outbox.count()).toBe(0)
    expect(await getMeta(db, 'cursor')).toBe(1)
  })

  it('pushes the outbox in order and sends the op fields as written', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    const id = await createNote({ title: 'First' }, db)
    await db.notes.update(id, { serverSeq: 1 })
    const { engine } = makeEngine(db, server)
    await engine.start()
    await updateNote(id, { title: 'Second' }, db)
    await engine.sync()
    const ops = server.pushes.flatMap((p) => p.ops)
    expect(ops.map((o) => [o.entity, o.kind, o.fields.title])).toEqual([
      ['note', 'upsert', 'First'],
      ['note', 'upsert', 'Second'],
    ])
    expect(server.pushes[0]!.device_id).toBe('device-1')
  })

  it('splits pushes by op count and by size', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    for (let i = 0; i < 5; i++) await createNote({ title: 'x'.repeat(400) }, db)
    const { engine } = makeEngine(db, server, { maxOps: 2, maxBatchBytes: 2000 })
    await engine.start()
    expect(server.log.filter((l) => l.startsWith('push'))).toEqual(['push:2', 'push:2', 'push:1'])

    const big = new FakeServer()
    for (let i = 0; i < 3; i++) await createNote({ title: 'y'.repeat(1000) }, db)
    const { engine: second } = makeEngine(db, big, { maxBatchBytes: 2000 })
    await second.start()
    expect(big.log.filter((l) => l.startsWith('push'))).toEqual(['push:1', 'push:1', 'push:1'])
  })

  it('removes applied, gone and rejected ops and reports rejections', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    const statuses = ['applied', 'gone', 'rejected'] as const
    let n = 0
    server.results = (op) => {
      const status = statuses[n++ % 3]!
      return { op_id: op.op_id, status, error: status === 'rejected' ? 'invalid_field' : null }
    }
    for (let i = 0; i < 3; i++) await createNote({}, db)
    const rejected = vi.fn()
    const { engine } = makeEngine(db, server, { onRejected: rejected })
    await engine.start()
    expect(await db.outbox.count()).toBe(0)
    expect(rejected).toHaveBeenCalledWith([expect.objectContaining({ error: 'invalid_field' })])
  })

  it('keeps blob_missing ops for a later cycle', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    server.results = (op) => ({ op_id: op.op_id, status: 'rejected', error: 'blob_missing' })
    await createNote({}, db)
    const { engine, states } = makeEngine(db, server)
    await engine.start()
    expect(server.log).toEqual(['push:1', 'pull:0'])
    expect(await db.outbox.toArray()).toEqual([expect.objectContaining({ inFlight: 0 })])
    expect(states.at(-1)).toBe('synced')
  })

  it('sends a purge for a new row the server has, even before the pull confirms it', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    const id = await createNote({ title: 'pushed' }, db)
    server.pull = () => Promise.reject(new Failure(null, 'network', 'offline'))
    const { engine } = makeEngine(db, server)
    await engine.start()
    expect(await db.outbox.count()).toBe(0)

    await purgeNote(id, db)
    expect(await db.outbox.toArray()).toEqual([
      expect.objectContaining({ kind: 'purge', entityId: id }),
    ])
  })

  it('holds back ops the blob transfer is not ready for', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    await createNote({ title: 'wait' }, db)
    await createNote({ title: 'go' }, db)
    const blobs: BlobTransfer = {
      upload: () => Promise.resolve(),
      download: () => Promise.resolve(),
      holdsBack: (entry) => Promise.resolve(entry.fields.title === 'wait'),
    }
    const { engine } = makeEngine(db, server, { blobs })
    await engine.start()
    expect(server.pushes.flatMap((p) => p.ops.map((o) => o.fields.title))).toEqual(['go'])
    expect(await db.outbox.count()).toBe(1)
  })

  it('pulls until has_more is false', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    server.pages = [
      { seq: 1000, has_more: true, changes: emptyChanges() },
      { seq: 1500, has_more: false, changes: emptyChanges() },
    ]
    const { engine } = makeEngine(db, server)
    await engine.start()
    expect(server.log).toEqual(['pull:0', 'pull:1000'])
    expect(await getMeta(db, 'cursor')).toBe(1500)
  })

  it('starts over when the server is behind the cursor', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    await db.meta.put({ key: 'cursor', value: 50 })
    await db.notes.add({
      id: 'stale',
      type: 'text',
      title: '',
      content: { type: 'doc', content: [] },
      color: 'default',
      pinned: false,
      archived: false,
      trashed_at: null,
      position: 'a0',
      conflict_of: null,
      created_at: 1,
      updated_at: 1,
      serverSeq: 40,
    })
    server.pages = [
      { seq: 10, has_more: false, changes: emptyChanges() },
      { seq: 10, has_more: false, changes: emptyChanges() },
    ]
    const { engine } = makeEngine(db, server)
    await engine.start()
    expect(server.log).toEqual(['pull:50', 'pull:0'])
    expect(await db.notes.count()).toBe(0)
  })

  it('runs one cycle at a time and one more for requests made meanwhile', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    const { engine } = makeEngine(db, server)
    await engine.start()
    server.log = []
    await Promise.all([engine.sync(), engine.sync(), engine.sync()])
    expect(server.log).toEqual(['pull:0', 'pull:0'])
  })
})

describe('failures', () => {
  it('backs off exponentially on network errors and keeps the outbox', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    await createNote({}, db)
    const { engine, states } = makeEngine(db, server)
    const request = vi.spyOn(engine, 'request')
    server.failNext = new Failure(null, 'network', 'Network error')
    await engine.start()
    expect(states.at(-1)).toBe('offline')
    expect(request).toHaveBeenLastCalledWith(1000)
    expect(await db.outbox.toArray()).toEqual([expect.objectContaining({ inFlight: 0 })])

    server.failNext = new Failure(500, 'unknown', 'Server error')
    await engine.sync()
    expect(states.at(-1)).toBe('error')
    expect(request).toHaveBeenLastCalledWith(2000)

    await engine.sync()
    expect(states.at(-1)).toBe('synced')
    expect(await db.outbox.count()).toBe(0)
  })

  it('caps the backoff at 60 seconds', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    const { engine } = makeEngine(db, server)
    const request = vi.spyOn(engine, 'request')
    await engine.start()
    for (let i = 0; i < 9; i++) {
      server.failNext = new Failure(null, 'network', '')
      await engine.sync()
    }
    expect(request).toHaveBeenLastCalledWith(60_000)
  })

  it('stops on 401, keeps local data, and resumes after signing in again', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    await createNote({ title: 'keep me' }, db)
    const { engine, states } = makeEngine(db, server)
    server.failNext = new Failure(401, 'unauthorized', '')
    await engine.start()
    expect(states.at(-1)).toBe('unauthorized')
    expect(await db.outbox.count()).toBe(1)
    expect(await db.notes.count()).toBe(1)

    server.log = []
    engine.request()
    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(server.log).toEqual([])

    await engine.resume()
    expect(states.at(-1)).toBe('synced')
    expect(await db.outbox.count()).toBe(0)
  })

  it('sends ops left in flight by a closed tab again', async () => {
    const db = testDatabase()
    const server = new FakeServer()
    await createNote({}, db)
    await db.outbox.toCollection().modify({ inFlight: 1 })
    const { engine } = makeEngine(db, server)
    await engine.start()
    expect(server.log[0]).toBe('push:1')
  })
})
