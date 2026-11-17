import { byPosition, rowFields, updateNote } from './notes'
import { enqueuePurge, enqueueUpsert } from './outbox'
import { insertKeys } from './positions'
import { emptyDoc, fromPlainText, plainText } from './richtext'
import {
  db as defaultDb,
  type LocalChecklistItem,
  type LocalNote,
  type NotesDatabase,
} from './schema'
import { refreshSearchText, searchTables } from './search'

/** Server limits (SPEC 4): items per note and characters per item. */
export const MAX_ITEMS = 1000
export const MAX_ITEM_LENGTH = 1000

export type ItemPatch = Partial<Pick<LocalChecklistItem, 'text' | 'checked' | 'position'>>

function tables(db: NotesDatabase) {
  return [...searchTables(db), db.outbox]
}

export async function noteItems(
  noteId: string,
  db: NotesDatabase = defaultDb,
): Promise<LocalChecklistItem[]> {
  return (await db.checklistItems.where('note_id').equals(noteId).toArray()).sort(byPosition)
}

/** Unchecked items first, then checked ones, each in list order: the order a checklist shows. */
export function displayOrder(items: LocalChecklistItem[]): LocalChecklistItem[] {
  return [...items.filter((i) => !i.checked), ...items.filter((i) => i.checked)]
}

/** The server moves a note's updated_at when its items change; the local copy follows. */
async function touch(db: NotesDatabase, noteId: string): Promise<void> {
  await db.notes.update(noteId, { updated_at: Date.now() })
  await refreshSearchText(db, [noteId])
}

export type NewItem = Pick<LocalChecklistItem, 'id' | 'note_id' | 'text' | 'position'>

/**
 * New unchecked items to insert at `index` of a note's items, sorted by position. The editor
 * plans items itself, so that a new row shows up before it is written; texts beyond the per-note
 * limit are dropped.
 */
export function planItems(
  noteId: string,
  items: { position: string }[],
  index: number,
  texts: string[],
): NewItem[] {
  const accepted = texts.slice(0, Math.max(MAX_ITEMS - items.length, 0))
  if (accepted.length === 0) return []
  const keys = insertKeys(
    items.map((item) => item.position),
    index,
    accepted.length,
  )
  return accepted.map((text, n) => ({
    id: crypto.randomUUID(),
    note_id: noteId,
    text: text.slice(0, MAX_ITEM_LENGTH),
    position: keys[n]!,
  }))
}

/** Writes planned items and returns the IDs written; items beyond the per-note limit are dropped. */
export async function insertItems(
  planned: NewItem[],
  db: NotesDatabase = defaultDb,
): Promise<string[]> {
  const noteId = planned[0]?.note_id
  if (!noteId) return []
  return db.transaction('rw', tables(db), async () => {
    const count = await db.checklistItems.where('note_id').equals(noteId).count()
    const accepted = planned.slice(0, Math.max(MAX_ITEMS - count, 0))
    if (accepted.length === 0) return []
    for (const fields of accepted) {
      const row: LocalChecklistItem = { ...fields, checked: false, serverSeq: 0 }
      await db.checklistItems.add(row)
      await enqueueUpsert(db, 'checklist_item', row.id, rowFields(row), 0)
    }
    await touch(db, noteId)
    return accepted.map((row) => row.id)
  })
}

/** Adds unchecked items after the given item, or at the start of the list, and returns their IDs. */
export async function addItems(
  noteId: string,
  texts: string[],
  afterId: string | null,
  db: NotesDatabase = defaultDb,
): Promise<string[]> {
  return db.transaction('rw', tables(db), async () => {
    const items = await noteItems(noteId, db)
    const index = afterId === null ? 0 : items.findIndex((item) => item.id === afterId) + 1
    return insertItems(planItems(noteId, items, index, texts), db)
  })
}

export async function updateItem(
  id: string,
  patch: ItemPatch,
  db: NotesDatabase = defaultDb,
): Promise<void> {
  await db.transaction('rw', tables(db), async () => {
    const item = await db.checklistItems.get(id)
    if (!item) return
    const wanted =
      patch.text === undefined ? patch : { ...patch, text: patch.text.slice(0, MAX_ITEM_LENGTH) }
    const changed = Object.fromEntries(
      Object.entries(wanted).filter(([key, value]) => item[key as keyof ItemPatch] !== value),
    ) as ItemPatch
    if (Object.keys(changed).length === 0) return
    await db.checklistItems.update(id, changed)
    await enqueueUpsert(db, 'checklist_item', id, changed, item.serverSeq)
    if ('text' in changed || 'checked' in changed) await touch(db, item.note_id)
  })
}

export async function removeItem(id: string, db: NotesDatabase = defaultDb): Promise<void> {
  await db.transaction('rw', tables(db), async () => {
    const item = await db.checklistItems.get(id)
    if (!item) return
    await db.checklistItems.delete(id)
    await enqueuePurge(db, 'checklist_item', id, item.serverSeq)
    await touch(db, item.note_id)
  })
}

/**
 * Turns a text note into a checklist with one item per non-empty line, or a checklist back into
 * text with one line per item (SPEC 9, Checklists). Formatting does not survive.
 */
export async function convertNote(
  id: string,
  type: LocalNote['type'],
  db: NotesDatabase = defaultDb,
): Promise<void> {
  await db.transaction('rw', tables(db), async () => {
    const note = await db.notes.get(id)
    if (!note || note.type === type) return
    if (type === 'checklist') {
      const lines = plainText(note.content)
        .split('\n')
        .filter((line) => line.trim())
      await updateNote(id, { type, content: emptyDoc() }, db)
      await addItems(id, lines, null, db)
      return
    }
    const items = await noteItems(id, db)
    for (const item of items) {
      await db.checklistItems.delete(item.id)
      await enqueuePurge(db, 'checklist_item', item.id, item.serverSeq)
    }
    const text = displayOrder(items)
      .map((item) => item.text)
      .join('\n')
    await updateNote(id, { type, content: fromPlainText(text) }, db)
  })
}
