import { generateKeyBetween } from 'fractional-indexing'
import { emptyDoc } from './richtext'
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

export async function createNote(
  init: Pick<NotePatch, 'type' | 'title' | 'content'> = {},
  db: NotesDatabase = defaultDb,
): Promise<string> {
  const id = crypto.randomUUID()
  await db.transaction('rw', db.notes, db.outbox, async () => {
    const first = await db.notes.orderBy('position').first()
    const now = Date.now()
    const note: LocalNote = {
      id,
      type: init.type ?? 'text',
      title: init.title ?? '',
      content: init.content ?? emptyDoc(),
      color: 'default',
      pinned: false,
      archived: false,
      trashed_at: null,
      // A new note goes before the current first one, so it appears at the top.
      position: generateKeyBetween(null, first?.position ?? null),
      conflict_of: null,
      created_at: now,
      updated_at: now,
      serverSeq: 0,
    }
    await db.notes.add(note)
    const { id: _id, serverSeq: _seq, updated_at: _updated, ...fields } = note
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
