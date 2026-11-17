import { defineStore } from 'pinia'
import { computed, shallowRef } from 'vue'

export interface SnackbarMessage {
  id: number
  text: string
  action?: { label: string; run: () => unknown }
}

const DURATION_MS = 6000

/** One message at a time at the bottom left, optionally with an Undo action (SPEC 9). */
export const useSnackbarStore = defineStore('snackbar', () => {
  const message = shallowRef<SnackbarMessage | null>(null)
  // A message that stays until closed, such as "Update available"; others show over it for a while.
  const pinned = shallowRef<SnackbarMessage | null>(null)
  const current = computed(() => message.value ?? pinned.value)
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

  function pin(text: string, action?: SnackbarMessage['action']): void {
    counter += 1
    pinned.value = { id: counter, text, action }
  }

  /** Closes the message on screen: the passing one if there is one, otherwise the pinned one. */
  function close(): void {
    if (message.value) dismiss()
    else pinned.value = null
  }

  async function act(): Promise<void> {
    const action = current.value?.action
    close()
    await action?.run()
  }

  return { message, current, show, pin, dismiss, close, act }
})
