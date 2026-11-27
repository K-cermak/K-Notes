import { describe, expect, it } from 'vitest'
import { applyTheme, parseTheme, setBarColor } from './theme'

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

describe('setBarColor', () => {
  it('colours both theme-color tags and restores the page colour', () => {
    document.head.innerHTML = `
      <meta name="theme-color" media="(prefers-color-scheme: light)" content="" />
      <meta name="theme-color" media="(prefers-color-scheme: dark)" content="" />`
    const contents = () =>
      [...document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')].map(
        (meta) => meta.content,
      )
    applyTheme('system', document.createElement('html'))
    setBarColor('rgb(1, 2, 3)')
    expect(contents()).toEqual(['rgb(1, 2, 3)', 'rgb(1, 2, 3)'])
    setBarColor(null)
    expect(contents()).toEqual(['#ffffff', '#0a0a0a'])
  })
})
