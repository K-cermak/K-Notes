import { afterEach, describe, expect, it } from 'vitest'
import { applyTimeFormat, i18n } from './i18n'

const afternoon = new Date(2026, 0, 5, 13, 5)

describe('applyTimeFormat', () => {
  afterEach(() => applyTimeFormat('24h'))

  it('uses a 24-hour clock by default, also in English', () => {
    expect(i18n.global.d(afternoon, 'time')).toBe('13:05')
  })

  it('switches to a 12-hour clock and back', () => {
    applyTimeFormat('12h')
    expect(i18n.global.d(afternoon, 'time')).toMatch(/^1:05\sPM$/)
    applyTimeFormat(undefined)
    expect(i18n.global.d(afternoon, 'time')).toBe('13:05')
  })
})
