import { describe, expect, it, vi } from 'vitest'

vi.mock('@/views/HomeView.vue', () => ({ default: {} }))
const { afterSignIn } = await import('./router')

describe('afterSignIn', () => {
  it('follows local paths only', () => {
    expect(afterSignIn('/admin')).toBe('/admin')
    expect(afterSignIn('//evil.test/x')).toBe('/')
    expect(afterSignIn('https://evil.test')).toBe('/')
    expect(afterSignIn(undefined)).toBe('/')
    expect(afterSignIn(['/admin'])).toBe('/')
  })
})
