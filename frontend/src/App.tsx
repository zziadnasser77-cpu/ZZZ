import { useState } from 'react'
import { Navigate, NavLink, Outlet, Route, Routes, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from './auth'
import LoginPage from './pages/Login'
import Dashboard from './pages/Dashboard'
import UsersPage from './pages/Users'
import AuditPage from './pages/Audit'
import CustomersPage from './pages/Customers'
import CatalogPage from './pages/Catalog'
import PriceListsPage from './pages/PriceLists'
import QuotationsPage from './pages/Quotations'
import DealsPage from './pages/Deals'
import ProcurementPage from './pages/Procurement'
import ShipmentsPage from './pages/Shipments'
import InventoryPage from './pages/Inventory'
import AccountingPage from './pages/Accounting'
import PaymentsPage from './pages/Payments'
import BiomedicalPage from './pages/Biomedical'
import DocumentsAIPage from './pages/DocumentsAI'
import NotificationCenter from './components/NotificationCenter'

function Guard({ perm, children }: { perm?: string; children: React.ReactNode }) {
  const { can } = useAuth()
  const { t } = useTranslation()
  if (perm && !can(perm)) return <div className="card">{t('common.noAccess')}</div>
  return <>{children}</>
}

function Shell() {
  const { me, loading, logout, can } = useAuth()
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const [globalSearch, setGlobalSearch] = useState('')

  // Auto-hide Floating Navigation Drawer (Default: closed/hidden so full screen is dedicated to content)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isPinned, setIsPinned] = useState(() => {
    try {
      return localStorage.getItem('sidebar_pinned') === 'true'
    } catch {
      return false
    }
  })

  const toggleSidebar = () => {
    setSidebarOpen((prev) => !prev)
  }

  const closeSidebar = () => {
    if (!isPinned) {
      setSidebarOpen(false)
    }
  }

  const togglePin = () => {
    setIsPinned((prev) => {
      const next = !prev
      try {
        localStorage.setItem('sidebar_pinned', String(next))
      } catch { }
      if (!next) {
        setSidebarOpen(false) // Auto-hide immediately if unpinned
      }
      return next
    })
  }

  // Auto-hide automatically whenever any navigation link is clicked
  const handleNavClick = () => {
    if (!isPinned) {
      setSidebarOpen(false)
    }
  }

  if (loading) return <div className="main-content">{t('common.loading')}</div>
  if (!me) return <Navigate to="/login" replace />

  const handleGlobalSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && globalSearch.trim()) {
      navigate(`/catalog?q=${encodeURIComponent(globalSearch.trim())}`)
    }
  }

  const userInitials = me.email ? me.email.slice(0, 2).toUpperCase() : 'AD'

  return (
    <div className="app-layout">
      {/* PERSISTENT TOP APP BAR (YouTube / Google Studio Style) */}
      <header className="topbar">
        <div className="topbar-start">
          <button
            className="topbar-menu-btn"
            onClick={toggleSidebar}
            title={sidebarOpen ? 'إغلاق القائمة الجانبية' : 'فتح القائمة الجانبية (تختفي تلقائياً)'}
            aria-label="القائمة الجانبية"
          >
            ☰
          </button>

          <div className="topbar-brand" onClick={() => navigate('/')}>
            <span className="brand-icon">🩺</span>
            <div>
              <span className="brand-title">SMSES</span>
              <span className="brand-subtitle">نظام المبيعات والهندسة الطبية الذكية</span>
            </div>
          </div>
        </div>

        {/* Global Omnibox Search */}
        <div className="topbar-center">
          <div className="topbar-search-box">
            <span className="topbar-search-icon">🔍</span>
            <input
              type="text"
              placeholder="البحث السريع في الأجهزة الطبية، الكتالوج، الموديلات، وعروض الأسعار... (اضغط Enter)"
              value={globalSearch}
              onChange={(e) => setGlobalSearch(e.target.value)}
              onKeyDown={handleGlobalSearch}
            />
          </div>
        </div>

        {/* Topbar Actions & User Menu */}
        <div className="topbar-end">
          <div className="status-pill">
            <span className="status-dot" />
            <span> Ziad AL-Radfani </span>
          </div>

          <NotificationCenter />

          <button
            onClick={() => i18n.changeLanguage(i18n.language === 'ar' ? 'en' : 'ar')}
            style={{
              background: '#f1f5f9',
              border: '1px solid #e2e8f0',
              borderRadius: '999px',
              padding: '0.35rem 0.75rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              color: '#334155',
            }}
          >
            🌐 {i18n.language === 'ar' ? 'English' : 'عربي'}
          </button>

          <div className="user-profile-pill">
            <div className="user-avatar-circle">{userInitials}</div>
            <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#0f172a' }}>
              {me.email.split('@')[0]}
            </div>
            <button
              onClick={logout}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#ef4444',
                padding: '0.2rem',
                fontSize: '1rem',
                display: 'flex',
                alignItems: 'center',
              }}
              title="تسجيل الخروج"
            >
              🚪
            </button>
          </div>
        </div>
      </header>

      {/* BODY (Sidebar + Main Content) */}
      <div className="app-body">
        {/* Backdrop for auto-hide when clicking anywhere outside */}
        {sidebarOpen && !isPinned && (
          <div className="sidebar-backdrop" onClick={closeSidebar} />
        )}

        {/* SIDEBAR NAVIGATION (Auto-Hide Floating Drawer) */}
        <aside
          className={`sidebar ${sidebarOpen ? 'open' : ''} ${isPinned ? 'pinned' : ''}`}
        >
          {/* Header of Drawer with Auto-Hide Status & Close Button */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingBottom: '0.65rem',
              marginBottom: '0.5rem',
              borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.82rem', color: '#cbd5e1' }}>
              <span>🩺</span>
              <span style={{ fontWeight: 700, color: '#f8fafc' }}>قائمة النظام</span>
            </div>

            <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
              <button
                onClick={togglePin}
                title={isPinned ? 'إلغاء التثبيت (تفعيل الإخفاء التلقائي)' : 'تثبيت القائمة دائماً'}
                style={{
                  background: isPinned ? 'rgba(2, 132, 199, 0.3)' : 'rgba(255, 255, 255, 0.08)',
                  border: isPinned ? '1px solid #0284c7' : '1px solid rgba(255, 255, 255, 0.15)',
                  color: isPinned ? '#38bdf8' : '#94a3b8',
                  borderRadius: '6px',
                  padding: '0.2rem 0.5rem',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  fontWeight: 600,
                }}
              >
                <span>📌</span>
                <span>{isPinned ? 'مثبتة' : 'إخفاء تلقائي'}</span>
              </button>

              {!isPinned && (
                <button
                  onClick={closeSidebar}
                  title="إخفاء القائمة"
                  style={{
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#94a3b8',
                    borderRadius: '6px',
                    width: '26px',
                    height: '26px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.85rem',
                  }}
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Main Dashboard */}
          <NavLink to="/" end onClick={handleNavClick}>
            <span>📊</span>
            <span>{t('nav.dashboard')}</span>
          </NavLink>

          {/* Section: المبيعات والعملاء */}
          <div className="sidebar-section-header">المبيعات والعملاء</div>
          {can('crm.customer.view') && (
            <NavLink to="/customers" onClick={handleNavClick}>
              <span>🏥</span>
              <span>{t('nav.customers')}</span>
            </NavLink>
          )}
          {can('catalog.product.view') && (
            <NavLink to="/catalog" onClick={handleNavClick}>
              <span>🔬</span>
              <span>{t('nav.catalog')}</span>
            </NavLink>
          )}
          {can('pricing.pricelist.view') && (
            <NavLink to="/price-lists" onClick={handleNavClick}>
              <span>🏷️</span>
              <span>{t('nav.priceLists')}</span>
            </NavLink>
          )}
          {can('quotations.quotation.view') && (
            <NavLink to="/quotations" onClick={handleNavClick}>
              <span>📑</span>
              <span>{t('nav.quotations')}</span>
            </NavLink>
          )}
          {can('sales_orders.deal.view') && (
            <NavLink to="/deals" onClick={handleNavClick}>
              <span>🤝</span>
              <span>{t('nav.deals')}</span>
            </NavLink>
          )}

          {/* Section: الإمداد وسلاسل التوريد */}
          <div className="sidebar-section-header">سلاسل الإمداد والمخزون</div>
          {can('procurement.order.view') && (
            <NavLink to="/procurement" onClick={handleNavClick}>
              <span>🚢</span>
              <span>{t('nav.procurement')}</span>
            </NavLink>
          )}
          {can('shipments.shipment.view') && (
            <NavLink to="/shipments" onClick={handleNavClick}>
              <span>📦</span>
              <span>{t('nav.shipments')}</span>
            </NavLink>
          )}
          {can('inventory.asset.view') && (
            <NavLink to="/inventory" onClick={handleNavClick}>
              <span>🏢</span>
              <span>{t('nav.inventory')}</span>
            </NavLink>
          )}

          {/* Section: المالية والخدمات الهندسية */}
          <div className="sidebar-section-header">المالية والخدمات الفنية</div>
          {can('accounting.entry.view') && (
            <NavLink to="/accounting" onClick={handleNavClick}>
              <span>💰</span>
              <span>{t('nav.accounting')}</span>
            </NavLink>
          )}
          {can('payments.invoice.view') && (
            <NavLink to="/payments" onClick={handleNavClick}>
              <span>💳</span>
              <span>{t('nav.payments')}</span>
            </NavLink>
          )}
          {can('biomedical.ticket.view') && (
            <NavLink to="/biomedical" onClick={handleNavClick}>
              <span>🛠️</span>
              <span>{t('nav.biomedical')}</span>
            </NavLink>
          )}
          {can('documents.document.view') && (
            <NavLink to="/documents" onClick={handleNavClick}>
              <span>🤖</span>
              <span>{t('nav.documents')}</span>
            </NavLink>
          )}

          {/* Section: إدارة النظام والرقابة */}
          <div className="sidebar-section-header">إدارة النظام والرقابة</div>
          {can('identity.user.view') && (
            <NavLink to="/users" onClick={handleNavClick}>
              <span>👥</span>
              <span>{t('nav.users')}</span>
            </NavLink>
          )}
          {can('audit.event.view') && (
            <NavLink to="/audit" onClick={handleNavClick}>
              <span>🛡️</span>
              <span>{t('nav.audit')}</span>
            </NavLink>
          )}

          {/* Sidebar Footer */}
          <div className="sidebar-footer">
            <button className="sidebar-btn" onClick={logout}>
              <span>🚪</span>
              <span>تسجيل الخروج ({me.email})</span>
            </button>
          </div>
        </aside>

        {/* MAIN CONTENT OUTLET */}
        <main className="main-content fade-in">
          <div className="content-container">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Shell />}>
        <Route index element={<Dashboard />} />
        <Route path="customers" element={<Guard perm="crm.customer.view"><CustomersPage /></Guard>} />
        <Route path="catalog" element={<Guard perm="catalog.product.view"><CatalogPage /></Guard>} />
        <Route path="price-lists" element={<Guard perm="pricing.pricelist.view"><PriceListsPage /></Guard>} />
        <Route path="quotations" element={<Guard perm="quotations.quotation.view"><QuotationsPage /></Guard>} />
        <Route path="deals" element={<Guard perm="sales_orders.deal.view"><DealsPage /></Guard>} />
        <Route path="procurement" element={<Guard perm="procurement.order.view"><ProcurementPage /></Guard>} />
        <Route path="shipments" element={<Guard perm="shipments.shipment.view"><ShipmentsPage /></Guard>} />
        <Route path="inventory" element={<Guard perm="inventory.asset.view"><InventoryPage /></Guard>} />
        <Route path="accounting" element={<Guard perm="accounting.entry.view"><AccountingPage /></Guard>} />
        <Route path="payments" element={<Guard perm="payments.invoice.view"><PaymentsPage /></Guard>} />
        <Route path="biomedical" element={<Guard perm="biomedical.ticket.view"><BiomedicalPage /></Guard>} />
        <Route path="documents" element={<Guard perm="documents.document.view"><DocumentsAIPage /></Guard>} />
        <Route path="users" element={<Guard perm="identity.user.view"><UsersPage /></Guard>} />
        <Route path="audit" element={<Guard perm="audit.event.view"><AuditPage /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
