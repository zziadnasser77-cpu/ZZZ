import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { useAuth } from '../auth'

interface BankAccount {
  id: string
  account_type: string
  name_ar: string
  name_en: string
  bank_name?: string
  account_number?: string
  currency: string
  currency_code?: string
  opening_balance: string | number
  current_balance: string | number
  is_active: boolean
}

interface InvoiceLine {
  id?: string
  description: string
  quantity: number
  unit_price: string | number
  subtotal?: string | number
}

interface CustomerInvoice {
  id: string
  invoice_number: string
  customer: string
  customer_name?: string
  invoice_date: string
  currency: string
  currency_code?: string
  total_amount: string | number
  paid_amount: string | number
  remaining_amount: string | number
  status: string
  gl_entry_number?: string
  lines?: InvoiceLine[]
}

interface SupplierBill {
  id: string
  bill_number: string
  supplier: string
  supplier_name?: string
  bill_date: string
  currency: string
  currency_code?: string
  total_amount: string | number
  paid_amount: string | number
  remaining_amount: string | number
  status: string
  gl_entry_number?: string
  lines?: InvoiceLine[]
}

interface PaymentAllocation {
  id: string
  invoice_number?: string
  bill_number?: string
  allocated_amount: string | number
  allocated_at: string
}

interface Payment {
  id: string
  payment_number: string
  payment_type: string
  customer?: string
  customer_name?: string
  supplier?: string
  supplier_name?: string
  bank_account: string
  bank_account_name?: string
  payment_date: string
  amount: string | number
  currency: string
  currency_code?: string
  unallocated_amount: string | number
  allocated_amount: string | number
  status: string
  gl_entry_number?: string
  allocations?: PaymentAllocation[]
}

export default function PaymentsPage() {
  const { t } = useTranslation()
  const { can } = useAuth()
  const [tab, setTab] = useState<'invoices' | 'bills' | 'payments' | 'banks'>('invoices')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Data
  const [invoices, setInvoices] = useState<CustomerInvoice[]>([])
  const [bills, setBills] = useState<SupplierBill[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [bankAccounts, setBankAccounts] = useState<BankAccount[]>([])

  // Allocate Modal
  const [selectedPaymentForAlloc, setSelectedPaymentForAlloc] = useState<Payment | null>(null)
  const [allocTargetInvoiceId, setAllocTargetInvoiceId] = useState('')
  const [allocTargetBillId, setAllocTargetBillId] = useState('')
  const [allocAmount, setAllocAmount] = useState('')

  const loadInvoices = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: CustomerInvoice[] }>('/payments/invoices/')
      setInvoices(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadBills = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: SupplierBill[] }>('/payments/bills/')
      setBills(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadPayments = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: Payment[] }>('/payments/payments/')
      setPayments(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  const loadBankAccounts = async () => {
    setLoading(true)
    try {
      const res = await api<{ results: BankAccount[] }>('/payments/bank-accounts/')
      setBankAccounts(res.results || [])
    } catch (e: any) {
      setError(e.message || t('common.error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (tab === 'invoices') loadInvoices()
    if (tab === 'bills') loadBills()
    if (tab === 'payments') loadPayments()
    if (tab === 'banks') loadBankAccounts()
  }, [tab])

  const handlePostInvoice = async (id: string) => {
    if (!window.confirm('هل أنت متأكد من ترحيل الفاتورة وتوليد القيد المحاسبي؟')) return
    try {
      await api(`/payments/invoices/${id}/post_invoice/`, { method: 'POST', json: {} })
      loadInvoices()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handlePostBill = async (id: string) => {
    if (!window.confirm('هل أنت متأكد من ترحيل فاتورة المورد وتوليد القيد المحاسبي؟')) return
    try {
      await api(`/payments/bills/${id}/post_bill/`, { method: 'POST', json: {} })
      loadBills()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handlePostPayment = async (id: string) => {
    if (!window.confirm('هل أنت متأكد من ترحيل السند وتحديث رصيد البنك/الصندوق؟')) return
    try {
      await api(`/payments/payments/${id}/post_payment/`, { method: 'POST', json: {} })
      loadPayments()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  const handleAllocate = async () => {
    if (!selectedPaymentForAlloc) return
    if (!allocAmount || Number(allocAmount) <= 0) {
      alert('يرجى إدخال مبلغ توزيع صحيح')
      return
    }
    try {
      await api(`/payments/payments/${selectedPaymentForAlloc.id}/allocate/`, {
        method: 'POST',
        json: {
          amount: allocAmount,
          invoice_id: allocTargetInvoiceId || undefined,
          bill_id: allocTargetBillId || undefined,
        },
      })
      alert('تم توزيع الدفعة بنجاح')
      setSelectedPaymentForAlloc(null)
      setAllocAmount('')
      setAllocTargetInvoiceId('')
      setAllocTargetBillId('')
      loadPayments()
      loadInvoices()
    } catch (e: any) {
      alert(e.message || t('common.error'))
    }
  }

  return (
    <div className="payments-page">
      <h2>{t('payments.title')}</h2>

      <div className="tabs">
        <button className={tab === 'invoices' ? 'active' : ''} onClick={() => setTab('invoices')}>
          🧾 {t('payments.invoicesTab')}
        </button>
        <button className={tab === 'bills' ? 'active' : ''} onClick={() => setTab('bills')}>
          📥 {t('payments.billsTab')}
        </button>
        <button className={tab === 'payments' ? 'active' : ''} onClick={() => setTab('payments')}>
          💳 {t('payments.paymentsTab')}
        </button>
        <button className={tab === 'banks' ? 'active' : ''} onClick={() => setTab('banks')}>
          🏦 {t('payments.bankAccountsTab')}
        </button>
      </div>

      {error && <div className="error" role="alert">{error}</div>}

      {/* Tab: Customer Invoices */}
      {tab === 'invoices' && (
        <div className="card fade-in">
          <h3>{t('payments.invoicesTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <div className="table-container">
              <table className="table" style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th>{t('payments.invoiceNumber')}</th>
                    <th>{t('payments.customer')}</th>
                    <th>التاريخ</th>
                    <th>{t('payments.total')}</th>
                    <th>{t('payments.paid')}</th>
                    <th>{t('payments.remaining')}</th>
                    <th>القيد المحاسبي</th>
                    <th>{t('common.status')}</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td style={{ fontWeight: 'bold' }}>{inv.invoice_number}</td>
                      <td>{inv.customer_name}</td>
                      <td>{inv.invoice_date}</td>
                      <td>
                        {Number(inv.total_amount).toLocaleString()} {inv.currency_code}
                      </td>
                      <td style={{ color: 'green' }}>{Number(inv.paid_amount).toLocaleString()}</td>
                      <td style={{ color: Number(inv.remaining_amount) > 0 ? 'red' : 'inherit', fontWeight: 'bold' }}>
                        {Number(inv.remaining_amount).toLocaleString()}
                      </td>
                      <td>{inv.gl_entry_number || '-'}</td>
                      <td>
                        <span className={`badge status-${inv.status.toLowerCase()}`}>
                          {t(`payments.invoiceStatuses.${inv.status}` as any) || inv.status}
                        </span>
                      </td>
                      <td>
                        {inv.status === 'DRAFT' && can('payments.invoice.post') && (
                          <button className="btn ok" style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }} onClick={() => handlePostInvoice(inv.id)}>
                            {t('payments.post')}
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

      {/* Tab: Supplier Bills */}
      {tab === 'bills' && (
        <div className="card">
          <h3>{t('payments.billsTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>{t('payments.billNumber')}</th>
                  <th>{t('payments.supplier')}</th>
                  <th>التاريخ</th>
                  <th>{t('payments.total')}</th>
                  <th>{t('payments.paid')}</th>
                  <th>{t('payments.remaining')}</th>
                  <th>القيد المحاسبي</th>
                  <th>{t('common.status')}</th>
                  <th>الإجراءات</th>
                </tr>
              </thead>
              <tbody>
                {bills.map((b) => (
                  <tr key={b.id}>
                    <td style={{ fontWeight: 'bold' }}>{b.bill_number}</td>
                    <td>{b.supplier_name}</td>
                    <td>{b.bill_date}</td>
                    <td>
                      {Number(b.total_amount).toLocaleString()} {b.currency_code}
                    </td>
                    <td style={{ color: 'green' }}>{Number(b.paid_amount).toLocaleString()}</td>
                    <td style={{ color: Number(b.remaining_amount) > 0 ? 'red' : 'inherit', fontWeight: 'bold' }}>
                      {Number(b.remaining_amount).toLocaleString()}
                    </td>
                    <td>{b.gl_entry_number || '-'}</td>
                    <td>
                      <span className={`badge status-${b.status.toLowerCase()}`}>
                        {t(`payments.invoiceStatuses.${b.status}` as any) || b.status}
                      </span>
                    </td>
                    <td>
                      {b.status === 'DRAFT' && can('payments.bill.post') && (
                        <button onClick={() => handlePostBill(b.id)} style={{ color: 'green' }}>
                          {t('payments.post')}
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

      {/* Tab: Payments */}
      {tab === 'payments' && (
        <div className="card">
          <h3>{t('payments.paymentsTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>{t('payments.paymentNumber')}</th>
                  <th>{t('payments.paymentType')}</th>
                  <th>الطرف (عميل/مورد)</th>
                  <th>{t('payments.bankAccount')}</th>
                  <th>التاريخ</th>
                  <th>المبلغ</th>
                  <th>{t('payments.unallocated')}</th>
                  <th>القيد المحاسبي</th>
                  <th>{t('common.status')}</th>
                  <th>الإجراءات</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 'bold' }}>{p.payment_number}</td>
                    <td>{t(`payments.paymentTypes.${p.payment_type}` as any) || p.payment_type}</td>
                    <td>{p.customer_name || p.supplier_name || '-'}</td>
                    <td>{p.bank_account_name}</td>
                    <td>{p.payment_date}</td>
                    <td style={{ fontWeight: 'bold' }}>
                      {Number(p.amount).toLocaleString()} {p.currency_code}
                    </td>
                    <td style={{ color: Number(p.unallocated_amount) > 0 ? '#d97706' : 'green' }}>
                      {Number(p.unallocated_amount).toLocaleString()}
                    </td>
                    <td>{p.gl_entry_number || '-'}</td>
                    <td>
                      <span className={`badge status-${p.status.toLowerCase()}`}>
                        {t(`payments.paymentStatuses.${p.status}` as any) || p.status}
                      </span>
                    </td>
                    <td style={{ display: 'flex', gap: '4px' }}>
                      {p.status === 'DRAFT' && can('payments.payment.post') && (
                        <button onClick={() => handlePostPayment(p.id)} style={{ color: 'green' }}>
                          {t('payments.post')}
                        </button>
                      )}
                      {p.status === 'POSTED' && Number(p.unallocated_amount) > 0 && can('payments.payment.edit') && (
                        <button
                          onClick={async () => {
                            if (invoices.length === 0) await loadInvoices()
                            if (bills.length === 0) await loadBills()
                            setSelectedPaymentForAlloc(p)
                            setAllocAmount(String(p.unallocated_amount))
                          }}
                        >
                          {t('payments.allocate')}
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

      {/* Tab: Bank & Cash Accounts */}
      {tab === 'banks' && (
        <div className="card">
          <h3>{t('payments.bankAccountsTab')}</h3>
          {loading ? (
            <div>{t('common.loading')}</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
              {bankAccounts.map((b) => (
                <div key={b.id} className="card" style={{ padding: '16px', border: '1px solid #e2e8f0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <h4 style={{ margin: 0 }}>{b.name_ar}</h4>
                    <span className="badge">{b.account_type === 'CASH_REGISTER' ? 'صندوق' : 'بنك'}</span>
                  </div>
                  {b.bank_name && <div><strong>البنك:</strong> {b.bank_name}</div>}
                  {b.account_number && <div><strong>رقم الحساب:</strong> {b.account_number}</div>}
                  <div style={{ marginTop: '12px', fontSize: '20px', fontWeight: 'bold', color: '#0f766e' }}>
                    {Number(b.current_balance).toLocaleString()} {b.currency_code}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Allocate Modal */}
      {selectedPaymentForAlloc && (
        <div className="modal-backdrop" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '600px', maxWidth: '90%' }}>
            <h3>توزيع دفعة من السند {selectedPaymentForAlloc.payment_number}</h3>
            <p>
              المبلغ المتاح للتوزيع: <strong>{Number(selectedPaymentForAlloc.unallocated_amount).toLocaleString()} {selectedPaymentForAlloc.currency_code}</strong>
            </p>

            {selectedPaymentForAlloc.payment_type === 'CUSTOMER_RECEIPT' ? (
              <div style={{ marginBottom: '16px' }}>
                <label>اختر فاتورة العميل المستحقة:</label>
                <select
                  style={{ width: '100%', marginTop: '4px' }}
                  value={allocTargetInvoiceId}
                  onChange={(e) => setAllocTargetInvoiceId(e.target.value)}
                >
                  <option value="">اختر فاتورة...</option>
                  {invoices
                    .filter((inv) => inv.status === 'POSTED' || inv.status === 'PARTIALLY_PAID')
                    .map((inv) => (
                      <option key={inv.id} value={inv.id}>
                        {inv.invoice_number} - {inv.customer_name} (المتبقي: {Number(inv.remaining_amount).toLocaleString()})
                      </option>
                    ))}
                </select>
              </div>
            ) : (
              <div style={{ marginBottom: '16px' }}>
                <label>اختر فاتورة المورد المستحقة:</label>
                <select
                  style={{ width: '100%', marginTop: '4px' }}
                  value={allocTargetBillId}
                  onChange={(e) => setAllocTargetBillId(e.target.value)}
                >
                  <option value="">اختر فاتورة مورد...</option>
                  {bills
                    .filter((b) => b.status === 'POSTED' || b.status === 'PARTIALLY_PAID')
                    .map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.bill_number} - {b.supplier_name} (المتبقي: {Number(b.remaining_amount).toLocaleString()})
                      </option>
                    ))}
                </select>
              </div>
            )}

            <div style={{ marginBottom: '16px' }}>
              <label>المبلغ المراد توزيعه:</label>
              <input
                type="number"
                style={{ width: '100%', marginTop: '4px' }}
                value={allocAmount}
                onChange={(e) => setAllocAmount(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setSelectedPaymentForAlloc(null)}>{t('common.cancel')}</button>
              <button onClick={handleAllocate} style={{ backgroundColor: '#2563eb', color: '#fff' }}>
                تأكيد التوزيع
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
