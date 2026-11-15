import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'
import { api, ApiError, type Page } from '../api'
import { useAuth } from '../auth'

interface QuotationLine {
  id: string
  model_name: string
  sku: string
  quantity: number
  unit_price: string
  total_price: string
  warranty_months: number
  description?: string
  display_image?: string | null
  specifications?: Record<string, any>
}

interface QuotationVersion {
  id: string
  version_number: number
  status: string
  total_amount: string
  subtotal: string
  discount_pct: string
  discount_amount?: string
  tax_amount?: string
  payment_terms?: string
  delivery_terms?: string
  notes?: string
  requires_approval: boolean
  approval_reason?: string
  lines: QuotationLine[]
}

interface Quotation {
  id: string
  quotation_number: string
  title: string
  customer: string
  customer_name: string
  commercial_model: string
  currency: string
  status: string
  current_version_number: number
  latest_version?: QuotationVersion
  created_at: string
}

interface CustomerOption {
  id: string
  customer_number: string
  legal_name_ar: string
  trade_name?: string
  phone?: string
  address?: string
}

interface ModelOption {
  id: string
  model_code: string
  model_name: string
  sku: string
  product_name_ar: string
  display_image?: string
  specifications?: Record<string, any>
  approved_price?: {
    base_price: string
    currency: string
  }
}

export default function QuotationsPage() {
  const { t } = useTranslation()
  const { can } = useAuth()
  const [selectedQuote, setSelectedQuote] = useState<Quotation | null>(null)
  const qc = useQueryClient()
  const [actionErr, setActionErr] = useState('')
  const location = useLocation()
  const [prefillNotice, setPrefillNotice] = useState<string | null>(null)

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showPrintModal, setShowPrintModal] = useState(false)

  // Lock body scroll when any modal is open
  useEffect(() => {
    if (showCreateModal || showPrintModal) {
      const orig = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = orig
      }
    }
  }, [showCreateModal, showPrintModal])

  // Creation form state
  const [quoteForm, setQuoteForm] = useState({
    customer: '',
    title: '',
    commercial_model: 'DIRECT_SALE',
    currency: 'USD',
    payment_terms: '100% الدفع مقدماً بحوالة بنكية أو نقداً',
    delivery_terms: 'شامل التوريد والتركيب والتشغيل والضمان في موقع المستشفى',
    notes: 'العرض ساري لمدة 30 يوماً من تاريخ الإصدار',
    lines: [
      {
        model: '',
        description: '',
        quantity: 1,
        unit_price: '0.00',
        discount_pct: '0.00',
        warranty_months: 24,
      },
    ],
  })

  // Detect prefill coming from Catalog device selection
  useEffect(() => {
    if (location.state && (location.state as any).prefill) {
      const p = (location.state as any).prefill
      setQuoteForm((prev) => ({
        ...prev,
        title: `عرض توريد وتجهيز جهاز ${p.modelName || p.sku}`,
        currency: p.currency || prev.currency || 'USD',
        lines: [
          {
            model: p.modelId,
            description: p.description || `${p.modelName} (${p.sku})`,
            quantity: 1,
            unit_price: p.unitPrice || '0.00',
            discount_pct: '0.00',
            warranty_months: p.warrantyMonths || 24,
          },
        ],
      }))
      setPrefillNotice(`✨ تم جلب الجهاز المحدد تلقائياً من الكتالوج: ${p.productName || ''} (${p.modelName}) — السعر المعتمد: ${Number(p.unitPrice).toLocaleString()} ${p.currency || 'USD'}`)
      setShowCreateModal(true)
      window.history.replaceState({}, document.title)
    }
  }, [location.state])

  const { data, isLoading } = useQuery({
    queryKey: ['quotations'],
    queryFn: () => api<Page<Quotation>>('/quotations/'),
  })

  const customersQuery = useQuery({
    queryKey: ['customers-list'],
    queryFn: () => api<Page<CustomerOption>>('/customers/'),
  })

  const modelsQuery = useQuery({
    queryKey: ['models-for-quotes'],
    queryFn: () => api<Page<ModelOption>>('/models/'),
  })

  // Auto-select customer if not selected and list loaded
  useEffect(() => {
    if (!quoteForm.customer && customersQuery.data?.results && customersQuery.data.results.length > 0) {
      setQuoteForm((prev) => ({
        ...prev,
        customer: prev.customer || customersQuery.data.results[0].id,
      }))
    }
  }, [customersQuery.data, quoteForm.customer])

  const calculatedTotal = quoteForm.lines.reduce((acc, l) => {
    const qty = Number(l.quantity) || 0
    const up = Number(l.unit_price) || 0
    const disc = Number(l.discount_pct) || 0
    const lineBase = qty * up
    return acc + (lineBase - (lineBase * disc) / 100)
  }, 0)

  // Auto-select latest quotation if none selected
  useEffect(() => {
    if (!selectedQuote && data?.results && data.results.length > 0) {
      setSelectedQuote(data.results[0])
    }
  }, [data, selectedQuote])

  const sendMutation = useMutation({
    mutationFn: (id: string) => api(`/quotations/${id}/send/`, { method: 'POST' }),
    onSuccess: (updated: any) => {
      qc.invalidateQueries({ queryKey: ['quotations'] })
      if (updated && updated.id) setSelectedQuote(updated)
    },
    onError: (e) => setActionErr(e instanceof ApiError ? e.message : t('common.error')),
  })

  const acceptMutation = useMutation({
    mutationFn: (id: string) => api(`/quotations/${id}/accept/`, { method: 'POST' }),
    onSuccess: (updated: any) => {
      qc.invalidateQueries({ queryKey: ['quotations'] })
      if (updated && updated.id) setSelectedQuote(updated)
    },
    onError: (e) => setActionErr(e instanceof ApiError ? e.message : t('common.error')),
  })

  const convertMutation = useMutation({
    mutationFn: (id: string) => api('/deals/from-quotation/', { method: 'POST', json: { quotation_id: id } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['quotations'] })
      qc.invalidateQueries({ queryKey: ['deals'] })
      alert('تم تحويل عرض السعر إلى صفقة وأمر بيع معتمد بنجاح!')
    },
    onError: (e) => setActionErr(e instanceof ApiError ? e.message : t('common.error')),
  })

  const handleModelSelect = (index: number, modelId: string) => {
    const selectedModel = modelsQuery.data?.results.find((m) => m.id === modelId)
    const newLines = [...quoteForm.lines]
    newLines[index].model = modelId
    if (selectedModel) {
      newLines[index].description = `${selectedModel.product_name_ar} - ${selectedModel.model_name}`
      if (selectedModel.approved_price) {
        newLines[index].unit_price = selectedModel.approved_price.base_price
      }
    }
    setQuoteForm({ ...quoteForm, lines: newLines })
  }

  const handleAddLine = () => {
    setQuoteForm({
      ...quoteForm,
      lines: [
        ...quoteForm.lines,
        {
          model: '',
          description: '',
          quantity: 1,
          unit_price: '0.00',
          discount_pct: '0.00',
          warranty_months: 24,
        },
      ],
    })
  }

  const handleRemoveLine = (index: number) => {
    if (quoteForm.lines.length <= 1) return
    const newLines = quoteForm.lines.filter((_, i) => i !== index)
    setQuoteForm({ ...quoteForm, lines: newLines })
  }

  const handleCreateQuotation = async () => {
    if (!quoteForm.customer || !quoteForm.title) {
      alert('يرجى اختيار العميل وتحديد عنوان عرض السعر')
      return
    }
    const validLines = quoteForm.lines.filter((l) => !!l.model)
    if (validLines.length === 0) {
      alert('يرجى اختيار جهاز واحد على الأقل في بنود العرض')
      return
    }

    try {
      const res = await api<Quotation>('/quotations/', {
        method: 'POST',
        json: {
          ...quoteForm,
          lines: validLines,
        },
      })
      alert(`تم إنشاء عرض السعر بنجاح برقم: ${res.quotation_number}`)
      setShowCreateModal(false)
      setPrefillNotice(null)
      qc.invalidateQueries({ queryKey: ['quotations'] })
      setSelectedQuote(res)
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  return (
    <>
      <div className="bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0 }}>{t('quotations.title')}</h1>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--muted)', fontSize: '0.85rem' }}>
            عروض الأسعار الطبية المعتمدة للعملاء والمستشفيات مع المواصفات والأسعار
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {can('quotations.quotation.create') && (
            <button className="btn" onClick={() => setShowCreateModal(true)}>
              + إنشاء عرض سعر رسمي
            </button>
          )}
        </div>
      </div>

      {actionErr && <div className="error" role="alert" style={{ marginBlockEnd: '1rem' }}>{actionErr}</div>}

      {isLoading ? (
        t('common.loading')
      ) : (
        <div className={`split-layout ${selectedQuote ? 'active' : ''}`}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('quotations.number')}</th>
                  <th>{t('quotations.customer')}</th>
                  <th>{t('quotations.model')}</th>
                  <th>{t('quotations.total')}</th>
                  <th>{t('quotations.version')}</th>
                  <th>{t('quotations.status')}</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((q) => (
                  <tr
                    key={q.id}
                    onClick={() => { setSelectedQuote(q); setActionErr('') }}
                    style={{
                      cursor: 'pointer',
                      background: selectedQuote?.id === q.id ? 'var(--bg-muted, #e0f2fe)' : undefined,
                      borderRight: selectedQuote?.id === q.id ? '4px solid var(--primary, #0284c7)' : undefined,
                    }}
                  >
                    <td><strong>{q.quotation_number}</strong></td>
                    <td>
                      <div style={{ fontWeight: 700, color: '#0f172a' }}>{q.customer_name}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.15rem' }}>{q.title}</div>
                      {q.latest_version?.lines && q.latest_version.lines.length > 0 && (
                        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginTop: '0.35rem' }}>
                          {q.latest_version.lines.map((line, lIdx) => (
                            <span
                              key={lIdx}
                              className="badge"
                              style={{
                                fontSize: '0.75rem',
                                background: '#e0f2fe',
                                color: '#0369a1',
                                border: '1px solid #bae6fd',
                                fontWeight: 600,
                              }}
                            >
                              🔬 {line.model_name || line.sku} {line.quantity > 1 ? `(x${line.quantity})` : ''}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td><span className="badge">{t(`commercialModels.${q.commercial_model}`)}</span></td>
                    <td>
                      <strong style={{ color: '#0369a1', fontSize: '0.95rem' }}>
                        {q.latest_version?.total_amount ? Number(q.latest_version.total_amount).toLocaleString() : '-'} {q.currency}
                      </strong>
                    </td>
                    <td>v{q.current_version_number}</td>
                    <td>
                      <span className={`badge ${q.status === 'ACCEPTED' ? 'ok' : q.status === 'APPROVED' ? 'ok' : q.status === 'PENDING_APPROVAL' ? 'warn' : 'off'}`}>
                        {t(`quotations.statuses.${q.status}`)}
                      </span>
                    </td>
                  </tr>
                ))}
                {data?.results.length === 0 && (
                  <tr><td colSpan={6}>{t('common.empty')} — يمكنك النقر على (+ إنشاء عرض سعر رسمي) أعلاه</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {selectedQuote && (
            <div className="card" style={{ borderTop: '3px solid #0284c7' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                <div>
                  <h3 style={{ margin: 0, color: '#0f172a' }}>{selectedQuote.quotation_number} — {selectedQuote.title}</h3>
                  <div style={{ fontSize: '0.85rem', color: 'var(--muted)', marginTop: '0.2rem' }}>
                    العميل: <strong>{selectedQuote.customer_name}</strong> | العملة: {selectedQuote.currency}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    className="btn secondary"
                    style={{ fontSize: '0.8rem', background: '#f8fafc', border: '1px solid #cbd5e1' }}
                    onClick={() => setShowPrintModal(true)}
                  >
                    🖨️ طباعة ومعاينة رسمية
                  </button>
                  <button className="btn secondary" style={{ fontSize: '0.8rem' }} onClick={() => setSelectedQuote(null)}>
                    ✖ {t('common.cancel')}
                  </button>
                </div>
              </div>

              <div style={{ marginBlock: '0.8rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {can('quotations.quotation.edit') && selectedQuote.status !== 'SENT' && selectedQuote.status !== 'ACCEPTED' && (
                  <button className="btn" onClick={() => sendMutation.mutate(selectedQuote.id)} disabled={sendMutation.isPending}>
                    ✉️ {t('quotations.send')} للعميل
                  </button>
                )}
                {can('quotations.quotation.edit') && selectedQuote.status === 'SENT' && (
                  <button className="btn ok" onClick={() => acceptMutation.mutate(selectedQuote.id)} disabled={acceptMutation.isPending}>
                    ✓ {t('quotations.accept')} العرض
                  </button>
                )}
                {can('sales_orders.deal.create') && (selectedQuote.status === 'ACCEPTED' || selectedQuote.status === 'APPROVED') && (
                  <button className="btn ok" onClick={() => convertMutation.mutate(selectedQuote.id)} disabled={convertMutation.isPending}>
                    ⚡ {t('quotations.convertToDeal')} وأمر بيع
                  </button>
                )}
              </div>

              {selectedQuote.latest_version?.requires_approval && (
                <div className="error" style={{ fontSize: '0.85rem', margin: '0.5rem 0' }}>
                  ⚠️ {t('quotations.pendingApprovalNotice')}: {selectedQuote.latest_version.approval_reason}
                </div>
              )}

              <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', margin: '0.75rem 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <span style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>إجمالي العرض المعتمد:</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#0369a1' }}>
                    {selectedQuote.latest_version?.total_amount ? Number(selectedQuote.latest_version.total_amount).toLocaleString() : '0.00'} {selectedQuote.currency}
                  </div>
                </div>
                <div style={{ textAlign: 'left', fontSize: '0.8rem', color: '#64748b' }}>
                  <div>الخصم: {selectedQuote.latest_version?.discount_pct || '0'}%</div>
                  <div>الضريبة: {selectedQuote.latest_version?.tax_amount || '0.00'} {selectedQuote.currency}</div>
                </div>
              </div>

              <h4>{t('quotations.lines')} (v{selectedQuote.latest_version?.version_number})</h4>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: '55px' }}>الصورة</th>
                      <th>{t('quotations.item')} والمواصفات</th>
                      <th>{t('quotations.qty')}</th>
                      <th>{t('quotations.price')}</th>
                      <th>الضمان</th>
                      <th>{t('quotations.lineTotal')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedQuote.latest_version?.lines?.map((l) => (
                      <tr key={l.id}>
                        <td style={{ textAlign: 'center', padding: '0.4rem' }}>
                          {l.display_image ? (
                            <img
                              src={l.display_image}
                              alt={l.model_name}
                              style={{ width: '44px', height: '44px', objectFit: 'contain', borderRadius: '6px', border: '1px solid #e2e8f0' }}
                            />
                          ) : (
                            <div style={{ width: '44px', height: '44px', background: '#f8fafc', borderRadius: '6px', display: 'grid', placeItems: 'center', fontSize: '1.2rem', margin: 'auto' }}>🩺</div>
                          )}
                        </td>
                        <td>
                          <strong style={{ color: '#0f172a' }}>{l.model_name}</strong>
                          {l.sku && <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>كود: {l.sku}</div>}
                          {l.specifications && Object.keys(l.specifications).length > 0 && (
                            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>
                              {Object.entries(l.specifications).slice(0, 2).map(([k, v]) => (
                                <span key={k} style={{ display: 'inline-block', marginInlineEnd: '0.5rem' }}>
                                  <strong>{k}:</strong> {String(v)}
                                </span>
                              ))}
                            </div>
                          )}
                        </td>
                        <td>{l.quantity}</td>
                        <td>{Number(l.unit_price).toLocaleString()}</td>
                        <td>{l.warranty_months} شهر</td>
                        <td><strong>{Number(l.total_price).toLocaleString()} {selectedQuote.currency}</strong></td>
                      </tr>
                    ))}
                    {(!selectedQuote.latest_version?.lines || selectedQuote.latest_version.lines.length === 0) && (
                      <tr><td colSpan={6}>{t('common.empty')}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#64748b', borderTop: '1px solid #e2e8f0', paddingTop: '0.5rem' }}>
                <div><strong>شروط الدفع:</strong> {selectedQuote.latest_version?.payment_terms || '100% الدفع مقدماً'}</div>
                <div><strong>شروط التسليم:</strong> {selectedQuote.latest_version?.delivery_terms || 'شامل التركيب والتشغيل في الموقع'}</div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* CREATE QUOTATION MODAL */}
      {showCreateModal && createPortal(
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.7)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '1rem',
          }}
          onClick={() => setShowCreateModal(false)}
        >
          <div
            className="card"
            style={{ width: 'min(860px, 95vw)', maxHeight: '90vh', overflowY: 'auto', borderRadius: '12px', background: '#ffffff' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, color: '#0f172a' }}>إنشاء وإصدار عرض سعر رسمي للعميل</h3>
              <button className="btn secondary" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>

            {prefillNotice && (
              <div
                style={{
                  background: '#ecfdf5',
                  border: '1px solid #6ee7b7',
                  color: '#065f46',
                  padding: '0.75rem 1rem',
                  borderRadius: '8px',
                  marginBottom: '1rem',
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <strong>{prefillNotice}</strong>
                </div>
                <button
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#065f46',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    fontSize: '1rem',
                  }}
                  onClick={() => setPrefillNotice(null)}
                >
                  ✕
                </button>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
              <div className="field">
                <label>العميل / المستشفى المستفيد *</label>
                <select
                  value={quoteForm.customer}
                  onChange={(e) => setQuoteForm({ ...quoteForm, customer: e.target.value })}
                >
                  <option value="">— اختر العميل أو المستشفى —</option>
                  {customersQuery.data?.results.map((c) => (
                    <option key={c.id} value={c.id}>{c.legal_name_ar} ({c.customer_number})</option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label>عنوان العرض والصفقة *</label>
                <input
                  placeholder="مثال: عرض توريد أجهزة عيون لمستشفى النخبة"
                  value={quoteForm.title}
                  onChange={(e) => setQuoteForm({ ...quoteForm, title: e.target.value })}
                />
              </div>

              <div className="field">
                <label>نموذج العمل التجاري (Commercial Model)</label>
                <select
                  value={quoteForm.commercial_model}
                  onChange={(e) => setQuoteForm({ ...quoteForm, commercial_model: e.target.value })}
                >
                  <option value="DIRECT_SALE">بيع وتوزيع مباشر (Buy & Resell)</option>
                  <option value="AGENCY">وكالة وعمولة (الشريك الصيني)</option>
                </select>
              </div>

              <div className="field">
                <label>عملة العرض (Currency)</label>
                <select
                  value={quoteForm.currency}
                  onChange={(e) => setQuoteForm({ ...quoteForm, currency: e.target.value })}
                >
                  <option value="USD">دولار أمريكي (USD)</option>
                  <option value="YER">ريال يمني (YER)</option>
                  <option value="SAR">ريال سعودي (SAR)</option>
                </select>
              </div>
            </div>

            {/* LINES EDITOR */}
            <h4 style={{ margin: '1rem 0 0.5rem', color: '#0f172a' }}>بنود الأجهزة والموديلات الطبية مع المواصفات</h4>
            <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
              <table>
                <thead>
                  <tr>
                    <th>الجهاز والموديل والمواصفات *</th>
                    <th style={{ width: '80px' }}>الكمية</th>
                    <th style={{ width: '130px' }}>السعر المعتمد</th>
                    <th style={{ width: '80px' }}>الخصم %</th>
                    <th style={{ width: '90px' }}>الضمان</th>
                    <th style={{ width: '50px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {quoteForm.lines.map((line, idx) => {
                    const sel = modelsQuery.data?.results.find((m) => m.id === line.model)

                    return (
                      <tr key={idx}>
                        <td>
                          <select
                            value={line.model}
                            onChange={(e) => handleModelSelect(idx, e.target.value)}
                            style={{ width: '100%' }}
                          >
                            <option value="">— اختر الجهاز —</option>
                            {modelsQuery.data?.results.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.sku} : {m.model_name} {m.approved_price ? `(${Number(m.approved_price.base_price).toLocaleString()} ${m.approved_price.currency})` : ''}
                              </option>
                            ))}
                          </select>

                          {/* Selected Device Live Photo & Specifications Preview Card */}
                          {sel && (
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '0.65rem',
                                background: '#f8fafc',
                                border: '1px solid #cbd5e1',
                                borderRadius: '6px',
                                padding: '0.45rem 0.65rem',
                                marginTop: '0.4rem',
                              }}
                            >
                              <div
                                style={{
                                  width: '46px',
                                  height: '46px',
                                  background: '#ffffff',
                                  borderRadius: '5px',
                                  border: '1px solid #e2e8f0',
                                  display: 'grid',
                                  placeItems: 'center',
                                  overflow: 'hidden',
                                  flexShrink: 0,
                                }}
                              >
                                {sel.display_image ? (
                                  <img src={sel.display_image} alt={sel.model_name} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                                ) : (
                                  <span style={{ fontSize: '1.2rem' }}>🩺</span>
                                )}
                              </div>
                              <div style={{ fontSize: '0.78rem', lineHeight: 1.35, flex: 1, minWidth: 0 }}>
                                <div style={{ fontWeight: 700, color: '#0f172a' }}>
                                  {sel.product_name_ar || sel.model_name} — كود: {sel.sku}
                                </div>
                                {sel.specifications && Object.keys(sel.specifications).length > 0 && (
                                  <div style={{ color: '#475569', fontSize: '0.75rem', marginTop: '0.15rem', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                    {Object.entries(sel.specifications).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </td>
                        <td>
                          <input
                            type="number"
                            min="1"
                            value={line.quantity}
                            onChange={(e) => {
                              const newLines = [...quoteForm.lines]
                              newLines[idx].quantity = Number(e.target.value) || 1
                              setQuoteForm({ ...quoteForm, lines: newLines })
                            }}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            step="0.01"
                            value={line.unit_price}
                            onChange={(e) => {
                              const newLines = [...quoteForm.lines]
                              newLines[idx].unit_price = e.target.value
                              setQuoteForm({ ...quoteForm, lines: newLines })
                            }}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            value={line.discount_pct}
                            onChange={(e) => {
                              const newLines = [...quoteForm.lines]
                              newLines[idx].discount_pct = e.target.value
                              setQuoteForm({ ...quoteForm, lines: newLines })
                            }}
                          />
                        </td>
                        <td>
                          <input
                            type="number"
                            value={line.warranty_months}
                            onChange={(e) => {
                              const newLines = [...quoteForm.lines]
                              newLines[idx].warranty_months = Number(e.target.value) || 12
                              setQuoteForm({ ...quoteForm, lines: newLines })
                            }}
                          />
                        </td>
                        <td>
                          <button
                            className="btn secondary"
                            style={{ color: 'red', padding: '0.2rem 0.5rem' }}
                            onClick={() => handleRemoveLine(idx)}
                            disabled={quoteForm.lines.length <= 1}
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <button className="btn secondary" style={{ fontSize: '0.85rem' }} onClick={handleAddLine}>
                + إضافة جهاز آخر للعرض
              </button>
              <div style={{ background: '#f0f9ff', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid #bae6fd', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.85rem', color: '#0369a1', fontWeight: 600 }}>إجمالي قيمة الأجهزة التقديري:</span>
                <strong style={{ fontSize: '1.2rem', color: '#0284c7' }}>
                  {calculatedTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {quoteForm.currency}
                </strong>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '0.5rem' }}>
              <div className="field">
                <label>شروط الدفع</label>
                <input
                  value={quoteForm.payment_terms}
                  onChange={(e) => setQuoteForm({ ...quoteForm, payment_terms: e.target.value })}
                />
              </div>
              <div className="field">
                <label>شروط التسليم والضمان</label>
                <input
                  value={quoteForm.delivery_terms}
                  onChange={(e) => setQuoteForm({ ...quoteForm, delivery_terms: e.target.value })}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1.25rem', borderTop: '1px solid #e2e8f0', paddingTop: '0.75rem' }}>
              <button className="btn secondary" onClick={() => setShowCreateModal(false)}>
                {t('common.cancel')}
              </button>
              <button className="btn" onClick={handleCreateQuotation}>
                حفظ وإصدار عرض السعر
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* OFFICIAL PRINTABLE QUOTATION MODAL */}
      {showPrintModal && selectedQuote && createPortal(
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '1rem',
          }}
          onClick={() => setShowPrintModal(false)}
        >
          <div
            className="card"
            style={{ width: 'min(900px, 98vw)', maxHeight: '92vh', overflowY: 'auto', background: '#ffffff', color: '#000000', padding: '2rem', borderRadius: '12px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '2px solid #0369a1', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <h2 style={{ margin: 0, color: '#0369a1' }}>شركة النظم الطبية الذكية المحدودة (SMSES)</h2>
                <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
                  الوكيل والموزع المعتمد للأجهزة والمعدات الطبية • صنعاء - الجمهورية اليمنية
                </div>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  سجل تجاري: 01/87654 • الرقم الضريبي: 200345678 • هاتف: 777000111
                </div>
              </div>
              <div style={{ textAlign: 'left' }}>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0369a1' }}>عرض سعر رسمي</div>
                <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>رقم: {selectedQuote.quotation_number}</div>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>التاريخ: {selectedQuote.created_at?.split('T')[0] || new Date().toISOString().split('T')[0]}</div>
              </div>
            </div>

            <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '6px', marginBottom: '1.5rem', border: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between' }}>
              <div>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>المستفيد / العميل:</span>
                <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>{selectedQuote.customer_name}</div>
                <div style={{ fontSize: '0.85rem', color: '#475569' }}>الموضوع: {selectedQuote.title}</div>
              </div>
              <div style={{ textAlign: 'left' }}>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>العملة ونموذج التعاقد:</span>
                <div style={{ fontWeight: 600 }}>{selectedQuote.currency} ({selectedQuote.commercial_model === 'DIRECT_SALE' ? 'بيع مباشر' : 'وكالة وعمولة'})</div>
                <div style={{ fontSize: '0.85rem', color: '#16a34a', fontWeight: 700 }}>الحالة: معتمد رسمياً</div>
              </div>
            </div>

            <table style={{ width: '100%', marginBottom: '1.5rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f1f5f9', borderBottom: '2px solid #cbd5e1' }}>
                  <th style={{ padding: '0.6rem', textAlign: 'right', width: '35px' }}>#</th>
                  <th style={{ padding: '0.6rem', textAlign: 'center', width: '55px' }}>صورة الجهاز</th>
                  <th style={{ padding: '0.6rem', textAlign: 'right' }}>بيان الجهاز والموديل والمواصفات الفنية</th>
                  <th style={{ padding: '0.6rem', textAlign: 'center', width: '60px' }}>الكمية</th>
                  <th style={{ padding: '0.6rem', textAlign: 'right', width: '110px' }}>سعر الوحدة</th>
                  <th style={{ padding: '0.6rem', textAlign: 'center', width: '70px' }}>الضمان</th>
                  <th style={{ padding: '0.6rem', textAlign: 'right', width: '120px' }}>الإجمالي</th>
                </tr>
              </thead>
              <tbody>
                {selectedQuote.latest_version?.lines?.map((l, i) => (
                  <tr key={l.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '0.6rem' }}>{i + 1}</td>
                    <td style={{ padding: '0.6rem', textAlign: 'center' }}>
                      {l.display_image ? (
                        <img
                          src={l.display_image}
                          alt={l.model_name}
                          style={{ width: '48px', height: '48px', objectFit: 'contain', borderRadius: '4px', border: '1px solid #e2e8f0', background: '#f8fafc' }}
                        />
                      ) : (
                        <div style={{ width: '48px', height: '48px', background: '#f8fafc', borderRadius: '4px', display: 'grid', placeItems: 'center', fontSize: '1.2rem', margin: 'auto' }}>🩺</div>
                      )}
                    </td>
                    <td style={{ padding: '0.6rem' }}>
                      <strong style={{ color: '#0f172a' }}>{l.model_name}</strong>
                      <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{l.description || `كود: ${l.sku}`}</div>
                      {l.specifications && Object.keys(l.specifications).length > 0 && (
                        <div style={{ fontSize: '0.74rem', color: '#475569', marginTop: '0.25rem', background: '#f8fafc', padding: '0.3rem 0.5rem', borderRadius: '4px' }}>
                          {Object.entries(l.specifications).slice(0, 3).map(([k, v]) => (
                            <span key={k} style={{ display: 'inline-block', marginInlineEnd: '0.75rem' }}>
                              <strong>{k}:</strong> {String(v)}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '0.6rem', textAlign: 'center' }}>{l.quantity}</td>
                    <td style={{ padding: '0.6rem', textAlign: 'right' }}>{Number(l.unit_price).toLocaleString()}</td>
                    <td style={{ padding: '0.6rem', textAlign: 'center' }}>{l.warranty_months} شهراً</td>
                    <td style={{ padding: '0.6rem', textAlign: 'right', fontWeight: 700 }}>
                      {Number(l.total_price).toLocaleString()} {selectedQuote.currency}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* TOTALS */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1.5rem' }}>
              <div style={{ width: '280px', background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                  <span>المجموع الفرعي:</span>
                  <strong>{Number(selectedQuote.latest_version?.subtotal || selectedQuote.latest_version?.total_amount || 0).toLocaleString()} {selectedQuote.currency}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem', color: '#16a34a' }}>
                  <span>الخصم الممنوح:</span>
                  <span>{selectedQuote.latest_version?.discount_pct || '0'}%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '2px solid #0369a1', paddingTop: '0.5rem', fontSize: '1.1rem', fontWeight: 800, color: '#0369a1' }}>
                  <span>الإجمالي الصافي:</span>
                  <span>{Number(selectedQuote.latest_version?.total_amount || 0).toLocaleString()} {selectedQuote.currency}</span>
                </div>
              </div>
            </div>

            {/* TERMS & SIGNATURES */}
            <div style={{ fontSize: '0.85rem', color: '#334155', borderTop: '1px solid #e2e8f0', paddingTop: '1rem', marginBottom: '2rem' }}>
              <p style={{ margin: '0.2rem 0' }}>• <strong>شروط الدفع:</strong> {selectedQuote.latest_version?.payment_terms || '100% الدفع مقدماً بحوالة بنكية'}</p>
              <p style={{ margin: '0.2rem 0' }}>• <strong>شروط التسليم والتركيب:</strong> {selectedQuote.latest_version?.delivery_terms || 'شامل التوريد والتركيب والتشغيل وتدريب الكادر الطبي'}</p>
              <p style={{ margin: '0.2rem 0' }}>• <strong>الضمان والصيانة:</strong> الضمان المصنعي سارٍ لجميع الأجهزة وفق الشهور المحددة أعلاه شاملاً قطع الغيار الأصلية.</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', textAlign: 'center', marginTop: '2rem' }}>
              <div>
                <div style={{ fontWeight: 700, marginBottom: '2.5rem' }}>إدارة المبيعات والتسويق</div>
                <div style={{ borderTop: '1px dashed #94a3b8', width: '60%', margin: 'auto', paddingTop: '0.3rem', fontSize: '0.8rem', color: '#64748b' }}>
                  التوقيع والاعتماد
                </div>
              </div>
              <div>
                <div style={{ fontWeight: 700, marginBottom: '2.5rem' }}>ختم الشركة المعتمد</div>
                <div style={{ borderTop: '1px dashed #94a3b8', width: '60%', margin: 'auto', paddingTop: '0.3rem', fontSize: '0.8rem', color: '#64748b' }}>
                  (SMSES Official Seal)
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '2rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
              <button
                className="btn"
                style={{ background: '#0284c7', color: '#fff' }}
                onClick={() => window.print()}
              >
                🖨️ طباعة الآن (Print)
              </button>
              <button className="btn secondary" onClick={() => setShowPrintModal(false)}>
                إغلاق المعاينة
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  )
}
