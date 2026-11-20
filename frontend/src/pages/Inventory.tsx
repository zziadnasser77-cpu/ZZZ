import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type Page, resolveImageUrl } from '../api'

interface SerialAsset {
  id: string
  serial_number: string
  model_name: string
  sku: string
  display_image?: string
  location_name: string
  current_owner: string
  current_custodian: string
  status: string
  cost_price: string
}

interface StockMovement {
  id: string
  movement_number: string
  movement_type: string
  model_name: string
  sku: string
  quantity: number
  from_location_code?: string
  to_location_code?: string
  reference_document?: string
  created_at: string
}

interface Location {
  id: string
  code: string
  name_ar: string
  location_type: string
}

export default function InventoryPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<'assets' | 'movements' | 'locations'>('assets')

  const assets = useQuery({
    queryKey: ['serial-assets'],
    queryFn: () => api<Page<SerialAsset>>('/serial-assets/'),
    enabled: activeTab === 'assets',
  })

  const movements = useQuery({
    queryKey: ['stock-movements'],
    queryFn: () => api<Page<StockMovement>>('/stock-movements/'),
    enabled: activeTab === 'movements',
  })

  const locations = useQuery({
    queryKey: ['locations'],
    queryFn: () => api<Page<Location>>('/locations/'),
    enabled: activeTab === 'locations',
  })

  return (
    <>
      <div className="bar">
        <h1>{t('inventory.title')}</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className={`btn ${activeTab === 'assets' ? 'ok' : ''}`} onClick={() => setActiveTab('assets')}>
            {t('inventory.assetsTab')}
          </button>
          <button className={`btn ${activeTab === 'movements' ? 'ok' : ''}`} onClick={() => setActiveTab('movements')}>
            {t('inventory.movementsTab')}
          </button>
          <button className={`btn ${activeTab === 'locations' ? 'ok' : ''}`} onClick={() => setActiveTab('locations')}>
            {t('inventory.locationsTab')}
          </button>
        </div>
      </div>

      {activeTab === 'assets' && (
        assets.isLoading ? (
          t('common.loading')
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th style={{ width: '55px' }}>الصورة</th>
                  <th>{t('inventory.serialNumber')}</th>
                  <th>{t('inventory.model')}</th>
                  <th>{t('inventory.location')}</th>
                  <th>{t('inventory.owner')} (الملكية القانونية)</th>
                  <th>{t('inventory.custodian')} (الحيازة والعهدة)</th>
                  <th>{t('inventory.status')}</th>
                </tr>
              </thead>
              <tbody>
                {assets.data?.results.map((a) => (
                  <tr key={a.id}>
                    <td style={{ textAlign: 'center', padding: '0.4rem' }}>
                      {a.display_image ? (
                        <img
                          src={resolveImageUrl(a.display_image)}
                          alt={a.model_name}
                          loading="lazy"
                          decoding="async"
                          style={{ width: '42px', height: '42px', objectFit: 'contain', borderRadius: '4px', border: '1px solid #e2e8f0', background: '#f8fafc' }}
                        />
                      ) : (
                        <div style={{ width: '42px', height: '42px', background: '#f8fafc', borderRadius: '4px', display: 'grid', placeItems: 'center', fontSize: '1.2rem', margin: 'auto' }}>🩺</div>
                      )}
                    </td>
                    <td><strong><code>{a.serial_number}</code></strong></td>
                    <td>{a.model_name}</td>
                    <td><span className="badge">{a.location_name}</span></td>
                    <td><strong>{a.current_owner}</strong></td>
                    <td><span className="badge ok">{a.current_custodian}</span></td>
                    <td>
                      <span className={`badge ${a.status === 'IN_STOCK' ? 'ok' : a.status === 'DELIVERED_TO_CUSTOMER' ? 'off' : 'warn'}`}>
                        {t(`inventory.assetStatuses.${a.status}`)}
                      </span>
                    </td>
                  </tr>
                ))}
                {assets.data?.results.length === 0 && (
                  <tr><td colSpan={7}>{t('common.empty')}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )
      )}

      {activeTab === 'movements' && (
        movements.isLoading ? (
          t('common.loading')
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('inventory.movementNumber')}</th>
                  <th>{t('inventory.movementType')}</th>
                  <th>{t('inventory.model')}</th>
                  <th>{t('inventory.qty')}</th>
                  <th>{t('inventory.fromLocation')}</th>
                  <th>{t('inventory.toLocation')}</th>
                  <th>{t('inventory.refDoc')}</th>
                  <th>{t('inventory.date')}</th>
                </tr>
              </thead>
              <tbody>
                {movements.data?.results.map((m) => (
                  <tr key={m.id}>
                    <td><strong>{m.movement_number}</strong></td>
                    <td><span className="badge">{t(`inventory.movementTypes.${m.movement_type}`)}</span></td>
                    <td>{m.model_name}</td>
                    <td><strong>{m.quantity}</strong></td>
                    <td>{m.from_location_code || '—'}</td>
                    <td>{m.to_location_code || '—'}</td>
                    <td><code>{m.reference_document || '—'}</code></td>
                    <td style={{ fontSize: '0.85rem' }}>{new Date(m.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
                {movements.data?.results.length === 0 && (
                  <tr><td colSpan={8}>{t('common.empty')}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )
      )}

      {activeTab === 'locations' && (
        locations.isLoading ? (
          t('common.loading')
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>{t('inventory.locCode')}</th>
                  <th>{t('inventory.locName')}</th>
                  <th>{t('inventory.locType')}</th>
                </tr>
              </thead>
              <tbody>
                {locations.data?.results.map((l) => (
                  <tr key={l.id}>
                    <td><strong>{l.code}</strong></td>
                    <td>{l.name_ar}</td>
                    <td><span className="badge">{t(`inventory.locationTypes.${l.location_type}`)}</span></td>
                  </tr>
                ))}
                {locations.data?.results.length === 0 && (
                  <tr><td colSpan={3}>{t('common.empty')}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )
      )}
    </>
  )
}
