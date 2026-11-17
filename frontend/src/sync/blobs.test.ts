import { describe, expect, it, vi } from 'vitest'
import { Failure } from '@/api/client'
import { attachImages, removeAttachment } from '@/db/attachments'
import { createNote } from '@/db/notes'
import type { NotesDatabase } from '@/db/schema'
import { testDatabase } from '@/db/testing'
import type { ProcessedImage } from '@/images/process'
import { BlobSync, type BlobApi } from './blobs'

function image(hash: string): ProcessedImage {
  return {
    blob: new Blob([hash], { type: 'image/png' }),
    hash: hash.padEnd(64, '0'),
    mime: 'image/png',
    width: 4,
    height: 3,
    size: 10,
  }
}

function fakeServer() {
  const stored = new Map<string, Blob>()
  const exists = vi.fn((hash: string) => Promise.resolve(stored.has(hash)))
  const upload = vi.fn((hash: string, blob: Blob) => {
    stored.set(hash, blob)
    return Promise.resolve()
  })
  const download = vi.fn((hash: string) => Promise.resolve(stored.get(hash) ?? null))
  const api: BlobApi = { exists, upload, download }
  return { api, stored, exists, upload }
}

async function noteWithImages(db: NotesDatabase, ...hashes: string[]): Promise<string> {
  const id = await createNote({ title: 'Photos' }, db)
  await attachImages(id, hashes.map(image), db)
  return id
}

describe('blob sync', () => {
  it('uploads new images once and then releases their attachment ops', async () => {
    const db = testDatabase()
    const server = fakeServer()
    const blobs = new BlobSync(db, server.api)
    await noteWithImages(db, 'a', 'a', 'b')
    const op = (await db.outbox.toArray()).find((entry) => entry.entity === 'attachment')!
    expect(await db.blobs.count()).toBe(2)
    expect(await blobs.holdsBack(op)).toBe(true)

    server.stored.set('b'.padEnd(64, '0'), new Blob(['b']))
    await blobs.upload()
    expect(server.upload).toHaveBeenCalledTimes(1)
    expect(await blobs.holdsBack(op)).toBe(false)
    await blobs.upload()
    expect(server.exists).toHaveBeenCalledTimes(2)
  })

  it('uploads an image again when the server no longer has it', async () => {
    const db = testDatabase()
    const server = fakeServer()
    const blobs = new BlobSync(db, server.api)
    await noteWithImages(db, 'a')
    await blobs.upload()
    const op = (await db.outbox.toArray()).find((entry) => entry.entity === 'attachment')!
    server.stored.clear()

    await blobs.missing(op)
    expect(await blobs.holdsBack(op)).toBe(true)
    await blobs.upload()
    expect(server.upload).toHaveBeenCalledTimes(2)
    expect(await blobs.holdsBack(op)).toBe(false)
  })

  it('keeps an image for the next cycle when the network fails', async () => {
    const db = testDatabase()
    const server = fakeServer()
    server.api.upload = () => Promise.reject(new Failure(null, 'network', 'offline'))
    await noteWithImages(db, 'a')
    await expect(new BlobSync(db, server.api).upload()).rejects.toThrow('offline')
    expect((await db.blobs.toArray())[0]!.uploaded).toBe(0)
  })

  it('drops an image the server refuses, with its attachments and their ops', async () => {
    const db = testDatabase()
    const server = fakeServer()
    server.api.upload = () => Promise.reject(new Failure(415, 'unsupported_image', 'no'))
    const onRefused = vi.fn()
    const noteId = await noteWithImages(db, 'a')
    await new BlobSync(db, server.api, { onRefused }).upload()
    expect(onRefused).toHaveBeenCalledWith(1)
    expect(await db.attachments.where('note_id').equals(noteId).count()).toBe(0)
    expect(await db.blobs.count()).toBe(0)
    expect((await db.outbox.toArray()).map((e) => e.entity)).toEqual(['note'])
  })

  it('downloads missing images unless the device downloads them on demand', async () => {
    const db = testDatabase()
    const server = fakeServer()
    const noteId = await noteWithImages(db, 'a')
    await new BlobSync(db, server.api).upload()
    await db.blobs.clear()

    let onDemand = true
    const blobs = new BlobSync(db, server.api, { onDemand: () => Promise.resolve(onDemand) })
    await blobs.download()
    expect(await db.blobs.count()).toBe(0)
    await blobs.downloadNote(noteId)
    expect(await db.blobs.count()).toBe(1)

    await db.blobs.clear()
    onDemand = false
    await blobs.download()
    expect((await db.blobs.toArray())[0]).toMatchObject({ uploaded: 1 })
  })

  it('forgets images no attachment uses', async () => {
    const db = testDatabase()
    const noteId = await noteWithImages(db, 'a', 'b')
    const [first] = await db.attachments.where('note_id').equals(noteId).sortBy('position')
    await removeAttachment(first!.id, db)
    expect((await db.blobs.toArray()).map((b) => b.hash)).toEqual(['b'.padEnd(64, '0')])
    // Never pushed, so removing it leaves no op behind.
    expect((await db.outbox.toArray()).map((e) => e.entity).sort()).toEqual(['attachment', 'note'])
  })
})
