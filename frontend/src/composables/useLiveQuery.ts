import { liveQuery } from 'dexie'
import { onScopeDispose, shallowRef, type Ref } from 'vue'

/** A ref that follows a Dexie query and updates whenever the data behind it changes. */
export function useLiveQuery<T>(query: () => T | Promise<T>, initial: T): Ref<T> {
  const value = shallowRef(initial) as Ref<T>
  const subscription = liveQuery(query).subscribe({
    next: (result) => {
      value.value = result
    },
    error: (error: unknown) => console.error('Live query failed', error),
  })
  onScopeDispose(() => subscription.unsubscribe())
  return value
}
