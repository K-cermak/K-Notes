import { onBeforeUnmount, ref, shallowRef, watch, type Ref } from 'vue'

const DRAG_THRESHOLD_PX = 6
const LONG_PRESS_MS = 450
// A finger that moves this far before the long-press fires is scrolling, not picking a card up.
const TOUCH_SLOP_PX = 10
const EDGE_PX = 72
const MAX_SCROLL_STEP_PX = 18

export interface DragPosition {
  id: string
  /** The dragged card's top left corner, relative to the container. */
  x: number
  y: number
}

interface Pending {
  id: string
  pointerId: number
  startX: number
  startY: number
  offsetX: number
  offsetY: number
  touch: boolean
  /** Mouse: at once. Touch: after the long-press. */
  armed: boolean
  timer: ReturnType<typeof setTimeout> | null
}

/**
 * Drag to reorder notes over the masonry layout (SPEC 9, Ordering and selection). A mouse drag
 * starts after a few pixels of movement, a touch drag after a long-press, which also selects the
 * note. While dragging, `preview` is the order to lay out, so the other cards move out of the way.
 */
export function useNoteDrag(options: {
  container: Ref<HTMLElement | null>
  keys: Ref<string[]>
  /** The card under a point in container coordinates, other than the dragged one. */
  hit: (x: number, y: number, dragged: string) => string | null
  canDrag: () => boolean
  onDrop: (id: string, order: string[]) => void
  onLongPress: (id: string) => void
}) {
  const preview = shallowRef<string[] | null>(null)
  const drag = ref<DragPosition | null>(null)
  let pending: Pending | null = null
  let pointer = { x: 0, y: 0 }
  let frame = 0
  let suppressClickUntil = 0

  // The written order arrives through the live query; until then the preview stays, so the
  // dropped card does not jump back for a moment.
  watch(options.keys, () => {
    if (!drag.value) preview.value = null
  })

  function onPointerDown(event: PointerEvent, id: string, card: HTMLElement): void {
    if (event.button !== 0 || pending) return
    const target = event.target as Element
    if (target.closest('button, a, input, textarea, [role="checkbox"], [contenteditable="true"]')) {
      return
    }
    const rect = card.getBoundingClientRect()
    const touch = event.pointerType !== 'mouse'
    pending = {
      id,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      touch,
      armed: !touch,
      timer: touch ? setTimeout(onLongPress, LONG_PRESS_MS) : null,
    }
    pointer = { x: event.clientX, y: event.clientY }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', cancel)
    window.addEventListener('contextmenu', blockMenu, { capture: true })
    // Only a non-passive touchmove listener can stop the page from scrolling under the finger.
    document.addEventListener('touchmove', blockScroll, { passive: false })
  }

  function onLongPress(): void {
    if (!pending) return
    pending.armed = true
    pending.timer = null
    suppressClickUntil = Number.POSITIVE_INFINITY
    options.onLongPress(pending.id)
  }

  function blockScroll(event: TouchEvent): void {
    if (pending?.armed && event.cancelable) event.preventDefault()
  }

  function blockMenu(event: Event): void {
    if (pending?.touch) event.preventDefault()
  }

  function onMove(event: PointerEvent): void {
    if (!pending || event.pointerId !== pending.pointerId) return
    pointer = { x: event.clientX, y: event.clientY }
    if (!drag.value) {
      const distance = Math.hypot(pointer.x - pending.startX, pointer.y - pending.startY)
      if (!pending.armed) {
        if (distance > TOUCH_SLOP_PX) cancel()
        return
      }
      if (distance < DRAG_THRESHOLD_PX || !options.canDrag()) return
      preview.value = [...options.keys.value]
      suppressClickUntil = Number.POSITIVE_INFINITY
      document.documentElement.dataset.dragging = ''
      frame = requestAnimationFrame(tick)
    }
    update()
  }

  function update(): void {
    const container = options.container.value
    if (!pending || !container) return
    const rect = container.getBoundingClientRect()
    const { id } = pending
    drag.value = {
      id,
      x: pointer.x - rect.left - pending.offsetX,
      y: pointer.y - rect.top - pending.offsetY,
    }
    const over = options.hit(pointer.x - rect.left, pointer.y - rect.top, id)
    const current = preview.value ?? options.keys.value
    const from = current.indexOf(id)
    const to = over ? current.indexOf(over) : -1
    if (from < 0 || to < 0 || from === to) return
    const next = current.filter((key) => key !== id)
    next.splice(to, 0, id)
    preview.value = next
  }

  // Scrolls while the card is held near the top or bottom edge of the window.
  function tick(): void {
    if (!drag.value) return
    const fromTop = pointer.y - EDGE_PX
    const fromBottom = window.innerHeight - EDGE_PX - pointer.y
    const step =
      fromTop < 0
        ? Math.max(fromTop / 4, -MAX_SCROLL_STEP_PX)
        : fromBottom < 0
          ? Math.min(-fromBottom / 4, MAX_SCROLL_STEP_PX)
          : 0
    if (step !== 0) {
      window.scrollBy(0, step)
      update()
    }
    frame = requestAnimationFrame(tick)
  }

  function onUp(event: PointerEvent): void {
    if (!pending || event.pointerId !== pending.pointerId) return
    const { id } = pending
    const order = preview.value
    const moved = !!drag.value && !!order && order.join() !== options.keys.value.join()
    finish()
    if (moved) options.onDrop(id, order)
    else preview.value = null
  }

  function cancel(): void {
    finish()
    preview.value = null
  }

  function finish(): void {
    if (pending?.timer) clearTimeout(pending.timer)
    pending = null
    drag.value = null
    cancelAnimationFrame(frame)
    delete document.documentElement.dataset.dragging
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('pointerup', onUp)
    window.removeEventListener('pointercancel', cancel)
    window.removeEventListener('contextmenu', blockMenu, { capture: true })
    document.removeEventListener('touchmove', blockScroll)
    // The click that follows the release must not open or select the card.
    if (suppressClickUntil === Number.POSITIVE_INFINITY) suppressClickUntil = Date.now() + 400
  }

  /** For the card's click handler: true when the click only ends a drag or a long-press. */
  function swallowClick(): boolean {
    return Date.now() < suppressClickUntil
  }

  onBeforeUnmount(cancel)

  return { preview, drag, onPointerDown, swallowClick }
}
