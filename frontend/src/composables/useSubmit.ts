import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { isFailure, type Failure } from '@/api/client'

/** Form submission state: one request at a time, and a translated error message. */
export function useSubmit(overrides: Partial<Record<string, string>> = {}) {
  const i18n = useI18n()
  const pending = ref(false)
  const error = ref<string | null>(null)
  const failure = ref<Failure | null>(null)

  function describe(f: Failure): string {
    const override = overrides[f.code] ?? (f.status ? overrides[String(f.status)] : undefined)
    if (override) return i18n.t(override, { seconds: f.retryAfter ?? 0 })
    const key = `errors.${f.code}`
    return i18n.te(key) ? i18n.t(key, { seconds: f.retryAfter ?? 0 }) : i18n.t('errors.unknown')
  }

  async function run(action: () => Promise<unknown>): Promise<boolean> {
    if (pending.value) return false
    pending.value = true
    error.value = null
    failure.value = null
    try {
      await action()
      return true
    } catch (e) {
      if (!isFailure(e)) throw e
      failure.value = e
      error.value = describe(e)
      return false
    } finally {
      pending.value = false
    }
  }

  /** Like run, but returns the action's result, or null when it failed. */
  async function attempt<T>(action: () => Promise<T>): Promise<T | null> {
    let result: T | null = null
    const ok = await run(async () => {
      result = await action()
    })
    return ok ? result : null
  }

  return { pending, error, failure, run, attempt }
}
