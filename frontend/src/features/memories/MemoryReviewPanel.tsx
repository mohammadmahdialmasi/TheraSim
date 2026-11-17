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

import { listMemoryCandidates, reviewMemoryCandidate } from './api'
import type { MemoryRecord } from './types'

const text = {
  en: {
    title: 'Memory review',
    description:
      'Review proposed memories and their source evidence before they can influence later sessions.',
    reviewerWarning:
      'Authentication is not configured. Decisions are recorded as “unverified_local_caller” and do not verify a person’s identity.',
    refresh: 'Refresh candidates',
    loading: 'Loading memory candidates…',
    empty: 'There are no memory candidates awaiting review for this Run.',
    rationale: 'Review rationale',
    rationalePlaceholder: 'Record why this memory should be accepted or rejected.',
    accept: 'Accept',
    reject: 'Reject',
    accepted: 'Memory accepted.',
    rejected: 'Memory rejected.',
    source: 'Source evidence',
    session: 'Session',
    message: 'Message ID',
    confidence: 'Proposal confidence',
    error: 'Could not load or review memory candidates.',
  },
  fa: {
    title: 'بازبینی حافظه',
    description:
      'پیشنهادهای حافظه و شواهد منبع آن‌ها را پیش از استفاده در جلسات بعدی بررسی کن.',
    reviewerWarning:
      'احراز هویت فعال نیست. تصمیم‌ها با شناسه «unverified_local_caller» ثبت می‌شوند و هویت هیچ فردی را تأیید نمی‌کنند.',
    refresh: 'تازه‌سازی پیشنهادها',
    loading: 'در حال بارگذاری پیشنهادهای حافظه…',
    empty: 'پیشنهاد حافظه‌ای برای این اجرا در انتظار بازبینی نیست.',
    rationale: 'دلیل بازبینی',
    rationalePlaceholder: 'بنویس چرا این حافظه باید پذیرفته یا رد شود.',
    accept: 'پذیرش',
    reject: 'رد',
    accepted: 'حافظه پذیرفته شد.',
    rejected: 'حافظه رد شد.',
    source: 'شواهد منبع',
    session: 'جلسه',
    message: 'شناسه پیام',
    confidence: 'اطمینان پیشنهاد',
    error: 'بارگذاری یا بازبینی پیشنهادهای حافظه ناموفق بود.',
  },
} as const

interface MemoryReviewPanelProps {
  runId: string
  language: Language
  refreshKey: number
}

export function MemoryReviewPanel({
  runId,
  language,
  refreshKey,
}: MemoryReviewPanelProps) {
  const copy = text[language]
  const [memories, setMemories] = useState<MemoryRecord[]>([])
  const [rationales, setRationales] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busyMemoryId, setBusyMemoryId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState<'accepted' | 'rejected' | ''>('')

  const loadCandidates = useCallback(async () => {
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const response = await listMemoryCandidates(runId)
      setMemories(response.data)
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : 'memory_request_failed',
      )
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCandidates()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadCandidates, refreshKey])

  async function handleReview(
    memory: MemoryRecord,
    decision: 'accepted' | 'rejected',
  ) {
    const rationale = rationales[memory.memory_id]?.trim() ?? ''
    if (!rationale || busyMemoryId) return

    setBusyMemoryId(memory.memory_id)
    setError('')
    setNotice('')
    try {
      await reviewMemoryCandidate(
        runId,
        memory.memory_id,
        decision,
        rationale,
      )
      setMemories((current) =>
        current.filter((item) => item.memory_id !== memory.memory_id),
      )
      setRationales((current) => {
        const next = { ...current }
        delete next[memory.memory_id]
        return next
      })
      setNotice(decision)
    } catch (reviewError) {
      setError(
        reviewError instanceof Error
          ? reviewError.message
          : 'memory_request_failed',
      )
    } finally {
      setBusyMemoryId('')
    }
  }

  return (
    <section
      className="surface-card memory-review-card"
      aria-labelledby="memory-review-title"
    >
      <div className="memory-review-heading">
        <div>
          <h2 id="memory-review-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <button
          type="button"
          className="secondary-button memory-refresh-button"
          onClick={() => void loadCandidates()}
          disabled={loading || Boolean(busyMemoryId)}
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
          <span>
            {error === 'memory_request_failed' ? copy.error : error}
          </span>
        </div>
      )}
      {notice && (
        <div className="sessions-alert sessions-alert-notice" role="status">
          <Check size={17} />
          <span>
            {notice === 'accepted' ? copy.accepted : copy.rejected}
          </span>
        </div>
      )}

      {loading && memories.length === 0 && (
        <p className="memory-review-state" role="status">
          <LoaderCircle className="spin" size={15} />
          {copy.loading}
        </p>
      )}
      {!loading && !error && memories.length === 0 && (
        <p className="memory-review-state">{copy.empty}</p>
      )}

      <div className="memory-candidate-list">
        {memories.map((memory) => {
          const rationale = rationales[memory.memory_id] ?? ''
          const isBusy = busyMemoryId === memory.memory_id

          return (
            <article className="memory-candidate" key={memory.memory_id}>
              <div className="memory-candidate-meta">
                <span>{memory.memory_scope}</span>
                <span>{memory.memory_type}</span>
                <span>{memory.information_class}</span>
                {memory.confidence !== null && (
                  <span>
                    {copy.confidence}: {Math.round(memory.confidence * 100)}%
                  </span>
                )}
              </div>
              <p className="memory-candidate-content" dir="auto">
                {memory.content}
              </p>

              <div className="memory-evidence">
                <strong>{copy.source}</strong>
                {memory.evidence.map((evidence) => (
                  <blockquote
                    key={`${memory.memory_id}-${evidence.message_id}`}
                    dir="auto"
                  >
                    {evidence.excerpt ? (
                      <p>{evidence.excerpt}</p>
                    ) : (
                      <p>{evidence.relationship_type}</p>
                    )}
                    <footer>
                      {copy.session}:{' '}
                      <bdi dir="ltr">
                        {memory.source_session_id ?? '—'}
                      </bdi>
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
                  onChange={(event) =>
                    setRationales((current) => ({
                      ...current,
                      [memory.memory_id]: event.target.value,
                    }))
                  }
                  placeholder={copy.rationalePlaceholder}
                  maxLength={4000}
                  rows={2}
                  required
                  disabled={Boolean(busyMemoryId)}
                />
              </label>

              <div className="memory-review-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void handleReview(memory, 'rejected')}
                  disabled={!rationale.trim() || Boolean(busyMemoryId)}
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
                  onClick={() => void handleReview(memory, 'accepted')}
                  disabled={!rationale.trim() || Boolean(busyMemoryId)}
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
