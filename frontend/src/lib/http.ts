import { env } from './env'
import { supabase } from './supabase'

const DEFAULT_TIMEOUT_MS = 30_000

export class ApiError extends Error {
  status: number | null
  isNetworkError: boolean
  payload: unknown

  constructor(message: string, options: { status?: number | null; isNetworkError?: boolean; payload?: unknown } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status ?? null
    this.isNetworkError = options.isNetworkError ?? false
    this.payload = options.payload ?? null
  }
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function withTimeout(timeoutMs: number): AbortSignal {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  controller.signal.addEventListener('abort', () => clearTimeout(timeout), { once: true })
  return controller.signal
}

function joinUrl(path: string): string {
  const base = env.apiBaseUrl.replace(/\/$/, '')
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${base}${suffix}`
}

export async function requestJson<T>(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const headers = {
    Accept: 'application/json',
    ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    ...(await authHeaders()),
    ...(init.headers ?? {}),
  }

  let response: Response
  try {
    response = await fetch(joinUrl(path), {
      ...init,
      headers,
      signal: init.signal ?? withTimeout(timeoutMs),
    })
  } catch (error) {
    throw new ApiError('Network request failed', { isNetworkError: true, payload: error })
  }

  let payload: unknown = null
  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) {
    payload = await response.json().catch(() => null)
  }

  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? String((payload as { detail?: unknown }).detail)
        : `Request failed with status ${response.status}`
    throw new ApiError(detail, { status: response.status, payload })
  }

  return payload as T
}

export async function requestStream(path: string, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<Response> {
  const headers = {
    ...(await authHeaders()),
    ...(init.headers ?? {}),
  }

  try {
    const response = await fetch(joinUrl(path), {
      ...init,
      headers,
      signal: init.signal ?? withTimeout(timeoutMs),
    })

    if (!response.ok) {
      const message = `Request failed with status ${response.status}`
      throw new ApiError(message, { status: response.status })
    }

    return response
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    throw new ApiError('Streaming request failed', { isNetworkError: true, payload: error })
  }
}
