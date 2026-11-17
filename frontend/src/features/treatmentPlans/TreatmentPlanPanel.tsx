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

import {
  createInitialTreatmentPlan,
  getTreatmentPlan,
  getTreatmentPlanAdaptationGuidance,
  proposeTreatmentPlanRevision,
  reviewTreatmentPlanRevision,
} from './api'
import type {
  PlanAdaptationGuidance,
  TreatmentPlanDefinition,
  TreatmentPlanListResponse,
  TreatmentPlanRevision,
} from './types'

const text = {
  en: {
    title: 'Treatment plan',
    description:
      'Plans are versioned. Revisions require accepted Run evidence and explicit review before they become active.',
    reviewerWarning:
      'Plan changes remain proposals until reviewed by the authenticated local reviewer.',
    adaptationTitle: 'Longitudinal adaptation review',
    noPlanGuidance: 'Create a plan before reviewing adaptation.',
    noNewEvidence:
      'No newly accepted evidence has appeared since this plan revision. The plan remains unchanged.',
    insufficientEvidence:
      'There are completed sessions but no new accepted event evidence. Do not infer progress or setbacks from missing data.',
    actionable: 'New accepted evidence is available for human review.',
    reviewFormulation: 'Review formulation; accounts may conflict.',
    reviewObjectives: 'Review objective fit and intervention readiness.',
    reviewProgress: 'Review goal progress and whether to continue.',
    humanReview: 'Review this evidence before proposing a change.',
    adaptationEvidence: 'New accepted event evidence',
    session: 'Session',
    refresh: 'Refresh plan',
    loading: 'Loading treatment plan…',
    noPlan: 'No treatment plan has been created for this Run.',
    formulation: 'Initial formulation',
    goal: 'Treatment goal',
    newGoal: 'New goal to propose',
    goalPlaceholder: 'Describe a treatment goal.',
    changeType: 'Plan change to propose',
    addGoalChange: 'Add a goal',
    reviseGoalChange: 'Revise a goal',
    reviseObjectiveChange: 'Revise an objective',
    pauseInterventionChange: 'Pause an intervention',
    reviseFormulationChange: 'Review formulation',
    target: 'Plan item',
    changeValue: 'Proposed text',
    pauseNote: 'The selected intervention will be proposed as paused.',
    rationale: 'Rationale',
    rationalePlaceholder: 'Explain the change and its relevance.',
    create: 'Create initial plan',
    propose: 'Propose revision',
    accept: 'Accept revision',
    reject: 'Reject revision',
    pending: 'Awaiting review',
    active: 'Active',
    superseded: 'Superseded',
    rejected: 'Rejected',
    accepted: 'Treatment plan revision accepted.',
    denied: 'Treatment plan revision rejected.',
    error: 'Could not load or update the treatment plan.',
    needEvidence: 'Select at least one new accepted event to propose a revision.',
    version: 'Version',
    objectives: 'Objectives',
    interventions: 'Interventions',
    progress: 'Progress',
    evidence: 'Supporting evidence',
    reviewer: 'Reviewer',
  },
  fa: {
    title: 'برنامه درمان',
    description:
      'برنامه‌ها نسخه‌بندی می‌شوند. هر بازنگری به شواهد پذیرفته‌شده اجرا و بازبینی صریح نیاز دارد.',
    reviewerWarning:
      'تغییرهای برنامه تا زمان بازبینی توسط بازبین محلی احراز هویت‌شده، پیشنهاد باقی می‌مانند.',
    adaptationTitle: 'بازبینی تطبیق طولی',
    noPlanGuidance: 'پیش از بررسی تطبیق، برنامه اولیه را ایجاد کن.',
    noNewEvidence:
      'از زمان نسخه فعلی برنامه، شواهد پذیرفته‌شده جدیدی وجود ندارد. برنامه بدون تغییر می‌ماند.',
    insufficientEvidence:
      'جلسه تکمیل‌شده وجود دارد اما رویداد پذیرفته‌شده جدیدی در دسترس نیست. از داده مفقود، پیشرفت یا پسرفت استنباط نکن.',
    actionable: 'شواهد پذیرفته‌شده جدید برای بازبینی انسانی موجود است.',
    reviewFormulation: 'فرمول‌بندی را بازبینی کن؛ ممکن است روایت‌ها ناسازگار باشند.',
    reviewObjectives: 'تناسب هدف‌ها و آمادگی مداخله‌ها را بازبینی کن.',
    reviewProgress: 'پیشرفت هدف‌ها و ادامه برنامه را بازبینی کن.',
    humanReview: 'پیش از پیشنهاد تغییر، این شواهد را بررسی کن.',
    adaptationEvidence: 'شواهد رویداد پذیرفته‌شده جدید',
    session: 'جلسه',
    refresh: 'تازه‌سازی برنامه',
    loading: 'در حال بارگذاری برنامه درمان…',
    noPlan: 'برای این اجرا هنوز برنامه درمانی ایجاد نشده است.',
    formulation: 'فرمول‌بندی اولیه',
    goal: 'هدف درمان',
    newGoal: 'هدف جدید پیشنهادی',
    goalPlaceholder: 'یک هدف درمانی را توصیف کن.',
    changeType: 'تغییر پیشنهادی برنامه',
    addGoalChange: 'افزودن هدف',
    reviseGoalChange: 'بازنگری هدف',
    reviseObjectiveChange: 'بازنگری هدف میانی',
    pauseInterventionChange: 'توقف مداخله',
    reviseFormulationChange: 'بازبینی فرمول‌بندی',
    target: 'مورد برنامه',
    changeValue: 'متن پیشنهادی',
    pauseNote: 'پیشنهاد می‌شود مداخله انتخاب‌شده متوقف شود.',
    rationale: 'دلیل',
    rationalePlaceholder: 'تغییر و ارتباط آن با شواهد را توضیح بده.',
    create: 'ایجاد برنامه اولیه',
    propose: 'پیشنهاد بازنگری',
    accept: 'پذیرش بازنگری',
    reject: 'رد بازنگری',
    pending: 'در انتظار بازبینی',
    active: 'فعال',
    superseded: 'جایگزین‌شده',
    rejected: 'ردشده',
    accepted: 'بازنگری برنامه درمان پذیرفته شد.',
    denied: 'بازنگری برنامه درمان رد شد.',
    error: 'بارگذاری یا به‌روزرسانی برنامه درمان ناموفق بود.',
    needEvidence: 'برای پیشنهاد بازنگری، دست‌کم یک رویداد پذیرفته‌شده جدید انتخاب کن.',
    version: 'نسخه',
    objectives: 'اهداف میانی',
    interventions: 'مداخلات',
    progress: 'پیشرفت',
    evidence: 'شواهد پشتیبان',
    reviewer: 'بازبین',
  },
} as const

interface TreatmentPlanPanelProps {
  runId: string
  language: Language
  refreshKey: number
}

type PlanChangeKind =
  | 'add_goal'
  | 'revise_goal'
  | 'revise_objective'
  | 'pause_intervention'
  | 'review_formulation'

function emptyDefinition(formulation: string, goal: string): TreatmentPlanDefinition {
  return {
    initial_formulation: formulation.trim(),
    goals: [
      {
        goal_id: `goal-${Date.now()}`,
        description: goal.trim(),
        relevant_processes: [],
        status: 'active',
        progress_notes: '',
      },
    ],
    objectives: [],
    interventions: [],
    outcome_measures: [],
    review_after_session: null,
  }
}

function proposedDefinition(
  current: TreatmentPlanDefinition,
  changeKind: PlanChangeKind,
  targetId: string,
  value: string,
): TreatmentPlanDefinition | null {
  if (changeKind === 'add_goal') {
    return {
      ...current,
      goals: [
        ...current.goals,
        {
          goal_id: `goal-${Date.now()}`,
          description: value.trim(),
          relevant_processes: [],
          status: 'active',
          progress_notes: '',
        },
      ],
    }
  }
  if (changeKind === 'revise_goal') {
    if (!current.goals.some((item) => item.goal_id === targetId)) return null
    return {
      ...current,
      goals: current.goals.map((item) =>
        item.goal_id === targetId
          ? { ...item, description: value.trim() }
          : item,
      ),
    }
  }
  if (changeKind === 'revise_objective') {
    if (!current.objectives.some((item) => item.objective_id === targetId)) {
      return null
    }
    return {
      ...current,
      objectives: current.objectives.map((item) =>
        item.objective_id === targetId
          ? { ...item, description: value.trim() }
          : item,
      ),
    }
  }
  if (changeKind === 'pause_intervention') {
    if (!current.interventions.some((item) => item.intervention_id === targetId)) {
      return null
    }
    return {
      ...current,
      interventions: current.interventions.map((item) =>
        item.intervention_id === targetId
          ? { ...item, status: 'paused' }
          : item,
      ),
    }
  }
  if (!value.trim()) return null
  return { ...current, initial_formulation: value.trim() }
}

export function TreatmentPlanPanel({
  runId,
  language,
  refreshKey,
}: TreatmentPlanPanelProps) {
  const copy = text[language]
  const [plan, setPlan] = useState<TreatmentPlanListResponse>({
    current: null,
    revisions: [],
  })
  const [guidance, setGuidance] = useState<PlanAdaptationGuidance | null>(null)
  const [formulation, setFormulation] = useState('')
  const [goal, setGoal] = useState('')
  const [changeKind, setChangeKind] = useState<PlanChangeKind>('add_goal')
  const [targetId, setTargetId] = useState('')
  const [rationale, setRationale] = useState('')
  const [eventIds, setEventIds] = useState<string[]>([])
  const [reviewRationales, setReviewRationales] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState<'accepted' | 'rejected' | ''>('')

  const loadPlan = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [planResponse, guidanceResponse] = await Promise.all([
        getTreatmentPlan(runId),
        getTreatmentPlanAdaptationGuidance(runId),
      ])
      setPlan(planResponse)
      setGuidance(guidanceResponse.data)
      setEventIds(guidanceResponse.data.evidence.map((event) => event.event_id))
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : 'plan_request_failed',
      )
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPlan()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadPlan, refreshKey])

  async function handleCreate() {
    if (!formulation.trim() || !goal.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      await createInitialTreatmentPlan(
        runId,
        emptyDefinition(formulation, goal),
      )
      setFormulation('')
      setGoal('')
      await loadPlan()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'plan_request_failed')
    } finally {
      setBusy(false)
    }
  }

  async function handlePropose() {
    const current = plan.current
    const requiresText = changeKind !== 'pause_intervention'
    if (!current ||
      (requiresText && !goal.trim()) ||
      !rationale.trim() ||
      !guidance ||
      guidance.status !== 'actionable' ||
      eventIds.length === 0 ||
      (changeKind !== 'add_goal' &&
        changeKind !== 'review_formulation' &&
        !targetId) ||
      busy
    ) {
      return
    }
    const definition = proposedDefinition(
      current.definition,
      changeKind,
      targetId,
      goal,
    )
    if (!definition) return
    setBusy(true)
    setError('')
    try {
      await proposeTreatmentPlanRevision(
        runId,
        current.revision_number,
        definition,
        eventIds,
        rationale.trim(),
      )
      setGoal('')
      setTargetId('')
      setRationale('')
      setEventIds([])
      await loadPlan()
    } catch (proposalError) {
      setError(proposalError instanceof Error ? proposalError.message : 'plan_request_failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleReview(
    revision: TreatmentPlanRevision,
    decision: 'accepted' | 'rejected',
  ) {
    const reviewRationale = reviewRationales[revision.revision_id]?.trim() ?? ''
    if (!reviewRationale || busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await reviewTreatmentPlanRevision(
        runId,
        revision.revision_id,
        decision,
        reviewRationale,
      )
      setNotice(decision)
      await loadPlan()
    } catch (reviewError) {
      setError(reviewError instanceof Error ? reviewError.message : 'plan_request_failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section
      className="surface-card memory-review-card"
      aria-labelledby="treatment-plan-title"
    >
      <div className="memory-review-heading">
        <div>
          <h2 id="treatment-plan-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <button
          type="button"
          className="secondary-button memory-refresh-button"
          onClick={() => void loadPlan()}
          disabled={loading || busy}
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
          <span>{error === 'plan_request_failed' ? copy.error : error}</span>
        </div>
      )}
      {notice && (
        <div className="sessions-alert sessions-alert-notice" role="status">
          <Check size={17} />
          <span>{notice === 'accepted' ? copy.accepted : copy.denied}</span>
        </div>
      )}
      {loading && plan.revisions.length === 0 && (
        <p className="memory-review-state" role="status">
          <LoaderCircle className="spin" size={15} />
          {copy.loading}
        </p>
      )}

      {plan.current && guidance && (
        <section className="memory-consolidation">
          <h3>{copy.adaptationTitle}</h3>
          <p>
            {guidance.status === 'actionable'
              ? copy.actionable
              : guidance.status === 'insufficient_evidence'
                ? copy.insufficientEvidence
                : guidance.status === 'no_new_evidence'
                  ? copy.noNewEvidence
                  : copy.noPlanGuidance}
          </p>
          {guidance.status === 'actionable' && (
            <p>
              {guidance.recommendation === 'review_formulation'
                ? copy.reviewFormulation
                : guidance.recommendation === 'review_objectives_and_interventions'
                  ? copy.reviewObjectives
                  : guidance.recommendation === 'review_progress_and_continue'
                    ? copy.reviewProgress
                    : copy.humanReview}
            </p>
          )}
          <p dir="auto">{guidance.rationale}</p>
          {guidance.evidence.length > 0 && (
            <div className="memory-evidence">
              <strong>{copy.adaptationEvidence}</strong>
              {guidance.evidence.map((event) => (
                <label
                  className="memory-candidate-meta"
                  key={event.event_id}
                  dir="auto"
                >
                  <input
                    type="checkbox"
                    checked={eventIds.includes(event.event_id)}
                    onChange={(change) =>
                      setEventIds((current) =>
                        change.target.checked
                          ? [...current, event.event_id]
                          : current.filter((id) => id !== event.event_id),
                      )
                    }
                    disabled={busy}
                  />
                  <span>{event.event_type}</span>
                  {event.session_id && (
                    <span>
                      {copy.session}:{' '}
                      <bdi dir="ltr">{event.session_id}</bdi>
                    </span>
                  )}
                  <span dir="auto">{event.summary}</span>
                </label>
              ))}
            </div>
          )}
        </section>
      )}

      {!loading && plan.current && (
        <article className="memory-candidate">
          <div className="memory-candidate-meta">
            <span>{copy.version}: {plan.current.revision_number}</span>
            <span>{plan.current.modality}</span>
            <span>{copy.active}</span>
          </div>
          <strong>{copy.formulation}</strong>
          <p dir="auto">{plan.current.definition.initial_formulation}</p>
          <div className="memory-evidence">
            <strong>{copy.goal}</strong>
            {plan.current.definition.goals.map((item) => (
              <p key={item.goal_id} dir="auto">
                {item.description} · {item.status}
                {item.progress_notes && ` · ${copy.progress}: ${item.progress_notes}`}
              </p>
            ))}
            {plan.current.definition.objectives.length > 0 && (
              <>
                <strong>{copy.objectives}</strong>
                {plan.current.definition.objectives.map((item) => (
                  <p key={item.objective_id} dir="auto">
                    {item.description} · {item.progress_indicator}
                  </p>
                ))}
              </>
            )}
            {plan.current.definition.interventions.length > 0 && (
              <>
                <strong>{copy.interventions}</strong>
                {plan.current.definition.interventions.map((item) => (
                  <p key={item.intervention_id} dir="auto">
                    {item.description} · {item.status}
                  </p>
                ))}
              </>
            )}
          </div>
        </article>
      )}

      {!loading && !plan.current && (
        <p className="memory-review-state">{copy.noPlan}</p>
      )}

      {!loading && !plan.current && (
        <div className="memory-candidate">
          <label className="memory-rationale">
            <span>{copy.formulation}</span>
            <textarea
              value={formulation}
              onChange={(change) => setFormulation(change.target.value)}
              maxLength={8000}
              rows={3}
              required
              disabled={busy}
            />
          </label>
          <label className="memory-rationale">
            <span>{copy.goal}</span>
            <textarea
              value={goal}
              onChange={(change) => setGoal(change.target.value)}
              placeholder={copy.goalPlaceholder}
              maxLength={2000}
              rows={2}
              required
              disabled={busy}
            />
          </label>
          <button
            type="button"
            className="primary-button"
            onClick={() => void handleCreate()}
            disabled={!formulation.trim() || !goal.trim() || busy}
          >
            {busy && <LoaderCircle className="spin" size={15} />}
            {copy.create}
          </button>
        </div>
      )}

      {plan.current && (
        <div className="memory-candidate">
          <label className="memory-rationale">
            <span>{copy.changeType}</span>
            <select
              value={changeKind}
              onChange={(change) => {
                const next = change.target.value as PlanChangeKind
                setChangeKind(next)
                setGoal('')
                setTargetId(
                  next === 'revise_goal'
                    ? plan.current?.definition.goals[0]?.goal_id ?? ''
                    : next === 'revise_objective'
                      ? plan.current?.definition.objectives[0]?.objective_id ?? ''
                      : next === 'pause_intervention'
                        ? plan.current?.definition.interventions[0]?.intervention_id ?? ''
                        : '',
                )
              }}
              disabled={busy}
            >
              <option value="add_goal">{copy.addGoalChange}</option>
              <option value="revise_goal" disabled={plan.current.definition.goals.length === 0}>
                {copy.reviseGoalChange}
              </option>
              <option value="revise_objective" disabled={plan.current.definition.objectives.length === 0}>
                {copy.reviseObjectiveChange}
              </option>
              <option value="pause_intervention" disabled={plan.current.definition.interventions.length === 0}>
                {copy.pauseInterventionChange}
              </option>
              <option value="review_formulation">{copy.reviseFormulationChange}</option>
            </select>
          </label>
          {changeKind !== 'add_goal' && changeKind !== 'review_formulation' && (
            <label className="memory-rationale">
              <span>{copy.target}</span>
              <select
                value={targetId}
                onChange={(change) => setTargetId(change.target.value)}
                disabled={busy}
              >
                {changeKind === 'revise_goal' &&
                  plan.current.definition.goals.map((item) => (
                    <option key={item.goal_id} value={item.goal_id}>
                      {item.description}
                    </option>
                  ))}
                {changeKind === 'revise_objective' &&
                  plan.current.definition.objectives.map((item) => (
                    <option key={item.objective_id} value={item.objective_id}>
                      {item.description}
                    </option>
                  ))}
                {changeKind === 'pause_intervention' &&
                  plan.current.definition.interventions.map((item) => (
                    <option key={item.intervention_id} value={item.intervention_id}>
                      {item.description} · {item.status}
                    </option>
                  ))}
              </select>
            </label>
          )}
          {changeKind === 'pause_intervention' ? (
            <p className="memory-review-state">{copy.pauseNote}</p>
          ) : (
            <label className="memory-rationale">
              <span>
                {changeKind === 'add_goal' ? copy.newGoal : copy.changeValue}
              </span>
              <textarea
                value={goal}
                onChange={(change) => setGoal(change.target.value)}
                placeholder={
                  changeKind === 'add_goal'
                    ? copy.goalPlaceholder
                    : copy.changeValue
                }
                maxLength={changeKind === 'review_formulation' ? 8000 : 2000}
                rows={2}
                disabled={busy}
              />
            </label>
          )}
          {(!guidance ||
            guidance.status !== 'actionable' ||
            eventIds.length === 0) && (
            <p className="memory-review-state">{copy.needEvidence}</p>
          )}
          <label className="memory-rationale">
            <span>{copy.rationale}</span>
            <textarea
              value={rationale}
              onChange={(change) => setRationale(change.target.value)}
              placeholder={copy.rationalePlaceholder}
              maxLength={4000}
              rows={2}
              disabled={busy}
            />
          </label>
          <button
            type="button"
            className="primary-button"
            onClick={() => void handlePropose()}
            disabled={
              (changeKind !== 'pause_intervention' && !goal.trim()) ||
              !rationale.trim() ||
              !guidance ||
              guidance.status !== 'actionable' ||
              eventIds.length === 0 ||
              busy
            }
          >
            {busy && <LoaderCircle className="spin" size={15} />}
            {copy.propose}
          </button>
        </div>
      )}

      <div className="memory-candidate-list">
        {plan.revisions
          .filter((revision) => revision.status !== 'active')
          .map((revision) => {
            const reviewRationale =
              reviewRationales[revision.revision_id] ?? ''
            return (
              <article className="memory-candidate" key={revision.revision_id}>
                <div className="memory-candidate-meta">
                  <span>{copy.version}: {revision.revision_number}</span>
                  <span>
                    {revision.status === 'requires_review'
                      ? copy.pending
                      : revision.status === 'superseded'
                        ? copy.superseded
                        : copy.rejected}
                  </span>
                </div>
                <p dir="auto">{revision.rationale}</p>
                <div className="memory-evidence">
                  <strong>{copy.evidence}</strong>
                  {revision.evidence.map((item) => (
                    <p key={`${item.kind}-${item.source_id}`} dir="auto">
                      {item.kind}: <bdi dir="ltr">{item.source_id}</bdi>
                    </p>
                  ))}
                  {revision.review && (
                    <>
                      <strong>{copy.reviewer}</strong>
                      <p dir="auto">{revision.review.rationale}</p>
                      <p>
                        <bdi dir="ltr">{revision.review.reviewer_id}</bdi>
                      </p>
                    </>
                  )}
                </div>
                {revision.status === 'requires_review' && (
                  <>
                    <label className="memory-rationale">
                      <span>{copy.rationale}</span>
                      <textarea
                        value={reviewRationale}
                        onChange={(change) =>
                          setReviewRationales((current) => ({
                            ...current,
                            [revision.revision_id]: change.target.value,
                          }))
                        }
                        maxLength={4000}
                        rows={2}
                        disabled={busy}
                      />
                    </label>
                    <div className="memory-review-actions">
                      <button
                        type="button"
                        className="secondary-button"
                        onClick={() => void handleReview(revision, 'rejected')}
                        disabled={!reviewRationale.trim() || busy}
                      >
                        <ThumbsDown size={15} />
                        {copy.reject}
                      </button>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => void handleReview(revision, 'accepted')}
                        disabled={!reviewRationale.trim() || busy}
                      >
                        <ThumbsUp size={15} />
                        {copy.accept}
                      </button>
                    </div>
                  </>
                )}
              </article>
            )
          })}
      </div>
    </section>
  )
}
