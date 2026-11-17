import { useEffect, useState } from 'react'
import { AlertCircle, ClipboardCheck, LoaderCircle, Sparkles } from 'lucide-react'

import type { Language } from '../../i18n'
import type { SessionMessage } from '../sessions/types'
import { createSessionEvaluation, listSessionEvaluations } from './api'
import { EvaluationReviewPanel } from './EvaluationReviewPanel'
import type { EvaluationReport, EvaluationReview } from './types'

const copy = {
  en: {
    title: 'Experimental session evaluation',
    description:
      'Formative feedback from the transcript only. It is not a validated clinical assessment or a substitute for qualified supervision.',
    generate: 'Generate evaluation',
    generating: 'Evaluating transcript...',
    loading: 'Loading evaluation history...',
    noReport: 'No evaluation report exists for this session.',
    summary: 'Overall summary',
    competency: 'Competency',
    evidence: 'Transcript evidence',
    source: 'Source message',
    missing: 'Missing evidence',
    strengths: 'Observed strengths',
    limitations: 'Limitations',
    confidence: 'Confidence',
    revision: 'Revision',
    reviewRequired: 'Human review required',
    historical: 'Historical record: evaluator provenance is unavailable; ratings are withheld.',
    unavailable: 'The Evaluator Agent is unavailable. Configure a local model and try again.',
    failed: 'Evaluation generation failed. No report was saved.',
    emptyEvidence: 'No therapist evidence was cited.',
    noSource: 'The cited source message is not present in the loaded transcript.',
  },
  fa: {
    title: 'ارزیابی آزمایشی جلسه',
    description:
      'بازخورد آموزشی فقط بر پایه رونوشت است؛ این ارزیابی بالینی اعتبارسنجی‌شده یا جایگزین نظارت تخصصی نیست.',
    generate: 'تولید ارزیابی',
    generating: 'در حال ارزیابی رونوشت...',
    loading: 'در حال بارگذاری تاریخچه ارزیابی...',
    noReport: 'برای این جلسه گزارشی ثبت نشده است.',
    summary: 'خلاصه کلی',
    competency: 'شایستگی',
    evidence: 'شواهد رونوشت',
    source: 'پیام منبع',
    missing: 'شواهد موجود نیست',
    strengths: 'نقاط قوت مشاهده‌شده',
    limitations: 'محدودیت‌ها',
    confidence: 'میزان اطمینان',
    revision: 'بازنگری',
    reviewRequired: 'نیازمند بازبینی انسانی',
    historical: 'سابقه قدیمی: منشأ ارزیاب در دسترس نیست؛ امتیازها نمایش داده نمی‌شوند.',
    unavailable: 'ارزیاب در دسترس نیست. یک مدل محلی تنظیم و دوباره تلاش کن.',
    failed: 'تولید ارزیابی ناموفق بود و گزارشی ذخیره نشد.',
    emptyEvidence: 'شواهدی از پیام درمانگر ثبت نشده است.',
    noSource: 'پیام منبع در رونوشت بارگذاری‌شده وجود ندارد.',
  },
} as const

function messageLabel(message: SessionMessage, language: Language) {
  const role = message.role.toLowerCase()
  if (['therapist', 'user', 'trainee'].includes(role)) {
    return language === 'fa' ? 'درمانگر' : 'Therapist'
  }
  return language === 'fa' ? 'مراجع شبیه‌سازی‌شده' : 'Simulated client'
}

export function EvaluationPanel({
  sessionId,
  sessionStatus,
  transcript,
  language,
}: {
  sessionId: string
  sessionStatus: string
  transcript: SessionMessage[]
  language: Language
}) {
  const labels = copy[language]
  const [reports, setReports] = useState<EvaluationReport[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    void listSessionEvaluations(sessionId)
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
  }, [sessionId, labels.failed])

  async function handleGenerate() {
    setGenerating(true)
    setError('')

    try {
      const response = await createSessionEvaluation(sessionId)
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
    <section className="surface-card evaluation-card" aria-labelledby="evaluation-title">
      <div className="evaluation-heading">
        <div>
          <div className="eyebrow">
            <ClipboardCheck size={15} />
            {labels.title}
          </div>
          <p>{labels.description}</p>
        </div>
        {sessionStatus === 'completed' && (
          <button
            type="button"
            className="primary-button evaluation-generate-button"
            onClick={() => void handleGenerate()}
            disabled={generating || loading}
          >
            {generating ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Sparkles size={16} />
            )}
            {generating ? labels.generating : labels.generate}
          </button>
        )}
      </div>

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
          </div>

          {report.overall_summary && (
            <div className="evaluation-summary">
              <strong>{labels.summary}</strong>
              <p>{report.overall_summary}</p>
            </div>
          )}

          {report.limitations.length > 0 && (
            <ul className="evaluation-limitations">
              {report.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
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
                  {item.justification && <p>{item.justification}</p>}
                  {item.confidence && (
                    <p><strong>{labels.confidence}:</strong> {item.confidence}</p>
                  )}
                  {item.strengths.length > 0 && (
                    <div>
                      <strong>{labels.strengths}</strong>
                      <ul>{item.strengths.map((value) => <li key={value}>{value}</li>)}</ul>
                    </div>
                  )}
                  {item.missing_evidence.length > 0 && (
                    <div>
                      <strong>{labels.missing}</strong>
                      <ul>{item.missing_evidence.map((value) => <li key={value}>{value}</li>)}</ul>
                    </div>
                  )}
                  {item.limitations && (
                    <p><strong>{labels.limitations}:</strong> {item.limitations}</p>
                  )}
                  <div>
                    <strong>{labels.evidence}</strong>
                    {item.evidence.length === 0 && (
                      <p className="evaluation-muted">{labels.emptyEvidence}</p>
                    )}
                    {item.evidence.map((evidence, index) => {
                      const source = transcript.find(
                        (message) => message.message_id === evidence.message_id,
                      )

                      return (
                        <blockquote
                          className="evaluation-evidence"
                          key={`${evidence.message_id}-${index}`}
                        >
                          <p>{evidence.evidence_excerpt}</p>
                          {evidence.evidence_note && <small>{evidence.evidence_note}</small>}
                          <small dir="ltr">
                            {labels.source}: {evidence.message_id}
                          </small>
                          {source ? (
                            <div className="evaluation-source">
                              <strong>{messageLabel(source, language)}</strong>
                              <p dir="auto">{source.content}</p>
                            </div>
                          ) : (
                            <small>{labels.noSource}</small>
                          )}
                        </blockquote>
                      )
                    })}
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
