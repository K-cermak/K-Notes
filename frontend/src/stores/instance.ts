import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, call, type PublicConfig } from '@/api/client'

export const useInstanceStore = defineStore('instance', () => {
  const config = ref<PublicConfig | null>(null)
  const failed = ref(false)

  async function load(): Promise<void> {
    try {
      config.value = await call(() => api.GET('/api/v1/config'))
      failed.value = false
    } catch {
      failed.value = true
    }
  }

  return { config, failed, load }
})
