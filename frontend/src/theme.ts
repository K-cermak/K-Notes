export const themes = ['system', 'light', 'dark'] as const

export type Theme = (typeof themes)[number]

export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  if (theme === 'system') {
    delete root.dataset.theme
  } else {
    root.dataset.theme = theme
  }
}

export function parseTheme(value: unknown): Theme | null {
  return themes.find((theme) => theme === value) ?? null
}
