/**
 * The captcha widget, alone in a same-origin frame. Only this page's Content-Security-Policy admits
 * the provider's scripts (SPEC 7); the form around it gets the token through postMessage.
 */
import './frame.css'
import type { CaptchaPayload, CaptchaProvider } from './protocol'

type Callbacks = {
  callback: (token: string) => void
  'expired-callback': () => void
  'error-callback': () => void
}
type HostedApi = {
  render: (element: HTMLElement, options: Record<string, unknown>) => unknown
}

const params = new URLSearchParams(location.search)
const provider = params.get('provider') as CaptchaProvider | null
const siteKey = params.get('sitekey') ?? ''
const theme = params.get('theme') === 'dark' ? 'dark' : 'light'
const language = params.get('lang') ?? 'en'
const root = document.getElementById('captcha') as HTMLElement

document.documentElement.lang = language
document.documentElement.dataset.theme = theme

function post(message: CaptchaPayload): void {
  parent.postMessage({ source: 'captcha', ...message }, location.origin)
}

const callbacks: Callbacks = {
  callback: (token) => post({ type: 'token', token }),
  'expired-callback': () => post({ type: 'token', token: null }),
  'error-callback': () => post({ type: 'error' }),
}

// The challenge pop-ups of reCAPTCHA and hCaptcha are absolutely positioned elements appended to
// the body, so the height comes from the children rather than from a resize observer.
let reported = 0
function reportSize(): void {
  let bottom = 0
  for (const element of document.body.children) {
    const box = element.getBoundingClientRect()
    if (box.height > 0 && box.bottom > 0) bottom = Math.max(bottom, box.bottom + scrollY)
  }
  const height = Math.ceil(bottom)
  if (height !== reported) {
    reported = height
    post({ type: 'size', height })
  }
}
setInterval(reportSize, 200)

/** Loads a provider's script, which calls window.onCaptchaLoad once its API is ready. */
function loadScript(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    ;(window as unknown as Record<string, unknown>).onCaptchaLoad = resolve
    const script = document.createElement('script')
    script.src = url
    script.async = true
    script.onerror = reject
    document.head.append(script)
  })
}

// Below the standard widget's 304 px, reCAPTCHA and hCaptcha have a compact variant.
const size = innerWidth < 304 ? 'compact' : 'normal'

async function renderHosted(name: string, url: string, options: Record<string, unknown>) {
  await loadScript(url)
  const api = (window as unknown as Record<string, HostedApi>)[name]
  api?.render(root, { sitekey: siteKey, theme, ...callbacks, ...options })
}

async function renderAltcha(): Promise<void> {
  const [, { default: Pbkdf2Worker }] = await Promise.all([
    import('altcha/external'),
    import('altcha/workers/pbkdf2?worker'),
    import('altcha/altcha.css'),
  ])
  // The external build keeps workers and styles out of the script, as a strict CSP needs.
  $altcha.algorithms.set('PBKDF2/SHA-256', () => new Pbkdf2Worker())
  const widget = document.createElement('altcha-widget')
  widget.setAttribute('challenge', '/api/v1/auth/captcha/challenge')
  // Starts the work as the page opens, so it is usually done before the form is filled in.
  widget.setAttribute('auto', 'onload')
  widget.addEventListener('statechange', (event) => {
    const { state, payload } = (event as CustomEvent<{ state: string; payload?: string }>).detail
    if (state === 'verified' && payload) post({ type: 'token', token: payload })
    else if (state === 'expired' || state === 'unverified') post({ type: 'token', token: null })
    else if (state === 'error') post({ type: 'error' })
  })
  root.append(widget)
}

const query = (extra: Record<string, string>) =>
  new URLSearchParams({ render: 'explicit', onload: 'onCaptchaLoad', ...extra })

async function render(): Promise<void> {
  switch (provider) {
    case 'recaptcha':
      return renderHosted(
        'grecaptcha',
        `https://www.google.com/recaptcha/api.js?${query({ hl: language })}`,
        { size },
      )
    case 'hcaptcha':
      return renderHosted(
        'hcaptcha',
        `https://js.hcaptcha.com/1/api.js?${query({ hl: language })}`,
        {
          size,
          'chalexpired-callback': callbacks['expired-callback'],
        },
      )
    case 'turnstile':
      return renderHosted(
        'turnstile',
        `https://challenges.cloudflare.com/turnstile/v0/api.js?${query({})}`,
        { size: 'flexible', language, 'timeout-callback': callbacks['expired-callback'] },
      )
    case 'altcha':
      return renderAltcha()
    default:
      throw new Error(`Unknown captcha provider ${provider}`)
  }
}

render().catch(() => post({ type: 'error' }))
