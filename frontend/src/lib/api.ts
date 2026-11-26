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
const TENANT_KEY = 'viltrumx.tenant'
const USER_KEY = 'viltrumx.user'

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
  get tenant() {
    const raw = localStorage.getItem(TENANT_KEY)
    return raw ? (JSON.parse(raw) as { id: number; name: string; slug: string }) : null
  },
  get user(): { id: number; email: string; name: string } | null {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as { id: number; email: string; name: string }) : null
  },
  save(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  saveProfile(user: { id: number; email: string; name: string }, tenant: { id: number; name: string; slug: string }) {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    localStorage.setItem(TENANT_KEY, JSON.stringify(tenant))
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(TENANT_KEY)
    localStorage.removeItem(USER_KEY)
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
  // Session is gone (401 with no usable refresh token): tell the app instead
  // of letting every screen silently fall back to mock fixtures. AppLayout
  // listens for this event and shows a "log in again" banner.
  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent('viltrumx:session-expired'))
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

/* ── auth flows — owner verification ────────────────────────────────────
 *
 * Signup and signin are now two-step. Step 1 (register / login-challenge /
 * resend) only asks the backend to email a 6-digit code and returns NO tokens.
 * Step 2 (verify / login-verify) exchanges the code for a real JWT session.
 * The single place that persists tokens + profile is `saveSession`, so it is
 * impossible to end up "logged in" before the code has been checked.
 * ─────────────────────────────────────────────────────────────────────── */

export type AuthPurpose = 'signup' | 'login'

export type Challenge = {
  email: string
  purpose: AuthPurpose
}

export type VerifiedSession = {
  access: string
  refresh: string
  user: { id: number; email: string; name: string }
  tenant: { id: number; name: string; slug: string }
}

/** Pull a human-readable message out of a DRF error body (string, list, or field-mapped). */
function authErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback
  const b = body as Record<string, unknown>
  const detail = b.detail ?? b.message ?? b.error
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && typeof detail[0] === 'string') return detail[0]
  for (const value of Object.values(b)) {
    if (typeof value === 'string') return value
    if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
  }
  return fallback
}

async function postAuth<T>(path: string, body: unknown, fallback: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
  const payload: unknown = res.status === 204 ? {} : await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new ApiError(authErrorMessage(payload, fallback), res.status)
  }
  return payload as T
}

/** The ONLY place a verification result becomes a logged-in session. */
function saveSession(body: VerifiedSession): VerifiedSession {
  auth.save(body.access, body.refresh)
  if (body.user && body.tenant) {
    auth.saveProfile(body.user, body.tenant)
  }
  return body
}

/** Step 1a — signup: create User + Tenant + Owner, email a code, issue NO tokens. */
export function register(data: {
  email: string
  password: string
  full_name: string
  tenant_name: string
  tenant_slug: string
}): Promise<Challenge> {
  return postAuth<Challenge>('/auth/register', data, 'Registration failed.')
}

/** Step 1b — signin: validate password, email a code, issue NO tokens. */
export function loginChallenge(email: string, password: string): Promise<Challenge> {
  return postAuth<Challenge>('/auth/login-challenge', { email, password }, 'Sign-in failed.')
}

/** Backward-compatible alias for older imports (now challenge-only, no tokens). */
export const login = loginChallenge

/** Step 2a — signup verification: exchange the code for a JWT session. */
export function verify(email: string, code: string): Promise<VerifiedSession> {
  return postAuth<VerifiedSession>('/auth/verify', { email, code }, 'Verification failed.').then(saveSession)
}

/** Step 2b — login verification: exchange password + code for a JWT session. */
export function loginVerify(email: string, password: string, code: string): Promise<VerifiedSession> {
  return postAuth<VerifiedSession>('/auth/login-verify', { email, password, code }, 'Verification failed.').then(saveSession)
}

/** Ask the backend to send (or re-send) a verification code. */
export function resend(email: string, purpose: AuthPurpose): Promise<Challenge> {
  return postAuth<Challenge>('/auth/resend', { email, purpose }, "Couldn't send the code.")
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
  githubOAuthStart: () => api.get<{ auth_url: string }>('/connectors/gh/oauth/start'),
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
  downloadFramework: (id: string) => `${BASE}/compliance/${id}/download`,
  members: () => api.get('/members'),
  inviteMember: (body: { email: string; role: string; display_name?: string }) =>
    api.post('/members/invite', body),
  entitlements: () =>
    api.get<{
      modules: string[]
      connectors_enabled: string | string[]
      connectors_connected: string[]
    }>('/tenant/entitlements'),
  invoices: () => api.get('/billing/invoices'),
  billingPlans: () =>
    api.get<{ configured: boolean; plans: { id: string; name: string; amount_inr: number }[] }>(
      '/billing/plans',
    ),
  createOrder: (plan: string) => api.post('/billing/orders', { plan }),
  verifyPayment: (body: {
    razorpay_order_id: string
    razorpay_payment_id: string
    razorpay_signature: string
  }) => api.post('/billing/verify', body),
  verifyStatus: () =>
    api.get<{ domain: string; domain_verified: boolean; verification_status: string }>(
      '/verify/status',
    ),
  verifyDomainStart: (domain: string) => api.post('/verify/domain/start', { domain }),
  verifyDomainCheck: () => api.post('/verify/domain/check', {}),
  verifyGstin: (gstin: string) => api.post('/verify/gstin', { gstin }),
}

/* ── WebSocket (Command Deck live feed) ──────────────────────────────── */

/**
 * Channels route is per-tenant: `/ws/tenant/<id>/stream` (backend asgi.py).
 * Needs an ASGI server — `daphne viltrumx.asgi:application`. Under plain
 * `manage.py runserver` the upgrade 404s and the feed falls back to polling
 * the REST endpoint, which is why the Command Deck still renders either way.
 *
 * Returns null when the tenant id isn't known yet — the caller then polls
 * instead of guessing tenant 1. The URL is always absolute (browsers reject
 * relative WebSocket URLs): the origin comes from VITE_API_URL when it is an
 * absolute URL, otherwise from the page's own location.
 */
export function streamUrl(): string | null {
  const tenantId = auth.tenant?.id
  if (!tenantId) return null

  let origin: string
  try {
    // BASE is VITE_API_URL when set, else the local dev API host.
    origin = /^https?:\/\//i.test(BASE) ? new URL(BASE).origin : window.location.origin
  } catch {
    origin = window.location.origin
  }
  const wsOrigin = origin.replace(/^http/i, 'ws')
  return `${wsOrigin}/ws/tenant/${tenantId}/stream`
}
