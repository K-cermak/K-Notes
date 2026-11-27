import { afterEach, describe, expect, it } from 'vitest'
import { allowZoom } from './zoom'

const BASE = 'width=device-width, initial-scale=1'

function viewport(): string {
  return document.querySelector<HTMLMetaElement>('meta[name="viewport"]')!.content
}

describe('allowZoom', () => {
  afterEach(() => {
    document.head.innerHTML = ''
  })

  it('lifts maximum-scale until the last allowance is released', () => {
    document.head.innerHTML = `<meta name="viewport" content="${BASE}, maximum-scale=1" />`
    const first = allowZoom()
    const second = allowZoom()
    expect(viewport()).toBe(BASE)
    first()
    first()
    expect(viewport()).toBe(BASE)
    second()
    expect(viewport()).toBe(`${BASE}, maximum-scale=1`)
  })
})
