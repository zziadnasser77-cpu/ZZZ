import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, hasSession, setLogoutHandler, setTokens } from './api'

export interface Me { id: string; email: string; full_name: string; preferred_language: string; roles: string[]; permissions: string[]; mfa_enabled: boolean }

interface AuthCtx {
  me: Me | null
  loading: boolean
  login: (email: string, password: string, otp?: string) => Promise<void>
  logout: () => Promise<void>
  can: (perm: string) => boolean
}
const Ctx = createContext<AuthCtx>(null!)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(hasSession())

  useEffect(() => {
    setLogoutHandler(() => setMe(null))
    if (hasSession()) api<Me>('/auth/me/').then(setMe).catch(() => setTokens(null, null)).finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string, otp?: string) => {
    const r = await api<{ access: string; refresh: string; user: Me }>('/auth/login/', { method: 'POST', json: { email, password, otp } })
    setTokens(r.access, r.refresh)
    setMe(r.user)
  }, [])

  const logout = useCallback(async () => {
    try { await api('/auth/logout/', { method: 'POST', json: { refresh: sessionStorage.getItem('refresh') } }) } catch (e) { if (!(e instanceof ApiError)) throw e }
    setTokens(null, null)
    setMe(null)
  }, [])

  const value = useMemo<AuthCtx>(() => ({ me, loading, login, logout, can: (p) => !!me?.permissions.includes(p) }), [me, loading, login, logout])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
