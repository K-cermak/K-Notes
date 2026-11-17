import type { ProcessedImage } from '@/images/process'
import { byPosition, rowFields } from './notes'
import { dropPending, enqueuePurge, enqueueUpsert } from './outbox'
import { insertKeys } from './positions'
import { db as defaultDb, type LocalAttachment, type NotesDatabase } from './schema'

function tables(db: NotesDatabase) {
  return [db.notes, db.attachments, db.blobs, db.outbox]
}

export async function noteAttachments(
  noteId: string,
  db: NotesDatabase = defaultDb,
): Promise<LocalAttachment[]> {
  return (await db.attachments.where('note_id').equals(noteId).toArray()).sort(byPosition)
}

/**
 * Attaches processed images after the note's existing ones. The bytes are stored locally and
 * uploaded in the next sync cycle; the attachment ops wait until then (SPEC 5.6).
 */
export async function attachImages(
  noteId: string,
  images: ProcessedImage[],
  db: NotesDatabase = defaultDb,
): Promise<void> {
  if (images.length === 0) return
  await db.transaction('rw', tables(db), async () => {
    const existing = await noteAttachments(noteId, db)
    const keys = insertKeys(
      existing.map((a) => a.position),
      existing.length,
      images.length,
    )
    for (const [n, image] of images.entries()) {
      if (!(await db.blobs.get(image.hash))) {
        await db.blobs.put({ hash: image.hash, blob: image.blob, uploaded: 0 })
      }
      const row: LocalAttachment = {
        id: crypto.randomUUID(),
        note_id: noteId,
        blob_hash: image.hash,
        mime: image.mime,
        width: image.width,
        height: image.height,
        size: image.size,
        position: keys[n]!,
        serverSeq: 0,
      }
      await db.attachments.add(row)
      await enqueueUpsert(db, 'attachment', row.id, rowFields(row), 0)
    }
    await db.notes.update(noteId, { updated_at: Date.now() })
  })
}

export async function removeAttachment(id: string, db: NotesDatabase = defaultDb): Promise<void> {
  await db.transaction('rw', tables(db), async () => {
    const row = await db.attachments.get(id)
    if (!row) return
    await db.attachments.delete(id)
    await enqueuePurge(db, 'attachment', id, row.serverSeq)
    await db.notes.update(row.note_id, { updated_at: Date.now() })
    await pruneBlobs(db)
  })
}

/** Deletes stored images that no local attachment uses any more. */
export async function pruneBlobs(db: NotesDatabase = defaultDb): Promise<void> {
  await db.transaction('rw', db.attachments, db.blobs, async () => {
    const used = new Set(await db.attachments.orderBy('blob_hash').uniqueKeys())
    const stored = await db.blobs.toCollection().primaryKeys()
    await db.blobs.bulkDelete(stored.filter((hash) => !used.has(hash)))
  })
}

/**
 * Gives up on an image the server refused, with the attachments that use it. Their ops were held
 * back until the upload, so the server has never seen them.
 */
export async function discardBlob(hash: string, db: NotesDatabase = defaultDb): Promise<number> {
  return db.transaction('rw', tables(db), async () => {
    const rows = await db.attachments.where('blob_hash').equals(hash).toArray()
    for (const row of rows) await dropPending(db, 'attachment', row.id)
    await db.attachments.bulkDelete(rows.map((row) => row.id))
    await db.blobs.delete(hash)
    return rows.length
  })
}
