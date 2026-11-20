import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api, type Page, resolveImageUrl } from '../api'
import { useAuth } from '../auth'

interface PriceListItem {
  id: string
  model_name: string
  sku: string
  product_name_ar: string
  display_image?: string
  base_price: string
  min_price: string
  cost_price?: string
  margin_pct?: number
}

interface PriceList {
  id: string
  code: string
  name_ar: string
  currency: string
  effective_from: string
  effective_to?: string
  status: string
  is_default: boolean
  items_count: number
}

interface ProductModelOption {
  id: string
  model_code: string
  model_name: string
  sku: string
  product_name_ar: string
}

export default function PriceListsPage() {
  const { t } = useTranslation()
  const { can } = useAuth()
  const queryClient = useQueryClient()
  const [selectedList, setSelectedList] = useState<PriceList | null>(null)
  const [showAddListModal, setShowAddListModal] = useState(false)
  const [showAddItemModal, setShowAddItemModal] = useState(false)

  // Forms
  const [listForm, setListForm] = useState({
    code: '',
    name_ar: '',
    name_en: '',
    currency: 'USD',
    effective_from: new Date().toISOString().split('T')[0],
    is_default: false,
    status: 'ACTIVE',
  })

  const [itemForm, setItemForm] = useState({
    model: '',
    base_price: '',
    min_price: '',
    cost_price: '',
  })

  const lists = useQuery({
    queryKey: ['price-lists'],
    queryFn: () => api<Page<PriceList>>('/price-lists/'),
  })

  const items = useQuery({
    queryKey: ['price-list-items', selectedList?.id],
    queryFn: () => api<Page<PriceListItem>>(`/price-list-items/?price_list=${selectedList?.id}`),
    enabled: !!selectedList,
  })

  const modelsQuery = useQuery({
    queryKey: ['models-for-pricing'],
    queryFn: () => api<Page<ProductModelOption>>('/models/'),
  })

  // Auto-select default/first price list so items are visible immediately
  useEffect(() => {
    if (!selectedList && lists.data?.results && lists.data.results.length > 0) {
      const defaultList = lists.data.results.find((l) => l.is_default) || lists.data.results[0]
      setSelectedList(defaultList)
    }
  }, [lists.data, selectedList])

  const canSeeCost = can('pricing.cost.view')

  const handleCreateList = async () => {
    if (!listForm.code || !listForm.name_ar || !listForm.effective_from) {
      alert('يرجى تعبئة رمز القائمة واسمها وتاريخ سريانها')
      return
    }
    try {
      await api('/price-lists/', {
        method: 'POST',
        json: listForm,
      })
      alert('تم إنشاء قائمة الأسعار بنجاح')
      setShowAddListModal(false)
      setListForm({
        code: '',
        name_ar: '',
        name_en: '',
        currency: 'USD',
        effective_from: new Date().toISOString().split('T')[0],
        is_default: false,
        status: 'ACTIVE',
      })
      queryClient.invalidateQueries({ queryKey: ['price-lists'] })
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleCreateItem = async () => {
    if (!selectedList) return
    if (!itemForm.model || !itemForm.base_price || !itemForm.min_price) {
      alert('يرجى اختيار الموديل وتحديد سعر البيع والحد الأدنى')
      return
    }
    try {
      await api('/price-list-items/', {
        method: 'POST',
        json: {
          price_list: selectedList.id,
          model: itemForm.model,
          base_price: itemForm.base_price,
          min_price: itemForm.min_price,
          cost_price: itemForm.cost_price || '0.00',
        },
      })
      alert('تمت إضافة بند التسعير للقائمة بنجاح')
      setShowAddItemModal(false)
      setItemForm({ model: '', base_price: '', min_price: '', cost_price: '' })
      queryClient.invalidateQueries({ queryKey: ['price-list-items', selectedList.id] })
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  return (
    <>
      <div className="bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0 }}>{t('pricing.title')}</h1>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--muted)', fontSize: '0.85rem' }}>
            قوائم الأسعار الرسمية والعملات وسقوف الخصومات المعتمدة
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Link to="/documents" className="btn secondary" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <span>📄</span>
            <span>رفع قائمة أسعار بالذكاء الاصطناعي (AI Gateway)</span>
          </Link>
          {can('pricing.pricelist.create') && (
            <button className="btn" onClick={() => setShowAddListModal(true)}>
              + {t('common.create')} قائمة أسعار
            </button>
          )}
        </div>
      </div>

      {lists.isLoading ? (
        t('common.loading')
      ) : (
        <div className={`split-layout ${selectedList ? 'active' : ''}`}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('pricing.code')}</th>
                  <th>{t('pricing.name')}</th>
                  <th>{t('pricing.currency')}</th>
                  <th>{t('pricing.effectiveFrom')}</th>
                  <th>{t('pricing.status')}</th>
                </tr>
              </thead>
              <tbody>
                {lists.data?.results.map((pl) => (
                  <tr
                    key={pl.id}
                    onClick={() => setSelectedList(pl)}
                    style={{ cursor: 'pointer', background: selectedList?.id === pl.id ? 'var(--bg-muted, #f0f4f8)' : undefined }}
                  >
                    <td><strong>{pl.code}</strong> {pl.is_default && <span className="badge ok">{t('pricing.default')}</span>}</td>
                    <td>{pl.name_ar}</td>
                    <td>{pl.currency}</td>
                    <td>{pl.effective_from}</td>
                    <td>
                      <span className={`badge ${pl.status === 'ACTIVE' ? 'ok' : 'off'}`}>
                        {t(`pricing.statuses.${pl.status}`)}
                      </span>
                    </td>
                  </tr>
                ))}
                {lists.data?.results.length === 0 && (
                  <tr><td colSpan={5}>{t('common.empty')}</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {selectedList && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <h3 style={{ margin: 0 }}>{selectedList.name_ar} ({selectedList.currency})</h3>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {can('pricing.item.create') && (
                    <button className="btn" style={{ fontSize: '0.8rem' }} onClick={() => setShowAddItemModal(true)}>
                      + إضافة بند تسعير
                    </button>
                  )}
                  <button className="btn secondary" style={{ fontSize: '0.8rem' }} onClick={() => setSelectedList(null)}>
                    {t('common.cancel')}
                  </button>
                </div>
              </div>

              {items.isLoading ? (
                t('common.loading')
              ) : (
                <div className="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th style={{ width: '55px' }}>الصورة</th>
                        <th>{t('pricing.product')}</th>
                        <th>{t('pricing.sku')}</th>
                        <th>{t('pricing.basePrice')}</th>
                        <th>{t('pricing.minPrice')}</th>
                        {canSeeCost && <th>{t('pricing.costPrice')}</th>}
                        {canSeeCost && <th>{t('pricing.margin')}</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {items.data?.results.map((it) => (
                        <tr key={it.id}>
                          <td style={{ textAlign: 'center', padding: '0.4rem' }}>
                            {it.display_image ? (
                              <img
                                src={resolveImageUrl(it.display_image)}
                                alt={it.model_name}
                                loading="lazy"
                                decoding="async"
                                style={{ width: '42px', height: '42px', objectFit: 'contain', borderRadius: '4px', border: '1px solid #e2e8f0', background: '#f8fafc' }}
                              />
                            ) : (
                              <div style={{ width: '42px', height: '42px', background: '#f8fafc', borderRadius: '4px', display: 'grid', placeItems: 'center', fontSize: '1.2rem', margin: 'auto' }}>🩺</div>
                            )}
                          </td>
                          <td><strong>{it.product_name_ar}</strong> - {it.model_name}</td>
                          <td><code>{it.sku}</code></td>
                          <td><strong>${Number(it.base_price).toLocaleString()}</strong></td>
                          <td>${Number(it.min_price).toLocaleString()}</td>
                          {canSeeCost && <td style={{ color: '#b91c1c' }}>{it.cost_price ? `$${Number(it.cost_price).toLocaleString()}` : '-'}</td>}
                          {canSeeCost && <td>{it.margin_pct != null ? `${it.margin_pct}%` : '-'}</td>}
                        </tr>
                      ))}
                      {items.data?.results.length === 0 && (
                        <tr><td colSpan={canSeeCost ? 7 : 5}>{t('common.empty')} — انقر (+ إضافة بند تسعير)</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* CREATE PRICE LIST MODAL */}
      {showAddListModal && createPortal(
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '1rem',
          }}
          onClick={() => setShowAddListModal(false)}
        >
          <div
            className="card"
            style={{ width: 'min(500px, 95vw)', maxHeight: '90vh', overflowY: 'auto', background: '#ffffff', borderRadius: '12px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>إنشاء قائمة أسعار جديدة</h3>
            <div className="field">
              <label>رمز القائمة (Code)*</label>
              <input
                placeholder="مثال: PL-2026-TENDER"
                value={listForm.code}
                onChange={(e) => setListForm({ ...listForm, code: e.target.value })}
              />
            </div>
            <div className="field">
              <label>اسم القائمة بالعربية*</label>
              <input
                placeholder="مثال: قائمة أسعار المناقصات الحكومية 2026"
                value={listForm.name_ar}
                onChange={(e) => setListForm({ ...listForm, name_ar: e.target.value })}
              />
            </div>
            <div className="field">
              <label>العملة (Currency)*</label>
              <select
                value={listForm.currency}
                onChange={(e) => setListForm({ ...listForm, currency: e.target.value })}
              >
                <option value="USD">دولار أمريكي (USD)</option>
                <option value="YER">ريال يمني (YER)</option>
                <option value="CNY">يوان صيني (CNY)</option>
                <option value="SAR">ريال سعودي (SAR)</option>
                <option value="EUR">يورو (EUR)</option>
              </select>
            </div>
            <div className="field">
              <label>تاريخ السريان (Effective From)*</label>
              <input
                type="date"
                value={listForm.effective_from}
                onChange={(e) => setListForm({ ...listForm, effective_from: e.target.value })}
              />
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button className="btn secondary" onClick={() => setShowAddListModal(false)}>
                {t('common.cancel')}
              </button>
              <button className="btn" onClick={handleCreateList}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* CREATE PRICE ITEM MODAL */}
      {showAddItemModal && selectedList && createPortal(
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.7)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '1rem',
          }}
          onClick={() => setShowAddItemModal(false)}
        >
          <div
            className="card"
            style={{ width: 'min(520px, 95vw)', maxHeight: '90vh', overflowY: 'auto', background: '#ffffff', borderRadius: '12px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>إضافة بند تسعير لـ: {selectedList.name_ar}</h3>
            <div className="field">
              <label>الموديل الطبي*</label>
              <select
                value={itemForm.model}
                onChange={(e) => setItemForm({ ...itemForm, model: e.target.value })}
              >
                <option value="">— اختر الموديل —</option>
                {modelsQuery.data?.results.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.product_name_ar} - {m.model_name} ({m.model_code})
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>سعر البيع المعتمد للعميل (Base Price)* ({selectedList.currency})</label>
              <input
                type="number"
                placeholder="مثال: 58000"
                value={itemForm.base_price}
                onChange={(e) => setItemForm({ ...itemForm, base_price: e.target.value })}
              />
            </div>
            <div className="field">
              <label>الحد الأدنى لسعر البيع (Min Price)* ({selectedList.currency})</label>
              <input
                type="number"
                placeholder="أقل سعر مسموح به لرجل المبيعات قبل طلب موافقة الخصم"
                value={itemForm.min_price}
                onChange={(e) => setItemForm({ ...itemForm, min_price: e.target.value })}
              />
            </div>
            {canSeeCost && (
              <div className="field">
                <label>تكلفة المورد الصيني (Cost Price) ({selectedList.currency})</label>
                <input
                  type="number"
                  placeholder="تكلفة الشراء الفعلية لحساب هامش الربح"
                  value={itemForm.cost_price}
                  onChange={(e) => setItemForm({ ...itemForm, cost_price: e.target.value })}
                />
              </div>
            )}
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button className="btn secondary" onClick={() => setShowAddItemModal(false)}>
                {t('common.cancel')}
              </button>
              <button className="btn" onClick={handleCreateItem}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  )
}
