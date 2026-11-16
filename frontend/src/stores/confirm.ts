import { defineStore } from 'pinia'
import { shallowRef } from 'vue'

export interface ConfirmRequest {
  title: string
  message: string
  confirmLabel: string
  danger?: boolean
  resolve: (confirmed: boolean) => void
}

/** One confirmation dialog for the whole app; ask() resolves with the user's answer. */
export const useConfirmStore = defineStore('confirm', () => {
  const request = shallowRef<ConfirmRequest | null>(null)

  function ask(options: Omit<ConfirmRequest, 'resolve'>): Promise<boolean> {
    request.value?.resolve(false)
    return new Promise((resolve) => {
      request.value = { ...options, resolve }
    })
  }

  function answer(confirmed: boolean): void {
    request.value?.resolve(confirmed)
    request.value = null
  }

  return { request, ask, answer }
})
