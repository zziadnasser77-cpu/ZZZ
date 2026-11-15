import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'

interface Account {
  id: string
  code: string
  name_ar: string
  name_en: string
  account_type: string
  parent_code?: string
  currency_code?: string
  is_reconcilable: boolean
  is_active: boolean
}

interface JournalLine {
  id?: string
  account: string
  account_code?: string
  account_name?: string
  description: string
  currency: string
  currency_code?: string
  exchange_rate: string | number
  debit: string | number
  credit: string | number
  base_debit?: string | number
  base_credit?: string | number
}

interface JournalEntry {
  id: string
  entry_number: string
  entry_date: string
  reference: string
  description: string
  status: string
  total_debit: number
  total_credit: number
  lines?: JournalLine[]
  reversed_entry_number?: string
  created_at: string
}

interface TrialBalanceAccount {
  account_id: string
  code: string
  name_ar: string
  name_en: string
  account_type: string
  debit: number
  credit: number
  balance: number
}

interface TrialBalance {
  accounts: TrialBalanceAccount[]
  total_debit: number
  total_credit: number
  is_balanced: boolean
}

interface Currency {
  id: string
  code: string
  name_ar: string
  name_en: string
  symbol: string
  is_base: boolean
}

interface ExchangeRate {
  id: string
  from_currency_code: string
  to_currency_code: string
  rate: string
  effective_date: string
  source: string
}

export default function AccountingPage() {
  const { t, i18n } = useTranslation()
  const { can } = useAuth()
  const [tab, setTab] = useState<'coa' | 'entries' | 'trial' | 'currencies'>('entries')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Data
  const [accounts, setAccounts] = useState<Account[]>([])
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null)
  const [trialBalance, setTrialBalance] = useState<TrialBalance | null>(null)
  const [currencies, setCurrencies] = useState<Currency[]>([])
  const [rates, setRates] = useState<ExchangeRate[]>([])

  // New Entry Modal
  const [showNewEntryModal, setShowNewEntryModal] = useState(false)
  const [newDesc, setNewDesc] = useState('')
  const [newRef, setNewRef] = useState('')
  const [newLines, setNewLines] = useState<
    { account: string; description: string; currency: string; exchange_rate: string; debit: string; credit: string }[]
  >([
    { account: '', description: '', currency: '', exchange_rate: '1', debit: '0', credit: '0' },
    { account: '', description: '', currency: '', exchange_rate: '1', debit: '0', credit: '0' },
  ])

  // Load functions
  const loadEntries = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api<{ results: JournalEntry[] }>('/accounting/entries/')
      setEntries(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadAccounts = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: Account[] }>('/accounting/accounts/')
      setAccounts(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadTrialBalance = async () => {
    setLoading(true)
    try {
      const res = await api<TrialBalance>('/accounting/entries/trial_balance/')
      setTrialBalance(res)
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadCurrencies = async () => {
    setLoading(true)
    try {
      const cRes = await api<{ results: Currency[] }>('/accounting/currencies/')
      const rRes = await api<{ results: ExchangeRate[] }>('/accounting/exchange-rates/')
      setCurrencies(cRes.results || [])
      setRates(rRes.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (tab === 'entries') loadEntries()
    if (tab === 'coa') loadAccounts()
    if (tab === 'trial') loadTrialBalance()
    if (tab === 'currencies') loadCurrencies()
  }, [tab])

  const handlePostEntry = async (id: string) => {
    if (!window.confirm('هل أنت متأكد من ترحيل هذا القيد؟ القيود المرحلة لا يمكن تعديلها أو حذفها.')) return
    try {
      await api(`/accounting/entries/${id}/post_entry/`, { method: 'POST', json: {} })
      loadEntries()
      if (selectedEntry?.id === id) {
        const refreshed = await api<JournalEntry>(`/accounting/entries/${id}/`)
        setSelectedEntry(refreshed)
      }
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleReverseEntry = async (id: string) => {
    const reason = window.prompt('سبب عكس القيد:')
    if (reason === null) return
    try {
      await api(`/accounting/entries/${id}/reverse/`, { method: 'POST', json: { reason } })
      loadEntries()
      setSelectedEntry(null)
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const openEntryDetail = async (id: string) => {
    try {
      const res = await api<JournalEntry>(`/accounting/entries/${id}/`)
      setSelectedEntry(res)
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleCreateEntry = async () => {
    if (!newDesc.trim()) {
      alert('يرجى إدخال بيان القيد')
      return
    }
    const linesToSubmit = newLines
      .filter((l) => l.account && (Number(l.debit) > 0 || Number(l.credit) > 0))
      .map((l) => ({
        account: l.account,
        description: l.description,
        currency: l.currency || currencies.find((c) => c.is_base)?.id || currencies[0]?.id,
        exchange_rate: l.exchange_rate,
        debit: l.debit,
        credit: l.credit,
      }))

    if (linesToSubmit.length < 2) {
      alert('يجب إدخال سطرين على الأقل للقيد المزدوج')
      return
    }

    try {
      await api('/accounting/entries/', {
        method: 'POST',
        json: {
          description: newDesc,
          reference: newRef,
          lines: linesToSubmit,
        },
      })
      setShowNewEntryModal(false)
      setNewDesc('')
      setNewRef('')
      loadEntries()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const baseCurr = currencies.find((c) => c.is_base)?.id || (currencies.length > 0 ? currencies[0].id : '')

  return (
    <div className="accounting-page">
      <h2>{t('accounting.title')}</h2>

      <div className="tabs">
        <button className={tab === 'entries' ? 'active' : ''} onClick={() => setTab('entries')}>
          📑 {t('accounting.entriesTab')}
        </button>
        <button className={tab === 'coa' ? 'active' : ''} onClick={() => setTab('coa')}>
          📊 {t('accounting.coaTab')}
        </button>
        <button className={tab === 'trial' ? 'active' : ''} onClick={() => setTab('trial')}>
          ⚖️ {t('accounting.trialBalanceTab')}
        </button>
        <button className={tab === 'currencies' ? 'active' : ''} onClick={() => setTab('currencies')}>
          💱 {t('accounting.currenciesTab')}
        </button>
      </div>

      {error && <div className="card" style={{ color: 'red' }}>{error}</div>}

      {/* Tab: Journal Entries */}
      {tab === 'entries' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3>{t('accounting.entriesTab')}</h3>
            {can('accounting.entry.create') && (
              <button
                onClick={async () => {
                  if (accounts.length === 0) await loadAccounts()
                  if (currencies.length === 0) await loadCurrencies()
                  setShowNewEntryModal(true)
                }}
              >
                + {t('accounting.newEntry')}
              </button>
            )}
          </div>

          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <div className="table-container">
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>{t('accounting.entryNumber')}</th>
                    <th>{t('accounting.entryDate')}</th>
                    <th>{t('accounting.reference')}</th>
                    <th>{t('accounting.description')}</th>
                    <th>{t('accounting.totalDebit')}</th>
                    <th>{t('accounting.totalCredit')}</th>
                    <th>{t('accounting.status')}</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id}>
                      <td>
                        <a
                          href="#detail"
                          onClick={(ev) => {
                            ev.preventDefault()
                            openEntryDetail(e.id)
                          }}
                        >
                          {e.entry_number}
                        </a>
                      </td>
                      <td>{e.entry_date}</td>
                      <td>{e.reference || '-'}</td>
                      <td>{e.description}</td>
                      <td>{e.total_debit.toLocaleString()}</td>
                      <td>{e.total_credit.toLocaleString()}</td>
                      <td>
                        <span className={`badge status-${e.status.toLowerCase()}`}>
                          {t(`accounting.entryStatuses.${e.status}` as any) || e.status}
                        </span>
                      </td>
                      <td style={{ display: 'flex', gap: '4px' }}>
                        <button className="btn secondary" style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }} onClick={() => openEntryDetail(e.id)}>عرض</button>
                        {e.status === 'DRAFT' && can('accounting.entry.post') && (
                          <button className="btn ok" style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }} onClick={() => handlePostEntry(e.id)}>
                            {t('accounting.postEntry')}
                          </button>
                        )}
                        {e.status === 'POSTED' && can('accounting.entry.post') && (
                          <button className="btn secondary" style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', color: 'orange' }} onClick={() => handleReverseEntry(e.id)}>
                            {t('accounting.reverseEntry')}
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

      {/* Tab: Chart of Accounts */}
      {tab === 'coa' && (
        <div className="card">
          <h3>{t('accounting.coaTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>{t('accounting.code')}</th>
                  <th>{t('accounting.name')}</th>
                  <th>{t('accounting.type')}</th>
                  <th>الحساب الرئيسي</th>
                  <th>{t('common.status')}</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((acc) => (
                  <tr key={acc.id}>
                    <td style={{ fontFamily: 'monospace', fontWeight: 'bold' }}>{acc.code}</td>
                    <td>{i18n.language === 'en' ? acc.name_en : acc.name_ar}</td>
                    <td>
                      <span className="badge">
                        {t(`accounting.accountTypes.${acc.account_type}` as any) || acc.account_type}
                      </span>
                    </td>
                    <td>{acc.parent_code || '-'}</td>
                    <td>{acc.is_active ? t('common.active') : t('common.inactive')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab: Trial Balance */}
      {tab === 'trial' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3>{t('accounting.trialBalanceTab')}</h3>
            {trialBalance && (
              <span
                className="badge"
                style={{
                  backgroundColor: trialBalance.is_balanced ? '#22c55e' : '#ef4444',
                  color: '#fff',
                  padding: '6px 12px',
                }}
              >
                {trialBalance.is_balanced ? t('accounting.isBalanced') : t('accounting.unbalanced')}
              </span>
            )}
          </div>
          {loading || !trialBalance ? (
            <div>{t('common.loading')}</div>
          ) : (
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>{t('accounting.code')}</th>
                  <th>{t('accounting.name')}</th>
                  <th>{t('accounting.type')}</th>
                  <th>{t('accounting.totalDebit')}</th>
                  <th>{t('accounting.totalCredit')}</th>
                  <th>الرصيد الصافي</th>
                </tr>
              </thead>
              <tbody>
                {trialBalance.accounts.map((row) => (
                  <tr key={row.account_id}>
                    <td style={{ fontFamily: 'monospace' }}>{row.code}</td>
                    <td>{i18n.language === 'en' ? row.name_en : row.name_ar}</td>
                    <td>{t(`accounting.accountTypes.${row.account_type}` as any) || row.account_type}</td>
                    <td>{row.debit.toLocaleString()}</td>
                    <td>{row.credit.toLocaleString()}</td>
                    <td style={{ fontWeight: 'bold' }}>{row.balance.toLocaleString()}</td>
                  </tr>
                ))}
                <tr style={{ borderTop: '2px solid #ccc', fontWeight: 'bold' }}>
                  <td colSpan={3}>الإجمالي العام</td>
                  <td>{trialBalance.total_debit.toLocaleString()}</td>
                  <td>{trialBalance.total_credit.toLocaleString()}</td>
                  <td>-</td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab: Currencies */}
      {tab === 'currencies' && (
        <div className="card">
          <h3>{t('accounting.currenciesTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <div>
              <h4>العملات المسجلة</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px', marginBottom: '24px' }}>
                {currencies.map((c) => (
                  <div key={c.id} className="card" style={{ padding: '12px', border: c.is_base ? '2px solid #3b82f6' : '1px solid #ddd' }}>
                    <div style={{ fontWeight: 'bold', fontSize: '18px' }}>
                      {c.code} ({c.symbol})
                    </div>
                    <div>{i18n.language === 'en' ? c.name_en : c.name_ar}</div>
                    {c.is_base && <span className="badge" style={{ backgroundColor: '#3b82f6', color: '#fff', marginTop: '6px' }}>العملة المحاسبية الأساسية</span>}
                  </div>
                ))}
              </div>

              <h4>جدول أسعار الصرف التاريخي</h4>
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>من عملة</th>
                    <th>إلى عملة</th>
                    <th>سعر التحويل</th>
                    <th>تاريخ السريان</th>
                    <th>المصدر</th>
                  </tr>
                </thead>
                <tbody>
                  {rates.map((r) => (
                    <tr key={r.id}>
                      <td>{r.from_currency_code}</td>
                      <td>{r.to_currency_code}</td>
                      <td style={{ fontWeight: 'bold' }}>{r.rate}</td>
                      <td>{r.effective_date}</td>
                      <td>{r.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Entry Detail Modal */}
      {selectedEntry && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '800px', maxWidth: '90%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3>تفاصيل القيد {selectedEntry.entry_number}</h3>
              <button onClick={() => setSelectedEntry(null)}>✕</button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '16px' }}>
              <div><strong>{t('accounting.entryDate')}:</strong> {selectedEntry.entry_date}</div>
              <div><strong>{t('accounting.reference')}:</strong> {selectedEntry.reference || '-'}</div>
              <div><strong>{t('accounting.status')}:</strong> {t(`accounting.entryStatuses.${selectedEntry.status}` as any) || selectedEntry.status}</div>
              <div><strong>{t('accounting.description')}:</strong> {selectedEntry.description}</div>
              {selectedEntry.reversed_entry_number && (
                <div style={{ color: 'red' }}><strong>معكوس بالقيد:</strong> {selectedEntry.reversed_entry_number}</div>
              )}
            </div>

            <h4>أسطر القيد</h4>
            <table className="table" style={{ width: '100%', marginBottom: '16px' }}>
              <thead>
                <tr>
                  <th>{t('accounting.code')}</th>
                  <th>الحساب</th>
                  <th>البيان</th>
                  <th>العملة</th>
                  <th>سعر الصرف</th>
                  <th>مدين</th>
                  <th>دائن</th>
                  <th>مدين (بالأساس)</th>
                  <th>دائن (بالأساس)</th>
                </tr>
              </thead>
              <tbody>
                {selectedEntry.lines?.map((line, idx) => (
                  <tr key={idx}>
                    <td>{line.account_code}</td>
                    <td>{line.account_name}</td>
                    <td>{line.description}</td>
                    <td>{line.currency_code}</td>
                    <td>{line.exchange_rate}</td>
                    <td>{Number(line.debit).toLocaleString()}</td>
                    <td>{Number(line.credit).toLocaleString()}</td>
                    <td>{Number(line.base_debit).toLocaleString()}</td>
                    <td>{Number(line.base_credit).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              {selectedEntry.status === 'DRAFT' && can('accounting.entry.post') && (
                <button onClick={() => handlePostEntry(selectedEntry.id)} style={{ color: 'green' }}>
                  {t('accounting.postEntry')}
                </button>
              )}
              {selectedEntry.status === 'POSTED' && can('accounting.entry.post') && (
                <button onClick={() => handleReverseEntry(selectedEntry.id)} style={{ color: 'orange' }}>
                  {t('accounting.reverseEntry')}
                </button>
              )}
              <button onClick={() => setSelectedEntry(null)}>إغلاق</button>
            </div>
          </div>
        </div>
      )}

      {/* New Entry Modal */}
      {showNewEntryModal && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '850px', maxWidth: '90%', maxHeight: '90vh', overflowY: 'auto' }}>
            <h3>{t('accounting.newEntry')}</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              <div>
                <label>{t('accounting.description')} *</label>
                <input style={{ width: '100%' }} value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="مثال: إثبات فاتورة أو سند..." />
              </div>
              <div>
                <label>{t('accounting.reference')}</label>
                <input style={{ width: '100%' }} value={newRef} onChange={(e) => setNewRef(e.target.value)} placeholder="رقم المستند / العقد..." />
              </div>
            </div>

            <h4>أسطر القيد المحاسبي</h4>
            {newLines.map((line, idx) => (
              <div key={idx} style={{ display: 'grid', gridTemplateColumns: '2fr 2fr 1fr 1fr 1fr 1fr auto', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                <select
                  value={line.account}
                  onChange={(e) => {
                    const copy = [...newLines]
                    copy[idx].account = e.target.value
                    setNewLines(copy)
                  }}
                >
                  <option value="">اختر الحساب...</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} - {a.name_ar}
                    </option>
                  ))}
                </select>
                <input
                  placeholder="بيان السطر"
                  value={line.description}
                  onChange={(e) => {
                    const copy = [...newLines]
                    copy[idx].description = e.target.value
                    setNewLines(copy)
                  }}
                />
                <select
                  value={line.currency || baseCurr}
                  onChange={(e) => {
                    const copy = [...newLines]
                    copy[idx].currency = e.target.value
                    setNewLines(copy)
                  }}
                >
                  {currencies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code}
                    </option>
                  ))}
                </select>
                <input
                  type="number"
                  placeholder="سعر الصرف"
                  value={line.exchange_rate}
                  onChange={(e) => {
                    const copy = [...newLines]
                    copy[idx].exchange_rate = e.target.value
                    setNewLines(copy)
                  }}
                />
                <input
                  type="number"
                  placeholder="مدين"
                  value={line.debit}
                  onChange={(e) => {
                    const copy = [...newLines]
                    copy[idx].debit = e.target.value
                    if (Number(e.target.value) > 0) copy[idx].credit = '0'
                    setNewLines(copy)
                  }}
                />
                <input
                  type="number"
                  placeholder="دائن"
                  value={line.credit}
                  onChange={(e) => {
                    const copy = [...newLines]
                    copy[idx].credit = e.target.value
                    if (Number(e.target.value) > 0) copy[idx].debit = '0'
                    setNewLines(copy)
                  }}
                />
                <button
                  type="button"
                  onClick={() => {
                    if (newLines.length > 2) {
                      setNewLines(newLines.filter((_, i) => i !== idx))
                    }
                  }}
                  disabled={newLines.length <= 2}
                >
                  ✕
                </button>
              </div>
            ))}

            <button
              type="button"
              onClick={() =>
                setNewLines([
                  ...newLines,
                  { account: '', description: '', currency: baseCurr, exchange_rate: '1', debit: '0', credit: '0' },
                ])
              }
              style={{ marginTop: '8px', marginBottom: '16px' }}
            >
              + إضافة سطر
            </button>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowNewEntryModal(false)}>{t('common.cancel')}</button>
              <button onClick={handleCreateEntry} style={{ backgroundColor: '#2563eb', color: '#fff' }}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
