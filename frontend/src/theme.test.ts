import { describe, expect, it } from 'vitest'
import { applyTheme, parseTheme } from './theme'

describe('applyTheme', () => {
  it('sets data-theme for an explicit choice and removes it for system', () => {
    const root = document.createElement('html')
    applyTheme('dark', root)
    expect(root.dataset.theme).toBe('dark')
    applyTheme('system', root)
    expect(root.dataset.theme).toBeUndefined()
  })
})

describe('parseTheme', () => {
  it('accepts known themes only', () => {
    expect(parseTheme('light')).toBe('light')
    expect(parseTheme('sepia')).toBeNull()
    expect(parseTheme(undefined)).toBeNull()
  })
})
