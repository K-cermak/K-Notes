import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/** Notes selected for bulk actions (SPEC 9, Ordering and selection). */
export const useSelectionStore = defineStore('selection', () => {
  const ids = ref<string[]>([])
  // Where a Shift+click range starts: the note last selected on its own.
  let anchor: string | null = null

  const active = computed(() => ids.value.length > 0)

  function has(id: string): boolean {
    return ids.value.includes(id)
  }

  function toggle(id: string): void {
    ids.value = has(id) ? ids.value.filter((other) => other !== id) : [...ids.value, id]
    anchor = id
  }

  /** Selects every note between the anchor and this one, in the order they are shown. */
  function extend(id: string, order: string[]): void {
    const from = anchor ? order.indexOf(anchor) : -1
    const to = order.indexOf(id)
    if (from < 0 || to < 0) {
      toggle(id)
      return
    }
    const range = order.slice(Math.min(from, to), Math.max(from, to) + 1)
    ids.value = [...new Set([...ids.value, ...range])]
  }

  function clear(): void {
    ids.value = []
    anchor = null
  }

  /** Selects exactly these notes, as a drawn selection rectangle does while it changes. */
  function replace(next: string[]): void {
    if (next.length === ids.value.length && next.every((id) => ids.value.includes(id))) return
    ids.value = next
  }

  return { ids, active, has, toggle, extend, clear, replace }
})
