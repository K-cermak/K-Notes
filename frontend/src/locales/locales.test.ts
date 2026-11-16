import { describe, expect, it } from 'vitest'
import { locales } from './index'

const files = import.meta.glob<{ default: Record<string, unknown> }>('./*.json', { eager: true })

function keys(messages: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) =>
    typeof value === 'object' && value !== null
      ? keys(value as Record<string, unknown>, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  )
}

describe('locales', () => {
  it('has a JSON file for every listed locale and no unlisted files', () => {
    const codes = Object.keys(files).map((path) => path.slice(2, -5))
    expect(codes.sort()).toEqual(locales.map((l) => l.code).sort())
  })

  it('every locale has the same keys as English', () => {
    const english = keys(files['./en.json']!.default).sort()
    for (const [path, module] of Object.entries(files)) {
      expect(keys(module.default).sort(), path).toEqual(english)
    }
  })
})
