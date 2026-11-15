import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type Page } from '../api'

interface SalesOrderLine {
  id: string
  model_name: string
  sku: string
  display_image?: string
  quantity: number
  unit_price: string
  total_price: string
  delivered_quantity: number
}

interface SalesOrder {
  id: string
  order_number: string
  status: string
  total_amount: string
  currency: string
  delivery_terms: string
  lines: SalesOrderLine[]
}

interface Deal {
  id: string
  deal_number: string
  title: string
  customer_name: string
  quotation_number?: string
  commercial_model: string
  seller_of_record: string
  invoice_issuer: string
  payment_recipient: string
  currency: string
  total_value: string
  status: string
  sales_orders: SalesOrder[]
}

export default function DealsPage() {
  const { t } = useTranslation()
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['deals'],
    queryFn: () => api<Page<Deal>>('/deals/'),
  })

  return (
    <>
      <div className="bar">
        <h1>{t('deals.title')}</h1>
      </div>

      {isLoading ? (
        t('common.loading')
      ) : (
        <div className={`split-layout ${selectedDeal ? 'active' : ''}`}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('deals.number')}</th>
                  <th>{t('deals.customer')}</th>
                  <th>{t('deals.model')}</th>
                  <th>{t('deals.seller')}</th>
                  <th>{t('deals.value')}</th>
                  <th>{t('deals.status')}</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((d) => (
                  <tr
                    key={d.id}
                    onClick={() => setSelectedDeal(d)}
                    style={{ cursor: 'pointer', background: selectedDeal?.id === d.id ? 'var(--bg-muted, #f0f4f8)' : undefined }}
                  >
                    <td><strong>{d.deal_number}</strong></td>
                    <td>{d.customer_name}</td>
                    <td><span className="badge">{t(`commercialModels.${d.commercial_model}`)}</span></td>
                    <td>{d.seller_of_record}</td>
                    <td><strong>{d.total_value} {d.currency}</strong></td>
                    <td>
                      <span className={`badge ${d.status === 'CONFIRMED' || d.status === 'DELIVERED' ? 'ok' : 'off'}`}>
                        {t(`deals.statuses.${d.status}`)}
                      </span>
                    </td>
                  </tr>
                ))}
                {data?.results.length === 0 && (
                  <tr><td colSpan={6}>{t('common.empty')}</td></tr>
                )}
              </tbody>
            </table>
          </div>

          {selectedDeal && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3>{selectedDeal.deal_number} — {selectedDeal.title}</h3>
                <button className="btn" onClick={() => setSelectedDeal(null)}>{t('common.cancel')}</button>
              </div>

              <div style={{ fontSize: '0.9rem', marginBlock: '0.5rem', lineHeight: '1.6' }}>
                <div><strong>{t('deals.seller')}:</strong> {selectedDeal.seller_of_record}</div>
                <div><strong>{t('deals.issuer')}:</strong> {selectedDeal.invoice_issuer}</div>
                <div><strong>{t('deals.recipient')}:</strong> {selectedDeal.payment_recipient}</div>
                {selectedDeal.quotation_number && (
                  <div><strong>{t('deals.fromQuotation')}:</strong> {selectedDeal.quotation_number}</div>
                )}
              </div>

              <h4>{t('deals.orders')}</h4>
              {selectedDeal.sales_orders?.map((so) => (
                <div key={so.id} style={{ borderTop: '1px solid var(--border, #e2e8f0)', paddingBlock: '0.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <strong>{so.order_number}</strong>
                    <span className="badge ok">{t(`deals.statuses.${so.status}`)}</span>
                  </div>
                  <table style={{ marginBlockStart: '0.5rem' }}>
                    <thead>
                      <tr>
                        <th style={{ width: '50px' }}>الصورة</th>
                        <th>{t('quotations.item')}</th>
                        <th>{t('quotations.qty')}</th>
                        <th>{t('quotations.price')}</th>
                        <th>{t('quotations.lineTotal')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {so.lines?.map((l) => (
                        <tr key={l.id}>
                          <td style={{ textAlign: 'center', padding: '0.35rem' }}>
                            {l.display_image ? (
                              <img
                                src={l.display_image}
                                alt={l.model_name}
                                style={{ width: '40px', height: '40px', objectFit: 'contain', borderRadius: '4px', border: '1px solid #e2e8f0', background: '#f8fafc' }}
                              />
                            ) : (
                              <div style={{ width: '40px', height: '40px', background: '#f8fafc', borderRadius: '4px', display: 'grid', placeItems: 'center', fontSize: '1.1rem', margin: 'auto' }}>🩺</div>
                            )}
                          </td>
                          <td>
                            <strong>{l.model_name}</strong>
                            {l.sku && <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>SKU: {l.sku}</div>}
                          </td>
                          <td>{l.quantity}</td>
                          <td>{l.unit_price}</td>
                          <td><strong>{l.total_price}</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
              {(!selectedDeal.sales_orders || selectedDeal.sales_orders.length === 0) && (
                <p>{t('common.empty')}</p>
              )}
            </div>
          )}
        </div>
      )}
    </>
  )
}
