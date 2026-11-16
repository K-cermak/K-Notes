import { plainText } from './richtext'
import type { LocalNote, NotesDatabase } from './schema'

/** Case and diacritics folding, so "cerny" finds "Černý" (SPEC 9, Search). */
export function fold(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{M}+/gu, '')
    .toLowerCase()
}

/** Every word of the query must appear somewhere in the note. */
export function matches(searchText: string | undefined, query: string): boolean {
  const terms = fold(query).split(/\s+/).filter(Boolean)
  return terms.length > 0 && terms.every((term) => (searchText ?? '').includes(term))
}

/** The tables a write that may change a note's search text must include in its transaction. */
export function searchTables(db: NotesDatabase) {
  return [db.notes, db.checklistItems, db.noteLabels, db.labels]
}

async function searchTextOf(db: NotesDatabase, note: LocalNote): Promise<string> {
  const items = await db.checklistItems.where('note_id').equals(note.id).toArray()
  const labelIds = (await db.noteLabels.where('note_id').equals(note.id).toArray()).map(
    (membership) => membership.label_id,
  )
  const labels = await db.labels.bulkGet(labelIds)
  return fold(
    [
      note.title,
      plainText(note.content),
      ...items.map((i) => i.text),
      ...labels.map((l) => l?.name ?? ''),
    ].join('\n'),
  )
}

/**
 * Recomputes the derived searchText of notes after their title, text, items or labels changed.
 * Must run inside a transaction that includes searchTables().
 */
export async function refreshSearchText(
  db: NotesDatabase,
  noteIds: Iterable<string>,
): Promise<void> {
  for (const id of new Set(noteIds)) {
    const note = await db.notes.get(id)
    if (!note) continue
    const searchText = await searchTextOf(db, note)
    if (searchText !== note.searchText) await db.notes.update(id, { searchText })
  }
}
