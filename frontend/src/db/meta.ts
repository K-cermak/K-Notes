import type { NotesDatabase } from './schema'

export async function getMeta<T>(db: NotesDatabase, key: string): Promise<T | undefined> {
  return (await db.meta.get(key))?.value as T | undefined
}

export async function setMeta(db: NotesDatabase, key: string, value: unknown): Promise<void> {
  await db.meta.put({ key, value })
}

/** Settings that belong to this browser rather than to the account (SPEC 9, Settings). */
export interface DeviceSettings {
  downloadOnDemand: boolean
}

export async function deviceSettings(db: NotesDatabase): Promise<DeviceSettings> {
  return { downloadOnDemand: false, ...(await getMeta<Partial<DeviceSettings>>(db, 'device')) }
}

export async function setDeviceSettings(
  db: NotesDatabase,
  patch: Partial<DeviceSettings>,
): Promise<void> {
  await setMeta(db, 'device', { ...(await deviceSettings(db)), ...patch })
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
