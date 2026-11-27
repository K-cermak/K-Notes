import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, call, type PublicConfig } from '@/api/client'
import { cachedConfig, rememberConfig } from '@/db/identity'
import { db } from '@/db/schema'

export const useInstanceStore = defineStore('instance', () => {
  const config = ref<PublicConfig | null>(null)
  const failed = ref(false)

  async function load(): Promise<void> {
    let fresh: PublicConfig
    try {
      fresh = await call(() => api.GET('/api/v1/config'))
    } catch {
      failed.value = true
      config.value ??= (await cachedConfig(db)) ?? null
      return
    }
    config.value = fresh
    failed.value = false
    // The plain response, not config.value: IndexedDB cannot store the reactive proxy.
    await rememberConfig(db, fresh)
  }

  /**
   * For the first navigation: a cached configuration is used at once and refreshed in the
   * background, so a slow or hanging connection does not hold up the start (SPEC 5.6).
   */
  async function start(): Promise<void> {
    const cached = await cachedConfig(db)
    // Until setup is done, the server's answer decides where the app goes.
    if (!cached || cached.setup_required) return load()
    config.value = cached
    void load()
  }

  return { config, failed, load, start }
})
