import { useEffect, useState } from 'react'
import { Download, LoaderCircle, ShieldCheck } from 'lucide-react'

import type { Language, Translation } from '../../i18n'
import { downloadSupportArchive, getSupportPreview } from '../../lib/api'
import { formatSupportPreview } from '../../lib/supportDiagnostics'

export function SupportExport({
  language,
  t,
}: {
  language: Language
  t: Translation
}) {
  return <SupportExportContent key={language} language={language} t={t} />
}

function SupportExportContent({
  language,
  t,
}: {
  language: Language
  t: Translation
}) {
  const [confirmedLanguage, setConfirmedLanguage] = useState<Language | null>(
    null,
  )
  const [supportBusy, setSupportBusy] = useState(false)
  const [supportError, setSupportError] = useState('')
  const [supportReady, setSupportReady] = useState(false)
  const [supportPreviewState, setSupportPreviewState] = useState<{
    language: Language
    loading: boolean
    preview: Awaited<ReturnType<typeof getSupportPreview>> | null
  }>({ language, loading: true, preview: null })

  useEffect(() => {
    let active = true
    void getSupportPreview(language)
      .then((preview) => {
        if (active) {
          setSupportPreviewState({
            language,
            loading: false,
            preview: preview.language === language ? preview : null,
          })
        }
      })
      .catch(() => {
        if (active) {
          setSupportPreviewState({ language, loading: false, preview: null })
        }
      })
    return () => {
      active = false
    }
  }, [language])

  const supportConfirmed = confirmedLanguage === language
  const supportPreviewLoading = supportPreviewState.language !== language
    || supportPreviewState.loading
  const supportPreview = supportPreviewState.language === language
    ? supportPreviewState.preview
    : null
  const previewText = supportPreview?.language === language
    ? formatSupportPreview(supportPreview, language)
    : null

  async function createSupportArchive() {
    if (!supportConfirmed || !previewText) return
    setSupportBusy(true)
    setSupportError('')
    setSupportReady(false)
    try {
      const archive = await downloadSupportArchive(language)
      const url = URL.createObjectURL(archive.blob)
      const download = document.createElement('a')
      download.href = url
      download.download = archive.filename
      document.body.append(download)
      download.click()
      download.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setSupportReady(true)
    } catch {
      setSupportError(t.supportExportFailed)
    } finally {
      setSupportBusy(false)
    }
  }

  const supportMailSubject = language === 'fa'
    ? 'درخواست پشتیبانی TheraSim'
    : 'TheraSim support request'
  const supportMailBody = language === 'fa'
    ? 'سلام،\n\nبرای بررسی مشکل، بستهٔ عیب‌یابی را پس از مرور محتوا به‌صورت دستی پیوست کنید. این پیش‌نویس به‌تنهایی چیزی ارسال نمی‌کند.\n\nشرح مشکل:\n'
    : 'Hello,\n\nFor troubleshooting, please review the diagnostics ZIP and attach it manually if you choose. This draft does not send anything by itself.\n\nIssue description:\n'
  const supportMailHref = `mailto:m.x.a.0096@gmail.com?subject=${encodeURIComponent(supportMailSubject)}&body=${encodeURIComponent(supportMailBody)}`

  return (
    <section className="surface-card support-card">
      <div className="card-heading">
        <span className="heading-icon"><ShieldCheck size={19} /></span>
        <div>
          <h3>{t.supportTitle}</h3>
          <p>{t.supportDescription}</p>
        </div>
      </div>
      <div className="support-preview" aria-label={t.supportPreviewTitle}>
        <strong>{t.supportPreviewTitle}</strong>
        <p>{t.supportPreviewIncluded}</p>
        <p>{t.supportPreviewExcluded}</p>
        <p>{t.supportPreviewFieldsLabel}</p>
        {supportPreviewLoading ? (
          <p role="status">{t.supportPreviewLoading}</p>
        ) : previewText ? (
          <pre
            dir="ltr"
            style={{
              maxHeight: '16rem',
              overflow: 'auto',
              overflowWrap: 'anywhere',
              textAlign: 'left',
              whiteSpace: 'pre-wrap',
            }}
          >
            {previewText}
          </pre>
        ) : (
          <p role="alert">{t.supportPreviewUnavailable}</p>
        )}
      </div>
      <label className="provider-api-key-clear">
        <input
          type="checkbox"
          checked={supportConfirmed}
          disabled={!previewText || supportBusy}
          onChange={(event) => {
            setConfirmedLanguage(event.target.checked ? language : null)
            setSupportError('')
          }}
        />
        <span>{t.supportConfirm}</span>
      </label>
      <div className="provider-settings-actions">
        <button
          type="button"
          className="primary-button"
          disabled={!previewText || !supportConfirmed || supportBusy}
          onClick={() => void createSupportArchive()}
        >
          {supportBusy
            ? <LoaderCircle className="spin" size={16} />
            : <Download size={16} />}
          {supportBusy ? t.supportExporting : t.supportExport}
        </button>
      </div>
      {supportError && <p className="provider-settings-error" role="alert">{supportError}</p>}
      {supportReady && (
        <>
          <p className="provider-settings-success" role="status">{t.supportExportReady}</p>
          <div>
            <a className="secondary-button support-email-link" href={supportMailHref}>
              {t.supportEmail}
            </a>
            <p className="provider-settings-note">{t.supportEmailHelp}</p>
          </div>
        </>
      )}
    </section>
  )
}
