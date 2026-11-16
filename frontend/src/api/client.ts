import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export const api = createClient<paths>({ baseUrl: '' })

export type ApiError = components['schemas']['ErrorResponse']
export type PublicConfig = components['schemas']['PublicConfig']
