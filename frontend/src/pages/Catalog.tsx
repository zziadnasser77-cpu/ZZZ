import { useState, useMemo, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type Page } from '../api'

interface ProductModel {
  id: string
  model_code: string
  model_name: string
  sku: string
  standard_warranty_months: number
  approval_status: string
  origin_country: string
  image?: string
  image_url?: string
  display_image?: string | null
  power_requirements?: string
  standard_accessories?: string
  optional_accessories?: string
  specifications?: Record<string, any>
  approved_price?: {
    base_price: string
    min_price: string
    currency: string
    price_list_code: string
  } | null
}

interface Product {
  id: string
  code: string
  name_ar: string
  name_en: string
  category: string
  category_name_ar: string
  manufacturer: string
  manufacturer_name_ar: string
  device_class: string
  description_ar?: string
  image?: string
  image_url?: string
  display_image?: string | null
  is_active: boolean
  models: ProductModel[]
}

interface Category {
  id: string
  code: string
  name_ar: string
  name_en: string
}

interface DocumentItem {
  id: string
  document_number: string
  title: string
  document_type: string
  file?: string | null
  file_size?: number
  content_type?: string
  language: string
  uploaded_by_name?: string
  created_at: string
}

export default function CatalogPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // 1. Primary Segmented Tabs:
  // 'devices': 🔬 الأجهزة والموديلات المستخرجة
  // 'catalogues': 📚 كتالوجات ومستندات الموردين
  const [activeTab, setActiveTab] = useState<'devices' | 'catalogues'>('devices')

  // Search & Filter states for Devices Tab
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [pricingFilter, setPricingFilter] = useState<'ALL' | 'PRICED' | 'UNPRICED'>('ALL')
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards')

  // Read URL query parameter if present
  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setSearchQuery(q)
      setActiveTab('devices')
    }
  }, [searchParams])

  // Selected Model for Full Specification Modal
  const [selectedModelDetail, setSelectedModelDetail] = useState<{
    model: ProductModel
    product: Product
  } | null>(null)

  // Instant Quotation Issuance Pop-up Modal State
  const [quoteModalItem, setQuoteModalItem] = useState<{ model: ProductModel; product: Product } | null>(null)
  const [quoteForm, setQuoteForm] = useState({
    customer: '',
    quantity: 1,
    unit_price: '0.00',
    discount_pct: '0.00',
    warranty_months: 24,
    commercial_model: 'DIRECT_SALE',
    currency: 'USD',
    payment_terms: '100% الدفع مقدماً بحوالة بنكية أو نقداً',
    delivery_terms: 'شامل التوريد والتركيب والتشغيل والتدريب في موقع المستشفى',
    notes: 'عرض سعر رسمي معتمد صادر من الوكالة الحصرية SRD Ophthalmic',
  })
  const [isSubmittingQuote, setIsSubmittingQuote] = useState(false)
  const [quoteSubmitError, setQuoteSubmitError] = useState<string | null>(null)
  const [createdQuoteSuccess, setCreatedQuoteSuccess] = useState<any | null>(null)

  // Lock body scroll when any modal is open
  useEffect(() => {
    if (selectedModelDetail || quoteModalItem) {
      const originalOverflow = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = originalOverflow
      }
    }
  }, [selectedModelDetail, quoteModalItem])

  // 1. Fetch Products & Models
  const { data: productsData, isLoading: loadingProducts } = useQuery({
    queryKey: ['products'],
    queryFn: () => api<Page<Product>>('/products/?is_active=true&page_size=250'),
  })

  // Customers Query for the pop-up quotation modal
  const { data: customersData } = useQuery({
    queryKey: ['customers-list-catalog'],
    queryFn: () => api<Page<{ id: string; customer_number: string; legal_name_ar: string }>>('/customers/?page_size=100'),
  })

  // 2. Fetch Categories
  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api<Page<Category>>('/categories/?page_size=50'),
  })

  // 3. Fetch Documents (Catalogues & Price Lists)
  const { data: documentsData, isLoading: loadingDocs } = useQuery({
    queryKey: ['catalog-documents'],
    queryFn: () => api<Page<DocumentItem>>('/documents/documents/?page_size=50'),
  })

  // Filter Catalogues and Price Lists for Tab 1
  const vendorCatalogues = useMemo(() => {
    if (!documentsData?.results) return []
    return documentsData.results.filter(
      (d) =>
        d.document_type === 'CATALOG_BROCHURE' ||
        d.document_type === 'PROFORMA_INVOICE' ||
        d.document_type === 'COMMERCIAL_INVOICE'
    )
  }, [documentsData])

  // Flattened device models with their parent product
  const allDeviceItems = useMemo(() => {
    if (!productsData?.results) return []
    const items: Array<{ product: Product; model: ProductModel }> = []
    for (const p of productsData.results) {
      if (!p.models || p.models.length === 0) {
        items.push({
          product: p,
          model: {
            id: p.id,
            model_code: p.code,
            model_name: p.name_ar,
            sku: p.code,
            standard_warranty_months: 12,
            approval_status: 'APPROVED',
            origin_country: 'China',
            display_image: p.display_image,
            approved_price: null,
            specifications: {},
          },
        })
      } else {
        for (const m of p.models) {
          items.push({ product: p, model: m })
        }
      }
    }
    return items
  }, [productsData])

  // Category items count lookup
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const item of allDeviceItems) {
      const catId = item.product.category
      counts[catId] = (counts[catId] || 0) + 1
    }
    return counts
  }, [allDeviceItems])

  // Filtered devices based on search, category, and pricing
  const filteredDevices = useMemo(() => {
    return allDeviceItems.filter(({ product, model }) => {
      // Category filter
      if (selectedCategory && product.category !== selectedCategory) {
        return false
      }

      // Pricing filter
      const isPriced = !!model.approved_price
      if (pricingFilter === 'PRICED' && !isPriced) return false
      if (pricingFilter === 'UNPRICED' && isPriced) return false

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matchNameAr = product.name_ar.toLowerCase().includes(q)
        const matchNameEn = product.name_en.toLowerCase().includes(q)
        const matchModelCode = model.model_code.toLowerCase().includes(q)
        const matchSku = model.sku.toLowerCase().includes(q)
        const matchCat = (product.category_name_ar || '').toLowerCase().includes(q)
        const matchSpecs = model.specifications
          ? JSON.stringify(model.specifications).toLowerCase().includes(q)
          : false

        return matchNameAr || matchNameEn || matchModelCode || matchSku || matchCat || matchSpecs
      }

      return true
    })
  }, [allDeviceItems, selectedCategory, pricingFilter, searchQuery])

  // Counts for summary
  const pricedCount = useMemo(
    () => allDeviceItems.filter((i) => !!i.model.approved_price).length,
    [allDeviceItems]
  )
  const unpricedCount = useMemo(
    () => allDeviceItems.filter((i) => !i.model.approved_price).length,
    [allDeviceItems]
  )

  // Instant quotation pop-up calculated total
  const quoteModalCalculatedTotal = useMemo(() => {
    const qty = Number(quoteForm.quantity) || 1
    const price = Number(quoteForm.unit_price) || 0
    const disc = Number(quoteForm.discount_pct) || 0
    const base = qty * price
    return base - (base * disc) / 100
  }, [quoteForm.quantity, quoteForm.unit_price, quoteForm.discount_pct])

  // Direct quotation issuance pop-up opener
  const handleIssueQuotation = (model: ProductModel, product: Product) => {
    setSelectedModelDetail(null) // Close specs modal if open
    const basePrice = model.approved_price ? model.approved_price.base_price : '0.00'
    const curr = model.approved_price ? model.approved_price.currency : 'USD'
    setQuoteForm({
      customer: customersData?.results?.[0]?.id || '',
      quantity: 1,
      unit_price: basePrice,
      discount_pct: '0.00',
      warranty_months: model.standard_warranty_months || 24,
      commercial_model: 'DIRECT_SALE',
      currency: curr,
      payment_terms: '100% الدفع مقدماً بحوالة بنكية أو نقداً',
      delivery_terms: 'شامل التوريد والتركيب والتشغيل وتدريب الكادر الطبي في موقع المستشفى',
      notes: 'عرض سعر رسمي معتمد صادر من الوكالة الحصرية SRD Ophthalmic Instruments',
    })
    setQuoteSubmitError(null)
    setCreatedQuoteSuccess(null)
    setQuoteModalItem({ model, product })
  }

  // Handle submitting the quotation directly from the pop-up modal
  const handleSubmitQuotation = async () => {
    if (!quoteModalItem) return
    if (!quoteForm.customer) {
      setQuoteSubmitError('يرجى اختيار العميل أو المستشفى المستفيد.')
      return
    }
    setIsSubmittingQuote(true)
    setQuoteSubmitError(null)
    try {
      const res = await api<any>('/quotations/', {
        method: 'POST',
        json: {
          customer: quoteForm.customer,
          title: `عرض توريد وتجهيز جهاز ${quoteModalItem.product.name_ar} (${quoteModalItem.model.model_code})`,
          commercial_model: quoteForm.commercial_model,
          currency: quoteForm.currency,
          payment_terms: quoteForm.payment_terms,
          delivery_terms: quoteForm.delivery_terms,
          notes: quoteForm.notes,
          lines: [
            {
              model: quoteModalItem.model.id,
              description: `${quoteModalItem.product.name_ar} (${quoteModalItem.model.model_name}) - مواصفات قياسية مصنعية`,
              quantity: Number(quoteForm.quantity) || 1,
              unit_price: String(quoteForm.unit_price || '0.00'),
              discount_pct: String(quoteForm.discount_pct || '0.00'),
              warranty_months: Number(quoteForm.warranty_months) || 24,
            },
          ],
        },
      })
      setCreatedQuoteSuccess(res)
    } catch (err: any) {
      setQuoteSubmitError(err.message || 'حدث خطأ أثناء إصدار عرض السعر.')
    } finally {
      setIsSubmittingQuote(false)
    }
  }

  // Format file size
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'غير محدد'
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} ميجابايت`
    return `${Math.round(bytes / 1024)} كيلوبايت`
  }

  return (
    <div className="fade-in">
      {/* PAGE HEADER & TOP CONTROLS (Engineered Alignment) */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.25rem',
          flexWrap: 'wrap',
          gap: '1rem',
          paddingBottom: '1rem',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <span style={{ fontSize: '1.8rem' }}>🔬</span>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', letterSpacing: '-0.3px' }}>
                الكتالوج الطبي وقاعدة بيانات الأجهزة
              </h1>
              <p style={{ margin: '0.2rem 0 0', color: 'var(--muted)', fontSize: '0.85rem' }}>
                الكتالوج الشامل المعتمد — أجهزة ومعدات طب العيون، جراحة المناظير، والمستلزمات الطبية والتعقيم (HEROMAX / HAS)
              </p>
            </div>
          </div>
        </div>

        {/* PRIMARY SEGMENTED TABS (Apple / YouTube Studio Style) */}
        <div className="segmented-control">
          <button
            className={`segmented-tab ${activeTab === 'devices' ? 'active' : ''}`}
            onClick={() => setActiveTab('devices')}
          >
            <span>🔬</span>
            <span>الأجهزة والموديلات المستخرجة</span>
            <span className="segmented-badge">{allDeviceItems.length}</span>
          </button>

          <button
            className={`segmented-tab ${activeTab === 'catalogues' ? 'active' : ''}`}
            onClick={() => setActiveTab('catalogues')}
          >
            <span>📚</span>
            <span>كتالوجات ومستندات الموردين</span>
            <span className="segmented-badge">{vendorCatalogues.length}</span>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: VENDOR CATALOGUES & DOCUMENTS                                       */}
      {/* ========================================================================= */}
      {activeTab === 'catalogues' && (
        <div className="fade-in">
          {/* Summary Banner */}
          <div
            className="card"
            style={{
              background: 'linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 100%)',
              borderColor: '#bfdbfe',
              padding: '1.25rem 1.5rem',
              marginBottom: '1.5rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '1rem',
            }}
          >
            <div>
              <h3 style={{ margin: 0, color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>📁</span>
                <span>أرشيف كتالوجات وقوائم أسعار المصنع المعتمد</span>
              </h3>
              <p style={{ margin: '0.35rem 0 0', color: '#475569', fontSize: '0.88rem' }}>
                المستندات الرسمية المرفوعة من المورد (HEROMAX / SRD Instruments). تم استخراج الأجهزة والمواصفات بالكامل.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <div
                style={{
                  background: '#ffffff',
                  padding: '0.5rem 0.9rem',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>إجمالي الأجهزة</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--blue)' }}>
                  {allDeviceItems.length}
                </div>
              </div>
              <div
                style={{
                  background: '#ffffff',
                  padding: '0.5rem 0.9rem',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>أجهزة مسعرة معتمدة</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#16a34a' }}>
                  {pricedCount}
                </div>
              </div>
              <div
                style={{
                  background: '#ffffff',
                  padding: '0.5rem 0.9rem',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '0.75rem', color: '#64748b' }}>بانتظار تسعيرة المصنع</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#d97706' }}>
                  {unpricedCount}
                </div>
              </div>
            </div>
          </div>

          {loadingDocs ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
              {t('common.loading')}
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
                gap: '1.25rem',
              }}
            >
              {vendorCatalogues.map((doc) => {
                const isCatalogue = doc.document_type === 'CATALOG_BROCHURE'
                const fileUrl = doc.file ? (doc.file.startsWith('http') ? doc.file : `/media/${doc.file}`) : null

                return (
                  <div
                    key={doc.id}
                    className="card"
                    style={{
                      borderTop: isCatalogue ? '4px solid #0284c7' : '4px solid #16a34a',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                        <span
                          className={`badge ${isCatalogue ? 'info' : 'ok'}`}
                          style={{ fontSize: '0.8rem', padding: '0.25rem 0.6rem' }}
                        >
                          {isCatalogue ? '📚 كتالوج ومواصفات أجهزة' : '🏷️ كشف أسعار معتمد'}
                        </span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--muted)', direction: 'ltr' }}>
                          {doc.document_number}
                        </span>
                      </div>

                      <h3 style={{ margin: '0 0 0.5rem', fontSize: '1.05rem', color: '#0f172a', lineHeight: 1.4 }}>
                        {doc.title}
                      </h3>

                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '1fr 1fr',
                          gap: '0.5rem',
                          margin: '0.85rem 0',
                          padding: '0.75rem',
                          background: '#f8fafc',
                          borderRadius: '8px',
                          fontSize: '0.82rem',
                          border: '1px solid #f1f5f9',
                        }}
                      >
                        <div>
                          <span style={{ color: '#64748b' }}>حجم الملف: </span>
                          <strong style={{ color: '#0f172a' }}>{formatFileSize(doc.file_size)}</strong>
                        </div>
                        <div>
                          <span style={{ color: '#64748b' }}>الصيغة: </span>
                          <strong style={{ color: '#0f172a' }}>PDF</strong>
                        </div>
                        <div>
                          <span style={{ color: '#64748b' }}>تاريخ الرفع: </span>
                          <span style={{ color: '#0f172a' }}>{doc.created_at ? doc.created_at.slice(0, 10) : '-'}</span>
                        </div>
                        <div>
                          <span style={{ color: '#64748b' }}>حالة الاستخراج: </span>
                          <strong style={{ color: '#16a34a' }}>✅ معتمد</strong>
                        </div>
                      </div>

                      <p style={{ fontSize: '0.85rem', color: '#475569', margin: '0 0 1rem', lineHeight: 1.5 }}>
                        {doc.title?.toLowerCase().includes('catalog-s') || doc.file?.toLowerCase().includes('catalog-s')
                          ? 'كتالوج جراحة المناظير والدباسات الطبية المعقمة، أدوات إغلاق الصفاق الجراحي، التروكارات وكلبسات فروة الرأس.'
                          : doc.title?.toLowerCase().includes('medical') || doc.file?.toLowerCase().includes('medical')
                          ? 'كتالوج المستلزمات الطبية وأدوات طب وجراحة الأسنان وعلاج الجذور، أرواب العزل وصناديق التعقيم الأوتوكلاف.'
                          : isCatalogue
                          ? 'كتالوج الأجهزة والمعدات العينية والبصرية الصادرة من المصنع بجميع المواصفات القياسية والملحقات.'
                          : 'كشف أسعار الوكالة الحصرية 2026 شاملاً تكاليف الشحن داخل الصين مع تطبيق هوامش الربح المعتمدة.'}
                      </p>
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        gap: '0.6rem',
                        borderTop: '1px solid #e2e8f0',
                        paddingTop: '0.85rem',
                        flexWrap: 'wrap',
                      }}
                    >
                      {fileUrl && (
                        <a
                          href={fileUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="btn secondary"
                          style={{
                            flex: '1 1 140px',
                            textDecoration: 'none',
                            textAlign: 'center',
                            fontSize: '0.85rem',
                          }}
                        >
                          <span>📄</span>
                          <span>فتح وتحميل PDF</span>
                        </a>
                      )}
                      <button
                        onClick={() => {
                          const t = (doc.title || '').toLowerCase()
                          const f = (doc.file || '').toLowerCase()
                          if (t.includes('catalog-s') || f.includes('catalog-s')) {
                            setSearchQuery('HAS')
                          } else if (t.includes('medical') || f.includes('medical') || f.includes('catalogue_3') || f.includes('hero_max')) {
                            setSearchQuery('HM')
                          } else if (t.includes('eyedoc') || f.includes('eyedoc')) {
                            setSearchQuery('YYK')
                          } else if (t.includes('hydrophilic') || f.includes('hydrophilic') || f.includes('lenses')) {
                            setSearchQuery('LAURALENS')
                          } else if (t.includes('brochure') || f.includes('brochure')) {
                            setSearchQuery('LM')
                          } else if (t.includes('2024.09.30') || f.includes('2024.09.30')) {
                            setSearchQuery('TQ10')
                          } else {
                            setSearchQuery('')
                          }
                          setSelectedCategory('')
                          setActiveTab('devices')
                        }}
                        className="btn"
                        style={{
                          flex: '1 1 160px',
                          fontSize: '0.85rem',
                        }}
                      >
                        <span>🔬</span>
                        <span>تصفح الأجهزة المستخرجة</span>
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: EXTRACTED EQUIPMENT & DEVICES (YouTube Standard Layout)            */}
      {/* ========================================================================= */}
      {activeTab === 'devices' && (
        <div className="fade-in">
          {/* 1. YOUTUBE CHIPS ROW FOR CATEGORIES */}
          <div className="chip-bar">
            <button
              className={`chip ${selectedCategory === '' ? 'active' : ''}`}
              onClick={() => setSelectedCategory('')}
            >
              <span>الكل</span>
              <span style={{ opacity: 0.7, fontSize: '0.78rem' }}>({allDeviceItems.length})</span>
            </button>

            {categoriesData?.results.map((c) => {
              const count = categoryCounts[c.id] || 0
              if (count === 0 && !selectedCategory) return null
              const isSelected = selectedCategory === c.id
              return (
                <button
                  key={c.id}
                  className={`chip ${isSelected ? 'active' : ''}`}
                  onClick={() => setSelectedCategory(c.id)}
                >
                  <span>{c.name_ar}</span>
                  <span style={{ opacity: 0.7, fontSize: '0.78rem' }}>({count})</span>
                </button>
              )
            })}
          </div>

          {/* 2. TOOLBAR: SEARCH & PRICING FILTER CHIPS & VIEW SWITCH */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.85rem',
              marginBottom: '1rem',
              background: '#ffffff',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border)',
            }}
          >
            {/* Search Input */}
            <div style={{ flex: '1 1 260px', position: 'relative' }}>
              <span
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#94a3b8',
                }}
              >
                🔍
              </span>
              <input
                type="text"
                style={{
                  width: '100%',
                  padding: '0.5rem 2.2rem 0.5rem 2rem',
                  borderRadius: '8px',
                  border: '1px solid var(--border)',
                  fontSize: '0.88rem',
                  background: '#f8fafc',
                }}
                placeholder="ابحث باسم الجهاز، رمز الموديل، الـ SKU، أو المواصفة..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    left: '10px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#94a3b8',
                    fontSize: '0.85rem',
                  }}
                >
                  ✕
                </button>
              )}
            </div>

            {/* Pricing Filter Chips */}
            <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
              <button
                className={`chip ${pricingFilter === 'ALL' ? 'active' : ''}`}
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.82rem' }}
                onClick={() => setPricingFilter('ALL')}
              >
                جميع الحالات
              </button>
              <button
                className={`chip ${pricingFilter === 'PRICED' ? 'active' : ''}`}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.82rem',
                  borderColor: pricingFilter === 'PRICED' ? '#16a34a' : undefined,
                  background: pricingFilter === 'PRICED' ? '#16a34a' : undefined,
                  color: pricingFilter === 'PRICED' ? '#ffffff' : '#15803d',
                }}
                onClick={() => setPricingFilter('PRICED')}
              >
                🏷️ مسعّرة معتمدة ({pricedCount})
              </button>
              <button
                className={`chip ${pricingFilter === 'UNPRICED' ? 'active' : ''}`}
                style={{
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.82rem',
                  borderColor: pricingFilter === 'UNPRICED' ? '#d97706' : undefined,
                  background: pricingFilter === 'UNPRICED' ? '#d97706' : undefined,
                  color: pricingFilter === 'UNPRICED' ? '#ffffff' : '#b45309',
                }}
                onClick={() => setPricingFilter('UNPRICED')}
              >
                ⏳ بانتظار التسعيرة ({unpricedCount})
              </button>
            </div>

            {/* View Switch Buttons */}
            <div
              style={{
                display: 'flex',
                background: '#f1f5f9',
                padding: '2px',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
              }}
            >
              <button
                onClick={() => setViewMode('cards')}
                style={{
                  border: 'none',
                  padding: '0.35rem 0.65rem',
                  borderRadius: '6px',
                  background: viewMode === 'cards' ? '#ffffff' : 'transparent',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                  fontWeight: viewMode === 'cards' ? 700 : 500,
                  boxShadow: viewMode === 'cards' ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
                }}
                title="عرض بطاقات مرئية"
              >
                🎴 بطاقات
              </button>
              <button
                onClick={() => setViewMode('table')}
                style={{
                  border: 'none',
                  padding: '0.35rem 0.65rem',
                  borderRadius: '6px',
                  background: viewMode === 'table' ? '#ffffff' : 'transparent',
                  cursor: 'pointer',
                  fontSize: '0.85rem',
                  fontWeight: viewMode === 'table' ? 700 : 500,
                  boxShadow: viewMode === 'table' ? '0 1px 2px rgba(0,0,0,0.08)' : 'none',
                }}
                title="عرض جدول تفصيلي"
              >
                📋 جدول
              </button>
            </div>
          </div>

          {/* Results Summary Bar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '0.85rem',
              color: 'var(--muted)',
              marginBottom: '0.75rem',
              padding: '0 0.25rem',
            }}
          >
            <div>
              عرض <strong style={{ color: '#0f172a' }}>{filteredDevices.length}</strong> جهاز طبي معتمد
              {selectedCategory && ` في التصنيف المحدد`}
            </div>
            {(searchQuery || selectedCategory || pricingFilter !== 'ALL') && (
              <button
                onClick={() => {
                  setSearchQuery('')
                  setSelectedCategory('')
                  setPricingFilter('ALL')
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--blue)',
                  cursor: 'pointer',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                }}
              >
                إلغاء كافة الفلاتر ✕
              </button>
            )}
          </div>

          {/* 3. PRODUCT LISTING: CARDS OR TABLE */}
          {loadingProducts ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
              {t('common.loading')}
            </div>
          ) : viewMode === 'cards' ? (
            /* ========================================================================= */
            /* YOUTUBE STYLE PRODUCT CARDS GRID                                          */
            /* ========================================================================= */
            <div className="product-grid">
              {filteredDevices.map(({ product, model }) => {
                const img = model.display_image || product.display_image
                const isPriced = !!model.approved_price
                const priceVal = model.approved_price?.base_price

                return (
                  <div key={`${product.id}-${model.id}`} className="product-card">
                    {/* Top Thumbnail (YouTube Video Thumbnail Style) */}
                    <div
                      className="product-thumbnail-container"
                      onClick={() => setSelectedModelDetail({ model, product })}
                    >
                      {img ? (
                        <img
                          src={img}
                          alt={product.name_ar}
                          className="product-thumbnail-img"
                        />
                      ) : (
                        <div style={{ fontSize: '3.5rem' }}>🩺</div>
                      )}

                      {/* Category Tag Overlay */}
                      <span className="thumbnail-category-badge">
                        {product.category_name_ar || 'أجهزة عينية'}
                      </span>

                      {/* Price Badge Overlay (YouTube Duration Badge Style) */}
                      {isPriced ? (
                        <span className="thumbnail-price-badge priced">
                          ${Number(priceVal).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD
                        </span>
                      ) : (
                        <span className="thumbnail-price-badge unpriced">
                          ⏳ بانتظار تسعيرة المصنع
                        </span>
                      )}
                    </div>

                    {/* Card Details Body */}
                    <div className="product-card-body">
                      <h4
                        className="product-card-title"
                        onClick={() => setSelectedModelDetail({ model, product })}
                        title={product.name_ar}
                      >
                        {product.name_ar}
                      </h4>

                      <div className="product-card-subtitle">
                        <span className="product-model-code">{model.model_code}</span>
                        <span style={{ direction: 'ltr', fontSize: '0.75rem' }}>{model.sku}</span>
                      </div>

                      {/* Specs Highlights */}
                      {model.specifications && Object.keys(model.specifications).length > 0 && (
                        <div className="product-card-specs-preview">
                          {Object.entries(model.specifications).slice(0, 2).map(([k, v]) => (
                            <div
                              key={k}
                              style={{
                                textOverflow: 'ellipsis',
                                overflow: 'hidden',
                                whiteSpace: 'nowrap',
                                marginBottom: '2px',
                              }}
                            >
                              <strong style={{ color: '#475569' }}>{k}: </strong>
                              <span>{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Card Actions Footer */}
                    <div className="product-card-footer">
                      <button
                        onClick={() => setSelectedModelDetail({ model, product })}
                        className="btn secondary"
                        style={{ fontSize: '0.8rem', padding: '0.45rem' }}
                      >
                        <span>🔍</span>
                        <span>المواصفات</span>
                      </button>
                      <button
                        onClick={() => handleIssueQuotation(model, product)}
                        className={`btn ${isPriced ? 'success' : ''}`}
                        style={{ fontSize: '0.8rem', padding: '0.45rem' }}
                      >
                        <span>📝</span>
                        <span>عرض سعر</span>
                      </button>
                    </div>
                  </div>
                )
              })}

              {filteredDevices.length === 0 && (
                <div className="card" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '3rem' }}>
                  لم يتم العثور على أجهزة مطابقة لشروط البحث والتصفية.
                </div>
              )}
            </div>
          ) : (
            /* ========================================================================= */
            /* DETAILED DATA TABLE                                                       */
            /* ========================================================================= */
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '60px' }}>صورة الجهاز</th>
                    <th>كود الموديل</th>
                    <th>اسم الجهاز الطبي</th>
                    <th>التصنيف الطبي</th>
                    <th>الحالة السعرية المعتمدة</th>
                    <th>أهم المواصفات</th>
                    <th>الإجراء</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDevices.map(({ product, model }) => {
                    const img = model.display_image || product.display_image
                    const isPriced = !!model.approved_price
                    const priceVal = model.approved_price?.base_price

                    return (
                      <tr key={`${product.id}-${model.id}`}>
                        <td style={{ textAlign: 'center', padding: '0.35rem' }}>
                          <div
                            onClick={() => setSelectedModelDetail({ model, product })}
                            style={{
                              width: '48px',
                              height: '48px',
                              borderRadius: '6px',
                              overflow: 'hidden',
                              background: '#f8fafc',
                              border: '1px solid #cbd5e1',
                              margin: 'auto',
                              cursor: 'pointer',
                              display: 'grid',
                              placeItems: 'center',
                            }}
                          >
                            {img ? (
                              <img
                                src={img}
                                alt={product.name_ar}
                                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                              />
                            ) : (
                              <span>🩺</span>
                            )}
                          </div>
                        </td>
                        <td>
                          <strong>{model.model_code}</strong>
                          <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{model.sku}</div>
                        </td>
                        <td>
                          <div
                            onClick={() => setSelectedModelDetail({ model, product })}
                            style={{ fontWeight: 600, color: '#0f172a', cursor: 'pointer' }}
                          >
                            {product.name_ar}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{product.name_en}</div>
                        </td>
                        <td>{product.category_name_ar || '-'}</td>
                        <td>
                          {isPriced ? (
                            <span
                              className="badge ok"
                              style={{ fontSize: '0.85rem', fontWeight: 700, padding: '0.3rem 0.6rem' }}
                            >
                              ${Number(priceVal).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD
                            </span>
                          ) : (
                            <span
                              style={{
                                background: '#fffbeb',
                                border: '1px solid #fde68a',
                                color: '#b45309',
                                padding: '0.25rem 0.55rem',
                                borderRadius: '4px',
                                fontSize: '0.78rem',
                                fontWeight: 700,
                                display: 'inline-block',
                              }}
                            >
                              ⏳ السعر بانتظار تسعيرة المصنع
                            </span>
                          )}
                        </td>
                        <td style={{ fontSize: '0.8rem', maxWidth: '240px' }}>
                          {model.specifications && Object.keys(model.specifications).length > 0 ? (
                            Object.entries(model.specifications)
                              .slice(0, 2)
                              .map(([k, v]) => (
                                <div key={k} style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                                  <strong>{k}:</strong> {String(v)}
                                </div>
                              ))
                          ) : (
                            <span style={{ color: 'var(--muted)' }}>المواصفات القياسية</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            <button
                              onClick={() => setSelectedModelDetail({ model, product })}
                              className="btn secondary"
                              style={{ fontSize: '0.75rem', padding: '0.3rem 0.5rem' }}
                            >
                              🔍 التفاصيل
                            </button>
                            <button
                              onClick={() => handleIssueQuotation(model, product)}
                              className={`btn ${isPriced ? 'success' : ''}`}
                              style={{ fontSize: '0.75rem', padding: '0.3rem 0.55rem' }}
                            >
                              📝 عرض سعر
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {filteredDevices.length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                        لم يتم العثور على أجهزة مطابقة لشروط البحث والتصفية.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* RICH DEVICE DETAILS & DYNAMIC SPECIFICATIONS MODAL                        */}
      {/* ========================================================================= */}
      {selectedModelDetail && createPortal(
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
          onClick={() => setSelectedModelDetail(null)}
        >
          <div
            className="card"
            style={{
              width: 'min(860px, 96vw)',
              maxHeight: '90vh',
              overflowY: 'auto',
              background: '#ffffff',
              borderRadius: '14px',
              padding: '1.75rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
              border: 'none',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                borderBottom: '1px solid #e2e8f0',
                paddingBottom: '1rem',
                marginBottom: '1.25rem',
              }}
            >
              <div>
                <span className="badge info" style={{ marginBottom: '0.4rem', display: 'inline-block' }}>
                  {selectedModelDetail.product.category_name_ar || 'أجهزة عينية'}
                </span>
                <h2 style={{ margin: '0 0 0.25rem', color: '#0f172a', fontSize: '1.4rem' }}>
                  {selectedModelDetail.product.name_ar}
                </h2>
                <div style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                  {selectedModelDetail.product.name_en} | الموديل: <strong>{selectedModelDetail.model.model_code}</strong> (SKU: {selectedModelDetail.model.sku})
                </div>
              </div>
              <button
                className="btn secondary"
                style={{ padding: '0.4rem 0.75rem', fontSize: '0.9rem' }}
                onClick={() => setSelectedModelDetail(null)}
              >
                ✕ إغلاق
              </button>
            </div>

            {/* Device Visual & Pricing Banner */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(200px, 280px) 1fr',
                gap: '1.25rem',
                marginBottom: '1.5rem',
                alignItems: 'center',
              }}
            >
              {/* Photo */}
              <div
                style={{
                  height: '230px',
                  background: '#f8fafc',
                  border: '1px solid #cbd5e1',
                  borderRadius: '10px',
                  display: 'grid',
                  placeItems: 'center',
                  overflow: 'hidden',
                  padding: '10px',
                }}
              >
                {selectedModelDetail.model.display_image || selectedModelDetail.product.display_image ? (
                  <img
                    src={selectedModelDetail.model.display_image || selectedModelDetail.product.display_image || ''}
                    alt={selectedModelDetail.product.name_ar}
                    style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  />
                ) : (
                  <div style={{ fontSize: '4rem' }}>🩺</div>
                )}
              </div>

              {/* Price & Primary Attributes */}
              <div>
                {/* Pricing Banner */}
                {selectedModelDetail.model.approved_price ? (
                  <div
                    style={{
                      background: '#f0fdf4',
                      border: '1px solid #bbf7d0',
                      borderRadius: '8px',
                      padding: '1rem',
                      marginBottom: '1rem',
                    }}
                  >
                    <div style={{ fontSize: '0.85rem', color: '#166534', fontWeight: 600 }}>
                      ✅ السعر المعتمد لعروض الأسعار الرسمية (قائمة {selectedModelDetail.model.approved_price.price_list_code}):
                    </div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#15803d', margin: '0.35rem 0' }}>
                      ${Number(selectedModelDetail.model.approved_price.base_price).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#166534' }}>
                      الحد الأدنى المسموح به للبيع: ${Number(selectedModelDetail.model.approved_price.min_price).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      background: '#fffbeb',
                      border: '1px solid #fde68a',
                      borderRadius: '8px',
                      padding: '1rem',
                      marginBottom: '1rem',
                    }}
                  >
                    <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#b45309', marginBottom: '0.3rem' }}>
                      ⏳ السعر بانتظار تسعيرة المصنع (لم يصل بعد)
                    </div>
                    <div style={{ fontSize: '0.82rem', color: '#78350f', lineHeight: 1.4 }}>
                      هذا الجهاز مستخرج بالكامل من كتالوج المورد الرسمي (SRD Ophthalmic). لم يتم تحديد سعر تكلفة في كشف الأسعار الأخير، ويمكن تقديم طلب تسعير خاص من المصنع للعميل مباشرة.
                    </div>
                  </div>
                )}

                {/* Quick details pills */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.83rem' }}>
                  <div style={{ background: '#f1f5f9', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                    <span style={{ color: '#64748b' }}>الشركة المصنعة: </span>
                    <strong style={{ color: '#0f172a' }}>{selectedModelDetail.product.manufacturer_name_ar || 'SRD / Heromax'}</strong>
                  </div>
                  <div style={{ background: '#f1f5f9', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                    <span style={{ color: '#64748b' }}>بلد المنشأ: </span>
                    <strong style={{ color: '#0f172a' }}>{selectedModelDetail.model.origin_country || 'China'}</strong>
                  </div>
                  <div style={{ background: '#f1f5f9', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                    <span style={{ color: '#64748b' }}>الضمان القياسي: </span>
                    <strong style={{ color: '#0f172a' }}>{selectedModelDetail.model.standard_warranty_months} شهراً</strong>
                  </div>
                  <div style={{ background: '#f1f5f9', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                    <span style={{ color: '#64748b' }}>التصنيف الطبي: </span>
                    <strong style={{ color: '#0f172a' }}>{selectedModelDetail.product.device_class || 'Class IIa'}</strong>
                  </div>
                </div>
              </div>
            </div>

            {/* DYNAMIC SPECIFICATIONS TABLE (المواصفات الفنية التفصيلية المعتمدة) */}
            <div style={{ marginBottom: '1.5rem' }}>
              <h3
                style={{
                  fontSize: '1.05rem',
                  fontWeight: 700,
                  color: '#0f172a',
                  borderBottom: '2px solid #e2e8f0',
                  paddingBottom: '0.5rem',
                  marginBottom: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                }}
              >
                <span>⚙️</span>
                <span>المواصفات الفنية التفصيلية المعتمدة من الكتالوج الرسمي</span>
              </h3>

              {selectedModelDetail.model.specifications &&
                Object.keys(selectedModelDetail.model.specifications).length > 0 ? (
                <div className="table-container">
                  <table style={{ margin: 0 }}>
                    <thead>
                      <tr>
                        <th style={{ width: '38%', background: '#f8fafc' }}>المعيار / المعلمة الفنية</th>
                        <th style={{ background: '#f8fafc' }}>القيمة والمدى المعتمد من المصنع</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(selectedModelDetail.model.specifications).map(([key, val]) => (
                        <tr key={key}>
                          <td style={{ fontWeight: 600, color: '#334155' }}>{key}</td>
                          <td style={{ color: '#0f172a' }}>{String(val)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: '6px', color: 'var(--muted)', textAlign: 'center' }}>
                  المواصفات الفنية القياسية للموديل وفق كراسة المورد.
                </div>
              )}
            </div>

            {/* Standard Accessories & Power */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '1rem',
                marginBottom: '1.5rem',
              }}
            >
              {selectedModelDetail.model.power_requirements && (
                <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#475569', marginBottom: '0.35rem' }}>
                    ⚡ متطلبات الطاقة والجهد الكهربائي:
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#0f172a' }}>
                    {selectedModelDetail.model.power_requirements}
                  </div>
                </div>
              )}

              {selectedModelDetail.model.standard_accessories && (
                <div style={{ background: '#f8fafc', padding: '0.85rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#475569', marginBottom: '0.35rem' }}>
                    📦 الملحقات القياسية المرفقة مع الجهاز:
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#0f172a', lineHeight: 1.4 }}>
                    {selectedModelDetail.model.standard_accessories}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer Actions */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                gap: '0.75rem',
                borderTop: '1px solid #e2e8f0',
                paddingTop: '1.25rem',
                flexWrap: 'wrap',
              }}
            >
              <button
                className="btn secondary"
                onClick={() => setSelectedModelDetail(null)}
              >
                إغلاق النافذة
              </button>
              <button
                className={`btn ${selectedModelDetail.model.approved_price ? 'success' : ''}`}
                style={{
                  padding: '0.65rem 1.4rem',
                  fontSize: '0.95rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                }}
                onClick={() => handleIssueQuotation(selectedModelDetail.model, selectedModelDetail.product)}
              >
                <span>📝</span>
                <span>
                  {selectedModelDetail.model.approved_price
                    ? 'إصدار عرض سعر معتمد لهذا الجهاز'
                    : 'إصدار عرض سعر / طلب تسعير للموديل'}
                </span>
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* ========================================================================= */}
      {/* INSTANT POP-UP QUOTATION ISSUANCE MODAL                                   */}
      {/* ========================================================================= */}
      {quoteModalItem && createPortal(
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.72)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999,
            padding: '1rem',
          }}
          onClick={() => {
            if (!isSubmittingQuote) setQuoteModalItem(null)
          }}
        >
          <div
            className="card"
            style={{
              width: 'min(760px, 96vw)',
              maxHeight: '92vh',
              overflowY: 'auto',
              background: '#ffffff',
              borderRadius: '14px',
              padding: '1.75rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
              border: 'none',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* SUCCESS SCREEN */}
            {createdQuoteSuccess ? (
              <div style={{ textAlign: 'center', padding: '1.5rem 1rem' }}>
                <div style={{ fontSize: '3.5rem', marginBottom: '0.75rem' }}>🎉</div>
                <h2 style={{ color: '#166534', margin: '0 0 0.5rem', fontSize: '1.5rem' }}>
                  تم إصدار عرض السعر الرسمي بنجاح!
                </h2>
                <p style={{ color: '#475569', fontSize: '0.92rem', marginBottom: '1.5rem' }}>
                  تم حفظ وتوثيق عرض السعر في قاعدة البيانات وفق المعايير المصنعية المعتمدة.
                </p>

                <div
                  style={{
                    background: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    borderRadius: '10px',
                    padding: '1.25rem',
                    maxWidth: '480px',
                    margin: '0 auto 1.75rem',
                    textAlign: 'right',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ color: '#64748b', fontSize: '0.85rem' }}>رقم عرض السعر:</span>
                    <strong style={{ color: '#0f172a' }}>{createdQuoteSuccess.quotation_number}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ color: '#64748b', fontSize: '0.85rem' }}>العميل / المستفيد:</span>
                    <strong style={{ color: '#0f172a' }}>{createdQuoteSuccess.customer_name}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ color: '#64748b', fontSize: '0.85rem' }}>الجهاز والموديل:</span>
                    <strong style={{ color: '#0f172a' }}>{quoteModalItem.product.name_ar} ({quoteModalItem.model.model_code})</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #bbf7d0', paddingTop: '0.5rem', marginTop: '0.5rem' }}>
                    <span style={{ color: '#166534', fontWeight: 700 }}>الإجمالي الصافي المعتمد:</span>
                    <strong style={{ color: '#15803d', fontSize: '1.2rem' }}>
                      ${Number(createdQuoteSuccess.latest_version?.total_amount || quoteModalCalculatedTotal).toLocaleString('en-US', { minimumFractionDigits: 2 })} {quoteForm.currency}
                    </strong>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <button
                    className="btn secondary"
                    onClick={() => setQuoteModalItem(null)}
                  >
                    ✓ إغلاق ومتابعة تصفح الكتالوج
                  </button>
                  <button
                    className="btn success"
                    onClick={() => {
                      setQuoteModalItem(null)
                      navigate('/quotations')
                    }}
                  >
                    🖨️ فتح وثيقة العرض للمعاينة والطباعة
                  </button>
                </div>
              </div>
            ) : (
              /* QUOTATION ISSUANCE FORM */
              <div>
                {/* Header */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    borderBottom: '1px solid #e2e8f0',
                    paddingBottom: '0.85rem',
                    marginBottom: '1.25rem',
                  }}
                >
                  <div>
                    <h3 style={{ margin: '0 0 0.25rem', color: '#0f172a', fontSize: '1.25rem' }}>
                      📝 إصدار عرض سعر رسمي مباشر
                    </h3>
                    <div style={{ color: 'var(--muted)', fontSize: '0.82rem' }}>
                      الوكالة الحصرية للأجهزة الطبية — SRD Ophthalmic Instruments / Heromax
                    </div>
                  </div>
                  <button
                    className="btn secondary"
                    style={{ padding: '0.35rem 0.65rem', fontSize: '0.85rem' }}
                    onClick={() => setQuoteModalItem(null)}
                    disabled={isSubmittingQuote}
                  >
                    ✕ إغلاق
                  </button>
                </div>

                {/* Device Visual & Summary Box */}
                <div
                  style={{
                    display: 'flex',
                    gap: '1rem',
                    alignItems: 'center',
                    background: '#f8fafc',
                    border: '1px solid #cbd5e1',
                    borderRadius: '10px',
                    padding: '0.85rem 1rem',
                    marginBottom: '1.25rem',
                  }}
                >
                  <div
                    style={{
                      width: '64px',
                      height: '64px',
                      background: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      display: 'grid',
                      placeItems: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {quoteModalItem.model.display_image || quoteModalItem.product.display_image ? (
                      <img
                        src={quoteModalItem.model.display_image || quoteModalItem.product.display_image || ''}
                        alt={quoteModalItem.product.name_ar}
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                    ) : (
                      <span style={{ fontSize: '1.8rem' }}>🩺</span>
                    )}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 800, color: '#0f172a', fontSize: '1rem' }}>
                      {quoteModalItem.product.name_ar}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                      الموديل: <strong>{quoteModalItem.model.model_code}</strong> | SKU: {quoteModalItem.model.sku}
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.35rem', flexWrap: 'wrap' }}>
                      {quoteModalItem.model.approved_price ? (
                        <span className="badge ok" style={{ fontSize: '0.8rem', fontWeight: 700 }}>
                          السعر المعتمد: ${Number(quoteModalItem.model.approved_price.base_price).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD
                        </span>
                      ) : (
                        <span style={{ background: '#fffbeb', border: '1px solid #fde68a', color: '#b45309', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.78rem', fontWeight: 700 }}>
                          ⏳ بانتظار تسعيرة المصنع (يمكنك تحديد سعر تقديري للعرض)
                        </span>
                      )}
                      <span className="badge" style={{ fontSize: '0.8rem' }}>
                        الضمان القياسي: {quoteModalItem.model.standard_warranty_months || 24} شهراً
                      </span>
                    </div>
                  </div>
                </div>

                {/* Form Inputs Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                  <div className="field">
                    <label style={{ fontWeight: 700 }}>العميل / المستشفى المستفيد *</label>
                    <select
                      value={quoteForm.customer}
                      onChange={(e) => setQuoteForm({ ...quoteForm, customer: e.target.value })}
                      style={{ width: '100%', padding: '0.55rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                    >
                      <option value="">— اختر العميل أو المستشفى —</option>
                      {customersData?.results?.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.legal_name_ar} ({c.customer_number})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="field">
                    <label style={{ fontWeight: 700 }}>نموذج التعاقد والعملة</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <select
                        value={quoteForm.commercial_model}
                        onChange={(e) => setQuoteForm({ ...quoteForm, commercial_model: e.target.value })}
                        style={{ flex: 1, padding: '0.55rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                      >
                        <option value="DIRECT_SALE">بيع مباشر (Direct Sale)</option>
                        <option value="AGENCY">وكالة وعمولة (Agency)</option>
                      </select>
                      <select
                        value={quoteForm.currency}
                        onChange={(e) => setQuoteForm({ ...quoteForm, currency: e.target.value })}
                        style={{ width: '90px', padding: '0.55rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                      >
                        <option value="USD">USD ($)</option>
                        <option value="YER">YER</option>
                        <option value="SAR">SAR</option>
                      </select>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.85rem', marginBottom: '1.25rem' }}>
                  <div className="field">
                    <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>الكمية المطلوبة</label>
                    <input
                      type="number"
                      min="1"
                      value={quoteForm.quantity}
                      onChange={(e) => setQuoteForm({ ...quoteForm, quantity: Number(e.target.value) || 1 })}
                      style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                    />
                  </div>

                  <div className="field">
                    <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>سعر الوحدة ({quoteForm.currency})</label>
                    <input
                      type="number"
                      step="0.01"
                      value={quoteForm.unit_price}
                      onChange={(e) => setQuoteForm({ ...quoteForm, unit_price: e.target.value })}
                      style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                    />
                  </div>

                  <div className="field">
                    <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>نسبة الخصم %</label>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={quoteForm.discount_pct}
                      onChange={(e) => setQuoteForm({ ...quoteForm, discount_pct: e.target.value })}
                      style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                    />
                  </div>

                  <div className="field">
                    <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>مدة الضمان (شهراً)</label>
                    <input
                      type="number"
                      value={quoteForm.warranty_months}
                      onChange={(e) => setQuoteForm({ ...quoteForm, warranty_months: Number(e.target.value) || 24 })}
                      style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                    />
                  </div>
                </div>

                {/* Live Total Calculation Banner */}
                <div
                  style={{
                    background: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
                    border: '1px solid #86efac',
                    borderRadius: '8px',
                    padding: '0.85rem 1.25rem',
                    marginBottom: '1.25rem',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.82rem', color: '#166534', fontWeight: 600 }}>
                      إجمالي قيمة العرض المعتمد:
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#15803d' }}>
                      الكمية: {quoteForm.quantity} • الخصم: {quoteForm.discount_pct}%
                    </div>
                  </div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#15803d' }}>
                    ${quoteModalCalculatedTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {quoteForm.currency}
                  </div>
                </div>

                {/* Commercial Terms */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.85rem', marginBottom: '1.25rem' }}>
                  <div className="field">
                    <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>شروط الدفع والتحصيل</label>
                    <input
                      value={quoteForm.payment_terms}
                      onChange={(e) => setQuoteForm({ ...quoteForm, payment_terms: e.target.value })}
                      style={{ width: '100%', padding: '0.45rem', fontSize: '0.82rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                    />
                  </div>
                  <div className="field">
                    <label style={{ fontSize: '0.8rem', fontWeight: 600 }}>شروط التسليم والتركيب والتدريب</label>
                    <input
                      value={quoteForm.delivery_terms}
                      onChange={(e) => setQuoteForm({ ...quoteForm, delivery_terms: e.target.value })}
                      style={{ width: '100%', padding: '0.45rem', fontSize: '0.82rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                    />
                  </div>
                </div>

                {/* Error Banner if any */}
                {quoteSubmitError && (
                  <div
                    style={{
                      background: '#fef2f2',
                      border: '1px solid #fca5a5',
                      color: '#b91c1c',
                      padding: '0.65rem 0.85rem',
                      borderRadius: '6px',
                      fontSize: '0.85rem',
                      marginBottom: '1rem',
                    }}
                  >
                    ⚠️ {quoteSubmitError}
                  </div>
                )}

                {/* Footer Actions */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: '0.75rem',
                    borderTop: '1px solid #e2e8f0',
                    paddingTop: '1rem',
                  }}
                >
                  <button
                    className="btn secondary"
                    onClick={() => setQuoteModalItem(null)}
                    disabled={isSubmittingQuote}
                  >
                    إلغاء
                  </button>
                  <button
                    className="btn success"
                    style={{ padding: '0.6rem 1.4rem', fontSize: '0.92rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                    onClick={handleSubmitQuotation}
                    disabled={isSubmittingQuote}
                  >
                    {isSubmittingQuote ? (
                      <span>جاري إصدار العرض...</span>
                    ) : (
                      <>
                        <span>✓</span>
                        <span>تأكيد وإصدار عرض السعر فوراً</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}
