import { generateKeyBetween } from 'fractional-indexing'
import { emptyDoc, plainText } from './richtext'
import { dropPending, enqueuePurge, enqueueUpsert } from './outbox'
import { db as defaultDb, type LocalNote, type NotesDatabase } from './schema'

/** The fields a client may write on a note. */
export type NotePatch = Partial<
  Pick<
    LocalNote,
    | 'type'
    | 'title'
    | 'content'
    | 'color'
    | 'pinned'
    | 'archived'
    | 'trashed_at'
    | 'position'
    | 'conflict_of'
  >
>

const CONTENT_FIELDS: (keyof NotePatch)[] = ['type', 'title', 'content']

/** Sorted ascending by position, then by id to break ties (SPEC 4.2). */
export function byPosition(
  a: { position: string; id: string },
  b: { position: string; id: string },
) {
  return a.position < b.position ? -1 : a.position > b.position ? 1 : a.id < b.id ? -1 : 1
}

function rowFields<T extends { id: string; serverSeq: number }>(row: T): Record<string, unknown> {
  const { id: _id, serverSeq: _seq, ...fields } = row
  return fields
}

async function topPosition(db: NotesDatabase): Promise<string> {
  const first = await db.notes.orderBy('position').first()
  return generateKeyBetween(null, first?.position ?? null)
}

/** Creates a note at the top of the list (SPEC 4.2) and returns its ID. */
export async function createNote(
  init: NotePatch = {},
  db: NotesDatabase = defaultDb,
): Promise<string> {
  const id = crypto.randomUUID()
  await db.transaction('rw', db.notes, db.outbox, async () => {
    const now = Date.now()
    const note: LocalNote = {
      id,
      type: 'text',
      title: '',
      content: emptyDoc(),
      color: 'default',
      pinned: false,
      archived: false,
      trashed_at: null,
      conflict_of: null,
      ...init,
      position: init.position ?? (await topPosition(db)),
      created_at: now,
      updated_at: now,
      serverSeq: 0,
    }
    await db.notes.add(note)
    const { updated_at: _updated, ...fields } = rowFields(note)
    await enqueueUpsert(db, 'note', id, fields, 0)
  })
  return id
}

export async function updateNote(
  id: string,
  patch: NotePatch,
  db: NotesDatabase = defaultDb,
): Promise<void> {
  await db.transaction('rw', db.notes, db.outbox, async () => {
    const note = await db.notes.get(id)
    if (!note) return
    const changed = Object.fromEntries(
      Object.entries(patch).filter(
        ([key, value]) => JSON.stringify(note[key as keyof LocalNote]) !== JSON.stringify(value),
      ),
    ) as NotePatch
    if (Object.keys(changed).length === 0) return
    const contentEdit = CONTENT_FIELDS.some((key) => key in changed)
    await db.notes.update(id, { ...changed, ...(contentEdit ? { updated_at: Date.now() } : {}) })
    await enqueueUpsert(db, 'note', id, changed, note.serverSeq)
  })
}

/** Deletes a note for good, with its items, label memberships and attachments. */
export async function purgeNote(id: string, db: NotesDatabase = defaultDb): Promise<void> {
  await db.transaction(
    'rw',
    [db.notes, db.checklistItems, db.noteLabels, db.attachments, db.outbox],
    async () => {
      const note = await db.notes.get(id)
      if (!note) return
      // The server tombstones the children itself; their pending ops would only come back as gone.
      for (const [table, entity] of [
        [db.checklistItems, 'checklist_item'],
        [db.noteLabels, 'note_label'],
        [db.attachments, 'attachment'],
      ] as const) {
        const children = await table.where('note_id').equals(id).primaryKeys()
        for (const childId of children) await dropPending(db, entity, childId)
        await table.bulkDelete(children)
      }
      await db.notes.delete(id)
      await enqueuePurge(db, 'note', id, note.serverSeq)
    },
  )
}

/** Duplicates a note with its items, labels and image references, at the top of the list. */
export async function copyNote(id: string, db: NotesDatabase = defaultDb): Promise<string | null> {
  const copyId = crypto.randomUUID()
  const done = await db.transaction(
    'rw',
    [db.notes, db.checklistItems, db.noteLabels, db.attachments, db.outbox],
    async () => {
      const note = await db.notes.get(id)
      if (!note) return false
      const now = Date.now()
      const copy: LocalNote = {
        ...note,
        id: copyId,
        pinned: false,
        conflict_of: null,
        position: await topPosition(db),
        created_at: now,
        updated_at: now,
        serverSeq: 0,
      }
      await db.notes.add(copy)
      const { updated_at: _updated, ...fields } = rowFields(copy)
      await enqueueUpsert(db, 'note', copyId, fields, 0)
      for (const item of await db.checklistItems.where('note_id').equals(id).toArray()) {
        const row = { ...item, id: crypto.randomUUID(), note_id: copyId, serverSeq: 0 }
        await db.checklistItems.add(row)
        await enqueueUpsert(db, 'checklist_item', row.id, rowFields(row), 0)
      }
      for (const attachment of await db.attachments.where('note_id').equals(id).toArray()) {
        const row = { ...attachment, id: crypto.randomUUID(), note_id: copyId, serverSeq: 0 }
        await db.attachments.add(row)
        await enqueueUpsert(db, 'attachment', row.id, rowFields(row), 0)
      }
      for (const membership of await db.noteLabels.where('note_id').equals(id).toArray()) {
        const row = {
          id: `${copyId}:${membership.label_id}`,
          note_id: copyId,
          label_id: membership.label_id,
          serverSeq: 0,
        }
        await db.noteLabels.add(row)
        await enqueueUpsert(db, 'note_label', row.id, {}, 0)
      }
      return true
    },
  )
  return done ? copyId : null
}

/** Permanently deletes every note in the trash. */
export async function emptyTrash(db: NotesDatabase = defaultDb): Promise<void> {
  const trashed = await db.notes.filter((note) => note.trashed_at !== null).primaryKeys()
  for (const id of trashed) await purgeNote(id, db)
}

/** A note with no title, text, items or images, which is discarded when its editor closes. */
export async function isNoteEmpty(id: string, db: NotesDatabase = defaultDb): Promise<boolean> {
  const note = await db.notes.get(id)
  if (!note) return true
  if (note.title.trim() || plainText(note.content).trim()) return false
  const items = await db.checklistItems.where('note_id').equals(id).count()
  const images = await db.attachments.where('note_id').equals(id).count()
  return items === 0 && images === 0
}
