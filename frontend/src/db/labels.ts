import { dropPending, enqueuePurge, enqueueUpsert } from './outbox'
import { db as defaultDb, type LocalLabel, type NotesDatabase } from './schema'
import { refreshSearchText, searchTables } from './search'

export const MAX_LABEL_LENGTH = 50

export function byName(a: LocalLabel, b: LocalLabel): number {
  return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
}

/** Label names are unique per user, compared case-insensitively, as on the server (SPEC 4). */
async function findByName(db: NotesDatabase, name: string): Promise<LocalLabel | undefined> {
  const wanted = name.toLocaleLowerCase()
  return db.labels.filter((label) => label.name.toLocaleLowerCase() === wanted).first()
}

export function membershipId(noteId: string, labelId: string): string {
  return `${noteId}:${labelId}`
}

/** Creates a label, or returns the existing one with the same name. Null for an invalid name. */
export async function createLabel(
  rawName: string,
  db: NotesDatabase = defaultDb,
): Promise<string | null> {
  const name = rawName.trim()
  if (!name || name.length > MAX_LABEL_LENGTH) return null
  return db.transaction('rw', db.labels, db.outbox, async () => {
    const existing = await findByName(db, name)
    if (existing) return existing.id
    const id = crypto.randomUUID()
    await db.labels.add({ id, name, serverSeq: 0 })
    await enqueueUpsert(db, 'label', id, { name }, 0)
    return id
  })
}

export type RenameResult = 'renamed' | 'unchanged' | 'invalid' | 'exists'

export async function renameLabel(
  id: string,
  rawName: string,
  db: NotesDatabase = defaultDb,
): Promise<RenameResult> {
  const name = rawName.trim()
  if (!name || name.length > MAX_LABEL_LENGTH) return 'invalid'
  return db.transaction('rw', [...searchTables(db), db.outbox], async () => {
    const label = await db.labels.get(id)
    if (!label) return 'invalid'
    if (label.name === name) return 'unchanged'
    const other = await findByName(db, name)
    if (other && other.id !== id) return 'exists'
    await db.labels.update(id, { name })
    await enqueueUpsert(db, 'label', id, { name }, label.serverSeq)
    const notes = await db.noteLabels.where('label_id').equals(id).toArray()
    await refreshSearchText(
      db,
      notes.map((m) => m.note_id),
    )
    return 'renamed'
  })
}

/**
 * Deletes a label and removes it from its notes, which stay (SPEC 9, Labels). Returns what Undo
 * needs to put it back: the server keeps a deleted label's ID as a tombstone, so Undo creates a
 * new label with the same name.
 */
export async function deleteLabel(
  id: string,
  db: NotesDatabase = defaultDb,
): Promise<{ name: string; noteIds: string[] } | null> {
  return db.transaction('rw', [...searchTables(db), db.outbox], async () => {
    const label = await db.labels.get(id)
    if (!label) return null
    const memberships = await db.noteLabels.where('label_id').equals(id).toArray()
    // The server removes the memberships along with the label.
    for (const membership of memberships) await dropPending(db, 'note_label', membership.id)
    await db.noteLabels.bulkDelete(memberships.map((m) => m.id))
    await db.labels.delete(id)
    await enqueuePurge(db, 'label', id, label.serverSeq)
    const noteIds = memberships.map((m) => m.note_id)
    await refreshSearchText(db, noteIds)
    return { name: label.name, noteIds }
  })
}

export async function setNoteLabel(
  noteId: string,
  labelId: string,
  on: boolean,
  db: NotesDatabase = defaultDb,
): Promise<void> {
  const id = membershipId(noteId, labelId)
  await db.transaction('rw', [...searchTables(db), db.outbox], async () => {
    const existing = await db.noteLabels.get(id)
    if (on && !existing) {
      await db.noteLabels.add({ id, note_id: noteId, label_id: labelId, serverSeq: 0 })
      // Adding a label the note had before revives the server's tombstoned membership (SPEC 4).
      await enqueueUpsert(db, 'note_label', id, { deleted: false }, 0)
    } else if (!on && existing) {
      await db.noteLabels.delete(id)
      await enqueuePurge(db, 'note_label', id, existing.serverSeq)
    } else {
      return
    }
    await refreshSearchText(db, [noteId])
  })
}

/** Adds a label to several notes, or removes it from them, in one transaction. */
export async function setNotesLabel(
  noteIds: string[],
  labelId: string,
  on: boolean,
  db: NotesDatabase = defaultDb,
): Promise<void> {
  await db.transaction('rw', [...searchTables(db), db.outbox], async () => {
    for (const noteId of noteIds) await setNoteLabel(noteId, labelId, on, db)
  })
}
