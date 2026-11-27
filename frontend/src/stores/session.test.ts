import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, type Me } from '@/api/client'
import { rememberUser, wipeLocalData } from '@/db/identity'
import { db } from '@/db/schema'
import { useSessionStore } from './session'

const me: Me = {
  id: 'user-1',
  email: 'ada@example.com',
  display_name: 'Ada',
  is_admin: false,
  locale: 'en',
  theme: 'system',
  default_view: 'grid',
  time_format: '24h',
  totp_enabled: false,
  has_password: true,
  oidc_linked: false,
}

function respond(status: number, data?: unknown) {
  return { data, error: data, response: new Response(null, { status }) }
}

describe('session start', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    await wipeLocalData(db)
  })
  afterEach(() => vi.restoreAllMocks())

  it('opens from the cached profile without waiting for the server', async () => {
    await rememberUser(db, me)
    // A connection that never answers, as on a weak signal.
    vi.spyOn(api, 'GET').mockReturnValue(new Promise(() => {}))
    const session = useSessionStore()
    await session.start()
    expect(session.user?.id).toBe('user-1')
    expect(session.loaded).toBe(true)
    expect(session.offline).toBe(true)
  })

  it('marks the session expired when the server refuses it later', async () => {
    await rememberUser(db, me)
    vi.spyOn(api, 'GET').mockResolvedValue(respond(401, { code: 'unauthorized', message: '' }))
    const session = useSessionStore()
    await session.start()
    await vi.waitFor(() => expect(session.expired).toBe(true))
    expect(session.user?.id).toBe('user-1')
  })

  it('takes the fresh profile when the server answers', async () => {
    await rememberUser(db, me)
    vi.spyOn(api, 'GET').mockResolvedValue(respond(200, { ...me, display_name: 'Ada L.' }))
    const session = useSessionStore()
    await session.start()
    await vi.waitFor(() => expect(session.offline).toBe(false))
    expect(session.user?.display_name).toBe('Ada L.')
  })

  it('waits for the server when nothing is cached', async () => {
    vi.spyOn(api, 'GET').mockResolvedValue(respond(401, { code: 'unauthorized', message: '' }))
    const session = useSessionStore()
    await session.start()
    expect(session.user).toBeNull()
    expect(session.expired).toBe(false)
  })
})
