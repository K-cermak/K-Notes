import { registerSW } from 'virtual:pwa-register'

const HOUR_MS = 60 * 60 * 1000
const HINT_DISMISSED_KEY = 'installHintDismissed'

/**
 * Registers the service worker. A new version waits until the user asks for it through
 * onUpdate's reload, since a reload by itself could interrupt typing (SPEC 10).
 */
export function registerServiceWorker(onUpdate: (reload: () => Promise<void>) => void): void {
  if (!('serviceWorker' in navigator) || import.meta.env.DEV) return
  const update = registerSW({
    onNeedRefresh: () => onUpdate(() => update(true)),
    onRegisteredSW: (_url, registration) => {
      if (!registration) return
      // An installed app can stay open for days; it looks for a new version now and then.
      const check = () => void registration.update().catch(() => undefined)
      setInterval(check, HOUR_MS)
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') check()
      })
    },
  })
}

function isIosSafari(): boolean {
  const ios =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const standalone =
    ('standalone' in navigator && navigator.standalone === true) ||
    matchMedia('(display-mode: standalone)').matches
  return ios && !standalone
}

/**
 * Safari may delete a site's data after seven days without use; apps on the home screen are
 * exempt, so iOS users are told how to add it (SPEC 10).
 */
export function wantsInstallHint(): boolean {
  if (!isIosSafari()) return false
  try {
    return localStorage.getItem(HINT_DISMISSED_KEY) === null
  } catch {
    return true
  }
}

export function dismissInstallHint(): void {
  try {
    localStorage.setItem(HINT_DISMISSED_KEY, '1')
  } catch {
    // Without storage the hint simply comes back next time.
  }
}

/** Keeps --viewport-top and --viewport-height on the part of the page the on-screen keyboard leaves free. */
export function trackVisualViewport(): void {
  const viewport = window.visualViewport
  if (!viewport) return
  const root = document.documentElement
  const update = () => {
    root.style.setProperty('--viewport-top', `${viewport.offsetTop}px`)
    root.style.setProperty('--viewport-height', `${viewport.height}px`)
  }
  viewport.addEventListener('resize', update)
  viewport.addEventListener('scroll', update)
  update()
}
