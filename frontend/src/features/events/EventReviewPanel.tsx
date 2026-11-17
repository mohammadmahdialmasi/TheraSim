import { useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  Check,
  LoaderCircle,
  RefreshCw,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'

import type { Language } from '../../i18n'

import { listPendingEvents, reviewEvent } from './api'
import type { BehavioralEvent } from './types'

const text = {
  en: {
    title: 'Behavioral event review',
    description:
      'Review model-proposed events, interpretations, and source evidence. Acceptance records a review decision; it does not establish a clinical fact.',
    reviewerWarning:
      'Event decisions are attributed to the authenticated local reviewer. Acceptance does not establish a clinical fact.',
    refresh: 'Refresh events',
    loading: 'Loading event proposals…',
    empty: 'There are no event proposals awaiting review for this Run.',
    rationale: 'Review rationale',
    rationalePlaceholder: 'Record why this event should be accepted or rejected.',
    accept: 'Accept',
    reject: 'Reject',
    accepted: 'Event accepted.',
    rejected: 'Event rejected.',
    observedFact: 'Observed report',
    interpretation: 'Model interpretation',
    source: 'Source evidence',
    session: 'Session',
    message: 'Message ID',
    confidence: 'Proposal confidence',
    error: 'Could not load or review event proposals.',
  },
  fa: {
    title: 'بازبینی رویدادهای رفتاری',
    description:
      'رویدادهای پیشنهادی مدل، تفسیرها و شواهد منبع را بررسی کن. پذیرش فقط تصمیم بازبینی را ثبت می‌کند و واقعیت بالینی را اثبات نمی‌کند.',
    reviewerWarning:
      'تصمیم‌ها به بازبین محلی احراز هویت‌شده نسبت داده می‌شوند. پذیرش یک رویداد، واقعیت بالینی را اثبات نمی‌کند.',
    refresh: 'تازه‌سازی رویدادها',
    loading: 'در حال بارگذاری پیشنهادهای رویداد…',
    empty: 'رویدادی برای این اجرا در انتظار بازبینی نیست.',
    rationale: 'دلیل بازبینی',
    rationalePlaceholder: 'بنویس چرا این رویداد باید پذیرفته یا رد شود.',
    accept: 'پذیرش',
    reject: 'رد',
    accepted: 'رویداد پذیرفته شد.',
    rejected: 'رویداد رد شد.',
    observedFact: 'گزارش مشاهده‌شده',
    interpretation: 'تفسیر مدل',
    source: 'شواهد منبع',
    session: 'جلسه',
    message: 'شناسه پیام',
    confidence: 'اطمینان پیشنهاد',
    error: 'بارگذاری یا بازبینی رویداد ناموفق بود.',
  },
} as const

interface EventReviewPanelProps {
  runId: string
  language: Language
  refreshKey: number
}

function payloadText(
  event: BehavioralEvent,
  key: 'summary' | 'observed_fact' | 'interpretation',
) {
  const value = event.payload[key]
  return typeof value === 'string' ? value : ''
}

export function EventReviewPanel({
  runId,
  language,
  refreshKey,
}: EventReviewPanelProps) {
  const copy = text[language]
  const [events, setEvents] = useState<BehavioralEvent[]>([])
  const [rationales, setRationales] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busyEventId, setBusyEventId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState<'accepted' | 'rejected' | ''>('')

  const loadEvents = useCallback(async () => {
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const response = await listPendingEvents(runId)
      setEvents(response.data)
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : 'event_request_failed',
      )
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadEvents()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadEvents, refreshKey])

  async function handleReview(
    event: BehavioralEvent,
    decision: 'accepted' | 'rejected',
  ) {
    const rationale = rationales[event.event_id]?.trim() ?? ''
    if (!rationale || busyEventId) return

    setBusyEventId(event.event_id)
    setError('')
    setNotice('')
    try {
      await reviewEvent(runId, event.event_id, decision, rationale)
      setEvents((current) =>
        current.filter((item) => item.event_id !== event.event_id),
      )
      setRationales((current) => {
        const next = { ...current }
        delete next[event.event_id]
        return next
      })
      setNotice(decision)
    } catch (reviewError) {
      setError(
        reviewError instanceof Error
          ? reviewError.message
          : 'event_request_failed',
      )
    } finally {
      setBusyEventId('')
    }
  }

  return (
    <section
      className="surface-card memory-review-card"
      aria-labelledby="event-review-title"
    >
      <div className="memory-review-heading">
        <div>
          <h2 id="event-review-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <button
          type="button"
          className="secondary-button memory-refresh-button"
          onClick={() => void loadEvents()}
          disabled={loading || Boolean(busyEventId)}
        >
          {loading ? (
            <LoaderCircle className="spin" size={15} />
          ) : (
            <RefreshCw size={15} />
          )}
          {copy.refresh}
        </button>
      </div>

      <div className="memory-review-warning" role="note">
        <ShieldAlert size={17} />
        <p>{copy.reviewerWarning}</p>
      </div>

      {error && (
        <div className="sessions-alert sessions-alert-error" role="alert">
          <AlertCircle size={17} />
          <span>{error === 'event_request_failed' ? copy.error : error}</span>
        </div>
      )}
      {notice && (
        <div className="sessions-alert sessions-alert-notice" role="status">
          <Check size={17} />
          <span>{notice === 'accepted' ? copy.accepted : copy.rejected}</span>
        </div>
      )}

      {loading && events.length === 0 && (
        <p className="memory-review-state" role="status">
          <LoaderCircle className="spin" size={15} />
          {copy.loading}
        </p>
      )}
      {!loading && !error && events.length === 0 && (
        <p className="memory-review-state">{copy.empty}</p>
      )}

      <div className="memory-candidate-list">
        {events.map((event) => {
          const rationale = rationales[event.event_id] ?? ''
          const isBusy = busyEventId === event.event_id
          const confidence = event.payload.confidence

          return (
            <article className="memory-candidate" key={event.event_id}>
              <div className="memory-candidate-meta">
                <span>{event.event_type}</span>
                <span>{event.extraction_method}</span>
                {typeof confidence === 'number' && (
                  <span>
                    {copy.confidence}: {Math.round(confidence * 100)}%
                  </span>
                )}
              </div>
              <p className="memory-candidate-content" dir="auto">
                {payloadText(event, 'summary')}
              </p>
              <div className="memory-evidence">
                <strong>{copy.observedFact}</strong>
                <p dir="auto">{payloadText(event, 'observed_fact')}</p>
                <strong>{copy.interpretation}</strong>
                <p dir="auto">{payloadText(event, 'interpretation')}</p>
              </div>

              <div className="memory-evidence">
                <strong>{copy.source}</strong>
                {event.evidence.map((evidence) => (
                  <blockquote
                    key={`${event.event_id}-${evidence.message_id}`}
                    dir="auto"
                  >
                    <p>{evidence.excerpt ?? evidence.annotation ?? '—'}</p>
                    <footer>
                      {copy.session}:{' '}
                      <bdi dir="ltr">{event.session_id ?? '—'}</bdi>
                      {' · '}
                      {copy.message}:{' '}
                      <bdi dir="ltr">{evidence.message_id}</bdi>
                    </footer>
                  </blockquote>
                ))}
              </div>

              <label className="memory-rationale">
                <span>{copy.rationale}</span>
                <textarea
                  value={rationale}
                  onChange={(change) =>
                    setRationales((current) => ({
                      ...current,
                      [event.event_id]: change.target.value,
                    }))
                  }
                  placeholder={copy.rationalePlaceholder}
                  maxLength={4000}
                  rows={2}
                  required
                  disabled={Boolean(busyEventId)}
                />
              </label>

              <div className="memory-review-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void handleReview(event, 'rejected')}
                  disabled={!rationale.trim() || Boolean(busyEventId)}
                >
                  {isBusy ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <ThumbsDown size={15} />
                  )}
                  {copy.reject}
                </button>
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => void handleReview(event, 'accepted')}
                  disabled={!rationale.trim() || Boolean(busyEventId)}
                >
                  {isBusy ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <ThumbsUp size={15} />
                  )}
                  {copy.accept}
                </button>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
