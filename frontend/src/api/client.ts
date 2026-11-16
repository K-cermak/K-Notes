import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export const api = createClient<paths>({ baseUrl: '' })

type Schemas = components['schemas']
export type ApiError = Schemas['ErrorResponse']
export type PublicConfig = Schemas['PublicConfig']
export type Me = Schemas['Me']
export type AdminUser = Schemas['AdminUser']
export type CreatedLink = Schemas['CreatedLink']
export type PendingInvite = Schemas['PendingInvite']

/** A failed call, reduced to what the UI shows. Network errors have no status. */
export class Failure extends Error {
  constructor(
    readonly status: number | null,
    readonly code: string,
    message: string,
    readonly retryAfter?: number,
  ) {
    super(message)
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response }

/** Unwraps an openapi-fetch call, turning every kind of failure into a Failure. */
export async function call<T>(request: () => Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await request()
  } catch {
    throw new Failure(null, 'network', 'Network error')
  }
  const { data, error, response } = result
  if (response.ok) {
    return data as T
  }
  const body = (error ?? {}) as Partial<ApiError>
  const retryAfter = Number(response.headers.get('retry-after')) || undefined
  throw new Failure(
    response.status,
    body.code ?? 'unknown',
    body.message ?? response.statusText,
    retryAfter,
  )
}

export function isFailure(value: unknown): value is Failure {
  return value instanceof Failure
}
