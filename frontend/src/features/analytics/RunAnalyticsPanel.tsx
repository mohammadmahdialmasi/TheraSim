import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, Download, LoaderCircle, RefreshCw } from 'lucide-react'

import type { Language } from '../../i18n'

import { getRunAnalytics, type RunAnalyticsSnapshot } from './api'

const text = {
  en: {
    title: 'Run analytics and export',
    description:
      'Counts and records come from this Run’s persisted data. Identifiers link each item to its source record.',
    refresh: 'Refresh analytics',
    loading: 'Loading persisted Run analytics…',
    export: 'Download JSON',
    privacy:
      'Export contains sensitive operational identifiers. Store and share it carefully.',
    sessions: 'Sessions',
    completedSessions: 'Completed sessions',
    events: 'Behavioral events',
    memories: 'Memory records',
    transitions: 'Character-state transitions',
    evaluations: 'Evaluations',
    stale: 'Stale longitudinal reports',
    staleMark: 'stale',
    competencyComparisons: 'Session competency observations',
    competencyComparisonNote:
      'Raw observations are grouped by exact rubric version and content hash. Ratings are not averaged or treated as clinical outcomes.',
    competency: 'Competency',
    rating: 'Rating',
    confidence: 'Confidence',
    fromSession: 'From session',
    throughSession: 'Through session',
    evaluable: 'Evaluable observations',
    notEvaluable: 'Not evaluable (NE)',
    missing: 'Missing observations',
    evidenceCoverage: 'Evidence coverage',
    reviewOutcomes: 'Human review outcomes',
    rawChange: 'Raw rating-code change',
    insufficientComparison: 'At least two evaluable observations are required for a raw comparison.',
    chartAxes:
      'X-axis: completed session number. Y-axis: raw rubric rating code (0–3). NE and missing observations are omitted, not plotted as zero. Each point links to its evaluation record.',
    noChartData: 'No evaluable numeric observations in this session range.',
    openEvaluation: 'Open evaluation',
    evaluationStatus: 'Evaluation status',
    evidenceMessages: 'Evidence message IDs',
    noCompetencyObservations: 'No eligible session competency observations.',
    noEvaluationForRubric: 'No evaluation with this rubric version',
    evaluationNotReportable: 'Evaluation is pending or not reportable',
    competencyNotReported: 'Competency not reported',
    plan: 'Active plan',
    goals: 'Goal status counts',
    record: 'Record',
    status: 'Status',
    type: 'Type',
    scope: 'Scope',
    timeRange: 'Data time range',
    generatedAt: 'Generated',
    transition: 'State transition',
    memory: 'Memory',
    planRevision: 'Plan revision',
    noPlan: 'No active treatment plan.',
    error: 'Could not load persisted Run analytics.',
    limitations: 'Limitations',
    session: 'Session',
  },
  fa: {
    title: 'تحلیل و خروجی اجرا',
    description:
      'شمارش‌ها و رکوردها از داده‌های ذخیره‌شده این اجرا می‌آیند. شناسه‌ها هر مورد را به رکورد منبع پیوند می‌دهند.',
    refresh: 'تازه‌سازی تحلیل',
    loading: 'در حال بارگذاری تحلیل داده‌های ذخیره‌شده…',
    export: 'دریافت JSON',
    privacy:
      'خروجی شامل شناسه‌های عملیاتی حساس است؛ آن را با احتیاط نگهداری و به‌اشتراک بگذار.',
    sessions: 'جلسات',
    completedSessions: 'جلسات تکمیل‌شده',
    events: 'رویدادهای رفتاری',
    memories: 'رکوردهای حافظه',
    transitions: 'گذارهای حالت شخصیت',
    evaluations: 'ارزیابی‌ها',
    stale: 'گزارش طولی قدیمی',
    staleMark: 'قدیمی',
    competencyComparisons: 'مشاهده‌های شایستگی در جلسات',
    competencyComparisonNote:
      'مشاهده‌های خام بر اساس نسخه و هش دقیق روبریک گروه‌بندی می‌شوند. امتیازها میانگین‌گیری یا به‌عنوان پیامد بالینی تفسیر نمی‌شوند.',
    competency: 'شایستگی',
    rating: 'امتیاز',
    confidence: 'میزان اطمینان',
    fromSession: 'از جلسه',
    throughSession: 'تا جلسه',
    evaluable: 'مشاهده‌های قابل ارزیابی',
    notEvaluable: 'غیرقابل ارزیابی (NE)',
    missing: 'مشاهده‌های مفقود',
    evidenceCoverage: 'پوشش شواهد',
    reviewOutcomes: 'نتایج بازبینی انسانی',
    rawChange: 'تغییر خام کد امتیاز',
    insufficientComparison: 'برای مقایسه خام دست‌کم دو مشاهده قابل ارزیابی لازم است.',
    chartAxes:
      'محور افقی: شماره جلسه تکمیل‌شده. محور عمودی: کد خام روبریک (۰ تا ۳). موارد NE و مفقود حذف می‌شوند و صفر نیستند. هر نقطه به گزارش ارزیابی پیوند دارد.',
    noChartData: 'در این بازه جلسه، مشاهده عددی قابل ارزیابی وجود ندارد.',
    openEvaluation: 'بازکردن ارزیابی',
    evaluationStatus: 'وضعیت ارزیابی',
    evidenceMessages: 'شناسه پیام‌های شواهد',
    noCompetencyObservations: 'مشاهده شایستگی معتبر برای جلسات وجود ندارد.',
    noEvaluationForRubric: 'ارزیابی با این نسخه روبریک وجود ندارد',
    evaluationNotReportable: 'ارزیابی در انتظار است یا نتیجه قابل گزارش نیست',
    competencyNotReported: 'شایستگی گزارش نشده است',
    plan: 'برنامه فعال',
    goals: 'شمارش وضعیت هدف‌ها',
    record: 'رکورد',
    status: 'وضعیت',
    type: 'نوع',
    scope: 'دامنه',
    timeRange: 'بازه زمانی داده',
    generatedAt: 'زمان تولید',
    transition: 'گذار حالت',
    memory: 'حافظه',
    planRevision: 'نسخه برنامه',
    noPlan: 'برنامه درمان فعال وجود ندارد.',
    error: 'بارگذاری تحلیل داده‌های اجرا ناموفق بود.',
    limitations: 'محدودیت‌ها',
    session: 'جلسه',
  },
} as const

const persianLimitations: Record<string, string> = {
  'Experimental operational analytics; not a clinical outcome measure.':
    'این تحلیل عملیاتی و آزمایشی است و معیار پیامد بالینی محسوب نمی‌شود.',
  'Counts do not establish therapeutic effectiveness or competency.':
    'شمارش‌ها اثربخشی درمان یا صلاحیت درمانگر را اثبات نمی‌کنند.',
  'Competency observations are raw session-level rubric results grouped by exact rubric version; no trend score or average is calculated.':
    'مشاهده‌های شایستگی، نتایج خام جلسات‌اند که بر اساس نسخه دقیق روبریک گروه‌بندی می‌شوند؛ امتیاز روندی یا میانگینی محاسبه نمی‌شود.',
  'Missing session observations mean no reportable score is available, not that the competency was absent.':
    'نبود مشاهده برای جلسه یعنی امتیاز قابل گزارشی در دسترس نیست، نه اینکه شایستگی وجود نداشته است.',
  "Evaluation staleness follows the evaluator's stored transcript and Run-scope validation.":
    'قدیمی‌شدن ارزیابی بر اساس رونوشت ذخیره‌شده توسط ارزیاب و اعتبارسنجی در محدوده اجرا تعیین می‌شود.',
  'Transcript text and case details are intentionally excluded from this export.':
    'متن رونوشت و جزئیات پرونده عمداً از این خروجی حذف شده‌اند.',
}

interface RunAnalyticsPanelProps {
  runId: string
  language: Language
  refreshKey: number
}

function countsLabel(counts: Record<string, number>) {
  const entries = Object.entries(counts)
  return entries.length > 0
    ? entries.map(([name, count]) => `${name}: ${count}`).join(' · ')
    : '0'
}

function trajectoryId(
  trajectory: RunAnalyticsSnapshot['competency_trajectories'][number],
) {
  return [
    trajectory.rubric_version_id,
    trajectory.rubric_content_hash ?? '',
    trajectory.competency_id,
  ].join(':')
}

export function RunAnalyticsPanel({
  runId,
  language,
  refreshKey,
}: RunAnalyticsPanelProps) {
  const copy = text[language]
  const [snapshot, setSnapshot] = useState<RunAnalyticsSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedTrajectoryId, setSelectedTrajectoryId] = useState('')
  const [rangeStart, setRangeStart] = useState<number | null>(null)
  const [rangeEnd, setRangeEnd] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setSnapshot(await getRunAnalytics(runId))
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : 'analytics_request_failed',
      )
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load, refreshKey])

  function download() {
    if (!snapshot) return
    const file = new Blob([JSON.stringify(snapshot, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = url
    link.download = `therasim-run-${runId}-analytics.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const completedSessions =
    snapshot?.sessions.filter((session) => session.status === 'completed') ?? []
  const firstCompletedNumber = completedSessions[0]?.session_number
  const lastCompletedNumber =
    completedSessions[completedSessions.length - 1]?.session_number
  const activeRangeStart = rangeStart ?? firstCompletedNumber
  const activeRangeEnd = rangeEnd ?? lastCompletedNumber
  const rangeSessions = completedSessions.filter(
    (session) =>
      session.session_number >= (activeRangeStart ?? Number.NEGATIVE_INFINITY) &&
      session.session_number <= (activeRangeEnd ?? Number.POSITIVE_INFINITY),
  )
  const rangeSessionIds = new Set(rangeSessions.map((session) => session.session_id))
  const selectedTrajectory =
    snapshot?.competency_trajectories.find(
      (trajectory) => trajectoryId(trajectory) === selectedTrajectoryId,
    ) ?? snapshot?.competency_trajectories[0]
  const sortedTrajectoryObservations = [
    ...(selectedTrajectory?.observations ?? []),
  ].sort(
    (left, right) =>
      left.session_number - right.session_number ||
      left.evaluation_revision - right.evaluation_revision,
  )
  const chartObservationBySession = new Map(
    sortedTrajectoryObservations
      .filter((observation) => rangeSessionIds.has(observation.session_id))
      .map((observation) => [observation.session_id, observation]),
  )
  const rangeObservations = [...chartObservationBySession.values()].sort(
    (left, right) => left.session_number - right.session_number,
  )
  const rangeEvaluableObservations = rangeObservations.filter(
    (observation) => observation.rating_code !== 'NE',
  )
  const rangeEvidenceCoverage = rangeEvaluableObservations.length
    ? rangeEvaluableObservations.filter(
      (observation) => observation.evidence_message_ids.length > 0,
      ).length / rangeEvaluableObservations.length
    : null
  const rangeMissingCount =
    selectedTrajectory?.missing_completed_sessions.filter((item) =>
      rangeSessionIds.has(item.session_id),
    ).length ?? 0
  const rangeReviewDecisionCounts = rangeObservations.reduce<
    Record<string, number>
  >((counts, observation) => {
    observation.review_decisions.forEach((review) => {
      counts[review.decision] = (counts[review.decision] ?? 0) + 1
    })
    return counts
  }, {})
  const rangeRatingChange =
    rangeEvaluableObservations.length >= 2
      ? {
        first: rangeEvaluableObservations[0],
        last: rangeEvaluableObservations[rangeEvaluableObservations.length - 1],
        delta:
          Number(
            rangeEvaluableObservations[
              rangeEvaluableObservations.length - 1
            ].rating_code,
          ) - Number(rangeEvaluableObservations[0].rating_code),
      }
      : null
  const chartObservations = [...chartObservationBySession.values()]
    .filter((observation) => /^[0-3]$/.test(observation.rating_code))
    .sort((left, right) => left.session_number - right.session_number)
  const chart = { width: 640, height: 240, left: 44, right: 18, top: 20, bottom: 36 }
  const minSession = rangeSessions[0]?.session_number ?? 1
  const maxSession =
    rangeSessions[rangeSessions.length - 1]?.session_number ?? minSession
  const chartX = (sessionNumber: number) =>
    chart.left +
    ((sessionNumber - minSession) / Math.max(1, maxSession - minSession)) *
      (chart.width - chart.left - chart.right)
  const chartY = (ratingCode: string) =>
    chart.top +
    ((3 - Number(ratingCode)) / 3) * (chart.height - chart.top - chart.bottom)
  const chartSegments = chartObservations.slice(1).flatMap((point, index) => {
    const previous = chartObservations[index]
    return point.session_number === previous.session_number + 1
      ? [
          `M ${chartX(previous.session_number)} ${chartY(previous.rating_code)} L ${chartX(point.session_number)} ${chartY(point.rating_code)}`,
        ]
      : []
  })

  return (
    <section
      className="surface-card run-analytics-card"
      aria-labelledby="run-analytics-title"
    >
      <div className="memory-review-heading">
        <div>
          <h2 id="run-analytics-title">{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <div className="run-analytics-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={() => void load()}
            disabled={loading}
          >
            {loading ? (
              <LoaderCircle className="spin" size={15} />
            ) : (
              <RefreshCw size={15} />
            )}
            {copy.refresh}
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={download}
            disabled={!snapshot}
          >
            <Download size={15} />
            {copy.export}
          </button>
        </div>
      </div>

      <p className="memory-review-warning">{copy.privacy}</p>

      {error && (
        <div className="sessions-alert sessions-alert-error" role="alert">
          <AlertCircle size={17} />
          <span>{error === 'analytics_request_failed' ? copy.error : error}</span>
        </div>
      )}
      {loading && (
        <p className="memory-review-state" role="status">
          <LoaderCircle className="spin" size={15} />
          {copy.loading}
        </p>
      )}

      {snapshot && (
        <>
          <div className="memory-candidate-meta">
            <span>
              {copy.scope}: {snapshot.data_scope}
            </span>
            <span>
              {copy.timeRange}:{' '}
              <bdi dir="ltr">
                {snapshot.time_range_start ?? '—'} – {snapshot.time_range_end ?? '—'}
              </bdi>
            </span>
            <span>
              {copy.generatedAt}: <bdi dir="ltr">{snapshot.generated_at}</bdi>
            </span>
          </div>
          <div className="run-analytics-summary">
            <article>
              <strong>{copy.sessions}</strong>
              <span>{snapshot.sessions.length}</span>
              <small>
                {copy.completedSessions}:{' '}
                {snapshot.sessions.filter((item) => item.status === 'completed').length}
              </small>
            </article>
            <article>
              <strong>{copy.events}</strong>
              <span>{snapshot.events.length}</span>
              <small>{countsLabel(snapshot.event_counts)}</small>
            </article>
            <article>
              <strong>{copy.memories}</strong>
              <span>{snapshot.memories.length}</span>
              <small>{countsLabel(snapshot.memory_counts)}</small>
            </article>
            <article>
              <strong>{copy.transitions}</strong>
              <span>{snapshot.state_transitions.length}</span>
              <small>{countsLabel(snapshot.transition_counts)}</small>
            </article>
            <article>
              <strong>{copy.evaluations}</strong>
              <span>{snapshot.evaluations.length}</span>
              <small>
                {copy.stale}:{' '}
                {snapshot.evaluations.filter((item) => item.stale).length}
              </small>
            </article>
          </div>

          <div className="memory-evidence">
            <strong>{copy.competencyComparisons}</strong>
            <p>{copy.competencyComparisonNote}</p>
            {snapshot.competency_trajectories.length === 0 ? (
              <p>{copy.noCompetencyObservations}</p>
            ) : (
              <>
              <div className="run-analytics-filters">
                <label>
                  {copy.competency}
                  <select
                    value={selectedTrajectory ? trajectoryId(selectedTrajectory) : ''}
                    onChange={(event) =>
                      setSelectedTrajectoryId(event.target.value)
                    }
                  >
                    {snapshot.competency_trajectories.map((trajectory) => (
                      <option
                        key={trajectoryId(trajectory)}
                        value={trajectoryId(trajectory)}
                      >
                        {trajectory.competency_id} · {trajectory.rubric_id}{' '}
                        {trajectory.rubric_version} · {trajectory.rubric_version_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {copy.fromSession}
                  <select
                    aria-label={copy.fromSession}
                    value={activeRangeStart ?? ''}
                    onChange={(event) => {
                      const nextStart = event.target.value
                        ? Number(event.target.value)
                        : null
                      setRangeStart(nextStart)
                      if (
                        nextStart !== null &&
                        activeRangeEnd !== undefined &&
                        activeRangeEnd < nextStart
                      ) {
                        setRangeEnd(nextStart)
                      }
                    }}
                  >
                    {completedSessions.map((session) => (
                      <option key={session.session_id} value={session.session_number}>
                        {session.session_number}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {copy.throughSession}
                  <select
                    aria-label={copy.throughSession}
                    value={activeRangeEnd ?? ''}
                    onChange={(event) =>
                      setRangeEnd(
                        event.target.value ? Number(event.target.value) : null,
                      )
                    }
                  >
                    {completedSessions
                      .filter(
                        (session) =>
                          session.session_number >=
                          (activeRangeStart ?? Number.NEGATIVE_INFINITY),
                      )
                      .map((session) => (
                        <option key={session.session_id} value={session.session_number}>
                          {session.session_number}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              {selectedTrajectory && (
                <>
                  <div className="run-analytics-metrics">
                    <span>
                      {copy.evaluable}: {rangeEvaluableObservations.length}
                    </span>
                    <span>
                      {copy.notEvaluable}:{' '}
                      {
                        rangeObservations.filter(
                          (observation) => observation.rating_code === 'NE',
                        ).length
                      }
                    </span>
                    <span>{copy.missing}: {rangeMissingCount}</span>
                    <span>
                      {copy.evidenceCoverage}:{' '}
                      {rangeEvidenceCoverage === null
                        ? '—'
                        : `${Math.round(rangeEvidenceCoverage * 100)}%`}
                    </span>
                    <span>
                      {copy.reviewOutcomes}:{' '}
                      {countsLabel(rangeReviewDecisionCounts)}
                    </span>
                  </div>
                  <p className="run-analytics-chart-description">
                    {copy.chartAxes}
                  </p>
                  {chartObservations.length > 0 ? (
                    <svg
                      className="run-analytics-chart"
                      viewBox={`0 0 ${chart.width} ${chart.height}`}
                      role="img"
                      aria-label={`${selectedTrajectory.competency_id}. ${copy.chartAxes}`}
                    >
                      {[0, 1, 2, 3].map((rating) => (
                        <g key={rating}>
                          <line
                            x1={chart.left}
                            x2={chart.width - chart.right}
                            y1={chartY(String(rating))}
                            y2={chartY(String(rating))}
                            className="run-analytics-gridline"
                          />
                          <text
                            x={chart.left - 10}
                            y={chartY(String(rating)) + 4}
                            textAnchor="end"
                          >
                            {rating}
                          </text>
                        </g>
                      ))}
                      {rangeSessions.map((session) => (
                        <text
                          key={session.session_id}
                          x={chartX(session.session_number)}
                          y={chart.height - 10}
                          textAnchor="middle"
                        >
                          {session.session_number}
                        </text>
                      ))}
                      {chartSegments.map((segment, index) => (
                        <path
                          key={index}
                          d={segment}
                          className="run-analytics-chart-line"
                        />
                      ))}
                      {chartObservations.map((observation) => (
                        <a
                          key={observation.evaluation_id}
                          href={`#evaluation-${observation.evaluation_id}`}
                          aria-label={`${copy.openEvaluation} ${observation.evaluation_id}, ${copy.session} ${observation.session_number}, ${copy.rating} ${observation.rating_code}`}
                        >
                          <circle
                            cx={chartX(observation.session_number)}
                            cy={chartY(observation.rating_code)}
                            r="6"
                            className="run-analytics-chart-point"
                          >
                            <title>
                              {copy.session} {observation.session_number}: {copy.rating}{' '}
                              {observation.rating_code} · {observation.evaluation_id}
                            </title>
                          </circle>
                        </a>
                      ))}
                    </svg>
                  ) : (
                    <p>{copy.noChartData}</p>
                  )}
                  {rangeRatingChange ? (
                    <p>
                      {copy.rawChange}:{' '}
                      {rangeRatingChange.first.rating_code}{' '}
                      →{' '}
                      {rangeRatingChange.last.rating_code} (Δ{' '}
                      {rangeRatingChange.delta})
                    </p>
                  ) : (
                    <p>{copy.insufficientComparison}</p>
                  )}
                </>
              )}
              <div className="run-analytics-records">
                {snapshot.competency_trajectories.map((trajectory) => (
                  <div
                    key={trajectoryId(trajectory)}
                  >
                    <strong>
                      {copy.competency}: {trajectory.competency_id} ·{' '}
                      {trajectory.rubric_id} {trajectory.rubric_version} ·{' '}
                      <bdi dir="ltr">{trajectory.rubric_version_id}</bdi>
                    </strong>
                    <p>
                      {copy.evaluable}: {trajectory.summary.evaluable_count} ·{' '}
                      {copy.notEvaluable}: {trajectory.summary.non_evaluable_count} ·{' '}
                      {copy.missing}: {trajectory.summary.missing_count}
                    </p>
                    {trajectory.observations.map((observation) => (
                      <p
                        id={`evaluation-${observation.evaluation_id}`}
                        key={`${observation.evaluation_id}:${observation.evaluation_revision}`}
                      >
                        {copy.session} {observation.session_number} · {copy.rating}:{' '}
                        {observation.rating_code} ·{' '}
                        {copy.confidence}: {observation.confidence ?? '—'} ·{' '}
                        {copy.evaluationStatus}: {observation.evaluation_status} ·{' '}
                        <bdi dir="ltr">{observation.evaluation_id}</bdi> ·{' '}
                        {copy.evidenceMessages}:{' '}
                        <bdi dir="ltr">
                          {observation.evidence_message_ids.length > 0
                            ? observation.evidence_message_ids.join(', ')
                            : '—'}
                        </bdi>
                      </p>
                    ))}
                    {trajectory.missing_completed_sessions.map((missing) => (
                      <p key={missing.session_id}>
                        {copy.session} {missing.session_number} ·{' '}
                        {missing.reason === 'no_evaluation_for_rubric'
                          ? copy.noEvaluationForRubric
                          : missing.reason === 'evaluation_not_reportable'
                            ? copy.evaluationNotReportable
                            : copy.competencyNotReported}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
              </>
            )}
          </div>

          <div className="memory-evidence">
            <strong>{copy.plan}</strong>
            {snapshot.current_plan ? (
              <p>
                {copy.record}:{' '}
                <bdi dir="ltr">{snapshot.current_plan.revision_id}</bdi>
                {' · '}
                {copy.goals}: {countsLabel(snapshot.current_plan.goal_status_counts)}
              </p>
            ) : (
              <p>{copy.noPlan}</p>
            )}
          </div>

          <div className="run-analytics-records">
            {snapshot.sessions.map((session) => (
              <p key={session.session_id}>
                {copy.sessions} {session.session_number}:{' '}
                <bdi dir="ltr">{session.session_id}</bdi> · {session.status}
              </p>
            ))}
            {snapshot.events.map((event) => (
              <p key={event.event_id}>
                {copy.events}: <bdi dir="ltr">{event.event_id}</bdi> ·{' '}
                {event.event_type} · {event.event_status}
                {event.session_id && (
                  <>
                    {' · '}
                    {copy.session}: <bdi dir="ltr">{event.session_id}</bdi>
                  </>
                )}
              </p>
            ))}
            {snapshot.memories.map((memory) => (
              <p key={memory.memory_id}>
                {copy.memory}: <bdi dir="ltr">{memory.memory_id}</bdi> ·{' '}
                {memory.memory_type} · {memory.status} · v
                {memory.memory_version}
                {memory.source_session_id && (
                  <>
                    {' · '}
                    {copy.session}:{' '}
                    <bdi dir="ltr">{memory.source_session_id}</bdi>
                  </>
                )}
              </p>
            ))}
            {snapshot.state_transitions.map((transition) => (
              <p key={transition.transition_id}>
                {copy.transition}:{' '}
                <bdi dir="ltr">{transition.transition_id}</bdi> ·{' '}
                {transition.variable_name} · {transition.validation_status} ·{' '}
                <bdi dir="ltr">{transition.session_id}</bdi>
              </p>
            ))}
            {snapshot.plan_revisions.map((revision) => (
              <p key={revision.revision_id}>
                {copy.planRevision}:{' '}
                <bdi dir="ltr">{revision.revision_id}</bdi> ·{' '}
                {revision.revision_number} · {revision.status}
              </p>
            ))}
            {snapshot.evaluations.map((evaluation) => (
              <p key={evaluation.evaluation_id}>
                {copy.evaluations}:{' '}
                <bdi dir="ltr">{evaluation.evaluation_id}</bdi> ·{' '}
                {evaluation.rubric_id} {evaluation.rubric_version} ·{' '}
                {evaluation.status}
                {evaluation.stale ? ` · ${copy.staleMark}` : ''}
              </p>
            ))}
          </div>

          <div className="memory-evidence">
            <strong>{copy.limitations}</strong>
            {snapshot.limitations.map((limitation) => (
              <p key={limitation}>
                {language === 'fa'
                  ? persianLimitations[limitation] ?? limitation
                  : limitation}
              </p>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
