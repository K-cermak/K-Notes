import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'cards-showing-checked'
// Notes deleted elsewhere leave their IDs behind; the oldest go once there are this many.
const MAX_REMEMBERED = 500

function load(): string[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(value) ? value.filter((id) => typeof id === 'string') : []
  } catch {
    return []
  }
}

/**
 * Checklists whose checked items are shown, on the card and in the editor alike; the others keep
 * them collapsed. A view preference of this device rather than note data, so it is kept in
 * localStorage and not synced.
 */
export const useExpandedChecklistsStore = defineStore('expandedChecklists', () => {
  const ids = ref<string[]>(load())

  function has(id: string): boolean {
    return ids.value.includes(id)
  }

  function toggle(id: string): void {
    ids.value = has(id)
      ? ids.value.filter((other) => other !== id)
      : [...ids.value, id].slice(-MAX_REMEMBERED)
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(ids.value))
    } catch {
      // Unavailable storage (private mode) only means the choice is not remembered.
    }
  }

  return { has, toggle }
})
