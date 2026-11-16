import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, call, isFailure, type Me } from '@/api/client'
import type { components } from '@/api/schema'
import { i18n } from '@/i18n'
import {
  cachedProfile,
  rememberUser,
  storedUserId,
  unsentCount,
  wipeLocalData,
} from '@/db/identity'
import { getMeta, setMeta } from '@/db/meta'
import { db } from '@/db/schema'
import { useConfirmStore } from './confirm'

type ProfileUpdate = components['schemas']['ProfileUpdate']
const PENDING_PROFILE = 'profilePatch'

export const useSessionStore = defineStore('session', () => {
  const user = ref<Me | null>(null)
  const loaded = ref(false)
  /** The server refused the session while local data stays usable; the user should sign in again. */
  const expired = ref(false)
  /** Started without the server, from the cached profile. */
  const offline = ref(false)

  async function confirmLosingChanges(): Promise<boolean> {
    const count = await unsentCount(db)
    if (count === 0) return true
    const { t } = i18n.global
    return useConfirmStore().ask({
      title: t('session.unsentTitle'),
      message: t('session.unsentMessage', { count }, count),
      confirmLabel: t('session.discard'),
      danger: true,
    })
  }

  async function load(): Promise<void> {
    try {
      const me = await call(() => api.GET('/api/v1/me'))
      const pending = (await getMeta<ProfileUpdate>(db, PENDING_PROFILE)) ?? {}
      if (!(await signedIn({ ...me, ...pending } as Me))) user.value = null
      offline.value = false
    } catch (e) {
      if (!isFailure(e)) throw e
      if (e.status === null) {
        // Offline the app opens straight into the local data (SPEC 5.6).
        user.value = (await cachedProfile(db)) ?? null
        offline.value = user.value !== null
      } else {
        user.value = null
      }
    }
    loaded.value = true
  }

  /**
   * Adopts the account the server just signed in. Another user's local data is wiped first,
   * after a confirmation when it has unsent changes. Returns false if the user backed out.
   */
  async function signedIn(me: Me): Promise<boolean> {
    const stored = await storedUserId(db)
    if (stored && stored !== me.id) {
      if (!(await confirmLosingChanges())) {
        await call(() => api.POST('/api/v1/auth/logout')).catch(() => undefined)
        return false
      }
      await wipeLocalData(db)
    }
    await rememberUser(db, me)
    user.value = me
    expired.value = false
    loaded.value = true
    return true
  }

  /** Signs out and wipes the local data. Returns false if the user kept their unsent changes. */
  async function logout(): Promise<boolean> {
    if (!(await confirmLosingChanges())) return false
    await call(() => api.POST('/api/v1/auth/logout')).catch((e: unknown) => {
      // An already invalid session is as good as signed out.
      if (!isFailure(e) || e.status !== 401) throw e
    })
    await wipeLocalData(db)
    user.value = null
    expired.value = false
    return true
  }

  /**
   * Applies a profile change at once and sends it to the server; offline it waits in the local
   * database and goes out with the next successful sync (SPEC 9, Visual design).
   */
  async function updateProfile(patch: ProfileUpdate): Promise<void> {
    if (!user.value) return
    // Stored before it is shown, so a reload right after the change cannot lose it.
    const pending = { ...((await getMeta<ProfileUpdate>(db, PENDING_PROFILE)) ?? {}), ...patch }
    await setMeta(db, PENDING_PROFILE, pending)
    // A plain object: IndexedDB cannot store Vue's reactive proxy.
    const next = { ...user.value, ...patch } as Me
    await rememberUser(db, next)
    user.value = next
    await sendProfile()
  }

  async function sendProfile(): Promise<void> {
    const pending = await getMeta<ProfileUpdate>(db, PENDING_PROFILE)
    if (!pending) return
    try {
      await call(() => api.PATCH('/api/v1/me', { body: pending }))
      await db.meta.delete(PENDING_PROFILE)
    } catch (e) {
      if (!isFailure(e)) throw e
      // Kept for the next attempt; a refused value is dropped so it does not block later changes.
      if (e.status !== null && e.status !== 401) await db.meta.delete(PENDING_PROFILE)
    }
  }

  return { user, loaded, expired, offline, load, signedIn, logout, updateProfile, sendProfile }
})
