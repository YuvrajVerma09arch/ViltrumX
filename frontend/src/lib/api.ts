/**
 * API client — the single seam between the React app and Django.
 *
 * Design rules:
 *  1. Every screen calls `useApi(fetcher, fallback)` and gets
 *     `{ data, loading, error, live }` back. `live` is false when the request
 *     failed and the caller is seeing `mock.ts` fixtures instead, so the UI can
 *     say so honestly rather than silently pretending fake data is real.
 *  2. Field names are camelCase end to end — the Django serializers already
 *     match `data/mock.ts`, so responses drop straight into the existing types.
 *  3. Tokens live in localStorage and refresh transparently on a 401; one
 *     retry, then sign-out. No refresh loops.
 */

const BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

const ACCESS_KEY = 'viltrumx.access'
const REFRESH_KEY = 'viltrumx.refresh'

export class ApiError extends Error {
  public status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/* ── token storage ───────────────────────────────────────────────────── */

export const auth = {
  get access() {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY)
  },
  get isAuthenticated() {
    return Boolean(localStorage.getItem(ACCESS_KEY))
  },
  save(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

/* ── core request ────────────────────────────────────────────────────── */

async function refreshAccessToken(): Promise<boolean> {
  const refresh = auth.refresh
  if (!refresh) return false
  try {
    const res = await fetch(`${BASE}/auth/token/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
    if (!res.ok) return false
    const body = (await res.json()) as { access?: string }
    if (!body.access) return false
    auth.save(body.access)
    return true
  } catch {
    return false
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  isRetry = false,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init.headers as Record<string, string>) ?? {}),
  }
  const token = auth.access
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...init, headers })

  // Expired access token: refresh once, replay once, then give up.
  if (res.status === 401 && !isRetry && auth.refresh) {
    if (await refreshAccessToken()) return request<T>(path, init, true)
    auth.clear()
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new ApiError(detail, res.status)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body ?? {}) }),
}

/* ── auth flows ──────────────────────────────────────────────────────── */

export async function login(username: string, password: string) {
  const res = await fetch(`${BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    throw new ApiError(
      res.status === 401 ? 'Invalid email or password.' : 'Sign-in failed.',
      res.status,
    )
  }
  const body = (await res.json()) as { access: string; refresh: string }
  auth.save(body.access, body.refresh)
  return body
}

export function logout() {
  auth.clear()
}

/* ── typed endpoint map ──────────────────────────────────────────────── */

export const endpoints = {
  agents: () => api.get('/agents/status'),
  feed: () => api.get('/feed'),
  incidents: () => api.get('/incidents'),
  incident: (id: string) => api.get(`/incidents/${id}`),
  narrative: (id: string, lang: string) =>
    api.get(`/incidents/${id}/narrative?lang=${lang}`),
  ontologyGraph: () => api.get('/ontology/graph'),
  inventory: (category: string) => api.get(`/inventory?category=${category}`),
  connectors: () => api.get('/connectors'),
  connect: (id: string) => api.post(`/connectors/${id}/connect`),
  replay: (scenario = 'inc-042') => api.post('/ingest/replay', { scenario }),
  actions: () => api.get('/actions'),
  actionTrace: (id: string) => api.get(`/actions/${id}/trace`),
  rollback: (id: string) => api.post(`/actions/${id}/rollback`),
  decide: (id: string, decision: 'approve' | 'reject') =>
    api.post(`/actions/${id}/decision`, { decision }),
  policies: () => api.get('/policies'),
  savePolicies: (rows: unknown) => api.put('/policies', rows),
  riskTrend: () => api.get('/risk/trend'),
  riskEntities: () => api.get('/risk/entities'),
  readiness: () => api.get('/risk/readiness'),
  purpleScenarios: () => api.get('/purple/scenarios'),
  runScenario: (id: string) => api.post(`/purple/scenarios/${id}/run`),
  frameworks: () => api.get('/compliance/frameworks'),
  exports: () => api.get('/compliance/exports'),
  exportFramework: (id: string) => api.post(`/compliance/${id}/export`),
  members: () => api.get('/members'),
  invoices: () => api.get('/billing/invoices'),
}

/* ── WebSocket (Command Deck live feed) ──────────────────────────────── */

/**
 * Channels route is per-tenant: `/ws/tenant/<id>/stream` (backend asgi.py).
 * Needs an ASGI server — `daphne viltrumx.asgi:application`. Under plain
 * `manage.py runserver` the upgrade 404s and the feed falls back to polling
 * the REST endpoint, which is why the Command Deck still renders either way.
 */
export function streamUrl(tenantId = 1): string {
  const httpBase = BASE.replace(/\/api\/v1\/?$/, '')
  const wsBase = httpBase.replace(/^http/, 'ws')
  return `${wsBase}/ws/tenant/${tenantId}/stream`
}
