import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'

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

interface ExtractionField {
  id: string
  field_key: string
  extracted_value: string
  corrected_value: string
  page_number: number
  confidence: string | number
  is_approved: boolean
  is_unknown_or_missing: boolean
}

interface ExtractionJob {
  id: string
  job_number: string
  document: string
  document_title?: string
  document_number?: string
  target_entity_type: string
  status: string
  provider: string
  confidence_score: string | number
  reviewed_by_name?: string
  reviewed_at?: string
  review_notes?: string
  raw_response?: any
  fields?: ExtractionField[]
  created_at: string
}

export default function DocumentsAIPage() {
  const { t } = useTranslation()
  const { can } = useAuth()
  const [tab, setTab] = useState<'docs' | 'jobs'>('docs')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Data
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [jobs, setJobs] = useState<ExtractionJob[]>([])

  // Modals
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [selectedJob, setSelectedJob] = useState<ExtractionJob | null>(null)
  const [triggerJobDoc, setTriggerJobDoc] = useState<DocumentItem | null>(null)

  // Forms
  const [newDocForm, setNewDocForm] = useState({
    title: '',
    document_type: 'CATALOG_BROCHURE',
    language: 'en',
  })
  const [autoExtractOnUpload, setAutoExtractOnUpload] = useState(true)
  const [uploadTargetEntity, setUploadTargetEntity] = useState('PRODUCT_SPECS')
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractionStatusText, setExtractionStatusText] = useState('')

  const [triggerForm, setTriggerForm] = useState({
    target_entity_type: 'PRODUCT_SPECS',
    provider: 'GEMINI_FLASH_GATEWAY',
  })

  const [fieldCorrections, setFieldCorrections] = useState<Record<string, string>>({})
  const [reviewNotes, setReviewNotes] = useState('')

  const loadDocuments = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: DocumentItem[] }>('/documents/documents/')
      setDocuments(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadJobs = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: ExtractionJob[] }>('/documents/extractions/')
      setJobs(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (tab === 'docs') loadDocuments()
    if (tab === 'jobs') loadJobs()
  }, [tab])

  const handleCreateDocument = async () => {
    const title = newDocForm.title.trim() || (selectedFile ? selectedFile.name.replace(/\.[^/.]+$/, '') : '')
    if (!title) {
      alert('يرجى اختيار ملف PDF أو كتابة عنوان المستند')
      return
    }
    setIsExtracting(true)
    setExtractionStatusText('جاري رفع المستند إلى السيرفر...')
    try {
      let createdDoc: DocumentItem
      if (selectedFile) {
        const formData = new FormData()
        formData.append('title', title)
        formData.append('document_type', newDocForm.document_type)
        formData.append('language', newDocForm.language)
        formData.append('file', selectedFile)

        createdDoc = await api<DocumentItem>('/documents/documents/', {
          method: 'POST',
          body: formData,
        })
      } else {
        createdDoc = await api<DocumentItem>('/documents/documents/', {
          method: 'POST',
          json: { ...newDocForm, title },
        })
      }

      if (autoExtractOnUpload) {
        setExtractionStatusText('جاري تحليل الصفحات واستخراج الأجهزة والمستلزمات الطبية بواسطة محرك Gemini Vision وقص صورها...')
        const job = await api<ExtractionJob>(`/documents/documents/${createdDoc.id}/trigger_extraction/`, {
          method: 'POST',
          json: {
            target_entity_type: uploadTargetEntity,
            provider: 'GEMINI_2_5_FLASH_VISION',
          },
        })
        const itemsCount = job.raw_response?.parsed_items_count || (job.raw_response?.items?.length || 0)
        setShowUploadModal(false)
        setSelectedFile(null)
        setNewDocForm({ title: '', document_type: 'CATALOG_BROCHURE', language: 'en' })
        loadDocuments()
        loadJobs()
        setTab('jobs')
        alert(`🎉 نجاح الاستخراج والنشر المباشر!\nتم استخراج ${itemsCount} صنف وموديل طبي بدقة مع صورها ومواصفاتها وأسعارها ونُشرت مباشرة في الكتالوج الطبي.\n\nيمكنك الآن فتح صفحة "الكتالوج الطبي" لمشاهدة جميع الأجهزة!`)
      } else {
        alert('تم رفع وحفظ المستند في الأرشيف بنجاح')
        setShowUploadModal(false)
        setSelectedFile(null)
        setNewDocForm({ title: '', document_type: 'CATALOG_BROCHURE', language: 'en' })
        loadDocuments()
      }
    } catch (e: any) {
      alert(e.message || t('common.error'))
    } finally {
      setIsExtracting(false)
      setExtractionStatusText('')
    }
  }

  const handleTriggerExtraction = async () => {
    if (!triggerJobDoc) return
    try {
      await api(`/documents/documents/${triggerJobDoc.id}/trigger_extraction/`, {
        method: 'POST',
        json: triggerForm,
      })
      alert('تم تشغيل استخراج البيانات بالذكاء الاصطناعي بنجاح وجاري المراجعة')
      setTriggerJobDoc(null)
      setTab('jobs')
      loadJobs()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleReviewDecision = async (isApproved: boolean) => {
    if (!selectedJob) return
    try {
      await api(`/documents/extractions/${selectedJob.id}/review/`, {
        method: 'POST',
        json: {
          field_corrections: fieldCorrections,
          is_approved: isApproved,
          review_notes: reviewNotes,
        },
      })
      alert(isApproved ? 'تم اعتماد البيانات المستخرجة وتحديثها بنجاح' : 'تم رفض مخرجات المهمة')
      setSelectedJob(null)
      setFieldCorrections({})
      setReviewNotes('')
      loadJobs()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  return (
    <div className="documents-ai-page">
      <div className="page-header">
        <div className="page-header-title">
          <span className="page-header-icon">🤖</span>
          <div>
            <h1>{t('documents.title')}</h1>
            <p>أرشفة مستندات الموردين والكتالوجات واستخراج المواصفات والأسعار تلقائياً بالذكاء الاصطناعي</p>
          </div>
        </div>
        <div className="page-header-actions">
          {can('documents.document.create') && (
            <button className="btn" onClick={() => setShowUploadModal(true)}>
              + {t('documents.newDoc')}
            </button>
          )}
        </div>
      </div>

      <div className="tabs">
        <button className={tab === 'docs' ? 'active' : ''} onClick={() => setTab('docs')}>
          📁 {t('documents.docsTab')}
        </button>
        <button className={tab === 'jobs' ? 'active' : ''} onClick={() => setTab('jobs')}>
          ⚡ {t('documents.extractionsTab')}
        </button>
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      {/* Tab: Documents Archive */}
      {tab === 'docs' && (
        <div className="card fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ margin: 0 }}>{t('documents.docsTab')}</h3>
          </div>

          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <div className="table-container">
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>{t('documents.number')}</th>
                    <th>{t('documents.docTitle')}</th>
                    <th>{t('documents.docType')}</th>
                    <th>{t('documents.language')}</th>
                    <th>{t('documents.uploadedBy')}</th>
                    <th>{t('documents.date')}</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((d) => (
                    <tr key={d.id}>
                      <td style={{ fontWeight: 'bold' }}>{d.document_number}</td>
                      <td>
                        <div><strong>{d.title}</strong></div>
                        {d.file && (
                          <div style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>
                            <a href={d.file} target="_blank" rel="noreferrer" style={{ color: '#2b6cb0', textDecoration: 'underline' }}>
                              📕 فتح ملف الـ PDF المرفق {d.file_size ? `(${(d.file_size / 1024 / 1024).toFixed(2)} MB)` : ''}
                            </a>
                          </div>
                        )}
                      </td>
                      <td>
                        <span className="badge">
                          {t(`documents.docTypes.${d.document_type}` as any) || d.document_type}
                        </span>
                      </td>
                      <td>{d.language.toUpperCase()}</td>
                      <td>{d.uploaded_by_name || '-'}</td>
                      <td>{d.created_at.split('T')[0]}</td>
                      <td>
                        {can('documents.extraction.create') && (
                          <button
                            className="btn"
                            style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
                            onClick={() => setTriggerJobDoc(d)}
                          >
                            ⚡ {t('documents.triggerExtract')}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab: AI Extraction Jobs */}
      {tab === 'jobs' && (
        <div className="card fade-in">
          <h3 style={{ margin: '0 0 1rem' }}>{t('documents.extractionsTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <div className="table-container">
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>{t('documents.jobNumber')}</th>
                    <th>المستند</th>
                    <th>{t('documents.targetEntity')}</th>
                    <th>{t('documents.provider')}</th>
                    <th>{t('documents.confidence')}</th>
                    <th>{t('documents.status')}</th>
                    <th>المراجع البشري</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id}>
                      <td style={{ fontWeight: 'bold' }}>{j.job_number}</td>
                      <td>{j.document_title}</td>
                      <td>{j.target_entity_type}</td>
                      <td><small>{j.provider}</small></td>
                      <td>
                        <span style={{ fontWeight: 'bold', color: Number(j.confidence_score) > 0.9 ? 'green' : 'orange' }}>
                          {(Number(j.confidence_score) * 100).toFixed(1)}%
                        </span>
                      </td>
                      <td>
                        <span className={`badge status-${j.status.toLowerCase()}`}>
                          {t(`documents.extractionStatuses.${j.status}` as any) || j.status}
                        </span>
                      </td>
                      <td>{j.reviewed_by_name || 'بانتظار المراجعة'}</td>
                      <td>
                        <button
                          className="btn secondary"
                          style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
                          onClick={async () => {
                            const refreshed = await api<ExtractionJob>(`/documents/extractions/${j.id}/`)
                            setSelectedJob(refreshed)
                            const initialCorr: Record<string, string> = {}
                            refreshed.fields?.forEach((f) => {
                              if (f.corrected_value) initialCorr[f.field_key] = f.corrected_value
                            })
                            setFieldCorrections(initialCorr)
                            setReviewNotes(refreshed.review_notes || '')
                          }}
                        >
                          {j.status === 'AWAITING_REVIEW' && can('documents.extraction.approve') ? 'مراجعة واعتماد' : 'عرض'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Upload Doc Modal */}
      {showUploadModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '540px', maxWidth: '95%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0 }}>رفع مستند أو كتالوج جديد</h3>
              <button className="btn secondary" style={{ padding: '0.2rem 0.5rem' }} onClick={() => setShowUploadModal(false)}>✕</button>
            </div>

            {/* File Drag & Drop / Selector */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                ملف الكتالوج أو المستند (PDF, Excel, Word, Image):
              </label>
              <div style={{
                border: selectedFile ? '2px solid #3182ce' : '2px dashed #cbd5e0',
                borderRadius: '8px',
                padding: '1.25rem',
                textAlign: 'center',
                background: selectedFile ? '#ebf8ff' : '#f7fafc',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}>
                <input
                  type="file"
                  id="fileUploadInput"
                  style={{ display: 'none' }}
                  accept=".pdf,.doc,.docx,.xls,.xlsx,image/*"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) {
                      setSelectedFile(file)
                      if (!newDocForm.title) {
                        setNewDocForm(prev => ({ ...prev, title: file.name.replace(/\.[^/.]+$/, '') }))
                      }
                    }
                  }}
                />
                <label htmlFor="fileUploadInput" style={{ cursor: 'pointer', display: 'block' }}>
                  <div style={{ fontSize: '2.2rem', marginBottom: '0.4rem' }}>
                    {selectedFile?.name.endsWith('.pdf') ? '📕' : selectedFile ? '📄' : '📁'}
                  </div>
                  {selectedFile ? (
                    <div>
                      <strong style={{ color: '#2b6cb0', fontSize: '1rem' }}>{selectedFile.name}</strong>
                      <div style={{ fontSize: '0.8rem', color: '#718096', marginTop: '0.25rem' }}>
                        الحجم: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB • انقر لاختيار ملف آخر
                      </div>
                    </div>
                  ) : (
                    <div>
                      <strong style={{ color: '#2d3748', fontSize: '0.95rem' }}>انقر هنا لاختيار ملف PDF أو الكتالوج من جهازك</strong>
                      <div style={{ fontSize: '0.8rem', color: '#a0aec0', marginTop: '0.25rem' }}>
                        يدعم ملفات PDF، جداول Excel، Word، والصور حتى 50MB
                      </div>
                    </div>
                  )}
                </label>
              </div>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label>{t('documents.docTitle')} *</label>
              <input
                style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                value={newDocForm.title}
                onChange={(e) => setNewDocForm({ ...newDocForm, title: e.target.value })}
                placeholder="مثال: كتالوج جهاز أشعة DR-500 أو قائمة أسعار 2026..."
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              <div>
                <label>{t('documents.docType')}</label>
                <select
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                  value={newDocForm.document_type}
                  onChange={(e) => setNewDocForm({ ...newDocForm, document_type: e.target.value })}
                >
                  <option value="CATALOG_BROCHURE">كتالوج ومواصفات الموديل (PDF)</option>
                  <option value="PROFORMA_INVOICE">فاتورة مبدئية PI (الصين)</option>
                  <option value="COMMERCIAL_INVOICE">فاتورة تجارية CI</option>
                  <option value="PACKING_LIST">كشف التعبئة والتغليف PL</option>
                  <option value="BILL_OF_LADING">بوليصة الشحن B/L</option>
                  <option value="SERVICE_MANUAL">دليل الصيانة والتشغيل</option>
                  <option value="WARRANTY_CERTIFICATE">شهادة الضمان المصنعي</option>
                  <option value="OTHER">أخرى</option>
                </select>
              </div>
              <div>
                <label>{t('documents.language')}</label>
                <select
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid var(--border)' }}
                  value={newDocForm.language}
                  onChange={(e) => setNewDocForm({ ...newDocForm, language: e.target.value })}
                >
                  <option value="en">English (الإنجليزية)</option>
                  <option value="zh">Chinese (الصينية 中文)</option>
                  <option value="ar">Arabic (العربية)</option>
                </select>
              </div>
            </div>

            <div style={{
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: '8px',
              padding: '0.85rem',
              marginBottom: '1rem',
            }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: 600, color: '#166534' }}>
                <input
                  type="checkbox"
                  checked={autoExtractOnUpload}
                  onChange={(e) => setAutoExtractOnUpload(e.target.checked)}
                />
                ⚡ بدء استخراج البيانات بالذكاء الاصطناعي آلياً بعد الرفع مباشرة
              </label>
              {autoExtractOnUpload && (
                <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.85rem', color: '#166534' }}>الهدف من الاستخراج:</span>
                  <select
                    style={{ flex: 1, padding: '0.35rem', borderRadius: '4px', border: '1px solid #86efac' }}
                    value={uploadTargetEntity}
                    onChange={(e) => setUploadTargetEntity(e.target.value)}
                  >
                    <option value="PRODUCT_SPECS">مواصفات جهاز طبي وكتالوج (نشر في الكتالوج)</option>
                    <option value="PRICE_LIST">قائمة أسعار مورد (تحديث قائمة الأسعار)</option>
                    <option value="SPARE_PARTS">قائمة قطع غيار</option>
                  </select>
                </div>
              )}
            </div>

            {isExtracting && (
              <div style={{
                margin: '1.25rem 0',
                padding: '1rem',
                background: '#eff6ff',
                borderRadius: '10px',
                border: '1.5px solid #93c5fd',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '1.75rem', marginBottom: '0.4rem' }}>
                  ⚡
                </div>
                <strong style={{ display: 'block', color: '#1e3a8a', fontSize: '0.95rem', marginBottom: '0.35rem' }}>
                  {extractionStatusText}
                </strong>
                <div style={{ fontSize: '0.8rem', color: '#2563eb' }}>
                  يقوم محرك الذكاء الاصطناعي البصري (Gemini Vision) بتحليل صفحات الكتالوج، واستخراج المواصفات، وقص وحفظ صور الأجهزة...
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                className="btn secondary"
                disabled={isExtracting}
                onClick={() => { setShowUploadModal(false); setSelectedFile(null); }}
              >
                {t('common.cancel')}
              </button>
              <button
                className="btn"
                disabled={isExtracting}
                onClick={handleCreateDocument}
              >
                {isExtracting ? '⏳ جاري الاستخراج والمعالجة…' : (selectedFile ? (autoExtractOnUpload ? '⚡ رفع وبدء الاستخراج الفوري' : '📤 رفع وحفظ الملف') : t('common.save'))}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Trigger Extraction Modal */}
      {triggerJobDoc && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '500px', maxWidth: '90%' }}>
            <h3>تشغيل استخراج الذكاء الاصطناعي للمستند</h3>
            <p><strong>المستند:</strong> {triggerJobDoc.document_number} - {triggerJobDoc.title}</p>

            <div style={{ marginBottom: '12px' }}>
              <label>الكيان والبيانات المستهدفة للاستخراج:</label>
              <select
                style={{ width: '100%', marginTop: '4px' }}
                value={triggerForm.target_entity_type}
                onChange={(e) => setTriggerForm({ ...triggerForm, target_entity_type: e.target.value })}
              >
                <option value="PRODUCT_SPECS">مواصفات موديل طبي (اسم، SKU، كهرباء، ضمان)</option>
                <option value="PRICE_LIST">قائمة أسعار مورد (أسعار شراء وهامش)</option>
                <option value="SPARE_PARTS">قائمة قطع غيار</option>
                <option value="SHIPMENT_DOC">بيانات شحنة وبوليصة B/L</option>
                <option value="INVOICE">بيانات فاتورة مورد ومطابقة</option>
              </select>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label>بوابة الذكاء الاصطناعي (AI Gateway Provider):</label>
              <select
                style={{ width: '100%', marginTop: '4px' }}
                value={triggerForm.provider}
                onChange={(e) => setTriggerForm({ ...triggerForm, provider: e.target.value })}
              >
                <option value="GEMINI_FLASH_GATEWAY">Google Gemini 2.0 Flash (سريع، دقيق، منخفض التكلفة)</option>
                <option value="GEMINI_PRO_GATEWAY">Google Gemini 2.0 Pro (للمستندات المعقدة والمتعددة اللغات)</option>
                <option value="MOCK_AI_GATEWAY">Simulated Local Gateway (اختبار تجريبي)</option>
              </select>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '1rem' }}>
              <button className="btn secondary" onClick={() => setTriggerJobDoc(null)}>{t('common.cancel')}</button>
              <button className="btn" onClick={handleTriggerExtraction}>
                ⚡ بدء الاستخراج الآلي
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Human-in-the-Loop Review Modal (§5.12) */}
      {selectedJob && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: '1rem' }}>
          <div className="card fade-in" style={{ width: '850px', maxWidth: '95%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
              <h3 style={{ margin: 0 }}>المراجعة والاعتماد البشري لمهمة الاستخراج {selectedJob.job_number}</h3>
              <button className="btn secondary" style={{ padding: '0.2rem 0.5rem' }} onClick={() => setSelectedJob(null)}>✕</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px', background: '#f8fafc', padding: '0.75rem', borderRadius: '8px' }}>
              <div><strong>المستند الأصلي:</strong> {selectedJob.document_title}</div>
              <div><strong>بوابة المزود:</strong> {selectedJob.provider}</div>
              <div><strong>الحالة:</strong> {selectedJob.status}</div>
              <div><strong>متوسط نسبة الثقة:</strong> {(Number(selectedJob.confidence_score) * 100).toFixed(1)}%</div>
            </div>

            <div style={{ backgroundColor: '#eff6ff', padding: '10px', borderRadius: '6px', marginBottom: '16px', borderRight: '4px solid #0284c7' }}>
              <strong>مبدأ الحوكمة (§5.12):</strong> لا يتم اعتماد وتمرير أي بيانات مستخرجة بالذكاء الاصطناعي إلى الكتالوج أو الأسعار دون مراجعة بشرية وتدقيق المصدر.
            </div>

            <h4>الحقول المستخرجة ومطابقتها</h4>
            <table className="table" style={{ width: '100%', marginBottom: '16px' }}>
              <thead>
                <tr>
                  <th>اسم الحقل</th>
                  <th>القيمة المستخرجة (AI)</th>
                  <th>الصفحة</th>
                  <th>نسبة الثقة</th>
                  <th>التصحيح البشري (إن وجد)</th>
                </tr>
              </thead>
              <tbody>
                {selectedJob.fields?.map((f) => (
                  <tr key={f.id} style={{ backgroundColor: f.is_unknown_or_missing ? '#fffbeb' : 'inherit' }}>
                    <td style={{ fontWeight: 'bold' }}>{f.field_key}</td>
                    <td>
                      {f.extracted_value}
                      {f.is_unknown_or_missing && (
                        <span className="badge" style={{ backgroundColor: '#f59e0b', color: '#fff', marginRight: '6px' }}>
                          غير موجود بالنص / يحتاج مراجعة
                        </span>
                      )}
                    </td>
                    <td>{f.page_number}</td>
                    <td>{(Number(f.confidence) * 100).toFixed(0)}%</td>
                    <td>
                      <input
                        style={{ width: '100%' }}
                        value={fieldCorrections[f.field_key] !== undefined ? fieldCorrections[f.field_key] : f.corrected_value || ''}
                        onChange={(e) =>
                          setFieldCorrections({
                            ...fieldCorrections,
                            [f.field_key]: e.target.value,
                          })
                        }
                        placeholder={f.extracted_value}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>ملاحظات وتوثيق المراجعة البشرية:</label>
              <textarea
                style={{ width: '100%', minHeight: '60px' }}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                placeholder="ملاحظات التدقيق والمطابقة مع المستند الورقي أو الأصلي..."
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', borderTop: '1px solid #e2e8f0', paddingTop: '0.75rem' }}>
              <button className="btn secondary" onClick={() => setSelectedJob(null)}>إغلاق</button>
              {selectedJob.status === 'AWAITING_REVIEW' && can('documents.extraction.approve') && (
                <>
                  <button className="btn secondary" onClick={() => handleReviewDecision(false)} style={{ color: '#dc2626', borderColor: '#fca5a5' }}>
                    ✕ رفض المخرجات
                  </button>
                  <button className="btn ok" onClick={() => handleReviewDecision(true)}>
                    ✓ اعتماد وتمرير البيانات للكتالوج
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
