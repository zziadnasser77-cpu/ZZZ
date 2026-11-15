import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type Page } from '../api'

interface ShipmentEvent {
  id: string
  location_name: string
  event_description: string
  created_at: string
}

interface Shipment {
  id: string
  shipment_number: string
  carrier_name: string
  tracking_number: string
  shipping_method: string
  status: string
  origin_port: string
  destination_port: string
  estimated_arrival?: string
  events: ShipmentEvent[]
}

export default function ShipmentsPage() {
  const { t } = useTranslation()
  const [selectedShipment, setSelectedShipment] = useState<Shipment | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['shipments'],
    queryFn: () => api<Page<Shipment>>('/shipments/'),
  })

  return (
    <>
      <div className="bar">
        <h1>{t('shipments.title')}</h1>
      </div>

      {isLoading ? (
        t('common.loading')
      ) : (
        <div className={`split-layout ${selectedShipment ? 'active' : ''}`}>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('shipments.number')}</th>
                  <th>{t('shipments.carrier')}</th>
                  <th>{t('shipments.tracking')}</th>
                  <th>{t('shipments.origin')}</th>
                  <th>{t('shipments.destination')}</th>
                  <th>{t('shipments.status')}</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => setSelectedShipment(s)}
                    style={{ cursor: 'pointer', background: selectedShipment?.id === s.id ? 'var(--bg-muted, #f0f4f8)' : undefined }}
                  >
                    <td><strong>{s.shipment_number}</strong></td>
                    <td>{s.carrier_name}</td>
                    <td><code>{s.tracking_number || '—'}</code></td>
                    <td>{s.origin_port}</td>
                    <td>{s.destination_port}</td>
                    <td>
                      <span className={`badge ${s.status === 'RECEIVED_LOCALLY' || s.status === 'DELIVERED_TO_CUSTOMER' ? 'ok' : 'warn'}`}>
                        {t(`shipments.statuses.${s.status}`)}
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

          {selectedShipment && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3>{selectedShipment.shipment_number} — {selectedShipment.carrier_name}</h3>
                <button className="btn" onClick={() => setSelectedShipment(null)}>{t('common.cancel')}</button>
              </div>

              <div style={{ fontSize: '0.9rem', marginBlock: '0.8rem', lineHeight: '1.7' }}>
                <div><strong>{t('shipments.tracking')}:</strong> <code>{selectedShipment.tracking_number || '—'}</code></div>
                <div><strong>{t('shipments.origin')}:</strong> {selectedShipment.origin_port}</div>
                <div><strong>{t('shipments.destination')}:</strong> {selectedShipment.destination_port}</div>
                <div><strong>{t('shipments.status')}:</strong> {t(`shipments.statuses.${selectedShipment.status}`)}</div>
              </div>

              <h4>{t('shipments.eventsTimeline')}</h4>
              <ul style={{ paddingInlineStart: '1.2rem', lineHeight: '1.6' }}>
                {selectedShipment.events?.map((ev) => (
                  <li key={ev.id}>
                    <strong>{ev.location_name}</strong>: {ev.event_description}
                  </li>
                ))}
                {(!selectedShipment.events || selectedShipment.events.length === 0) && (
                  <li>{t('common.empty')}</li>
                )}
              </ul>
            </div>
          )}
        </div>
      )}
    </>
  )
}
