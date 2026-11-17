export const themes = ['system', 'light', 'dark'] as const

export type Theme = (typeof themes)[number]

const STORAGE_KEY = 'theme'

// The --bg token of each scheme in main.css, for the browser and system bars around the app.
const BAR_COLORS = { light: '#ffffff', dark: '#0a0a0a' } as const

export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  if (theme === 'system') {
    delete root.dataset.theme
  } else {
    root.dataset.theme = theme
  }
  for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    const scheme = meta.media.includes('dark') ? 'dark' : 'light'
    meta.content = BAR_COLORS[theme === 'system' ? scheme : theme]
  }
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
