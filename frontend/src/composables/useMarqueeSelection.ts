import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'
import { useSelectionStore } from '@/stores/selection'

export interface MarqueeBox {
  left: number
  top: number
  width: number
  height: number
}

// Movement before a press on empty space becomes a selection rectangle rather than a click.
const THRESHOLD_PX = 4
// Where a press starts a rectangle: empty space, not a note, a control or text being edited.
const NOT_EMPTY =
  '[data-masonry-key], button, a, input, textarea, select, label, [contenteditable="true"], [role="dialog"]'

/**
 * Selecting several notes by drawing a rectangle over them with the mouse, as in Keep. Touch has
 * long-press for selection instead. A plain drag replaces the selection; with Shift, Ctrl or Cmd it
 * adds to it, as in a file manager. Returns the rectangle to draw, in viewport coordinates.
 */
export function useMarqueeSelection(area: Ref<HTMLElement | null>, enabled: () => boolean) {
  const selection = useSelectionStore()
  const box = ref<MarqueeBox | null>(null)
  let pointerId: number | null = null
  // Kept in page coordinates, so the rectangle stays anchored while the page scrolls.
  let start = { x: 0, y: 0 }
  let pointer = { x: 0, y: 0 }
  let kept: string[] = []

  function emptySpace(target: EventTarget | null): boolean {
    if (!(target instanceof Element) || !area.value) return false
    const inArea =
      area.value.contains(target) || target === document.body || target === document.documentElement
    return inArea && !target.closest(NOT_EMPTY)
  }

  function onPointerDown(event: PointerEvent): void {
    if (event.button !== 0 || event.pointerType !== 'mouse' || !enabled()) return
    if (!emptySpace(event.target)) return
    pointerId = event.pointerId
    start = { x: event.clientX + window.scrollX, y: event.clientY + window.scrollY }
    pointer = { x: event.clientX, y: event.clientY }
    kept = event.shiftKey || event.ctrlKey || event.metaKey ? [...selection.ids] : []
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', stop)
    window.addEventListener('scroll', update, { passive: true })
  }

  function onPointerMove(event: PointerEvent): void {
    if (event.pointerId !== pointerId) return
    pointer = { x: event.clientX, y: event.clientY }
    if (!box.value) {
      const x = start.x - window.scrollX
      const y = start.y - window.scrollY
      if (Math.hypot(pointer.x - x, pointer.y - y) < THRESHOLD_PX) return
      // Otherwise the drag would also select the text it passes over.
      document.documentElement.style.userSelect = 'none'
      window.getSelection()?.removeAllRanges()
    }
    update()
  }

  function update(): void {
    if (pointerId === null || !area.value) return
    const x = start.x - window.scrollX
    const y = start.y - window.scrollY
    const left = Math.min(x, pointer.x)
    const top = Math.min(y, pointer.y)
    const right = Math.max(x, pointer.x)
    const bottom = Math.max(y, pointer.y)
    if (!box.value && Math.hypot(pointer.x - x, pointer.y - y) < THRESHOLD_PX) return
    box.value = { left, top, width: right - left, height: bottom - top }
    const hit: string[] = []
    // Cards on their way out are still in the DOM for their exit animation.
    for (const card of area.value.querySelectorAll<HTMLElement>(
      '[data-masonry-key]:not(.card-leave)',
    )) {
      const r = card.getBoundingClientRect()
      if (r.left < right && r.right > left && r.top < bottom && r.bottom > top) {
        hit.push(card.dataset.masonryKey!)
      }
    }
    selection.replace([...new Set([...kept, ...hit])])
  }

  function onPointerUp(event: PointerEvent): void {
    if (event.pointerId !== pointerId) return
    // The click that ends a drawn rectangle is not a click on whatever it ended over. It follows
    // pointerup at once, if at all (not when the button is released outside the window).
    if (box.value) {
      window.addEventListener('click', swallow, { capture: true, once: true })
      setTimeout(() => window.removeEventListener('click', swallow, { capture: true }))
    }
    stop()
  }

  function swallow(event: MouseEvent): void {
    event.stopPropagation()
    event.preventDefault()
  }

  function stop(): void {
    pointerId = null
    box.value = null
    document.documentElement.style.userSelect = ''
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
    window.removeEventListener('pointercancel', stop)
    window.removeEventListener('scroll', update)
  }

  onMounted(() => window.addEventListener('pointerdown', onPointerDown))
  onBeforeUnmount(() => {
    window.removeEventListener('pointerdown', onPointerDown)
    stop()
  })

  return { box }
}
