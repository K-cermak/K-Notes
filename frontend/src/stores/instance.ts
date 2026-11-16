import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, call, type PublicConfig } from '@/api/client'
import { cachedConfig, rememberConfig } from '@/db/identity'
import { db } from '@/db/schema'

export const useInstanceStore = defineStore('instance', () => {
  const config = ref<PublicConfig | null>(null)
  const failed = ref(false)

  async function load(): Promise<void> {
    try {
      config.value = await call(() => api.GET('/api/v1/config'))
      failed.value = false
      await rememberConfig(db, config.value)
    } catch {
      failed.value = true
      config.value ??= (await cachedConfig(db)) ?? null
    }
  }

  return { config, failed, load }
})
