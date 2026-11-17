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

  return { config, failed, load }
})
