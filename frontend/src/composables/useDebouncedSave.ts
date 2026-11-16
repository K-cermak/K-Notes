import { onBeforeUnmount } from 'vue'

const TEXT_DELAY_MS = 800

/**
 * Debounces text input before it reaches the repository (SPEC 5.6), and flushes at once when
 * the page is hidden or the component goes away, so no keystroke is lost.
 */
export function useDebouncedSave(save: () => Promise<void>, delayMs = TEXT_DELAY_MS) {
  let timer: ReturnType<typeof setTimeout> | null = null

  function flush(): void {
    if (timer === null) return
    clearTimeout(timer)
    timer = null
    void save()
  }

  function schedule(): void {
    if (timer !== null) clearTimeout(timer)
    timer = setTimeout(flush, delayMs)
  }

  const onHidden = () => {
    if (document.visibilityState === 'hidden') flush()
  }
  document.addEventListener('visibilitychange', onHidden)
  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onHidden)
    flush()
  })

  return { schedule, flush, pending: () => timer !== null }
}
