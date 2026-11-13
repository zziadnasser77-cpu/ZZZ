import { Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from './auth'
import LoginPage from './pages/Login'
import Dashboard from './pages/Dashboard'
import UsersPage from './pages/Users'
import AuditPage from './pages/Audit'

function Guard({ perm, children }: { perm?: string; children: React.ReactNode }) {
  const { can } = useAuth()
  const { t } = useTranslation()
  if (perm && !can(perm)) return <div className="card">{t('common.noAccess')}</div>
  return <>{children}</>
}

function Shell() {
  const { me, loading, logout, can } = useAuth()
  const { t, i18n } = useTranslation()
  if (loading) return <div className="main">{t('common.loading')}</div>
  if (!me) return <Navigate to="/login" replace />
  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="brand">{t('app.name')}<small>{t('app.tagline')}</small></div>
        {/* menu entries are filtered by permission (spec §13) */}
        <NavLink to="/" end>{t('nav.dashboard')}</NavLink>
        {can('identity.user.view') && <NavLink to="/users">{t('nav.users')}</NavLink>}
        {can('audit.event.view') && <NavLink to="/audit">{t('nav.audit')}</NavLink>}
        <div className="spacer" />
        <button onClick={() => i18n.changeLanguage(i18n.language === 'ar' ? 'en' : 'ar')}>{t('nav.language')}</button>
        <button onClick={logout}>{t('nav.logout')} ({me.email})</button>
      </nav>
      <main className="main"><Outlet /></main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Shell />}>
        <Route index element={<Dashboard />} />
        <Route path="users" element={<Guard perm="identity.user.view"><UsersPage /></Guard>} />
        <Route path="audit" element={<Guard perm="audit.event.view"><AuditPage /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
