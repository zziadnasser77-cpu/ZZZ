import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, downloadFile } from '../api'
import { useAuth } from '../auth'

interface DashboardData {
  as_of_date: string
  commercial: {
    open_opportunities_count: number
    open_opportunities_value: string
    active_deals_count: number
    sales_orders_count: number
    sales_by_currency: Array<{ currency: string; total_amount: string; order_count: number }>
  }
  receivables: {
    unpaid_invoices_count: number
    unpaid_total: string
    aging_buckets: {
      current: string
      days_1_30: string
      days_31_60: string
      days_61_90: string
      days_90_plus: string
    }
  }
  inventory: {
    total_assets: number
    in_stock: number
    delivered_to_customer: number
    in_maintenance: number
  }
  logistics: {
    active_shipments_count: number
    active_purchase_orders_count: number
  }
  biomedical: {
    open_tickets_count: number
    critical_tickets_count: number
    warranties_expiring_30d_count: number
  }
  financial_access: boolean
}

interface ReceivablesAgingData {
  as_of_date: string
  summary: {
    current: string
    days_1_30: string
    days_31_60: string
    days_61_90: string
    days_90_plus: string
    total_outstanding: string
  }
  customers: Array<{
    customer_id: string
    customer_number: string
    customer_name_ar: string
    customer_name_en: string
    currency: string
    current: string
    days_1_30: string
    days_31_60: string
    days_61_90: string
    days_90_plus: string
    total_outstanding: string
    invoices_count: number
  }>
}

interface CommercialReportData {
  opportunities_by_stage: Array<{ stage: string; count: number; total_expected_value: string }>
  win_rate_percentage: number
  deals_by_commercial_model: Array<{ commercial_model: string; count: number; total_value: string }>
  deals_by_status: Array<{ status: string; count: number; total_value: string }>
  top_customers: Array<{ customer_number: string; customer_name: string; currency: string; orders_count: number; total_revenue: string }>
  top_models: Array<{ model_code: string; model_name: string; units_sold: number; revenue: string }>
}

interface MaintenanceData {
  total_tickets: number
  resolved_tickets: number
  resolution_rate_percentage: number
  by_type: Array<{ ticket_type: string; count: number }>
  by_priority: Array<{ priority: string; count: number }>
  by_status: Array<{ status: string; count: number }>
  by_engineer: Array<{ engineer_name: string; engineer_email: string; total_assigned: number; resolved: number }>
}

interface WarrantiesData {
  today: string
  counts: {
    expired: number
    expiring_30d: number
    expiring_60d: number
    expiring_90d: number
    active_long_term: number
  }
  warranties: {
    expiring_30d: Array<{
      contract_number: string
      asset_serial: string
      model_code: string
      model_name: string
      customer_name: string
      end_date: string
      days_remaining: number
    }>
    expired: Array<any>
    expiring_60d: Array<any>
    expiring_90d: Array<any>
    active_long_term: Array<any>
  }
}

interface LogisticsData {
  purchase_orders_by_status: Array<{ status: string; count: number; total_value: string }>
  shipments_by_status: Array<{ status: string; count: number }>
  active_shipments: Array<{
    shipment_number: string
    carrier_name: string
    tracking_number: string
    origin: string
    destination: string
    eta: string | null
    status: string
  }>
}

export default function Dashboard() {
  const { me, can } = useAuth()
  const { t } = useTranslation()

  // ضبط إظهار قسم تحليل أعمار الديون والذمم المدينة للعملاء (false = إخفاء، true = إظهار)
  const SHOW_DEBT_AGING_ANALYSIS = false

  const [tab, setTab] = useState<'overview' | 'pipeline' | 'biomedical' | 'warranties' | 'logistics' | 'exports'>('overview')
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [summary, setSummary] = useState<DashboardData | null>(null)
  const [aging, setAging] = useState<ReceivablesAgingData | null>(null)
  const [commercial, setCommercial] = useState<CommercialReportData | null>(null)
  const [maintenance, setMaintenance] = useState<MaintenanceData | null>(null)
  const [warranties, setWarranties] = useState<WarrantiesData | null>(null)
  const [logistics, setLogistics] = useState<LogisticsData | null>(null)

  const loadSummary = async () => {
    try {
      setLoading(true)
      const data = await api<DashboardData>('/reporting/dashboard/')
      setSummary(data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const loadTabData = async (activeTab: string) => {
    try {
      if (SHOW_DEBT_AGING_ANALYSIS && activeTab === 'overview' && !aging && can('reporting.financial.view')) {
        const d = await api<ReceivablesAgingData>('/reporting/receivables-aging/')
        setAging(d)
      } else if (activeTab === 'pipeline' && !commercial && can('reporting.commercial.view')) {
        const d = await api<CommercialReportData>('/reporting/commercial/')
        setCommercial(d)
      } else if (activeTab === 'biomedical' && !maintenance && can('reporting.biomedical.view')) {
        const d = await api<MaintenanceData>('/reporting/maintenance-performance/')
        setMaintenance(d)
      } else if (activeTab === 'warranties' && !warranties && can('reporting.biomedical.view')) {
        const d = await api<WarrantiesData>('/reporting/warranties-forecast/')
        setWarranties(d)
      } else if (activeTab === 'logistics' && !logistics && can('reporting.inventory.view')) {
        const d = await api<LogisticsData>('/reporting/procurement-shipments/')
        setLogistics(d)
      }
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    loadSummary()
  }, [])

  useEffect(() => {
    loadTabData(tab)
  }, [tab])

  const downloadCSV = async (endpoint: string, filename: string) => {
    try {
      setDownloading(filename)
      await downloadFile(endpoint.replace(/^\/api\/v1/, ''), filename)
    } catch (err) {
      console.error('Export download error', err)
      alert(t('common.error'))
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-header-title">
          <span className="page-header-icon">📊</span>
          <div>
            <h1>{t('dashboard.welcome')}, {me?.full_name || me?.email}</h1>
            <p>{t('dashboard.title')} • {summary?.as_of_date || new Date().toISOString().split('T')[0]}</p>
          </div>
        </div>
        <div className="page-header-actions">
          <button className="btn secondary" onClick={loadSummary} disabled={loading}>
            {loading ? t('common.loading') : `↻ ${t('dashboard.refresh')}`}
          </button>
        </div>
      </div>

      {/* KPI METRICS GRID */}
      {summary && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1rem',
          marginBottom: '1.5rem'
        }}>
          {/* Commercial & Revenue */}
          <div className="card" style={{ borderInlineStart: '4px solid #2b6cb0' }}>
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem', fontWeight: 600 }}>{t('dashboard.kpi.revenue')}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0.35rem 0', color: '#1a365d' }}>
              {summary.commercial.sales_by_currency.length > 0 ? (
                summary.commercial.sales_by_currency.map(c => `${Number(c.total_amount).toLocaleString()} ${c.currency}`).join(' | ')
              ) : '$0.00'}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#4a5568' }}>
              {summary.commercial.sales_orders_count} {t('dashboard.kpi.deals')}
            </div>
          </div>

          {/* Sales Pipeline */}
          <div className="card" style={{ borderInlineStart: '4px solid #319795' }}>
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem', fontWeight: 600 }}>{t('dashboard.kpi.pipeline')}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0.35rem 0', color: '#234e52' }}>
              ${Number(summary.commercial.open_opportunities_value).toLocaleString()}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#4a5568' }}>
              {summary.commercial.open_opportunities_count} فرصة نشطة
            </div>
          </div>

          {/* Receivables & Debt */}
          <div className="card" style={{ borderInlineStart: '4px solid #dd6b20' }}>
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem', fontWeight: 600 }}>{t('dashboard.kpi.receivables')}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0.35rem 0', color: '#7b341e' }}>
              ${Number(summary.receivables.unpaid_total).toLocaleString()}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#c53030', fontWeight: 600 }}>
              {summary.receivables.unpaid_invoices_count} فاتورة غير محصلة
            </div>
          </div>

          {/* Medical Assets */}
          <div className="card" style={{ borderInlineStart: '4px solid #805ad5' }}>
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem', fontWeight: 600 }}>{t('dashboard.kpi.inventory')}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0.35rem 0', color: '#44337a' }}>
              {summary.inventory.total_assets} جهاز طبي
            </div>
            <div style={{ fontSize: '0.75rem', color: '#4a5568' }}>
              {summary.inventory.in_stock} بالمستودع • {summary.inventory.delivered_to_customer} مسلّم
            </div>
          </div>

          {/* Biomedical Maintenance */}
          <div className="card" style={{ borderInlineStart: '4px solid #e53e3e' }}>
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem', fontWeight: 600 }}>{t('dashboard.kpi.tickets')}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0.35rem 0', color: '#9b2c2c' }}>
              {summary.biomedical.open_tickets_count} تذكرة
            </div>
            <div style={{ fontSize: '0.75rem', color: summary.biomedical.critical_tickets_count > 0 ? '#e53e3e' : '#4a5568', fontWeight: 600 }}>
              {summary.biomedical.critical_tickets_count > 0 ? `⚠️ ${summary.biomedical.critical_tickets_count} حرجة وتوقف جهاز` : 'لا توجد أعطال حرجة'}
            </div>
          </div>

          {/* Warranties 30d */}
          <div className="card" style={{ borderInlineStart: '4px solid #d69e2e' }}>
            <div style={{ color: 'var(--muted)', fontSize: '0.8rem', fontWeight: 600 }}>{t('dashboard.kpi.warranties')}</div>
            <div style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0.35rem 0', color: '#744210' }}>
              {summary.biomedical.warranties_expiring_30d_count}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#744210' }}>
              {summary.logistics.active_shipments_count} شحنة دولية قيد العبور
            </div>
          </div>
        </div>
      )}

      {/* UNIFIED TABS NAVIGATION */}
      <div className="tabs">
        <button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>
          📈 {t('dashboard.tabs.overview')}
        </button>
        {can('reporting.commercial.view') && (
          <button className={tab === 'pipeline' ? 'active' : ''} onClick={() => setTab('pipeline')}>
            💼 {t('dashboard.tabs.pipeline')}
          </button>
        )}
        {can('reporting.biomedical.view') && (
          <button className={tab === 'biomedical' ? 'active' : ''} onClick={() => setTab('biomedical')}>
            🔧 {t('dashboard.tabs.biomedical')}
          </button>
        )}
        {can('reporting.biomedical.view') && (
          <button className={tab === 'warranties' ? 'active' : ''} onClick={() => setTab('warranties')}>
            🛡️ {t('dashboard.tabs.warranties')}
          </button>
        )}
        {can('reporting.inventory.view') && (
          <button className={tab === 'logistics' ? 'active' : ''} onClick={() => setTab('logistics')}>
            🚚 {t('dashboard.tabs.logistics')}
          </button>
        )}
        <button className={tab === 'exports' ? 'active' : ''} onClick={() => setTab('exports')}>
          📥 {t('dashboard.tabs.exports')}
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {tab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* قسم تحليل أعمار الديون والذمم المدينة للعملاء (مخفي مؤقتاً بناءً على الطلب - يمكن إعادته بتغيير SHOW_DEBT_AGING_ANALYSIS إلى true) */}
          {SHOW_DEBT_AGING_ANALYSIS && (
            <>
              {summary && (
                <div className="card">
                  <h3 style={{ margin: '0 0 1rem 0' }}>{t('dashboard.aging.title')}</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                    <div style={{ padding: '0.75rem', background: '#ebf8ff', borderRadius: '8px', border: '1px solid #bee3f8' }}>
                      <div style={{ fontSize: '0.75rem', color: '#2b6cb0' }}>{t('dashboard.aging.current')}</div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>${Number(summary.receivables.aging_buckets.current).toLocaleString()}</div>
                    </div>
                    <div style={{ padding: '0.75rem', background: '#fefcbf', borderRadius: '8px', border: '1px solid #faf089' }}>
                      <div style={{ fontSize: '0.75rem', color: '#975a16' }}>{t('dashboard.aging.days1_30')}</div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>${Number(summary.receivables.aging_buckets.days_1_30).toLocaleString()}</div>
                    </div>
                    <div style={{ padding: '0.75rem', background: '#feebc8', borderRadius: '8px', border: '1px solid #fbd38d' }}>
                      <div style={{ fontSize: '0.75rem', color: '#c05621' }}>{t('dashboard.aging.days31_60')}</div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>${Number(summary.receivables.aging_buckets.days_31_60).toLocaleString()}</div>
                    </div>
                    <div style={{ padding: '0.75rem', background: '#fed7d7', borderRadius: '8px', border: '1px solid #feb2b2' }}>
                      <div style={{ fontSize: '0.75rem', color: '#c53030' }}>{t('dashboard.aging.days61_90')}</div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>${Number(summary.receivables.aging_buckets.days_61_90).toLocaleString()}</div>
                    </div>
                    <div style={{ padding: '0.75rem', background: '#fed7d7', borderRadius: '8px', border: '2px solid #e53e3e' }}>
                      <div style={{ fontSize: '0.75rem', color: '#9b2c2c', fontWeight: 700 }}>{t('dashboard.aging.days90_plus')}</div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#9b2c2c' }}>${Number(summary.receivables.aging_buckets.days_90_plus).toLocaleString()}</div>
                    </div>
                  </div>
                </div>
              )}

              {aging && aging.customers.length > 0 && (
                <div className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <h4 style={{ margin: 0 }}>تفصيل ديون وفواتير العملاء</h4>
                    {can('reporting.financial.export') && (
                      <button
                        className="btn secondary"
                        style={{ fontSize: '0.8rem' }}
                        onClick={() => downloadCSV('/reporting/export/receivables/', 'receivables_aging.csv')}
                      >
                        📥 تصدير كشف الديون (CSV)
                      </button>
                    )}
                  </div>
                  <div style={{ overflowX: 'auto' }}>
                    <table>
                      <thead>
                        <tr>
                          <th>{t('dashboard.aging.customer')}</th>
                          <th>{t('dashboard.aging.current')}</th>
                          <th>{t('dashboard.aging.days1_30')}</th>
                          <th>{t('dashboard.aging.days31_60')}</th>
                          <th>{t('dashboard.aging.days61_90')}</th>
                          <th>{t('dashboard.aging.days90_plus')}</th>
                          <th>{t('dashboard.aging.total')}</th>
                          <th>{t('dashboard.aging.invoicesCount')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {aging.customers.map(c => (
                          <tr key={c.customer_id}>
                            <td>
                              <strong>{c.customer_name_ar}</strong>
                              <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{c.customer_number}</div>
                            </td>
                            <td>${Number(c.current).toLocaleString()}</td>
                            <td>${Number(c.days_1_30).toLocaleString()}</td>
                            <td>${Number(c.days_31_60).toLocaleString()}</td>
                            <td>${Number(c.days_61_90).toLocaleString()}</td>
                            <td style={{ color: Number(c.days_90_plus) > 0 ? '#c53030' : 'inherit', fontWeight: Number(c.days_90_plus) > 0 ? 700 : 'normal' }}>
                              ${Number(c.days_90_plus).toLocaleString()}
                            </td>
                            <td style={{ fontWeight: 700 }}>${Number(c.total_outstanding).toLocaleString()} {c.currency}</td>
                            <td>{c.invoices_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}

          {/* لوحة العمليات التشغيلية الذكية (تظهر كبديل أنيق عند إخفاء قسم تحليل الديون) */}
          {!SHOW_DEBT_AGING_ANALYSIS && (
            <div className="card" style={{ padding: '1.5rem', background: '#ffffff', borderRadius: '14px', border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid #f1f5f9', paddingBottom: '0.85rem' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#0f172a' }}>🚀 مركز العمليات والموجز التشغيلي الطبي</h3>
                  <p style={{ margin: '0.25rem 0 0', fontSize: '0.82rem', color: '#64748b' }}>إدارة سريعة للمنظومة، الكتالوج الطبي، عروض الأسعار، والأصول الميدانية</p>
                </div>
                <span style={{ fontSize: '0.8rem', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', padding: '0.35rem 0.75rem', borderRadius: '20px', fontWeight: 600 }}>
                  النظام جاهز ومستقر
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
                <a href="/catalog" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div style={{ padding: '1.1rem', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '12px', transition: 'all 0.2s', cursor: 'pointer' }}>
                    <div style={{ fontSize: '1.6rem', marginBottom: '0.4rem' }}>🩺</div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#166534' }}>الكتالوج الطبي الذكي</div>
                    <div style={{ fontSize: '0.8rem', color: '#15803d', marginTop: '0.35rem' }}>استعراض الأصناف والموديلات المستخرجة من الكتالوجات بصورها ومواصفاتها</div>
                  </div>
                </a>

                <a href="/quotations" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div style={{ padding: '1.1rem', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '12px', transition: 'all 0.2s', cursor: 'pointer' }}>
                    <div style={{ fontSize: '1.6rem', marginBottom: '0.4rem' }}>📝</div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#1e40af' }}>عروض الأسعار والصفقات</div>
                    <div style={{ fontSize: '0.8rem', color: '#2563eb', marginTop: '0.35rem' }}>إصدار وتتبع عروض الأسعار للعملاء والجهات الطبية بالعملات المتعددة</div>
                  </div>
                </a>

                <a href="/biomedical" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div style={{ padding: '1.1rem', background: '#fdf4ff', border: '1px solid #f5d0fe', borderRadius: '12px', transition: 'all 0.2s', cursor: 'pointer' }}>
                    <div style={{ fontSize: '1.6rem', marginBottom: '0.4rem' }}>🛠️</div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#86198f' }}>الهندسة الطبية والصيانة</div>
                    <div style={{ fontSize: '0.8rem', color: '#a21caf', marginTop: '0.35rem' }}>بروتوكولات التركيب، الضمانات، وتذاكر الصيانة الدورية للأجهزة</div>
                  </div>
                </a>

                <a href="/inventory" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div style={{ padding: '1.1rem', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '12px', transition: 'all 0.2s', cursor: 'pointer' }}>
                    <div style={{ fontSize: '1.6rem', marginBottom: '0.4rem' }}>📦</div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#92400e' }}>المستودعات وحركات الأصول</div>
                    <div style={{ fontSize: '0.8rem', color: '#b45309', marginTop: '0.35rem' }}>تتبع الأرقام التسلسلية والحيازة والعهد لدى المستشفيات والعيادات</div>
                  </div>
                </a>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: COMMERCIAL PIPELINE */}
      {tab === 'pipeline' && commercial && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            <div className="card">
              <h4 style={{ margin: '0 0 0.75rem 0' }}>معدل إغلاق الفرص (Win Rate)</h4>
              <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#2b6cb0' }}>
                {commercial.win_rate_percentage}%
              </div>
              <p style={{ margin: '0.25rem 0 0 0', color: 'var(--muted)', fontSize: '0.85rem' }}>
                نسبة الفوز بالفرص مقارنة بإجمالي الفرص المغلقة
              </p>
            </div>

            <div className="card">
              <h4 style={{ margin: '0 0 0.75rem 0' }}>الصفقات حسب النموذج التجاري</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {commercial.deals_by_commercial_model.map(d => (
                  <div key={d.commercial_model} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.4rem', background: '#f7fafc', borderRadius: '6px' }}>
                    <span>{d.commercial_model}</span>
                    <strong>${Number(d.total_value).toLocaleString()} ({d.count})</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
            <div className="card">
              <h4 style={{ margin: '0 0 0.75rem 0' }}>أعلى العملاء إيراداً</h4>
              <table>
                <thead>
                  <tr>
                    <th>العميل</th>
                    <th>الطلبات</th>
                    <th>الإجمالي</th>
                  </tr>
                </thead>
                <tbody>
                  {commercial.top_customers.map(c => (
                    <tr key={c.customer_number}>
                      <td>{c.customer_name}</td>
                      <td>{c.orders_count}</td>
                      <td><strong>${Number(c.total_revenue).toLocaleString()} {c.currency}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="card">
              <h4 style={{ margin: '0 0 0.75rem 0' }}>الموديلات الطبية الأكثر مبيعاً</h4>
              <table>
                <thead>
                  <tr>
                    <th>الموديل</th>
                    <th>الوحدات المباعة</th>
                    <th>الإيراد</th>
                  </tr>
                </thead>
                <tbody>
                  {commercial.top_models.map(m => (
                    <tr key={m.model_code}>
                      <td><strong>{m.model_code}</strong> - {m.model_name}</td>
                      <td>{m.units_sold}</td>
                      <td>${Number(m.revenue).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: BIOMEDICAL & MAINTENANCE */}
      {tab === 'biomedical' && maintenance && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
            <div className="card">
              <h4 style={{ margin: '0 0 0.5rem 0' }}>نسبة حل التذاكر</h4>
              <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#38a169' }}>
                {maintenance.resolution_rate_percentage}%
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
                {maintenance.resolved_tickets} تم إصلاحه من أصل {maintenance.total_tickets} تذكرة
              </div>
            </div>

            <div className="card">
              <h4 style={{ margin: '0 0 0.5rem 0' }}>التذاكر حسب نوع الصيانة</h4>
              {maintenance.by_type.map(t => (
                <div key={t.ticket_type} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
                  <span>{t.ticket_type}</span>
                  <span className="badge ok">{t.count}</span>
                </div>
              ))}
            </div>

            <div className="card">
              <h4 style={{ margin: '0 0 0.5rem 0' }}>التذاكر حسب الأولوية</h4>
              {maintenance.by_priority.map(p => (
                <div key={p.priority} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
                  <span>{p.priority}</span>
                  <span className={`badge ${p.priority === 'CRITICAL' ? 'off' : 'ok'}`}>{p.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h4 style={{ margin: '0 0 0.75rem 0' }}>أداء المهندسين الطبيين</h4>
            <table>
              <thead>
                <tr>
                  <th>المهندس الطبي</th>
                  <th>البريد الإلكتروني</th>
                  <th>إجمالي التذاكر المسندة</th>
                  <th>التذاكر المنجزة</th>
                </tr>
              </thead>
              <tbody>
                {maintenance.by_engineer.map(e => (
                  <tr key={e.engineer_email}>
                    <td><strong>{e.engineer_name}</strong></td>
                    <td>{e.engineer_email}</td>
                    <td>{e.total_assigned}</td>
                    <td><span className="badge ok">{e.resolved}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: WARRANTIES FORECAST */}
      {tab === 'warranties' && warranties && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
            <div className="card" style={{ borderInlineStart: '4px solid #e53e3e' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>منتهية الصلاحية</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#c53030' }}>{warranties.counts.expired}</div>
            </div>
            <div className="card" style={{ borderInlineStart: '4px solid #dd6b20' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>تنتهي خلال 30 يوم</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#dd6b20' }}>{warranties.counts.expiring_30d}</div>
            </div>
            <div className="card" style={{ borderInlineStart: '4px solid #d69e2e' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>تنتهي خلال 60 يوم</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#d69e2e' }}>{warranties.counts.expiring_60d}</div>
            </div>
            <div className="card" style={{ borderInlineStart: '4px solid #38a169' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>نشطة طويلة الأجل</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#38a169' }}>{warranties.counts.active_long_term}</div>
            </div>
          </div>

          <div className="card">
            <h4 style={{ margin: '0 0 0.75rem 0' }}>الأجهزة الطبية التي ينتهي ضمانها خلال 30 يوماً</h4>
            {warranties.warranties.expiring_30d.length === 0 ? (
              <p style={{ color: 'var(--muted)' }}>لا توجد أجهزة قريبة من انتهاء الضمان حالياً.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>عقد الضمان</th>
                    <th>الرقم التسلسلي S/N</th>
                    <th>الموديل</th>
                    <th>العميل</th>
                    <th>تاريخ الانتهاء</th>
                    <th>الأيام المتبقية</th>
                  </tr>
                </thead>
                <tbody>
                  {warranties.warranties.expiring_30d.map(w => (
                    <tr key={w.contract_number}>
                      <td><strong>{w.contract_number}</strong></td>
                      <td>{w.asset_serial}</td>
                      <td>{w.model_code} - {w.model_name}</td>
                      <td>{w.customer_name}</td>
                      <td>{w.end_date}</td>
                      <td><span className="badge off">{w.days_remaining} يوم</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 5: LOGISTICS & PROCUREMENT */}
      {tab === 'logistics' && logistics && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            <div className="card">
              <h4 style={{ margin: '0 0 0.75rem 0' }}>طلبات التوريد من المصنع الصيني</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {logistics.purchase_orders_by_status.map(p => (
                  <div key={p.status} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.4rem', background: '#f7fafc', borderRadius: '6px' }}>
                    <span>{p.status}</span>
                    <strong>${Number(p.total_value).toLocaleString()} ({p.count})</strong>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <h4 style={{ margin: '0 0 0.75rem 0' }}>حالات الشحنات الدولية والمحلية</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {logistics.shipments_by_status.map(s => (
                  <div key={s.status} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.4rem', background: '#f7fafc', borderRadius: '6px' }}>
                    <span>{s.status}</span>
                    <span className="badge ok">{s.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <h4 style={{ margin: '0 0 0.75rem 0' }}>الشحنات النشطة قيد العبور والتتبع</h4>
            {logistics.active_shipments.length === 0 ? (
              <p style={{ color: 'var(--muted)' }}>لا توجد شحنات في العبور حالياً.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>رقم الشحنة</th>
                    <th>الناقل والتتبع</th>
                    <th>ميناء الانطلاق</th>
                    <th>ميناء الوصول</th>
                    <th>الوصول المتوقع ETA</th>
                    <th>الحالة</th>
                  </tr>
                </thead>
                <tbody>
                  {logistics.active_shipments.map(s => (
                    <tr key={s.shipment_number}>
                      <td><strong>{s.shipment_number}</strong></td>
                      <td>{s.carrier_name} ({s.tracking_number})</td>
                      <td>{s.origin}</td>
                      <td>{s.destination}</td>
                      <td>{s.eta || '—'}</td>
                      <td><span className="badge ok">{s.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* TAB 6: DATA EXPORTS (CSV) */}
      {tab === 'exports' && (
        <div className="card">
          <h3 style={{ margin: '0 0 1rem 0' }}>{t('dashboard.exports.title')}</h3>
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
            تصدير تقارير وبيانات النظام بصيغة CSV القياسية مع تطبيق قيود وسياق الصلاحيات الأمنية.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
            {/* Receivables Export */}
            {can('reporting.financial.export') && (
              <div style={{ border: '1px solid var(--border)', borderRadius: '10px', padding: '1.25rem', background: '#fcfdfd' }}>
                <h4 style={{ margin: '0 0 0.5rem 0' }}>💰 {t('dashboard.exports.receivables')}</h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '1rem' }}>
                  كشف أعمار الديون الكامل لجميع العملاء مقسمة حسب الفئات الزمنية مع الفواتير غير المحصلة.
                </p>
                <button
                  className="btn"
                  disabled={downloading !== null}
                  onClick={() => downloadCSV('/reporting/export/receivables/', 'receivables_aging.csv')}
                >
                  {downloading === 'receivables_aging.csv' ? t('dashboard.exports.downloading') : 'تحميل CSV'}
                </button>
              </div>
            )}

            {/* Inventory Assets Export */}
            {can('reporting.inventory.export') && (
              <div style={{ border: '1px solid var(--border)', borderRadius: '10px', padding: '1.25rem', background: '#fcfdfd' }}>
                <h4 style={{ margin: '0 0 0.5rem 0' }}>🔬 {t('dashboard.exports.inventory')}</h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '1rem' }}>
                  جرد الأجهزة الطبية والأرقام التسلسلية مع فصل الملكية القانونية عن الحيازة الفعلية والموقع.
                </p>
                <button
                  className="btn"
                  disabled={downloading !== null}
                  onClick={() => downloadCSV('/reporting/export/inventory-assets/', 'inventory_assets.csv')}
                >
                  {downloading === 'inventory_assets.csv' ? t('dashboard.exports.downloading') : 'تحميل CSV'}
                </button>
              </div>
            )}

            {/* Trial Balance Export */}
            {can('reporting.financial.export') && (
              <div style={{ border: '1px solid var(--border)', borderRadius: '10px', padding: '1.25rem', background: '#fcfdfd' }}>
                <h4 style={{ margin: '0 0 0.5rem 0' }}>📊 {t('dashboard.exports.trialBalance')}</h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '1rem' }}>
                  ميزان المراجعة المحاسبي العام الموزون لجميع الحسابات من واقع دفتر الأستاذ العام المتوازن.
                </p>
                <button
                  className="btn"
                  disabled={downloading !== null}
                  onClick={() => downloadCSV('/reporting/export/trial-balance/', 'trial_balance.csv')}
                >
                  {downloading === 'trial_balance.csv' ? t('dashboard.exports.downloading') : 'تحميل CSV'}
                </button>
              </div>
            )}

            {/* Audit Log Export */}
            {can('audit.event.export') && (
              <div style={{ border: '1px solid var(--border)', borderRadius: '10px', padding: '1.25rem', background: '#fcfdfd' }}>
                <h4 style={{ margin: '0 0 0.5rem 0' }}>🛡️ {t('dashboard.exports.auditLog')}</h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--muted)', marginBottom: '1rem' }}>
                  سجل التدقيق الرقابي غير القابل للتعديل لجميع العمليات الحساسة ومحاولات الوصول والأنشطة.
                </p>
                <button
                  className="btn"
                  disabled={downloading !== null}
                  onClick={() => downloadCSV('/reporting/export/audit-log/', 'audit_log.csv')}
                >
                  {downloading === 'audit_log.csv' ? t('dashboard.exports.downloading') : 'تحميل CSV'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
