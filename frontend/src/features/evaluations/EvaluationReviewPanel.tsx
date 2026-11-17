import { useState, type FormEvent } from 'react'

import type { Language } from '../../i18n'

import { addEvaluationReview } from './api'
import type { EvaluationReport, EvaluationReview } from './types'

const copy = {
  en: {
    title: 'Human review history',
    pending: 'No human review has been recorded.',
    accepted: 'Accepted',
    revisionRequested: 'Revision requested',
    decision: 'Decision',
    feedback: 'Reviewer feedback',
    feedbackPlaceholder: 'Record a concise rationale for this decision.',
    submit: 'Save review',
    saving: 'Saving review…',
    error: 'Could not save the review. Please try again.',
    unavailable: 'This report is stale or lacks evaluator provenance and cannot be reviewed.',
  },
  fa: {
    title: 'تاریخچه بازبینی انسانی',
    pending: 'هنوز بازبینی انسانی ثبت نشده است.',
    accepted: 'پذیرفته شد',
    revisionRequested: 'درخواست بازنگری',
    decision: 'تصمیم',
    feedback: 'بازخورد بازبین',
    feedbackPlaceholder: 'دلیل کوتاهی برای این تصمیم ثبت کن.',
    submit: 'ثبت بازبینی',
    saving: 'در حال ثبت بازبینی…',
    error: 'ثبت بازبینی ناموفق بود. دوباره تلاش کن.',
    unavailable: 'این گزارش قدیمی است یا منشأ ارزیابی ندارد و قابل بازبینی نیست.',
  },
} as const

export function EvaluationReviewPanel({
  report,
  language,
  onReview,
}: {
  report: EvaluationReport
  language: Language
  onReview: (review: EvaluationReview) => void
}) {
  const labels = copy[language]
  const [decision, setDecision] =
    useState<EvaluationReview['decision']>('accepted')
  const [feedback, setFeedback] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const reviewable =
    report.evaluator_model !== null &&
    !report.stale &&
    ['requires_review', 'completed'].includes(report.status)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      const response = await addEvaluationReview(report.evaluation_id, {
        decision,
        feedback: feedback.trim(),
      })
      onReview(response.data)
      setFeedback('')
    } catch {
      setError(labels.error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="evaluation-review-panel">
      <strong>{labels.title}</strong>
      {report.reviews.length === 0 ? (
        <p className="evaluation-muted">{labels.pending}</p>
      ) : (
        <div className="evaluation-review-history">
          {report.reviews.map((review) => (
            <article key={review.review_id}>
              <strong>
                {review.review_number} ·{' '}
                {review.decision === 'accepted'
                  ? labels.accepted
                  : labels.revisionRequested}
              </strong>
              <small>
                {review.reviewer_name} · <bdi dir="ltr">{review.created_at}</bdi>
              </small>
              <p>{review.feedback}</p>
            </article>
          ))}
        </div>
      )}

      {reviewable ? (
        <form className="evaluation-review-form" onSubmit={submit}>
          <label>
            {labels.decision}
            <select
              value={decision}
              onChange={(event) => {
                const nextDecision = event.target.value
                if (
                  nextDecision === 'accepted' ||
                  nextDecision === 'revision_requested'
                ) {
                  setDecision(nextDecision)
                }
              }}
              disabled={saving}
            >
              <option value="accepted">{labels.accepted}</option>
              <option value="revision_requested">
                {labels.revisionRequested}
              </option>
            </select>
          </label>
          <label>
            {labels.feedback}
            <textarea
              value={feedback}
              onChange={(event) => setFeedback(event.target.value)}
              placeholder={labels.feedbackPlaceholder}
              minLength={1}
              maxLength={4000}
              required
              disabled={saving}
            />
          </label>
          {error && <p className="evaluation-review-error" role="alert">{error}</p>}
          <button type="submit" className="secondary-button" disabled={saving}>
            {saving ? labels.saving : labels.submit}
          </button>
        </form>
      ) : (
        <p className="evaluation-muted">{labels.unavailable}</p>
      )}
    </div>
  )
}
