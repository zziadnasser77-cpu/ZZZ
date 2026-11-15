import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'

interface NotificationItem {
  id: string
  title: string
  message: string
  channel: string
  priority: string
  status: string
  read_at: string | null
  created_at: string
}

export default function NotificationCenter() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [loading, setLoading] = useState(false)

  const loadNotifications = async () => {
    try {
      setLoading(true)
      const data = await api<NotificationItem[] | { results: NotificationItem[] }>('/notifications/items/')
      const items = Array.isArray(data) ? data : (data.results || [])
      setNotifications(items)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadNotifications()
    const timer = setInterval(loadNotifications, 45000)
    return () => clearInterval(timer)
  }, [])

  const unreadCount = notifications.filter(n => n.status !== 'READ').length

  const handleMarkRead = async (id: string) => {
    try {
      await api(`/notifications/items/${id}/mark_read/`, { method: 'POST' })
      setNotifications(prev => prev.map(n => (n.id === id ? { ...n, status: 'READ', read_at: new Date().toISOString() } : n)))
    } catch (e) {
      console.error(e)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api('/notifications/items/mark_all_read/', { method: 'POST' })
      setNotifications(prev => prev.map(n => ({ ...n, status: 'READ', read_at: new Date().toISOString() })))
    } catch (e) {
      console.error(e)
    }
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => {
          setOpen(!open)
          if (!open) loadNotifications()
        }}
        style={{
          position: 'relative',
          background: 'rgba(255,255,255,0.1)',
          border: '1px solid rgba(255,255,255,0.2)',
          color: '#fff',
          borderRadius: '8px',
          padding: '0.45rem 0.75rem',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          fontSize: '0.9rem'
        }}
        title={t('notifications.title')}
      >
        <span>🔔</span>
        <span>{t('notifications.title')}</span>
        {unreadCount > 0 && (
          <span style={{
            background: '#e53e3e',
            color: '#fff',
            borderRadius: '999px',
            padding: '0.1rem 0.45rem',
            fontSize: '0.75rem',
            fontWeight: 700
          }}>
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: '110%',
          insetInlineEnd: 0,
          width: '320px',
          maxHeight: '400px',
          overflowY: 'auto',
          background: '#ffffff',
          color: '#1a202c',
          border: '1px solid #cbd5e0',
          borderRadius: '10px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
          zIndex: 1000,
          padding: '0.75rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.5rem' }}>
            <strong style={{ fontSize: '0.9rem' }}>{t('notifications.title')}</strong>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                style={{ fontSize: '0.75rem', background: 'none', border: 'none', color: '#2b6cb0', cursor: 'pointer', textDecoration: 'underline' }}
              >
                {t('notifications.markAllRead')}
              </button>
            )}
          </div>

          {loading && notifications.length === 0 && (
            <div style={{ padding: '1rem', textAlign: 'center', color: '#718096', fontSize: '0.85rem' }}>
              {t('common.loading')}
            </div>
          )}

          {!loading && notifications.length === 0 && (
            <div style={{ padding: '1rem', textAlign: 'center', color: '#718096', fontSize: '0.85rem' }}>
              {t('notifications.empty')}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {notifications.map(n => {
              const isUnread = n.status !== 'READ'
              return (
                <div
                  key={n.id}
                  style={{
                    padding: '0.5rem',
                    borderRadius: '6px',
                    background: isUnread ? '#ebf8ff' : '#f7fafc',
                    border: isUnread ? '1px solid #bee3f8' : '1px solid #edf2f7',
                    fontSize: '0.8rem'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.25rem' }}>
                    <strong style={{ color: isUnread ? '#2b6cb0' : '#4a5568' }}>{n.title}</strong>
                    {isUnread && (
                      <button
                        onClick={() => handleMarkRead(n.id)}
                        style={{ fontSize: '0.7rem', background: '#3182ce', color: '#fff', border: 'none', borderRadius: '4px', padding: '0.1rem 0.4rem', cursor: 'pointer' }}
                      >
                        ✓
                      </button>
                    )}
                  </div>
                  <div style={{ color: '#2d3748', whiteSpace: 'pre-wrap', lineHeight: 1.3 }}>{n.message}</div>
                  <div style={{ color: '#a0aec0', fontSize: '0.7rem', marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between' }}>
                    <span>{new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    <span>{n.priority}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
