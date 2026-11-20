import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'

interface ServiceVisit {
  id: string
  engineer_name?: string
  visit_date: string
  actions_taken: string
  diagnostic_details: string
  is_resolved: boolean
  customer_sign_off_name?: string
}

interface SparePart {
  id: string
  part_name: string
  part_sku: string
  quantity: number
  coverage: string
  status: string
  cost_price: string | number
  customer_price: string | number
  approved_by_name?: string
}

interface ServiceTicket {
  id: string
  ticket_number: string
  ticket_type: string
  priority: string
  asset: string
  asset_serial?: string
  model_name?: string
  customer: string
  customer_name?: string
  assigned_engineer?: string
  assigned_engineer_name?: string
  title: string
  reported_issue: string
  diagnostic_findings?: string
  resolution_summary?: string
  warranty_status: string
  status: string
  labor_hours: string | number
  labor_cost: string | number
  parts_cost: string | number
  total_cost: string | number
  visits?: ServiceVisit[]
  spare_parts?: SparePart[]
  created_at: string
}

interface InstallationProtocol {
  id: string
  protocol_number: string
  asset: string
  asset_serial?: string
  model_name?: string
  customer: string
  customer_name?: string
  location: string
  installed_at: string
  lead_engineer: string
  lead_engineer_name?: string
  status: string
  electrical_safety_passed: boolean
  performance_verification_passed: boolean
  user_training_completed: boolean
  trainees_list?: string
  customer_representative_name?: string
  customer_representative_title?: string
  customer_signed_at?: string
  notes?: string
}

interface WarrantyContract {
  id: string
  contract_number: string
  asset: string
  asset_serial?: string
  model_name?: string
  customer?: string
  customer_name?: string
  warranty_type: string
  start_date: string
  end_date: string
  sla_response_hours: number
  coverage_details?: string
  is_active: boolean
}

interface UserOption {
  id: string
  email: string
  full_name?: string
}

interface AssetOption {
  id: string
  serial_number: string
  model_name?: string
}

interface CustomerOption {
  id: string
  legal_name_ar: string
}

interface LocationOption {
  id: string
  name_ar: string
}

export default function BiomedicalPage() {
  const { t } = useTranslation()
  const { can } = useAuth()
  const [tab, setTab] = useState<'tickets' | 'protocols' | 'warranties' | 'parts'>('tickets')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Data
  const [tickets, setTickets] = useState<ServiceTicket[]>([])
  const [protocols, setProtocols] = useState<InstallationProtocol[]>([])
  const [warranties, setWarranties] = useState<WarrantyContract[]>([])
  const [spareParts, setSpareParts] = useState<SparePart[]>([])

  // Lookups
  const [users, setUsers] = useState<UserOption[]>([])
  const [assets, setAssets] = useState<AssetOption[]>([])
  const [customers, setCustomers] = useState<CustomerOption[]>([])
  const [locations, setLocations] = useState<LocationOption[]>([])

  // Modals
  const [selectedTicket, setSelectedTicket] = useState<ServiceTicket | null>(null)
  const [showNewTicketModal, setShowNewTicketModal] = useState(false)
  const [showSignProtocolModal, setShowSignProtocolModal] = useState<InstallationProtocol | null>(null)
  const [showNewProtocolModal, setShowNewProtocolModal] = useState(false)
  const [showAddVisitModal, setShowAddVisitModal] = useState(false)
  const [showRequestPartModal, setShowRequestPartModal] = useState(false)
  const [showCloseTicketModal, setShowCloseTicketModal] = useState(false)

  // Forms State
  const [newTicketForm, setNewTicketForm] = useState({
    ticket_type: 'CORRECTIVE',
    priority: 'MEDIUM',
    asset: '',
    customer: '',
    title: '',
    reported_issue: '',
    warranty_status: 'PENDING_ASSESSMENT',
  })

  const [newProtocolForm, setNewProtocolForm] = useState({
    asset: '',
    customer: '',
    location: '',
    lead_engineer: '',
    electrical_safety_passed: true,
    performance_verification_passed: true,
    user_training_completed: true,
    trainees_list: '',
    notes: '',
  })

  const [signRepName, setSignRepName] = useState('')
  const [signRepTitle, setSignRepTitle] = useState('')

  const [visitForm, setVisitForm] = useState({
    actions_taken: '',
    diagnostic_details: '',
    is_resolved: false,
    customer_sign_off_name: '',
  })

  const [partForm, setPartForm] = useState({
    part_name: '',
    part_sku: '',
    quantity: 1,
    coverage: 'WARRANTY_FREE',
  })

  const [closeForm, setCloseForm] = useState({
    labor_hours: '2',
    labor_cost: '5000',
    resolution: '',
  })

  const loadTickets = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: ServiceTicket[] }>('/biomedical/tickets/')
      setTickets(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadProtocols = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: InstallationProtocol[] }>('/biomedical/protocols/')
      setProtocols(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadWarranties = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: WarrantyContract[] }>('/biomedical/warranties/')
      setWarranties(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadSpareParts = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: SparePart[] }>('/biomedical/spare-parts/')
      setSpareParts(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadLookups = async () => {
    try {
      const [uRes, aRes, cRes, lRes] = await Promise.all([
        api<{ results: UserOption[] }>('/users/'),
        api<{ results: AssetOption[] }>('/inventory/assets/'),
        api<{ results: CustomerOption[] }>('/customers/'),
        api<{ results: LocationOption[] }>('/inventory/locations/'),
      ])
      setUsers(uRes.results || [])
      setAssets(aRes.results || [])
      setCustomers(cRes.results || [])
      setLocations(lRes.results || [])
    } catch (e) {
      // ignore
    }
  }

  useEffect(() => {
    if (tab === 'tickets') loadTickets()
    if (tab === 'protocols') loadProtocols()
    if (tab === 'warranties') loadWarranties()
    if (tab === 'parts') loadSpareParts()
    loadLookups()
  }, [tab])

  const handleCreateTicket = async () => {
    if (!newTicketForm.title || !newTicketForm.reported_issue || !newTicketForm.asset || !newTicketForm.customer) {
      alert('يرجى ملء جميع الحقول المطلوبة')
      return
    }
    try {
      await api('/biomedical/tickets/', { method: 'POST', json: newTicketForm })
      setShowNewTicketModal(false)
      loadTickets()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleCreateProtocol = async () => {
    if (!newProtocolForm.asset || !newProtocolForm.customer || !newProtocolForm.location || !newProtocolForm.lead_engineer) {
      alert('يرجى ملء جميع الحقول المطلوبة')
      return
    }
    try {
      await api('/biomedical/protocols/', { method: 'POST', json: newProtocolForm })
      setShowNewProtocolModal(false)
      loadProtocols()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleSignProtocol = async () => {
    if (!showSignProtocolModal || !signRepName.trim()) {
      alert('يرجى إدخال اسم ممثل العميل المستلم')
      return
    }
    try {
      await api(`/biomedical/protocols/${showSignProtocolModal.id}/sign/`, {
        method: 'POST',
        json: {
          customer_representative_name: signRepName,
          customer_representative_title: signRepTitle,
        },
      })
      alert('تم اعتماد محضر التركيب وتوليد عقد الضمان تلقائياً بنجاح')
      setShowSignProtocolModal(null)
      setSignRepName('')
      setSignRepTitle('')
      loadProtocols()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleAddVisit = async () => {
    if (!selectedTicket || !visitForm.actions_taken.trim()) {
      alert('يرجى كتابة الإجراءات المتخذة في الزيارة')
      return
    }
    try {
      await api(`/biomedical/tickets/${selectedTicket.id}/add_visit/`, {
        method: 'POST',
        json: visitForm,
      })
      alert('تم تسجيل زيارة الصيانة بنجاح')
      setShowAddVisitModal(false)
      setVisitForm({ actions_taken: '', diagnostic_details: '', is_resolved: false, customer_sign_off_name: '' })
      const refreshed = await api<ServiceTicket>(`/biomedical/tickets/${selectedTicket.id}/`)
      setSelectedTicket(refreshed)
      loadTickets()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleRequestPart = async () => {
    if (!selectedTicket || !partForm.part_name.trim()) {
      alert('يرجى إدخال اسم قطعة الغيار المطلوبة')
      return
    }
    try {
      await api(`/biomedical/tickets/${selectedTicket.id}/request_part/`, {
        method: 'POST',
        json: partForm,
      })
      alert('تم إرسال طلب قطعة الغيار بنجاح')
      setShowRequestPartModal(false)
      setPartForm({ part_name: '', part_sku: '', quantity: 1, coverage: 'WARRANTY_FREE' })
      const refreshed = await api<ServiceTicket>(`/biomedical/tickets/${selectedTicket.id}/`)
      setSelectedTicket(refreshed)
      loadTickets()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleCloseTicket = async () => {
    if (!selectedTicket) return
    try {
      await api(`/biomedical/tickets/${selectedTicket.id}/close/`, {
        method: 'POST',
        json: closeForm,
      })
      alert('تم إغلاق تذكرة الصيانة بنجاح')
      setShowCloseTicketModal(false)
      setSelectedTicket(null)
      loadTickets()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  return (
    <div className="biomedical-page">
      <div className="page-header">
        <div className="page-header-title">
          <span className="page-header-icon">🔧</span>
          <div>
            <h1>{t('biomedical.title')}</h1>
            <p>الهندسة الطبية الحيوية، تذاكر الصيانة الدورية والطارئة، بروتوكولات الفحص، والضمانات</p>
          </div>
        </div>
      </div>

      <div className="tabs">
        <button className={tab === 'tickets' ? 'active' : ''} onClick={() => setTab('tickets')}>
          🎫 {t('biomedical.ticketsTab')}
        </button>
        <button className={tab === 'protocols' ? 'active' : ''} onClick={() => setTab('protocols')}>
          📋 {t('biomedical.protocolsTab')}
        </button>
        <button className={tab === 'warranties' ? 'active' : ''} onClick={() => setTab('warranties')}>
          🛡️ {t('biomedical.warrantiesTab')}
        </button>
        <button className={tab === 'parts' ? 'active' : ''} onClick={() => setTab('parts')}>
          🔩 {t('biomedical.sparePartsTab')}
        </button>
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      {/* Tab: Service Tickets */}
      {tab === 'tickets' && (
        <div className="card fade-in">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ margin: 0 }}>{t('biomedical.ticketsTab')}</h3>
            {can('biomedical.ticket.create') && (
              <button className="btn" onClick={() => setShowNewTicketModal(true)}>+ {t('biomedical.newTicket')}</button>
            )}
          </div>

          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <div className="table-container">
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>{t('biomedical.ticketNumber')}</th>
                    <th>العنوان</th>
                    <th>النوع</th>
                    <th>{t('biomedical.priority')}</th>
                    <th>{t('biomedical.customer')}</th>
                    <th>{t('biomedical.asset')}</th>
                    <th>{t('biomedical.engineer')}</th>
                    <th>التكلفة</th>
                    <th>{t('biomedical.status')}</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((tkt) => (
                    <tr key={tkt.id}>
                      <td style={{ fontWeight: 'bold' }}>
                        <a
                          href="#detail"
                          onClick={(e) => {
                            e.preventDefault()
                            setSelectedTicket(tkt)
                          }}
                        >
                          {tkt.ticket_number}
                        </a>
                      </td>
                      <td>{tkt.title}</td>
                      <td>{t(`biomedical.ticketTypes.${tkt.ticket_type}` as any) || tkt.ticket_type}</td>
                      <td>
                        <span className={`badge priority-${tkt.priority.toLowerCase()}`}>
                          {t(`biomedical.ticketPriorities.${tkt.priority}` as any) || tkt.priority}
                        </span>
                      </td>
                      <td>{tkt.customer_name}</td>
                      <td>{tkt.asset_serial}</td>
                      <td>{tkt.assigned_engineer_name || 'غير معيّن'}</td>
                      <td>{Number(tkt.total_cost).toLocaleString()}</td>
                      <td>
                        <span className={`badge status-${tkt.status.toLowerCase()}`}>
                          {t(`biomedical.ticketStatuses.${tkt.status}` as any) || tkt.status}
                        </span>
                      </td>
                      <td>
                        <button className="btn secondary" style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }} onClick={() => setSelectedTicket(tkt)}>تفاصيل</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab: Installation Protocols */}
      {tab === 'protocols' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3>{t('biomedical.protocolsTab')}</h3>
            {can('biomedical.protocol.create') && (
              <button onClick={() => setShowNewProtocolModal(true)}>+ {t('biomedical.newProtocol')}</button>
            )}
          </div>

          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>{t('biomedical.protocolNumber')}</th>
                  <th>{t('biomedical.asset')}</th>
                  <th>الموديل</th>
                  <th>{t('biomedical.customer')}</th>
                  <th>التاريخ</th>
                  <th>{t('biomedical.engineer')}</th>
                  <th>فحوصات السلامة</th>
                  <th>{t('biomedical.status')}</th>
                  <th>الإجراءات</th>
                </tr>
              </thead>
              <tbody>
                {protocols.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 'bold' }}>{p.protocol_number}</td>
                    <td>{p.asset_serial}</td>
                    <td>{p.model_name}</td>
                    <td>{p.customer_name}</td>
                    <td>{p.installed_at}</td>
                    <td>{p.lead_engineer_name}</td>
                    <td>
                      {p.electrical_safety_passed && p.performance_verification_passed && p.user_training_completed ? (
                        <span style={{ color: 'green' }}>✓ مستوفاة بالكامل</span>
                      ) : (
                        <span style={{ color: 'orange' }}>قيد الاختبارات</span>
                      )}
                    </td>
                    <td>
                      <span className={`badge status-${p.status.toLowerCase()}`}>
                        {t(`biomedical.protocolStatuses.${p.status}` as any) || p.status}
                      </span>
                    </td>
                    <td>
                      {p.status !== 'ACCEPTED' && can('biomedical.protocol.approve') && (
                        <button
                          onClick={() => {
                            setShowSignProtocolModal(p)
                          }}
                          style={{ color: 'green' }}
                        >
                          {t('biomedical.signProtocol')}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab: Warranties */}
      {tab === 'warranties' && (
        <div className="card">
          <h3>{t('biomedical.warrantiesTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>{t('biomedical.contractNumber')}</th>
                  <th>{t('biomedical.asset')}</th>
                  <th>الموديل</th>
                  <th>{t('biomedical.customer')}</th>
                  <th>{t('biomedical.warrantyType')}</th>
                  <th>تاريخ البداية</th>
                  <th>تاريخ الانتهاء</th>
                  <th>SLA الاستجابة</th>
                  <th>{t('common.status')}</th>
                </tr>
              </thead>
              <tbody>
                {warranties.map((w) => (
                  <tr key={w.id}>
                    <td style={{ fontWeight: 'bold' }}>{w.contract_number}</td>
                    <td>{w.asset_serial}</td>
                    <td>{w.model_name}</td>
                    <td>{w.customer_name || '-'}</td>
                    <td>{t(`biomedical.warrantyTypes.${w.warranty_type}` as any) || w.warranty_type}</td>
                    <td>{w.start_date}</td>
                    <td style={{ fontWeight: 'bold' }}>{w.end_date}</td>
                    <td>{w.sla_response_hours} ساعة</td>
                    <td>{w.is_active ? <span style={{ color: 'green' }}>ساري</span> : <span style={{ color: 'gray' }}>منتهي</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab: Spare Parts */}
      {tab === 'parts' && (
        <div className="card">
          <h3>{t('biomedical.sparePartsTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>اسم القطعة</th>
                  <th>رقم SKU</th>
                  <th>الكمية</th>
                  <th>التغطية</th>
                  <th>سعر الشراء (التكلفة)</th>
                  <th>سعر العميل</th>
                  <th>{t('biomedical.status')}</th>
                  <th>المعتمد</th>
                </tr>
              </thead>
              <tbody>
                {spareParts.map((sp) => (
                  <tr key={sp.id}>
                    <td style={{ fontWeight: 'bold' }}>{sp.part_name}</td>
                    <td>{sp.part_sku || '-'}</td>
                    <td>{sp.quantity}</td>
                    <td>{sp.coverage === 'WARRANTY_FREE' ? 'مغطى مجاناً بالضمان' : 'على حساب العميل'}</td>
                    <td>{Number(sp.cost_price).toLocaleString()}</td>
                    <td>{Number(sp.customer_price).toLocaleString()}</td>
                    <td>
                      <span className="badge">{sp.status}</span>
                    </td>
                    <td>{sp.approved_by_name || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Ticket Details & Timeline Drawer / Modal */}
      {selectedTicket && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '850px', maxWidth: '90%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3>تذكرة صيانة: {selectedTicket.ticket_number} - {selectedTicket.title}</h3>
              <button onClick={() => setSelectedTicket(null)}>✕</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px' }}>
              <div><strong>العميل:</strong> {selectedTicket.customer_name}</div>
              <div><strong>الجهاز:</strong> {selectedTicket.asset_serial} ({selectedTicket.model_name})</div>
              <div><strong>الأولوية:</strong> {selectedTicket.priority}</div>
              <div><strong>الحالة:</strong> {selectedTicket.status}</div>
              <div><strong>المهندس المسؤول:</strong> {selectedTicket.assigned_engineer_name || 'غير معيّن'}</div>
              <div><strong>حالة الضمان:</strong> {selectedTicket.warranty_status}</div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <strong>وصف العطل المبلغ عنه:</strong>
              <p style={{ backgroundColor: '#f8fafc', padding: '8px', borderRadius: '4px' }}>{selectedTicket.reported_issue}</p>
            </div>

            {selectedTicket.resolution_summary && (
              <div style={{ marginBottom: '16px' }}>
                <strong>ملخص الإصلاح والحل الفني:</strong>
                <p style={{ backgroundColor: '#f0fdf4', padding: '8px', borderRadius: '4px', color: '#166534' }}>{selectedTicket.resolution_summary}</p>
              </div>
            )}

            <h4>سجل زيارات الصيانة ({selectedTicket.visits?.length || 0})</h4>
            <div style={{ marginBottom: '16px' }}>
              {selectedTicket.visits?.map((v, i) => (
                <div key={i} style={{ border: '1px solid #e2e8f0', padding: '8px', borderRadius: '4px', marginBottom: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <strong>{v.engineer_name} - {v.visit_date}</strong>
                    {v.is_resolved && <span style={{ color: 'green', fontWeight: 'bold' }}>✓ تم حل المشكلة</span>}
                  </div>
                  <p>{v.actions_taken}</p>
                  {v.customer_sign_off_name && <small>توقيع العميل: {v.customer_sign_off_name}</small>}
                </div>
              ))}
            </div>

            <h4>قطع الغيار المطلوبة ({selectedTicket.spare_parts?.length || 0})</h4>
            <div style={{ marginBottom: '16px' }}>
              {selectedTicket.spare_parts?.map((sp, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #eee', padding: '4px 0' }}>
                  <span>{sp.part_name} (x{sp.quantity}) - {sp.part_sku}</span>
                  <span>{sp.status} | {sp.coverage}</span>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
              {can('biomedical.ticket.edit') && selectedTicket.status !== 'CLOSED' && (
                <>
                  <button onClick={() => setShowAddVisitModal(true)} style={{ backgroundColor: '#0284c7', color: '#fff' }}>
                    + {t('biomedical.addVisit')}
                  </button>
                  <button onClick={() => setShowRequestPartModal(true)} style={{ backgroundColor: '#d97706', color: '#fff' }}>
                    + {t('biomedical.requestPart')}
                  </button>
                </>
              )}
              {can('biomedical.ticket.approve') && selectedTicket.status !== 'CLOSED' && (
                <button onClick={() => setShowCloseTicketModal(true)} style={{ backgroundColor: '#16a34a', color: '#fff' }}>
                  {t('biomedical.closeTicket')}
                </button>
              )}
              <button onClick={() => setSelectedTicket(null)}>إغلاق</button>
            </div>
          </div>
        </div>
      )}

      {/* Sign Protocol Modal */}
      {showSignProtocolModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '500px', maxWidth: '90%' }}>
            <h3>اعتماد محضر التركيب والتشغيل {showSignProtocolModal.protocol_number}</h3>
            <p>الجهاز: <strong>{showSignProtocolModal.asset_serial}</strong> - العميل: <strong>{showSignProtocolModal.customer_name}</strong></p>

            <div style={{ marginBottom: '12px' }}>
              <label>اسم ممثل العميل المستلم للجهاز *</label>
              <input style={{ width: '100%' }} value={signRepName} onChange={(e) => setSignRepName(e.target.value)} placeholder="مثال: د. محمد عبد الله" />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label>المسمى الوظيفي لممثل العميل</label>
              <input style={{ width: '100%' }} value={signRepTitle} onChange={(e) => setSignRepTitle(e.target.value)} placeholder="مثال: مدير المستشفى / رئيس قسم الأشعة" />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowSignProtocolModal(null)}>{t('common.cancel')}</button>
              <button onClick={handleSignProtocol} style={{ backgroundColor: '#16a34a', color: '#fff' }}>
                تأكيد الاستلام والاعتماد
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Visit Modal */}
      {showAddVisitModal && selectedTicket && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 110 }}>
          <div className="card" style={{ width: '550px', maxWidth: '90%' }}>
            <h3>تسجيل زيارة صيانة للتذكرة {selectedTicket.ticket_number}</h3>

            <div style={{ marginBottom: '12px' }}>
              <label>الإجراءات الفنية المتخذة *</label>
              <textarea
                style={{ width: '100%', minHeight: '80px' }}
                value={visitForm.actions_taken}
                onChange={(e) => setVisitForm({ ...visitForm, actions_taken: e.target.value })}
                placeholder="تفاصيل الفحص، قطع الغيار المستبدلة، التعديلات..."
              />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label>ملاحظات التشخيص الفني</label>
              <input
                style={{ width: '100%' }}
                value={visitForm.diagnostic_details}
                onChange={(e) => setVisitForm({ ...visitForm, diagnostic_details: e.target.value })}
                placeholder="سبب العطل الجذري..."
              />
            </div>

            <div style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                id="is_res"
                checked={visitForm.is_resolved}
                onChange={(e) => setVisitForm({ ...visitForm, is_resolved: e.target.checked })}
              />
              <label htmlFor="is_res">تم إصلاح الجهاز بنجاح وجاهز للتشغيل السريري</label>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label>اسم المستلم من طرف العميل</label>
              <input
                style={{ width: '100%' }}
                value={visitForm.customer_sign_off_name}
                onChange={(e) => setVisitForm({ ...visitForm, customer_sign_off_name: e.target.value })}
                placeholder="اسم الطبيب أو الفني المستلم بعد الصيانة..."
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowAddVisitModal(false)}>{t('common.cancel')}</button>
              <button onClick={handleAddVisit} style={{ backgroundColor: '#0284c7', color: '#fff' }}>
                حفظ الزيارة
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Request Part Modal */}
      {showRequestPartModal && selectedTicket && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 110 }}>
          <div className="card" style={{ width: '500px', maxWidth: '90%' }}>
            <h3>طلب قطعة غيار للتذكرة {selectedTicket.ticket_number}</h3>

            <div style={{ marginBottom: '12px' }}>
              <label>اسم قطعة الغيار *</label>
              <input
                style={{ width: '100%' }}
                value={partForm.part_name}
                onChange={(e) => setPartForm({ ...partForm, part_name: e.target.value })}
                placeholder="مثال: لوحة التغذية الكهربائية PSU..."
              />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label>رقم SKU المورد الصيني</label>
              <input
                style={{ width: '100%' }}
                value={partForm.part_sku}
                onChange={(e) => setPartForm({ ...partForm, part_sku: e.target.value })}
                placeholder="مثال: CN-MED-450-X"
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              <div>
                <label>الكمية</label>
                <input
                  type="number"
                  min="1"
                  style={{ width: '100%' }}
                  value={partForm.quantity}
                  onChange={(e) => setPartForm({ ...partForm, quantity: Number(e.target.value) })}
                />
              </div>
              <div>
                <label>تغطية الضمان</label>
                <select
                  style={{ width: '100%' }}
                  value={partForm.coverage}
                  onChange={(e) => setPartForm({ ...partForm, coverage: e.target.value })}
                >
                  <option value="WARRANTY_FREE">مغطى بالضمان مجاناً</option>
                  <option value="BILLABLE_CUSTOMER">على حساب العميل (خارج الضمان)</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowRequestPartModal(false)}>{t('common.cancel')}</button>
              <button onClick={handleRequestPart} style={{ backgroundColor: '#d97706', color: '#fff' }}>
                إرسال الطلب
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Close Ticket Modal */}
      {showCloseTicketModal && selectedTicket && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 110 }}>
          <div className="card" style={{ width: '500px', maxWidth: '90%' }}>
            <h3>إغلاق واعتماد تذكرة الصيانة {selectedTicket.ticket_number}</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label>ساعات العمل الفعلية</label>
                <input
                  type="number"
                  step="0.5"
                  style={{ width: '100%' }}
                  value={closeForm.labor_hours}
                  onChange={(e) => setCloseForm({ ...closeForm, labor_hours: e.target.value })}
                />
              </div>
              <div>
                <label>تكلفة أجور العمل</label>
                <input
                  type="number"
                  style={{ width: '100%' }}
                  value={closeForm.labor_cost}
                  onChange={(e) => setCloseForm({ ...closeForm, labor_cost: e.target.value })}
                />
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label>ملخص الحل النهائي</label>
              <textarea
                style={{ width: '100%', minHeight: '60px' }}
                value={closeForm.resolution}
                onChange={(e) => setCloseForm({ ...closeForm, resolution: e.target.value })}
                placeholder="التأكيد على استقرار الجهاز وتسليمه رسمياً للقسم..."
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowCloseTicketModal(false)}>{t('common.cancel')}</button>
              <button onClick={handleCloseTicket} style={{ backgroundColor: '#16a34a', color: '#fff' }}>
                تأكيد الإغلاق النهائي
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Ticket Modal */}
      {showNewTicketModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '600px', maxWidth: '90%' }}>
            <h3>{t('biomedical.newTicket')}</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label>العميل *</label>
                <select
                  style={{ width: '100%' }}
                  value={newTicketForm.customer}
                  onChange={(e) => setNewTicketForm({ ...newTicketForm, customer: e.target.value })}
                >
                  <option value="">اختر العميل...</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.legal_name_ar}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>الجهاز الطبي *</label>
                <select
                  style={{ width: '100%' }}
                  value={newTicketForm.asset}
                  onChange={(e) => setNewTicketForm({ ...newTicketForm, asset: e.target.value })}
                >
                  <option value="">اختر الجهاز S/N...</option>
                  {assets.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.serial_number} {a.model_name ? `(${a.model_name})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label>نوع التذكرة</label>
                <select
                  style={{ width: '100%' }}
                  value={newTicketForm.ticket_type}
                  onChange={(e) => setNewTicketForm({ ...newTicketForm, ticket_type: e.target.value })}
                >
                  <option value="CORRECTIVE">صيانة تصحيحية</option>
                  <option value="PREVENTIVE">صيانة وقائية دورية</option>
                  <option value="EMERGENCY">عطل طارئ وتوقف جهاز</option>
                  <option value="CALIBRATION">معايرة واختبار دقة</option>
                </select>
              </div>
              <div>
                <label>الأولوية</label>
                <select
                  style={{ width: '100%' }}
                  value={newTicketForm.priority}
                  onChange={(e) => setNewTicketForm({ ...newTicketForm, priority: e.target.value })}
                >
                  <option value="LOW">منخفضة</option>
                  <option value="MEDIUM">متوسطة</option>
                  <option value="HIGH">عالية</option>
                  <option value="CRITICAL">حرجة جداً</option>
                </select>
              </div>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label>عنوان البلاغ / العطل *</label>
              <input
                style={{ width: '100%' }}
                value={newTicketForm.title}
                onChange={(e) => setNewTicketForm({ ...newTicketForm, title: e.target.value })}
                placeholder="مثال: توقف الشاشة، قراءة ضغط غير دقيقة..."
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label>تفاصيل العطل والظروف المصاحبة *</label>
              <textarea
                style={{ width: '100%', minHeight: '70px' }}
                value={newTicketForm.reported_issue}
                onChange={(e) => setNewTicketForm({ ...newTicketForm, reported_issue: e.target.value })}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowNewTicketModal(false)}>{t('common.cancel')}</button>
              <button onClick={handleCreateTicket} style={{ backgroundColor: '#2563eb', color: '#fff' }}>
                إنشاء التذكرة
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Protocol Modal */}
      {showNewProtocolModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '650px', maxWidth: '90%' }}>
            <h3>{t('biomedical.newProtocol')}</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label>الجهاز الطبي *</label>
                <select
                  style={{ width: '100%' }}
                  value={newProtocolForm.asset}
                  onChange={(e) => setNewProtocolForm({ ...newProtocolForm, asset: e.target.value })}
                >
                  <option value="">اختر الجهاز S/N...</option>
                  {assets.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.serial_number}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>العميل المستلم *</label>
                <select
                  style={{ width: '100%' }}
                  value={newProtocolForm.customer}
                  onChange={(e) => setNewProtocolForm({ ...newProtocolForm, customer: e.target.value })}
                >
                  <option value="">اختر العميل...</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.legal_name_ar}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
              <div>
                <label>موقع التركيب *</label>
                <select
                  style={{ width: '100%' }}
                  value={newProtocolForm.location}
                  onChange={(e) => setNewProtocolForm({ ...newProtocolForm, location: e.target.value })}
                >
                  <option value="">اختر الموقع...</option>
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name_ar}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>المهندس المشرف *</label>
                <select
                  style={{ width: '100%' }}
                  value={newProtocolForm.lead_engineer}
                  onChange={(e) => setNewProtocolForm({ ...newProtocolForm, lead_engineer: e.target.value })}
                >
                  <option value="">اختر المهندس...</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name || u.email}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <h4>قائمة التحقق الفنية والإلزامية (§5.10):</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
              <label>
                <input
                  type="checkbox"
                  checked={newProtocolForm.electrical_safety_passed}
                  onChange={(e) => setNewProtocolForm({ ...newProtocolForm, electrical_safety_passed: e.target.checked })}
                />{' '}
                اجتياز اختبارات السلامة الكهربائية والعزل والتأريض الطبي
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={newProtocolForm.performance_verification_passed}
                  onChange={(e) =>
                    setNewProtocolForm({ ...newProtocolForm, performance_verification_passed: e.target.checked })
                  }
                />{' '}
                اجتياز المعايرة واختبارات الأداء التشغيلية ومطابقة كتالوج المورد الصيني
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={newProtocolForm.user_training_completed}
                  onChange={(e) => setNewProtocolForm({ ...newProtocolForm, user_training_completed: e.target.checked })}
                />{' '}
                إتمام التدريب النظري والعملي للكادر الطبي المشغل
              </label>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label>قائمة الكادر المتدرب</label>
              <input
                style={{ width: '100%' }}
                value={newProtocolForm.trainees_list}
                onChange={(e) => setNewProtocolForm({ ...newProtocolForm, trainees_list: e.target.value })}
                placeholder="أسماء الأطباء والفنيين..."
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowNewProtocolModal(false)}>{t('common.cancel')}</button>
              <button onClick={handleCreateProtocol} style={{ backgroundColor: '#2563eb', color: '#fff' }}>
                إنشاء المحضر
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
