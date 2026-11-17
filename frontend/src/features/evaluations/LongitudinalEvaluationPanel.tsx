import { useEffect, useState } from 'react'
import { AlertCircle, ClipboardCheck, LoaderCircle, Sparkles } from 'lucide-react'

import type { Language } from '../../i18n'
import { createRunEvaluation, listRunEvaluations } from './api'
import { EvaluationReviewPanel } from './EvaluationReviewPanel'
import type { EvaluationReport, EvaluationReview } from './types'

const copy = {
  en: {
    title: 'Experimental longitudinal evaluation',
    description:
      'Reviews therapist behavior across completed sessions using transcript evidence. It is not a validated clinical assessment or a substitute for qualified supervision.',
    generate: 'Evaluate completed sessions',
    generating: 'Evaluating session history...',
    loading: 'Loading longitudinal evaluation history...',
    noReport: 'No longitudinal evaluation exists for this run.',
    needsSessions: 'At least two completed sessions are required.',
    stale: 'This report is stale because the run’s completed-session scope has changed. Generate a new revision.',
    scope: 'Included sessions',
    session: 'Session',
    revision: 'Revision',
    summary: 'Overall summary',
    competency: 'Competency',
    evidence: 'Cross-session evidence',
    source: 'Source',
    inspectSource: 'Inspect original message',
    confidence: 'Confidence',
    missing: 'Missing evidence',
    limitations: 'Limitations',
    reviewRequired: 'Human review required',
    unavailable: 'The Evaluator Agent is unavailable. Configure a local model and try again.',
    failed: 'Longitudinal evaluation failed. No report was saved.',
    noEvidence: 'No transcript evidence was cited.',
    historical: 'Historical record: evaluator provenance is unavailable; ratings are withheld.',
  },
  fa: {
    title: 'ارزیابی طولی آزمایشی',
    description:
      'رفتار درمانگر را در جلسات تکمیل‌شده با استناد به شواهد رونوشت بررسی می‌کند. این ارزیابی بالینی اعتبارسنجی‌شده یا جایگزین نظارت تخصصی نیست.',
    generate: 'ارزیابی جلسات تکمیل‌شده',
    generating: 'در حال ارزیابی تاریخچه جلسات...',
    loading: 'در حال بارگذاری تاریخچه ارزیابی طولی...',
    noReport: 'برای این اجرا ارزیابی طولی وجود ندارد.',
    needsSessions: 'حداقل دو جلسه تکمیل‌شده لازم است.',
    stale: 'این گزارش به‌دلیل تغییر دامنه جلسات تکمیل‌شده قدیمی شده است. بازنگری تازه‌ای تولید کن.',
    scope: 'جلسات مشمول',
    session: 'جلسه',
    revision: 'بازنگری',
    summary: 'خلاصه کلی',
    competency: 'شایستگی',
    evidence: 'شواهد میان‌جلسه‌ای',
    source: 'منبع',
    inspectSource: 'مشاهده پیام اصلی',
    confidence: 'میزان اطمینان',
    missing: 'شواهد موجود نیست',
    limitations: 'محدودیت‌ها',
    reviewRequired: 'نیازمند بازبینی انسانی',
    unavailable: 'ارزیاب در دسترس نیست. یک مدل محلی تنظیم و دوباره تلاش کن.',
    failed: 'ارزیابی طولی ناموفق بود و گزارشی ذخیره نشد.',
    noEvidence: 'شواهدی از رونوشت ثبت نشده است.',
    historical: 'سابقه قدیمی: منشأ ارزیاب در دسترس نیست؛ امتیازها نمایش داده نمی‌شوند.',
  },
} as const

export function LongitudinalEvaluationPanel({
  runId,
  modality,
  completedSessionCount,
  refreshKey,
  language,
}: {
  runId: string
  modality: string
  completedSessionCount: number
  refreshKey: number
  language: Language
}) {
  const labels = copy[language]
  const [reports, setReports] = useState<EvaluationReport[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    void listRunEvaluations(runId)
      .then((response) => {
        if (active) setReports(response.data)
      })
      .catch(() => {
        if (active) setError(labels.failed)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [runId, refreshKey, labels.failed])

  async function handleGenerate() {
    setGenerating(true)
    setError('')

    try {
      const response = await createRunEvaluation(runId)
      setReports((current) => [
        response.data,
        ...current.filter(
          (report) => report.evaluation_id !== response.data.evaluation_id,
        ),
      ])
    } catch (requestError) {
      const message =
        requestError instanceof Error ? requestError.message : ''
      setError(
        message === 'evaluator_unavailable_experimental'
          ? labels.unavailable
          : labels.failed,
      )
    } finally {
      setGenerating(false)
    }
  }

  const orderedReports = [...reports].sort(
    (left, right) => right.evaluation_revision - left.evaluation_revision,
  )

  function handleReview(evaluationId: string, review: EvaluationReview) {
    setReports((current) =>
      current.map((report) =>
        report.evaluation_id === evaluationId
          ? {
              ...report,
              reviews: [...report.reviews, review],
              review_status: review.decision,
              human_review_required: review.decision !== 'accepted',
            }
          : report,
      ),
    )
  }

  return (
    <section className="surface-card evaluation-card" aria-labelledby="longitudinal-evaluation-title">
      <div className="evaluation-heading">
        <div>
          <div id="longitudinal-evaluation-title" className="eyebrow">
            <ClipboardCheck size={15} />
            {labels.title}
          </div>
          <p>{labels.description}</p>
        </div>
        <button
          type="button"
          className="primary-button evaluation-generate-button"
          onClick={() => void handleGenerate()}
          disabled={
            generating ||
            loading ||
            modality.toLowerCase() !== 'act' ||
            completedSessionCount < 2
          }
        >
          {generating ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Sparkles size={16} />
          )}
          {generating ? labels.generating : labels.generate}
        </button>
      </div>

      {modality.toLowerCase() === 'act' && completedSessionCount < 2 && (
        <p className="evaluation-muted">{labels.needsSessions}</p>
      )}

      {error && (
        <div className="sessions-alert sessions-alert-error" role="alert">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <p className="evaluation-muted" role="status">{labels.loading}</p>
      )}

      {!loading && orderedReports.length === 0 && (
        <p className="evaluation-muted">{labels.noReport}</p>
      )}

      {orderedReports.map((report) => (
        <article className="evaluation-report" key={report.evaluation_id}>
          <div className="evaluation-report-meta">
            <span>{labels.revision} {report.evaluation_revision}</span>
            <span dir="ltr">{report.rubric_id} · {report.rubric_version}</span>
            {report.human_review_required && (
              <span className="evaluation-review-badge">{labels.reviewRequired}</span>
            )}
            {report.stale && (
              <span className="evaluation-review-badge">{labels.stale}</span>
            )}
          </div>

          {report.session_scope.length > 0 && (
            <p className="evaluation-muted">
              <strong>{labels.scope}:</strong>{' '}
              {report.session_scope.map((session) => (
                <span key={session.session_id} dir="ltr">
                  {labels.session} {session.session_number} ({session.session_id}){' '}
                </span>
              ))}
            </p>
          )}

          {report.overall_summary && (
            <div className="evaluation-summary">
              <strong>{labels.summary}</strong>
              <p dir="auto">{report.overall_summary}</p>
            </div>
          )}

          {report.limitations.length > 0 && (
            <ul className="evaluation-limitations">
              {report.limitations.map((limitation) => (
                <li key={limitation} dir="auto">{limitation}</li>
              ))}
            </ul>
          )}

          {report.items.length === 0 && (
            <p className="evaluation-muted">{labels.historical}</p>
          )}

          <div className="evaluation-items">
            {report.items.map((item) => (
              <details className="evaluation-item" key={item.evaluation_item_id}>
                <summary>
                  <span>{item.competency_id.replaceAll('_', ' ')}</span>
                  <strong>{item.rating_code}</strong>
                </summary>
                <div className="evaluation-item-content">
                  {item.justification && <p dir="auto">{item.justification}</p>}
                  {item.confidence && (
                    <p dir="auto"><strong>{labels.confidence}:</strong> {item.confidence}</p>
                  )}
                  {item.missing_evidence.length > 0 && (
                    <div>
                      <strong>{labels.missing}</strong>
                      <ul>{item.missing_evidence.map((value) => <li key={value} dir="auto">{value}</li>)}</ul>
                    </div>
                  )}
                  {item.limitations && (
                    <p dir="auto"><strong>{labels.limitations}:</strong> {item.limitations}</p>
                  )}
                  <div>
                    <strong>{labels.evidence}</strong>
                    {item.evidence.length === 0 && (
                      <p className="evaluation-muted">{labels.noEvidence}</p>
                    )}
                    {item.evidence.map((evidence, index) => (
                      <blockquote
                        className="evaluation-evidence"
                        key={`${evidence.message_id}-${index}`}
                      >
                        <p dir="auto">{evidence.evidence_excerpt}</p>
                        {evidence.evidence_note && <small dir="auto">{evidence.evidence_note}</small>}
                        <small dir="ltr">
                          {labels.source}: {labels.session} {evidence.session_number ?? '?'} ·{' '}
                          {evidence.session_id ?? '?'} · {evidence.message_id}
                        </small>
                        {evidence.source_message_content !== null && (
                          <details className="evaluation-source">
                            <summary>{labels.inspectSource}</summary>
                            <p dir="auto">{evidence.source_message_content}</p>
                          </details>
                        )}
                      </blockquote>
                    ))}
                  </div>
                </div>
              </details>
            ))}
          </div>
          <EvaluationReviewPanel
            report={report}
            language={language}
            onReview={(review) => handleReview(report.evaluation_id, review)}
          />
        </article>
      ))}
    </section>
  )
}
