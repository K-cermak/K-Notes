import { describe, expect, it } from 'vitest'
import { call, Failure } from './client'

function respond(status: number, body: unknown, headers: Record<string, string> = {}) {
  const response = new Response(JSON.stringify(body), { status, headers })
  return () => Promise.resolve(status < 400 ? { data: body, response } : { error: body, response })
}

describe('call', () => {
  it('returns the data of a successful response', async () => {
    await expect(call(respond(200, { ok: 1 }))).resolves.toEqual({ ok: 1 })
  })

  it('turns an error response into a Failure with its code', async () => {
    const failure = await call(respond(409, { code: 'email_taken', message: 'Taken' })).catch(
      (e: unknown) => e,
    )
    expect(failure).toBeInstanceOf(Failure)
    expect(failure).toMatchObject({ status: 409, code: 'email_taken', message: 'Taken' })
  })

  it('reads Retry-After for throttled requests', async () => {
    const request = respond(429, { code: 'too_many_requests', message: '' }, { 'retry-after': '8' })
    await expect(call(request)).rejects.toMatchObject({ retryAfter: 8 })
  })

  it('reports network errors without a status', async () => {
    const request = () => Promise.reject(new TypeError('Failed to fetch'))
    await expect(call(request)).rejects.toMatchObject({ status: null, code: 'network' })
  })
})
