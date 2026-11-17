import type { Me, PublicConfig } from '@/api/client'
import { getMeta, setMeta } from './meta'
import type { NotesDatabase } from './schema'

/** Whose notes this browser holds. Signing in as someone else wipes them first (SPEC 5.6). */
export async function storedUserId(db: NotesDatabase): Promise<string | undefined> {
  return getMeta<string>(db, 'userId')
}

/** The profile and instance config are cached so the app can open offline, in the right theme. */
export async function rememberUser(db: NotesDatabase, me: Me): Promise<void> {
  await db.transaction('rw', db.meta, async () => {
    await setMeta(db, 'userId', me.id)
    await setMeta(db, 'profile', me)
  })
}

export async function cachedProfile(db: NotesDatabase): Promise<Me | undefined> {
  return getMeta<Me>(db, 'profile')
}

export async function rememberConfig(db: NotesDatabase, config: PublicConfig): Promise<void> {
  await setMeta(db, 'config', config)
}

export async function cachedConfig(db: NotesDatabase): Promise<PublicConfig | undefined> {
  return getMeta<PublicConfig>(db, 'config')
}

export async function unsentCount(db: NotesDatabase): Promise<number> {
  return db.outbox.count()
}

/** Removes every note and pending change, keeping only this browser's ID and settings. */
export async function wipeLocalData(db: NotesDatabase): Promise<void> {
  await db.transaction('rw', db.tables, async () => {
    const kept = await db.meta.bulkGet(['deviceId', 'device'])
    await Promise.all(db.tables.map((table) => table.clear()))
    await db.meta.bulkPut(kept.filter((entry) => entry !== undefined))
  })
}
