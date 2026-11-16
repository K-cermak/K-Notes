import { api, call } from '@/api/client'
import type { SyncTransport } from './engine'

export const apiTransport: SyncTransport = {
  push: (body) => call(() => api.POST('/api/v1/sync/push', { body })),
  pull: (since) => call(() => api.GET('/api/v1/sync/pull', { params: { query: { since } } })),
}
