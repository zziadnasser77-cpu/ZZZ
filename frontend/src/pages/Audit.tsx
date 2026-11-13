import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { api, type Page } from '../api'

interface Ev { id: string; occurred_at: string; actor_email: string | null; action: string; entity_type: string; summary: string; sensitive: boolean }

export default function AuditPage() {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['audit'], queryFn: () => api<Page<Ev>>('/audit-events/') })
  const fmt = (s: string) => new Date(s).toLocaleString(i18n.language === 'ar' ? 'ar-YE' : 'en-GB')
  return (
    <>
      <h1>{t('audit.title')}</h1>
      {q.isLoading ? t('common.loading') : (
        <table>
          <thead><tr><th>{t('audit.when')}</th><th>{t('audit.who')}</th><th>{t('audit.action')}</th><th>{t('audit.entity')}</th><th>{t('audit.summary')}</th></tr></thead>
          <tbody>
            {q.data?.results.map((e) => (
              <tr key={e.id}><td>{fmt(e.occurred_at)}</td><td>{e.actor_email ?? '—'}</td><td>{e.action}{e.sensitive ? ' ⚠' : ''}</td><td>{e.entity_type}</td><td>{e.summary}</td></tr>
            ))}
            {q.data?.results.length === 0 && <tr><td colSpan={5}>{t('common.empty')}</td></tr>}
          </tbody>
        </table>
      )}
    </>
  )
}
