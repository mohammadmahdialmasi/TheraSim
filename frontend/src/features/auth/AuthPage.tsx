import { useState, type FormEvent } from 'react'
import {
  AlertCircle,
  Languages,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
} from 'lucide-react'

import brandLogo from '../../assets/brand-logo.svg'
import type { Language } from '../../i18n'

const copy = {
  en: {
    initializeTitle: 'Secure local setup',
    loginTitle: 'Sign in to TheraSim',
    initializeDescription:
      'Create the single local reviewer account. Your password is stored as a scrypt hash and is never returned by the API.',
    loginDescription:
      'Sign in with the local reviewer password. This browser session expires after eight hours.',
    reviewerName: 'Reviewer name',
    password: 'Password',
    passwordHelp: 'Use at least 12 characters.',
    initialize: 'Create account',
    login: 'Sign in',
    submitting: 'Please wait...',
    unavailable: 'The local backend could not be reached. Start it and retry.',
    retry: 'Retry',
    failed: 'Authentication failed. Check the input and try again.',
    loopbackOnly:
      'Initial account setup is only allowed from the local computer.',
    switchLanguage: 'فارسی',
  },
  fa: {
    initializeTitle: 'راه‌اندازی امن محلی',
    loginTitle: 'ورود به تراسیم',
    initializeDescription:
      'حساب محلی بازبین را ایجاد کنید. گذرواژه به‌صورت هش scrypt ذخیره می‌شود و هرگز از API بازگردانده نمی‌شود.',
    loginDescription:
      'با گذرواژهٔ بازبین محلی وارد شوید. این نشست مرورگر پس از هشت ساعت منقضی می‌شود.',
    reviewerName: 'نام بازبین',
    password: 'گذرواژه',
    passwordHelp: 'گذرواژه‌ای با دست‌کم ۱۲ نویسه انتخاب کنید.',
    initialize: 'ساخت حساب',
    login: 'ورود',
    submitting: 'لطفاً صبر کنید…',
    unavailable: 'اتصال به بک‌اند محلی برقرار نشد. آن را اجرا و دوباره تلاش کنید.',
    retry: 'تلاش دوباره',
    failed: 'ورود ناموفق بود. اطلاعات را بررسی و دوباره تلاش کنید.',
    loopbackOnly: 'ساخت حساب اولیه فقط از همین رایانه مجاز است.',
    switchLanguage: 'English',
  },
} as const

export function AuthPage({
  language,
  mode,
  error,
  onAuthenticate,
  onRetry,
  onToggleLanguage,
}: {
  language: Language
  mode: 'checking' | 'initialize' | 'login' | 'unavailable'
  error: string
  onAuthenticate: (reviewerName: string, password: string) => Promise<void>
  onRetry: () => void
  onToggleLanguage: () => void
}) {
  const labels = copy[language]
  const [reviewerName, setReviewerName] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    try {
      await onAuthenticate(reviewerName, password)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="auth-page" dir={language === 'fa' ? 'rtl' : 'ltr'}>
      <section className="surface-card auth-card">
        <div className="auth-brand">
          <img src={brandLogo} alt="TheraSim" />
          <div>
            <h1>TheraSim</h1>
            <p>{mode === 'initialize' ? labels.initializeTitle : labels.loginTitle}</p>
          </div>
          <button
            type="button"
            className="language-switch auth-language-switch"
            onClick={onToggleLanguage}
            aria-label={labels.switchLanguage}
          >
            <Languages size={17} />
            <span>{labels.switchLanguage}</span>
          </button>
        </div>

        {mode === 'checking' ? (
          <p className="auth-status" role="status">
            <LoaderCircle className="spin" size={18} />
            {labels.submitting}
          </p>
        ) : mode === 'unavailable' ? (
          <>
            <p>{labels.unavailable}</p>
            <button type="button" className="primary-button" onClick={onRetry}>
              {labels.retry}
            </button>
          </>
        ) : (
          <>
            <p className="auth-description">
              <ShieldCheck size={18} />
              {mode === 'initialize'
                ? labels.initializeDescription
                : labels.loginDescription}
            </p>

            {error && (
              <div className="sessions-alert sessions-alert-error" role="alert">
                <AlertCircle size={17} />
                <span dir="auto">
                  {error === 'loopback_setup_required'
                    ? labels.loopbackOnly
                    : language === 'fa'
                      ? labels.failed
                      : error}
                </span>
              </div>
            )}

            <form className="auth-form" onSubmit={(event) => void handleSubmit(event)}>
              {mode === 'initialize' && (
                <label className="sessions-field">
                  <span>{labels.reviewerName}</span>
                  <input
                    autoComplete="name"
                    maxLength={80}
                    required
                    value={reviewerName}
                    onChange={(event) => setReviewerName(event.target.value)}
                  />
                </label>
              )}
              <label className="sessions-field">
                <span>{labels.password}</span>
                <input
                  autoComplete={mode === 'initialize' ? 'new-password' : 'current-password'}
                  minLength={mode === 'initialize' ? 12 : 1}
                  maxLength={1024}
                  required
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                {mode === 'initialize' && (
                  <small className="auth-help">{labels.passwordHelp}</small>
                )}
              </label>
              <button
                type="submit"
                className="primary-button"
                disabled={submitting}
              >
                {submitting ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <LockKeyhole size={16} />
                )}
                {submitting
                  ? labels.submitting
                  : mode === 'initialize'
                    ? labels.initialize
                    : labels.login}
              </button>
            </form>
          </>
        )}
      </section>
    </main>
  )
}
