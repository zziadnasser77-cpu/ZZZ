import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth'

export default function Dashboard() {
  const { me } = useAuth()
  const { t } = useTranslation()
  return (
    <>
      <h1>{t('dashboard.welcome')} {me?.full_name || me?.email}</h1>
      <div className="card">{t('dashboard.hint')}</div>
    </>
  )
}
