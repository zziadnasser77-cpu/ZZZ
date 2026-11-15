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
  const [showPassword, setShowPassword] = useState(false)

  if (me) return <Navigate to="/" replace />

  async function performLogin(identifier: string, pwd: string, otpCode?: string) {
    setBusy(true)
    setError('')
    try {
      await login(identifier, pwd, otpCode)
      nav('/')
    } catch (err) {
      if (err instanceof ApiError && err.code === 'mfa_required') {
        setNeedOtp(true)
        setError(t('login.otpRequired') || 'أدخل رمز التحقق الثنائي MFA')
      } else if (err instanceof ApiError && err.code === 'locked') {
        setError(t('login.locked') || 'الحساب مقفل مؤقتاً لمحاولات خاطئة')
      } else {
        setError(t('login.failed') || 'بيانات الدخول غير صحيحة. تأكد من إدخال 1 و 1')
      }
    } finally {
      setBusy(false)
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    await performLogin(email, password, needOtp ? otp : undefined)
  }

  // Quick 1-click Dev login
  async function handleQuickDevLogin() {
    setEmail('1')
    setPassword('1')
    await performLogin('1', '1')
  }

  return (
    <div className="login-wrapper" style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(circle at 50% 20%, #0d233a 0%, #071320 100%)',
      padding: '1.5rem',
      fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, Tahoma, sans-serif",
      direction: 'rtl'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '440px',
        background: '#ffffff',
        borderRadius: '18px',
        boxShadow: '0 20px 45px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.1)',
        overflow: 'hidden',
        border: '1px solid rgba(226, 232, 240, 0.8)'
      }}>
        {/* Header Banner */}
        <div style={{
          background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
          color: '#ffffff',
          padding: '2rem 1.75rem 1.75rem',
          textAlign: 'center',
          position: 'relative'
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            margin: '0 auto 1rem',
            background: 'rgba(255, 255, 255, 0.15)',
            borderRadius: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backdropFilter: 'blur(8px)',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            border: '1px solid rgba(255, 255, 255, 0.25)'
          }}>
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>
          <h1 style={{ margin: 0, fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
            نظام SMSES الطبي الذكي
          </h1>
          <p style={{ margin: '0.4rem 0 0', fontSize: '0.85rem', opacity: 0.9, fontWeight: 500 }}>
            Smart Medical Sales & Engineering Suite
          </p>
        </div>

        {/* Quick Dev Login Callout */}
        <div style={{
          padding: '1rem 1.75rem 0.5rem',
          background: '#f8fafc',
          borderBottom: '1px solid #e2e8f0'
        }}>
          <button
            type="button"
            onClick={handleQuickDevLogin}
            disabled={busy}
            style={{
              width: '100%',
              padding: '0.75rem 1rem',
              background: '#ecfdf5',
              border: '1.5px dashed #059669',
              borderRadius: '10px',
              color: '#065f46',
              fontWeight: 700,
              fontSize: '0.9rem',
              cursor: busy ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              transition: 'all 0.2s ease',
              boxShadow: '0 1px 3px rgba(5, 150, 105, 0.1)'
            }}
            onMouseOver={(e) => (e.currentTarget.style.background = '#d1fae5')}
            onMouseOut={(e) => (e.currentTarget.style.background = '#ecfdf5')}
          >
            <span>⚡</span>
            <span>تسجيل دخول سريع كمسؤول (1 / 1)</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={submit} style={{ padding: '1.5rem 1.75rem 2rem' }}>
          {error && (
            <div style={{
              background: '#fef2f2',
              border: '1px solid #fecaca',
              color: '#b91c1c',
              padding: '0.8rem 1rem',
              borderRadius: '10px',
              fontSize: '0.85rem',
              fontWeight: 600,
              marginBottom: '1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem'
            }} role="alert">
              <span>⚠️</span>
              <div>{error}</div>
            </div>
          )}

          {/* Identifier Input */}
          <div style={{ marginBottom: '1.2rem' }}>
            <label htmlFor="email" style={{
              display: 'block',
              fontSize: '0.86rem',
              fontWeight: 700,
              color: '#334155',
              marginBottom: '0.45rem'
            }}>
              اسم المستخدم أو البريد:
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="email"
                type="text"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="أدخل 1 أو اسم المستخدم"
                required
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  border: '1.5px solid #cbd5e1',
                  fontSize: '0.95rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                  background: '#f8fafc'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = '#0284c7'
                  e.target.style.background = '#ffffff'
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = '#cbd5e1'
                  e.target.style.background = '#f8fafc'
                }}
              />
            </div>
          </div>

          {/* Password Input */}
          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
              <label htmlFor="password" style={{
                fontSize: '0.86rem',
                fontWeight: 700,
                color: '#334155'
              }}>
                كلمة المرور:
              </label>
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#0284c7',
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  fontWeight: 600,
                  padding: 0
                }}
              >
                {showPassword ? 'إخفاء' : 'إظهار'}
              </button>
            </div>
            <div style={{ position: 'relative' }}>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="أدخل 1 أو كلمة المرور"
                required
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  border: '1.5px solid #cbd5e1',
                  fontSize: '0.95rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                  background: '#f8fafc'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = '#0284c7'
                  e.target.style.background = '#ffffff'
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = '#cbd5e1'
                  e.target.style.background = '#f8fafc'
                }}
              />
            </div>
          </div>

          {/* OTP MFA (if enabled) */}
          {needOtp && (
            <div style={{ marginBottom: '1.25rem' }}>
              <label htmlFor="otp" style={{
                display: 'block',
                fontSize: '0.86rem',
                fontWeight: 700,
                color: '#334155',
                marginBottom: '0.45rem'
              }}>
                رمز التحقق (MFA):
              </label>
              <input
                id="otp"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="6 أرقام"
                required
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  border: '1.5px solid #0284c7',
                  fontSize: '1.1rem',
                  textAlign: 'center',
                  letterSpacing: '0.3em',
                  outline: 'none',
                  boxSizing: 'border-box'
                }}
              />
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={busy}
            style={{
              width: '100%',
              padding: '0.85rem 1rem',
              background: busy ? '#94a3b8' : 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '10px',
              fontSize: '1rem',
              fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 12px rgba(2, 132, 199, 0.3)',
              transition: 'all 0.2s ease',
              marginTop: '0.5rem'
            }}
          >
            {busy ? 'جاري التحقق وتسجيل الدخول…' : 'تسجيل الدخول'}
          </button>

          <div style={{
            marginTop: '1.5rem',
            paddingTop: '1rem',
            borderTop: '1px solid #f1f5f9',
            textAlign: 'center',
            fontSize: '0.8rem',
            color: '#64748b'
          }}>
            <span>بيانات التطوير السريعة: </span>
            <strong style={{ color: '#0f172a' }}>المستخدم: 1 | كلمة المرور: 1</strong>
          </div>
        </form>
      </div>
    </div>
  )
}
