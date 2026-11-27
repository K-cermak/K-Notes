export const themes = ['system', 'light', 'dark'] as const

export type Theme = (typeof themes)[number]

const STORAGE_KEY = 'theme'

// The --bg token of each scheme in main.css, for the browser and system bars around the app.
const BAR_COLORS = { light: '#ffffff', dark: '#0a0a0a' } as const

let current: Theme = 'system'
let barOverride: string | null = null

export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  current = theme
  if (theme === 'system') {
    delete root.dataset.theme
  } else {
    root.dataset.theme = theme
  }
  paintBars()
}

/**
 * Colours the browser and system bars with a CSS colour instead of the page background, or
 * restores them with null. A phone's full-screen editor uses it, so the status bar above a
 * coloured note takes the note's colour.
 */
export function setBarColor(color: string | null): void {
  barOverride = color
  paintBars()
}

function paintBars(): void {
  for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    const media = meta.getAttribute('media') ?? ''
    const scheme = current === 'system' ? (media.includes('dark') ? 'dark' : 'light') : current
    meta.content = barOverride ? resolveColor(barOverride, scheme) : BAR_COLORS[scheme]
  }
}

// The meta tags need a plain colour per scheme, while the note palette is defined with
// light-dark() in tokens.css; a probe element resolves it without repeating the values here.
function resolveColor(color: string, scheme: 'light' | 'dark'): string {
  const probe = document.createElement('div')
  probe.style.cssText = `position: absolute; visibility: hidden; color-scheme: ${scheme}`
  probe.style.backgroundColor = color
  document.body.append(probe)
  const resolved = getComputedStyle(probe).backgroundColor
  probe.remove()
  return resolved
}

export function parseTheme(value: unknown): Theme | null {
  return themes.find((theme) => theme === value) ?? null
}

/**
 * The profile lives in IndexedDB, which is asynchronous; a copy in localStorage lets the first
 * paint already use the right theme.
 */
export function rememberTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Storage can be unavailable (private mode); the theme then follows the profile a moment later.
  }
}

export function rememberedTheme(): Theme {
  try {
    return parseTheme(localStorage.getItem(STORAGE_KEY)) ?? 'system'
  } catch {
    return 'system'
  }
}
