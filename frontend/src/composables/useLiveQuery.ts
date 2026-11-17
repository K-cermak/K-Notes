import { liveQuery, type Subscription } from 'dexie'
import { onScopeDispose, shallowRef, watch, type Ref, type WatchSource } from 'vue'

/**
 * A ref that follows a Dexie query and updates whenever the data behind it changes.
 *
 * Dexie re-runs a query only when rows it read change, so a query that reads a Vue ref (such as
 * the ID of a note created after the form opened) names that ref as `source` to be restarted.
 */
export function useLiveQuery<T>(
  query: () => T | Promise<T>,
  initial: T,
  source?: WatchSource,
): Ref<T> {
  const value = shallowRef(initial) as Ref<T>
  let subscription: Subscription | null = null
  function subscribe(): void {
    subscription?.unsubscribe()
    subscription = liveQuery(query).subscribe({
      next: (result) => {
        value.value = result
      },
      error: (error: unknown) => console.error('Live query failed', error),
    })
  }
  if (source) watch(source, subscribe, { immediate: true })
  else subscribe()
  onScopeDispose(() => subscription?.unsubscribe())
  return value
}
