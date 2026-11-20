import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError, type Page } from '../api'
import { useAuth } from '../auth'

interface User { id: string; email: string; full_name: string; is_active: boolean; role_codes: string[] }
interface Role { id: string; code: string; name_ar: string; name_en: string }

export default function UsersPage() {
  const { t, i18n } = useTranslation()
  const { can } = useAuth()
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [showForm, setShowForm] = useState(false)
  const users = useQuery({ queryKey: ['users', q], queryFn: () => api<Page<User>>(`/users/?search=${encodeURIComponent(q)}`) })
  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<Page<Role>>('/roles/?page_size=100'), enabled: can('identity.role.view') })

  return (
    <>
      <div className="page-header">
        <div className="page-header-title">
          <span className="page-header-icon">👥</span>
          <div>
            <h1>{t('users.title')}</h1>
            <p>إدارة المستخدمين، الصلاحيات، الأدوار الوظيفية، وحالة الحسابات</p>
          </div>
        </div>
        <div className="page-header-actions">
          {can('identity.user.create') && (
            <button className="btn" onClick={() => setShowForm((v) => !v)}>
              {showForm ? t('common.cancel') : `+ ${t('users.new')}`}
            </button>
          )}
        </div>
      </div>

      <div className="filter-bar">
        <div className="search-input-wrapper">
          <span className="search-input-icon">🔍</span>
          <input placeholder={t('common.search')} value={q} onChange={(e) => setQ(e.target.value)} />
          {q && <button className="search-clear-btn" onClick={() => setQ('')}>✕</button>}
        </div>
      </div>
      {showForm && <NewUser roles={roles.data?.results ?? []} onDone={() => { setShowForm(false); qc.invalidateQueries({ queryKey: ['users'] }) }} />}
      {users.isLoading ? t('common.loading') : (
        <div className="table-container">
          <table>
            <thead><tr><th>{t('users.email')}</th><th>{t('users.name')}</th><th>{t('users.roles')}</th><th>{t('users.status')}</th></tr></thead>
            <tbody>
              {users.data?.results.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td><td>{u.full_name}</td>
                  <td>{u.role_codes.map((c) => { const r = roles.data?.results.find((x) => x.code === c); return r ? (i18n.language === 'ar' ? r.name_ar : r.name_en) : c }).join('، ')}</td>
                  <td><span className={`badge ${u.is_active ? 'ok' : 'off'}`}>{u.is_active ? t('common.active') : t('common.inactive')}</span></td>
                </tr>
              ))}
              {users.data?.results.length === 0 && <tr><td colSpan={4}>{t('common.empty')}</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function NewUser({ roles, onDone }: { roles: Role[]; onDone: () => void }) {
  const { t, i18n } = useTranslation()
  const [f, setF] = useState({ email: '', full_name: '', password: '', role: '' })
  const [err, setErr] = useState('')
  const m = useMutation({
    mutationFn: () => api('/users/', { method: 'POST', json: { email: f.email, full_name: f.full_name, password: f.password, role_codes: f.role ? [f.role] : [] } }),
    onSuccess: onDone,
    onError: (e) => setErr(e instanceof ApiError ? JSON.stringify(e.details ?? e.message) : t('common.error')),
  })
  const submit = (e: FormEvent) => { e.preventDefault(); setErr(''); m.mutate() }
  return (
    <form className="card" onSubmit={submit} style={{ marginBlockEnd: '1rem' }}>
      <div className="field"><label>{t('users.email')}</label><input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
      <div className="field"><label>{t('users.name')}</label><input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></div>
      <div className="field"><label>{t('users.password')}</label><input type="password" required minLength={10} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></div>
      <div className="field"><label>{t('users.roles')}</label>
        <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
          <option value="" />
          {roles.map((r) => <option key={r.id} value={r.code}>{i18n.language === 'ar' ? r.name_ar : r.name_en}</option>)}
        </select></div>
      {err && <div className="error" role="alert">{err}</div>}
      <button className="btn" disabled={m.isPending}>{t('common.save')}</button>
    </form>
  )
}
