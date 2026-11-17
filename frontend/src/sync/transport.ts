import { api, call, Failure, type ApiError } from '@/api/client'
import type { BlobApi } from './blobs'
import type { SyncTransport } from './engine'

export const apiTransport: SyncTransport = {
  push: (body) => call(() => api.POST('/api/v1/sync/push', { body })),
  pull: (since) => call(() => api.GET('/api/v1/sync/pull', { params: { query: { since } } })),
}

// Raw bytes do not suit the generated JSON client, so blobs use fetch with the same error shape.
async function blobRequest(hash: string, init: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(`/api/v1/blobs/${hash}`, { credentials: 'same-origin', ...init })
  } catch {
    throw new Failure(null, 'network', 'Network error')
  }
  if (response.ok || response.status === 404) return response
  const body = (await response.json().catch(() => ({}))) as Partial<ApiError>
  throw new Failure(response.status, body.code ?? 'unknown', body.message ?? response.statusText)
}

export const blobApi: BlobApi = {
  async exists(hash) {
    return (await blobRequest(hash, { method: 'HEAD' })).ok
  },
  async upload(hash, blob) {
    await blobRequest(hash, {
      method: 'PUT',
      body: blob,
      headers: { 'Content-Type': 'application/octet-stream' },
    })
  },
  async download(hash) {
    const response = await blobRequest(hash, { method: 'GET' })
    return response.ok ? response.blob() : null
  },
}
