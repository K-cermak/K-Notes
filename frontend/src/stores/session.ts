import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, call, isFailure, type Me } from '@/api/client'

export const useSessionStore = defineStore('session', () => {
  const user = ref<Me | null>(null)
  const loaded = ref(false)

  async function load(): Promise<void> {
    try {
      user.value = await call(() => api.GET('/api/v1/me'))
    } catch (e) {
      if (!isFailure(e) || e.status !== 401) throw e
      user.value = null
    }
    loaded.value = true
  }

  async function logout(): Promise<void> {
    await call(() => api.POST('/api/v1/auth/logout'))
    user.value = null
  }

  return { user, loaded, load, logout }
})
