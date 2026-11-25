export type CaptchaProvider = 'recaptcha' | 'turnstile' | 'hcaptcha' | 'altcha'

export type CaptchaPayload =
  { type: 'token'; token: string | null } | { type: 'error' } | { type: 'size'; height: number }

/** Messages from the captcha frame (captcha.html) to the form that embeds it. */
export type CaptchaMessage = { source: 'captcha' } & CaptchaPayload

export function isCaptchaMessage(data: unknown): data is CaptchaMessage {
  return (
    typeof data === 'object' && data !== null && (data as { source?: unknown }).source === 'captcha'
  )
}
