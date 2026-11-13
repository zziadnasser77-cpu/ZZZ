import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../api'
import { useAuth } from '../auth'

export default function LoginPage() {
  const { me, login } = useAuth()
  const { t } = useTranslation()
  const nav = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [needOtp, setNeedOtp] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (me) return <Navigate to="/" replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(email, password, needOtp ? otp : undefined)
      nav('/')
    } catch (err) {
      if (err instanceof ApiError && err.code === 'mfa_required') { setNeedOtp(true); setError(t('login.otpRequired')) }
      else if (err instanceof ApiError && err.code === 'locked') setError(t('login.locked'))
      else setError(t('login.failed'))
    } finally { setBusy(false) }
  }

  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <h1>{t('app.name')} — {t('login.title')}</h1>
        <div className="field"><label htmlFor="email">{t('login.email')}</label>
          <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
        <div className="field"><label htmlFor="password">{t('login.password')}</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div>
        {needOtp && <div className="field"><label htmlFor="otp">{t('login.otp')}</label>
          <input id="otp" inputMode="numeric" autoComplete="one-time-code" value={otp} onChange={(e) => setOtp(e.target.value)} required /></div>}
        {error && <div className="error" role="alert">{error}</div>}
        <button className="btn" disabled={busy}>{t('login.submit')}</button>
      </form>
    </div>
  )
}
