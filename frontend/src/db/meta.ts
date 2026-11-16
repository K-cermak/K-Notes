import type { NotesDatabase } from './schema'

export async function getMeta<T>(db: NotesDatabase, key: string): Promise<T | undefined> {
  return (await db.meta.get(key))?.value as T | undefined
}

export async function setMeta(db: NotesDatabase, key: string, value: unknown): Promise<void> {
  await db.meta.put({ key, value })
}

/** A stable random ID for this browser, used as device_id when pushing. */
export async function deviceId(db: NotesDatabase): Promise<string> {
  return db.transaction('rw', db.meta, async () => {
    const existing = await getMeta<string>(db, 'deviceId')
    if (existing) return existing
    const id = crypto.randomUUID()
    await setMeta(db, 'deviceId', id)
    return id
  })
}
