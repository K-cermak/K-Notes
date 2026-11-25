import { computed, ref, useTemplateRef } from 'vue'
import { isFailure } from '@/api/client'
import { useInstanceStore } from '@/stores/instance'

/**
 * The captcha of a sign-in or registration form, as the admin configured it. Pass the template ref
 * name of the form's CaptchaFrame.
 */
export function useCaptcha(form: 'login' | 'registration', refName = 'captchaFrame') {
  const instance = useInstanceStore()
  const frame = useTemplateRef<{ reset: () => void }>(refName)
  const token = ref<string | null>(null)

  const config = computed(() => {
    const captcha = instance.config?.captcha
    return captcha?.[form] ? captcha : null
  })

  /** After a failed submit: a token counts once, and the instance may have changed its captcha. */
  async function afterFailure(error: unknown): Promise<void> {
    frame.value?.reset()
    if (isFailure(error) && error.code === 'captcha_failed' && !config.value) await instance.load()
  }

  return { config, token, afterFailure }
}
