import { onBeforeUnmount, onMounted, ref } from 'vue'

/** How far the spinner travels before releasing syncs, in pixels (SPEC 9, Pull to sync). */
export const PULL_THRESHOLD = 70
const PULL_MAX = 120
// A finger moving less than this has not chosen between pulling and scrolling sideways yet.
const SLOP = 8
// A sync that answers at once would only flash the spinner.
const MIN_SPIN_MS = 500
// Matches the spinner's slide back in PullToSync.vue.
const LEAVE_MS = 240

export type PullPhase = 'idle' | 'pulling' | 'syncing' | 'leaving'

/**
 * Pull the list down from its top to sync, on touch screens. `allowed` is asked on every move, so
 * a long-press that starts a selection or a drag ends the pull. The page's own pull-to-refresh is
 * switched off in CSS (`overscroll-behavior-y` on html), so this needs no non-passive listeners.
 */
export function usePullToSync(allowed: () => boolean, sync: () => Promise<void>) {
  const distance = ref(0)
  const phase = ref<PullPhase>('idle')
  let start: { x: number; y: number } | null = null
  let decided = false
  let leaving: ReturnType<typeof setTimeout> | undefined

  function leave(): void {
    phase.value = 'leaving'
    distance.value = 0
    clearTimeout(leaving)
    leaving = setTimeout(() => (phase.value = 'idle'), LEAVE_MS)
  }

  // Rubber band: the spinner follows the finger at first and slows down towards PULL_MAX.
  function resist(dy: number): number {
    return PULL_MAX * (1 - Math.exp(-dy / PULL_MAX))
  }

  function onStart(event: TouchEvent): void {
    // A second finger ends the pull.
    if (start) {
      cancel()
      return
    }
    if (phase.value === 'syncing') return
    if (event.touches.length !== 1 || window.scrollY > 0 || !allowed()) return
    const touch = event.touches[0]!
    start = { x: touch.clientX, y: touch.clientY }
    decided = false
  }

  function cancel(): void {
    start = null
    if (phase.value === 'pulling') leave()
  }

  function onMove(event: TouchEvent): void {
    if (!start) return
    const touch = event.touches[0]!
    const dx = touch.clientX - start.x
    const dy = touch.clientY - start.y
    if (event.touches.length !== 1 || window.scrollY > 0 || !allowed()) {
      cancel()
      return
    }
    if (!decided) {
      if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return
      // Sideways or upwards is not a pull; the touch is left to the page.
      if (dy <= 0 || Math.abs(dx) > dy) {
        start = null
        return
      }
      decided = true
      clearTimeout(leaving)
      phase.value = 'pulling'
    }
    distance.value = resist(Math.max(0, dy - SLOP))
  }

  async function onEnd(): Promise<void> {
    if (!start) return
    start = null
    if (phase.value !== 'pulling') return
    if (distance.value < PULL_THRESHOLD) {
      cancel()
      return
    }
    phase.value = 'syncing'
    distance.value = PULL_THRESHOLD
    try {
      await Promise.all([sync(), new Promise((resolve) => setTimeout(resolve, MIN_SPIN_MS))])
    } finally {
      leave()
    }
  }

  const listeners: [keyof WindowEventMap, (event: TouchEvent) => void][] = [
    ['touchstart', onStart],
    ['touchmove', onMove],
    ['touchend', () => void onEnd()],
    ['touchcancel', cancel],
  ]
  onMounted(() => {
    for (const [name, listener] of listeners) {
      window.addEventListener(name, listener as EventListener, { passive: true })
    }
  })
  onBeforeUnmount(() => {
    clearTimeout(leaving)
    for (const [name, listener] of listeners) {
      window.removeEventListener(name, listener as EventListener)
    }
  })

  return { distance, phase }
}
