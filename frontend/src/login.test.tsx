import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import './i18n'
import i18n from './i18n'
import { AuthProvider } from './auth'
import LoginPage from './pages/Login'

describe('Login page', () => {
  it('renders Arabic by default with RTL document direction', () => {
    render(<AuthProvider><MemoryRouter><LoginPage /></MemoryRouter></AuthProvider>)
    expect(screen.getByLabelText('البريد الإلكتروني')).toBeInTheDocument()
    expect(document.documentElement.dir).toBe('rtl')
  })

  it('switches to LTR for English', async () => {
    await i18n.changeLanguage('en')
    expect(document.documentElement.dir).toBe('ltr')
    await i18n.changeLanguage('ar')
  })
})
