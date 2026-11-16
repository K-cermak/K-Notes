import type { components } from '@/api/schema'
import { setMeta } from './meta'
import type { Entity, NotesDatabase } from './schema'

type Changes = components['schemas']['Changes']

const TABLES: [keyof Changes, Entity][] = [
  ['notes', 'note'],
  ['labels', 'label'],
  ['checklist_items', 'checklist_item'],
  ['note_labels', 'note_label'],
  ['attachments', 'attachment'],
]

/**
 * Writes one page of pulled changes and the new cursor in one transaction (SPEC 5.6).
 *
 * Fields that unsent ops touch keep their local values: those ops will be pushed and settled by
 * the server. A tombstone removes the local row and drops the ops still pending for it.
 */
export async function applyChanges(
  db: NotesDatabase,
  changes: Changes,
  cursor: number,
): Promise<void> {
  await db.transaction('rw', [...db.syncedTables, db.outbox, db.meta], async () => {
    for (const [key, entity] of TABLES) {
      const table = db.syncedTable(entity)
      for (const row of changes[key]) {
        const pending = await db.outbox
          .where('[entity+entityId]')
          .equals([entity, row.id])
          .toArray()
        if (row.deleted) {
          await table.delete(row.id)
          await db.outbox.bulkDelete(pending.map((e) => e.seq!))
          continue
        }
        // A pending purge means the user deleted the row here; it stays deleted until the server agrees.
        if (pending.some((e) => e.kind === 'purge')) continue
        const { seq, deleted: _deleted, ...fields } = row
        const local = (await table.get(row.id)) as Record<string, unknown> | undefined
        const merged: Record<string, unknown> = { ...fields, serverSeq: seq }
        if (local) {
          for (const entry of pending) {
            for (const name of Object.keys(entry.fields)) merged[name] = local[name]
          }
        }
        await table.put(merged as never)
      }
    }
    await setMeta(db, 'cursor', cursor)
  })
}

/** Forgets every synced row and the cursor, keeping only rows that still have pending ops. */
export async function resetSyncedData(db: NotesDatabase): Promise<void> {
  await db.transaction('rw', [...db.syncedTables, db.outbox, db.meta], async () => {
    const pending = new Set((await db.outbox.toArray()).map((e) => `${e.entity}:${e.entityId}`))
    for (const [, entity] of TABLES) {
      const table = db.syncedTable(entity)
      const ids: string[] = await table.toCollection().primaryKeys()
      await table.bulkDelete(ids.filter((id) => !pending.has(`${entity}:${id}`)))
    }
    await setMeta(db, 'cursor', 0)
  })
}
