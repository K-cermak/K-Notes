import { defineStore } from 'pinia'
import { shallowRef } from 'vue'

export interface SnackbarMessage {
  id: number
  text: string
  action?: { label: string; run: () => unknown }
}

const DURATION_MS = 6000

/** One message at a time at the bottom left, optionally with an Undo action (SPEC 9). */
export const useSnackbarStore = defineStore('snackbar', () => {
  const message = shallowRef<SnackbarMessage | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null
  let counter = 0

  function dismiss(): void {
    if (timer) clearTimeout(timer)
    timer = null
    message.value = null
  }

  function show(text: string, action?: SnackbarMessage['action']): void {
    dismiss()
    counter += 1
    message.value = { id: counter, text, action }
    timer = setTimeout(dismiss, DURATION_MS)
  }

  async function act(): Promise<void> {
    const action = message.value?.action
    dismiss()
    await action?.run()
  }

  return { message, show, dismiss, act }
})
