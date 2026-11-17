import {
  computed,
  onBeforeUnmount,
  reactive,
  ref,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'

export interface MasonryOptions {
  columnWidth: number
  gap: number
  /** Below this width two narrower columns still fit, as on a phone. */
  minTwoColumns: number
}

export const GRID: MasonryOptions = { columnWidth: 240, gap: 16, minTwoColumns: 320 }
export const LIST: MasonryOptions = { columnWidth: 600, gap: 12, minTwoColumns: Infinity }

export interface Placement {
  x: number
  y: number
}

/**
 * Masonry layout: measures each card with ResizeObserver and places it in the shortest column.
 * Cards are positioned absolutely with transforms, so a drag can lay out a preview order and let
 * the other cards move out of the way. The list view is the same layout with one column.
 */
export function useMasonry(
  container: Ref<HTMLElement | null>,
  keys: Ref<string[]>,
  options: MaybeRefOrGetter<MasonryOptions> = GRID,
) {
  const width = ref(0)
  const heights = reactive(new Map<string, number>())
  const elements = new Map<string, Element>()

  const containerObserver = new ResizeObserver(([entry]) => {
    if (entry) width.value = entry.contentRect.width
  })
  const cardObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const key = (entry.target as HTMLElement).dataset.masonryKey
      if (key) heights.set(key, entry.borderBoxSize[0]?.blockSize ?? entry.contentRect.height)
    }
  })

  watch(container, (element, previous) => {
    if (previous) containerObserver.unobserve(previous)
    if (element) containerObserver.observe(element)
  })

  /** Function ref for each card: `:ref="(el) => track(key, el)"`. */
  function track(key: string, element: unknown): void {
    const previous = elements.get(key)
    if (previous === element) return
    if (previous) cardObserver.unobserve(previous)
    if (element instanceof Element) {
      elements.set(key, element)
      cardObserver.observe(element)
    } else {
      elements.delete(key)
      heights.delete(key)
    }
  }

  const layout = computed(() => {
    const { columnWidth, gap, minTwoColumns } = toValue(options)
    const available = width.value
    let columns = Math.max(1, Math.floor((available + gap) / (columnWidth + gap)))
    if (columns === 1 && available >= minTwoColumns) columns = 2
    const cardWidth =
      columns * columnWidth + (columns - 1) * gap <= available
        ? columnWidth
        : (available - (columns - 1) * gap) / columns
    const offset = (available - (columns * cardWidth + (columns - 1) * gap)) / 2
    const bottoms: number[] = Array.from({ length: columns }, () => 0)
    const placements = new Map<string, Placement>()
    let measured = true
    for (const key of keys.value) {
      const height = heights.get(key)
      if (height === undefined) measured = false
      const column = bottoms.indexOf(Math.min(...bottoms))
      placements.set(key, { x: offset + column * (cardWidth + gap), y: bottoms[column]! })
      bottoms[column]! += (height ?? 0) + gap
    }
    return {
      cardWidth,
      offset,
      placements,
      height: Math.max(0, Math.max(...bottoms) - gap),
      measured,
    }
  })

  onBeforeUnmount(() => {
    containerObserver.disconnect()
    cardObserver.disconnect()
  })

  return { layout, heights, track }
}
