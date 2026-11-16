import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type PublicConfig } from '@/api/client'

export const useInstanceStore = defineStore('instance', () => {
  const config = ref<PublicConfig | null>(null)
  const failed = ref(false)

  async function load(): Promise<void> {
    failed.value = false
    try {
      const { data } = await api.GET('/api/v1/config')
      config.value = data ?? null
      failed.value = !data
    } catch {
      failed.value = true
    }
  }

  return { config, failed, load }
})
