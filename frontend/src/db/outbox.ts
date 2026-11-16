import type { Entity, NotesDatabase, OutboxEntry } from './schema'

/** Wakes the sync engine shortly after any local write. */
export const localWrites = new EventTarget()

function entriesFor(db: NotesDatabase, entity: Entity, entityId: string) {
  return db.outbox.where('[entity+entityId]').equals([entity, entityId])
}

/**
 * Records an upsert, merging it into an unsent op for the same row (SPEC 5.6).
 * Must run inside a transaction that includes the outbox.
 */
export async function enqueueUpsert(
  db: NotesDatabase,
  entity: Entity,
  entityId: string,
  fields: Record<string, unknown>,
  baseSeq: number,
): Promise<void> {
  const now = Date.now()
  const unsent = (await entriesFor(db, entity, entityId).toArray()).filter((e) => !e.inFlight)
  const last = unsent.at(-1)
  if (last?.kind === 'upsert') {
    // A new op_id: the old one may already have been applied, and a replay of it would be answered
    // from the server's record of that op without applying the fields merged in since.
    await db.outbox.update(last.seq, {
      fields: { ...last.fields, ...fields },
      editedAt: now,
      opId: crypto.randomUUID(),
    })
  } else {
    await db.outbox.add({
      opId: crypto.randomUUID(),
      entity,
      entityId,
      kind: 'upsert',
      fields,
      baseSeq,
      editedAt: now,
      inFlight: 0,
    })
  }
  localWrites.dispatchEvent(new Event('write'))
}

/**
 * Records a purge. A row the server has never seen is simply forgotten, along with its pending ops.
 * Must run inside a transaction that includes the outbox.
 */
export async function enqueuePurge(
  db: NotesDatabase,
  entity: Entity,
  entityId: string,
  serverSeq: number,
): Promise<void> {
  const entries = await entriesFor(db, entity, entityId).toArray()
  const unsent = entries.filter((e) => !e.inFlight)
  await db.outbox.bulkDelete(unsent.map((e) => e.seq!))
  const neverSent = serverSeq === 0 && entries.every((e) => !e.inFlight)
  if (!neverSent) {
    await db.outbox.add({
      opId: crypto.randomUUID(),
      entity,
      entityId,
      kind: 'purge',
      fields: {},
      baseSeq: serverSeq,
      editedAt: Date.now(),
      inFlight: 0,
    })
  }
  localWrites.dispatchEvent(new Event('write'))
}

/** Drops ops for a row that no longer exists, such as a child of a purged note. */
export async function dropPending(
  db: NotesDatabase,
  entity: Entity,
  entityId: string,
): Promise<void> {
  await entriesFor(db, entity, entityId).delete()
}

export async function pendingFor(
  db: NotesDatabase,
  entity: Entity,
  entityId: string,
): Promise<OutboxEntry[]> {
  return entriesFor(db, entity, entityId).toArray()
}
