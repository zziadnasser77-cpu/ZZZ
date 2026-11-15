import { useState, type FormEvent } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, ApiError, type Page } from '../api'
import { useAuth } from '../auth'

interface Customer {
  id: string
  customer_number: string
  customer_type: string
  legal_name_ar: string
  trade_name: string
  governorate: string
  phone: string
  status: string
  primary_contact?: { name: string; phone: string; role: string }
}

export default function CustomersPage() {
  const { t } = useTranslation()
  const { can } = useAuth()
  const [showNew, setShowNew] = useState(false)
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: () => api<Page<Customer>>('/customers/'),
  })

  return (
    <>
      <div className="bar">
        <h1>{t('customers.title')}</h1>
        {can('crm.customer.create') && (
          <button className="btn" onClick={() => setShowNew((v) => !v)}>
            {showNew ? t('common.cancel') : t('customers.new')}
          </button>
        )}
      </div>

      {showNew && <NewCustomer onDone={() => { setShowNew(false); qc.invalidateQueries({ queryKey: ['customers'] }) }} />}

      {isLoading ? (
        t('common.loading')
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>{t('customers.number')}</th>
                <th>{t('customers.name')}</th>
                <th>{t('customers.type')}</th>
                <th>{t('customers.governorate')}</th>
                <th>{t('customers.contact')}</th>
                <th>{t('customers.phone')}</th>
                <th>{t('customers.status')}</th>
              </tr>
            </thead>
            <tbody>
              {data?.results.map((c) => (
                <tr key={c.id}>
                  <td><strong>{c.customer_number}</strong></td>
                  <td>{c.legal_name_ar}</td>
                  <td><span className="badge">{t(`customers.types.${c.customer_type}`)}</span></td>
                  <td>{c.governorate || '-'}</td>
                  <td>{c.primary_contact ? `${c.primary_contact.name} (${c.primary_contact.phone || '-'})` : '-'}</td>
                  <td dir="ltr">{c.phone || '-'}</td>
                  <td>
                    <span className={`badge ${c.status === 'ACTIVE' ? 'ok' : 'off'}`}>
                      {t(`customers.statuses.${c.status}`)}
                    </span>
                  </td>
                </tr>
              ))}
              {data?.results.length === 0 && (
                <tr>
                  <td colSpan={7}>{t('common.empty')}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function NewCustomer({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation()
  const [f, setF] = useState({
    legal_name_ar: '',
    customer_type: 'HOSPITAL',
    governorate: '',
    phone: '',
    email: '',
    address: '',
    status: 'ACTIVE',
  })
  const [err, setErr] = useState('')

  const m = useMutation({
    mutationFn: () => api('/customers/', { method: 'POST', json: f }),
    onSuccess: onDone,
    onError: (e) => setErr(e instanceof ApiError ? JSON.stringify(e.details ?? e.message) : t('common.error')),
  })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setErr('')
    m.mutate()
  }

  return (
    <form className="card" onSubmit={submit} style={{ marginBlockEnd: '1rem' }}>
      <div className="field">
        <label>{t('customers.name')}</label>
        <input required value={f.legal_name_ar} onChange={(e) => setF({ ...f, legal_name_ar: e.target.value })} />
      </div>
      <div className="field">
        <label>{t('customers.type')}</label>
        <select value={f.customer_type} onChange={(e) => setF({ ...f, customer_type: e.target.value })}>
          <option value="HOSPITAL">{t('customers.types.HOSPITAL')}</option>
          <option value="MEDICAL_CENTER">{t('customers.types.MEDICAL_CENTER')}</option>
          <option value="CLINIC">{t('customers.types.CLINIC')}</option>
          <option value="GOVERNMENT">{t('customers.types.GOVERNMENT')}</option>
          <option value="DISTRIBUTOR">{t('customers.types.DISTRIBUTOR')}</option>
          <option value="OTHER">{t('customers.types.OTHER')}</option>
        </select>
      </div>
      <div className="field">
        <label>{t('customers.governorate')}</label>
        <input value={f.governorate} onChange={(e) => setF({ ...f, governorate: e.target.value })} />
      </div>
      <div className="field">
        <label>{t('customers.phone')}</label>
        <input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
      </div>
      <div className="field">
        <label>{t('customers.email')}</label>
        <input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
      </div>
      {err && <div className="error" role="alert">{err}</div>}
      <button className="btn" disabled={m.isPending}>{t('common.save')}</button>
    </form>
  )
}
