// Minimal typed API client: bearer auth, single-flight refresh, structured error mapping.
export class ApiError extends Error {
  status: number
  code: string
  details?: unknown
  traceId?: string
  constructor(status: number, code: string, message: string, details?: unknown, traceId?: string) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
    this.traceId = traceId
  }
}

let access: string | null = sessionStorage.getItem('access')
let refresh: string | null = sessionStorage.getItem('refresh')
let refreshing: Promise<boolean> | null = null
let onLogout: () => void = () => {}

export function setTokens(a: string | null, r: string | null) {
  access = a
  refresh = r
  a ? sessionStorage.setItem('access', a) : sessionStorage.removeItem('access')
  r ? sessionStorage.setItem('refresh', r) : sessionStorage.removeItem('refresh')
}
export const hasSession = () => !!access
export const setLogoutHandler = (fn: () => void) => (onLogout = fn)

async function doRefresh(): Promise<boolean> {
  if (!refresh) return false
  const res = await fetch('/api/v1/auth/refresh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }) })
  if (!res.ok) return false
  const data = await res.json()
  setTokens(data.access, data.refresh)
  return true
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.json !== undefined) headers.set('Content-Type', 'application/json')
  if (access) headers.set('Authorization', `Bearer ${access}`)
  const res = await fetch(`/api/v1${path}`, { ...init, headers, body: init.json !== undefined ? JSON.stringify(init.json) : init.body })
  if (res.status === 401 && retry && refresh && !path.startsWith('/auth/login') && !path.startsWith('/auth/logout') && !path.startsWith('/auth/refresh')) {
    refreshing ??= doRefresh().finally(() => (refreshing = null))
    if (await refreshing) return api<T>(path, init, false)
    setTokens(null, null)
    onLogout()
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const e = body?.error
    throw new ApiError(res.status, e?.code ?? 'error', e?.message ?? res.statusText, e?.details, e?.trace_id)
  }
  return body as T
}

/** Authenticated file download (CSV/PDF). Uses the same bearer token as api(); never a public URL. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const headers = new Headers()
  if (access) headers.set('Authorization', `Bearer ${access}`)
  let res = await fetch(`/api/v1${path}`, { headers })
  if (res.status === 401 && refresh && (await (refreshing ??= doRefresh().finally(() => (refreshing = null))))) {
    if (access) headers.set('Authorization', `Bearer ${access}`)
    res = await fetch(`/api/v1${path}`, { headers })
  }
  if (!res.ok) throw new ApiError(res.status, 'download_failed', res.statusText)
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
