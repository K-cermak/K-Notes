import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, type PublicConfig } from '@/api/client'
import { cachedConfig } from '@/db/identity'
import { db } from '@/db/schema'
import { useInstanceStore } from './instance'

const config: PublicConfig = {
  app_name: 'Notes',
  version: '1.0.0',
  setup_required: false,
  registration_open: false,
  password_login_enabled: true,
  oidc_enabled: false,
  oidc_provider_name: 'SSO',
  trash_retention_days: 7,
  max_image_mb: 10,
  captcha: null,
}

describe('instance store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('caches the configuration for an offline start', async () => {
    vi.spyOn(api, 'GET').mockResolvedValueOnce({
      data: config,
      response: new Response(null, { status: 200 }),
    })
    await useInstanceStore().load()
    expect(await cachedConfig(db)).toEqual(config)

    setActivePinia(createPinia())
    vi.spyOn(api, 'GET').mockRejectedValueOnce(new TypeError('offline'))
    const offline = useInstanceStore()
    await offline.load()
    expect(offline.config).toEqual(config)
    expect(offline.failed).toBe(true)
  })

  it('starts from the cached configuration without waiting for the server', async () => {
    vi.spyOn(api, 'GET').mockResolvedValueOnce({
      data: config,
      response: new Response(null, { status: 200 }),
    })
    await useInstanceStore().load()

    setActivePinia(createPinia())
    vi.spyOn(api, 'GET').mockReturnValueOnce(new Promise(() => {}))
    const instance = useInstanceStore()
    await instance.start()
    expect(instance.config).toEqual(config)
  })
})
