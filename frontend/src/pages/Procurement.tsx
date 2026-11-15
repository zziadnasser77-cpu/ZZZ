import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type Page } from '../api'

interface SupplierOrder {
  id: string
  order_number: string
  supplier_name: string
  deal_number?: string
  procurement_model: string
  status: string
  currency: string
  total_amount: string
  supplier_pi_reference?: string
  shipping_port?: string
  destination_port?: string
}

export default function ProcurementPage() {
  const { t } = useTranslation()
  const [selectedOrder, setSelectedOrder] = useState<SupplierOrder | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['supplier-orders'],
    queryFn: () => api<Page<SupplierOrder>>('/supplier-orders/'),
  })

  return (
    <>
      <div className="bar">
        <h1>{t('procurement.title')}</h1>
      </div>

      {isLoading ? (
        t('common.loading')
      ) : (
        <div className={`split-layout ${selectedOrder ? 'active' : ''}`}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('procurement.orderNumber')}</th>
                  <th>{t('procurement.supplier')}</th>
                  <th>{t('procurement.model')}</th>
                  <th>{t('procurement.piRef')}</th>
                  <th>{t('procurement.total')}</th>
                  <th>{t('procurement.status')}</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((po) => (
                  <tr
                    key={po.id}
                    onClick={() => setSelectedOrder(po)}
                    style={{ cursor: 'pointer', background: selectedOrder?.id === po.id ? 'var(--bg-muted, #f0f4f8)' : undefined }}
                  >
                    <td><strong>{po.order_number}</strong></td>
                    <td>{po.supplier_name}</td>
                    <td><span className="badge">{t(`procurement.models.${po.procurement_model}`)}</span></td>
                    <td><code>{po.supplier_pi_reference || '-'}</code></td>
                    <td><strong>{po.total_amount} {po.currency}</strong></td>
                    <td>
                      <span className={`badge ${po.status === 'RECEIVED' || po.status === 'CONFIRMED_BY_SUPPLIER' ? 'ok' : 'off'}`}>
                        {t(`procurement.statuses.${po.status}`)}
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

          {selectedOrder && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3>{selectedOrder.order_number} — {selectedOrder.supplier_name}</h3>
                <button className="btn" onClick={() => setSelectedOrder(null)}>{t('common.cancel')}</button>
              </div>

              <div style={{ fontSize: '0.9rem', marginBlock: '0.8rem', lineHeight: '1.7' }}>
                <div><strong>{t('procurement.piRef')}:</strong> <code>{selectedOrder.supplier_pi_reference || t('procurement.noPiYet')}</code></div>
                {selectedOrder.deal_number && <div><strong>{t('procurement.linkedDeal')}:</strong> {selectedOrder.deal_number}</div>}
                <div><strong>{t('procurement.shippingPort')}:</strong> {selectedOrder.shipping_port || '-'}</div>
                <div><strong>{t('procurement.destinationPort')}:</strong> {selectedOrder.destination_port || '-'}</div>
                <div><strong>{t('procurement.status')}:</strong> {t(`procurement.statuses.${selectedOrder.status}`)}</div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
