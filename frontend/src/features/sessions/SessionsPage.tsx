import { useEffect, useState, type FormEvent } from 'react'

import {
  AlertCircle,
  Check,
  LoaderCircle,
  MessageSquare,
  Play,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
} from 'lucide-react'

import type { Language } from '../../i18n'
import { MemoryReviewPanel } from '../memories/MemoryReviewPanel'
import { EventReviewPanel } from '../events/EventReviewPanel'
import { TreatmentPlanPanel } from '../treatmentPlans/TreatmentPlanPanel'
import { EvaluationPanel } from '../evaluations/EvaluationPanel'
import { LongitudinalEvaluationPanel } from '../evaluations/LongitudinalEvaluationPanel'
import { RunAnalyticsPanel } from '../analytics/RunAnalyticsPanel'

import {
  completeSimulationRun,
  completeSimulationSession,
  createSimulationRun,
  createSimulationSession,
  getCaseDetail,
  getInteractionRequestStatus,
  listCases,
  listRunSessions,
  listSessionMessages,
  listSimulationRuns,
  resumeSimulationRun,
  startSimulationRun,
  submitTherapistMessage,
} from './api'

import type {
  CaseCatalogItem,
  CaseDetail,
  CaseVersion,
  SessionMessage,
  SimulationRun,
  SimulationSession,
} from './types'

const text = {
  en: {
    eyebrow: 'CLINICAL SIMULATION WORKSPACE',
    title: 'Simulation sessions',
    description:
      'Create a simulation run and add sequential sessions as the work progresses.',
    disclaimer:
      'Training and research simulation only. Synthetic responses are not clinical advice or a validated assessment of therapist competence.',
    configuration: 'Case configuration',
    case: 'Case',
    chooseCase: 'Choose a case',
    version: 'Case version',
    chooseVersion: 'Choose a version',
    planningPolicy: 'Session planning policy',
    flexiblePlanning: 'Flexible planning',
    goalBasedPlanning: 'Goal-based planning',
    milestonePlanning: 'Milestone-based planning',
    openEndedPlanning: 'Open-ended educational simulation',
    caseLoading: 'Loading case details...',
    noCases: 'No active public cases are currently available.',
    noVersions: 'This case has no compatible public versions.',
    age: 'Age',
    occupation: 'Occupation',
    concerns: 'Presenting concerns',
    createRun: 'Create and start run',
    creatingRun: 'Creating run...',
    runHistory: 'Existing simulation runs',
    chooseRun: 'Open an existing run',
    noRuns: 'No previous runs found.',
    workspace: 'Run workspace',
    noRun: 'Create a new run or open an existing run to begin.',
    runId: 'Run ID',
    protocol: 'Protocol',
    evaluationRubric: 'Evaluation rubric',
    status: 'Status',
    sessions: 'Sessions',
    startRun: 'Start run',
    resumeRun: 'Resume run',
    startingRun: 'Updating run...',
    createSession: 'Create next session',
    creatingSession: 'Creating session...',
    completeSession: 'Complete session',
    completingSession: 'Completing...',
    completeRun: 'Complete run',
    completingRun: 'Completing run...',
    session: 'Session',
    active: 'Active',
    completed: 'Completed',
    initialized: 'Initialized',
    interrupted: 'Interrupted',
    failed: 'Failed',
    transcript: 'Session transcript',
    chooseSession: 'Choose a session',
    noMessages: 'No messages in this session yet.',
    therapist: 'Therapist',
    patient: 'Simulated client',
    composer: 'Write a therapist response...',
    send: 'Send',
    sending: 'Waiting for simulated response...',
    interactionProcessing: 'The local model is generating a response.',
    interactionDone: 'Response received and transcript refreshed.',
    processingTimeout: 'The response is taking longer than expected. Check the transcript before retrying.',
    interactionFailed: 'The interaction request failed.',
    sessionCompleteNote: 'This session is complete. Its transcript is read-only.',
    createNextNote: 'The previous session is complete. You can create the next session.',
    sessionsCompletedNote: 'All created sessions are complete. You can now complete this run.',
    runCompletedNote: 'This run is complete and can no longer accept new sessions.',
    selectCaseFirst: 'Choose a case and version first.',
    genericError: 'Something went wrong. Check the backend and try again.',
    refresh: 'Refresh transcript',
    loading: 'Loading...',
    technicalNote:
      'The transcript is persisted by the backend. Completing a session seals its transcript against further changes.',
  },
  fa: {
    eyebrow: 'محیط شبیه‌سازی بالینی',
    title: 'جلسات شبیه‌سازی',
    description:
      'یک اجرای شبیه‌سازی ایجاد کن و با پیشرفت کار، جلسات متوالی را اضافه کن.',
    disclaimer:
      'این سامانه برای آموزش و پژوهش است. پاسخ‌های مراجعان مصنوعی، توصیه بالینی یا سنجش اعتبارسنجی‌شده صلاحیت درمانگر نیستند.',
    configuration: 'تنظیم پرونده',
    case: 'پرونده',
    chooseCase: 'انتخاب پرونده',
    version: 'نسخه پرونده',
    chooseVersion: 'انتخاب نسخه',
    planningPolicy: 'سیاست برنامه‌ریزی جلسات',
    flexiblePlanning: 'برنامه‌ریزی انعطاف‌پذیر',
    goalBasedPlanning: 'برنامه‌ریزی بر پایه هدف',
    milestonePlanning: 'برنامه‌ریزی بر پایه نقاط عطف',
    openEndedPlanning: 'شبیه‌سازی آموزشی بدون پایان ازپیش‌تعیین‌شده',
    caseLoading: 'در حال دریافت اطلاعات پرونده...',
    noCases: 'در حال حاضر پرونده عمومی فعال در دسترس نیست.',
    noVersions: 'برای این پرونده نسخه عمومی سازگار وجود ندارد.',
    age: 'سن',
    occupation: 'شغل',
    concerns: 'مسائل مطرح‌شده',
    createRun: 'ایجاد و شروع اجرا',
    creatingRun: 'در حال ایجاد اجرا...',
    runHistory: 'اجراهای قبلی',
    chooseRun: 'بازکردن اجرای قبلی',
    noRuns: 'اجرای قبلی‌ای پیدا نشد.',
    workspace: 'فضای اجرای شبیه‌سازی',
    noRun: 'برای شروع، اجرای جدید بساز یا یکی از اجراهای قبلی را باز کن.',
    runId: 'شناسه اجرا',
    protocol: 'پروتکل',
    evaluationRubric: 'روبرک ارزیابی',
    status: 'وضعیت',
    sessions: 'جلسات',
    startRun: 'شروع اجرا',
    resumeRun: 'ادامه اجرا',
    startingRun: 'در حال به‌روزرسانی اجرا...',
    createSession: 'ایجاد جلسه بعدی',
    creatingSession: 'در حال ایجاد جلسه...',
    completeSession: 'پایان جلسه',
    completingSession: 'در حال پایان‌دادن...',
    completeRun: 'پایان اجرای شبیه‌سازی',
    completingRun: 'در حال پایان‌دادن به اجرا...',
    session: 'جلسه',
    active: 'فعال',
    completed: 'تکمیل‌شده',
    initialized: 'آماده شروع',
    interrupted: 'متوقف‌شده',
    failed: 'ناموفق',
    transcript: 'رونوشت جلسه',
    chooseSession: 'انتخاب جلسه',
    noMessages: 'هنوز پیامی در این جلسه ثبت نشده است.',
    therapist: 'درمانگر',
    patient: 'مراجع شبیه‌سازی‌شده',
    composer: 'پاسخ درمانگر را بنویس...',
    send: 'ارسال',
    sending: 'در انتظار پاسخ مراجع شبیه‌سازی‌شده...',
    interactionProcessing: 'مدل محلی در حال تولید پاسخ است.',
    interactionDone: 'پاسخ دریافت شد و رونوشت به‌روزرسانی شد.',
    processingTimeout: 'تولید پاسخ بیش از حد انتظار طول کشیده است. پیش از ارسال مجدد، رونوشت را بررسی کن.',
    interactionFailed: 'درخواست تعامل ناموفق بود.',
    sessionCompleteNote: 'این جلسه تکمیل شده و رونوشت آن فقط قابل مشاهده است.',
    createNextNote: 'جلسه قبلی تکمیل شده است. می‌توانی جلسه بعدی را ایجاد کنی.',
    sessionsCompletedNote: 'همه جلسات ایجادشده تکمیل شده‌اند. اکنون می‌توانی کل اجرا را تکمیل کنی.',
    runCompletedNote: 'این اجرا تکمیل شده و جلسه جدیدی نمی‌پذیرد.',
    selectCaseFirst: 'ابتدا پرونده و نسخه آن را انتخاب کن.',
    genericError: 'خطایی رخ داد. وضعیت بک‌اند را بررسی و دوباره تلاش کن.',
    refresh: 'تازه‌سازی رونوشت',
    loading: 'در حال بارگذاری...',
    technicalNote:
      'رونوشت در بک‌اند ذخیره می‌شود. با تکمیل جلسه، تغییرات بعدی روی رونوشت آن مسدود می‌شود.',
  },
} as const

type Copy = { [K in keyof typeof text.en]: string }

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback
}

function statusLabel(status: string, copy: Copy) {
  if (status === 'active') return copy.active
  if (status === 'completed') return copy.completed
  if (status === 'initialized') return copy.initialized
  if (status === 'interrupted') return copy.interrupted
  if (status === 'failed') return copy.failed
  return status
}

function planningPolicyLabel(policy: string, copy: Copy) {
  if (policy === 'goal_based') return copy.goalBasedPlanning
  if (policy === 'milestone_based') return copy.milestonePlanning
  if (policy === 'open_ended') return copy.openEndedPlanning
  return copy.flexiblePlanning
}

function createIdempotencyKey(sessionId: string) {
  const randomPart =
    typeof window.crypto?.randomUUID === 'function'
      ? window.crypto.randomUUID()
      : Math.random().toString(36).slice(2)

  return `${sessionId}:${Date.now()}:${randomPart}`
}

async function wait(milliseconds: number) {
  await new Promise<void>((resolve) => {
    window.setTimeout(resolve, milliseconds)
  })
}

export function SessionsPage({ language }: { language: Language }) {
  const copy = text[language]
  const isPersian = language === 'fa'

  const [cases, setCases] = useState<CaseCatalogItem[]>([])
  const [runs, setRuns] = useState<SimulationRun[]>([])

  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState('')
  const [sessionPlanningPolicy, setSessionPlanningPolicy] = useState('flexible')

  const [selectedRunId, setSelectedRunId] = useState('')
  const [activeRun, setActiveRun] = useState<SimulationRun | null>(null)

  const [sessions, setSessions] = useState<SimulationSession[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState('')
  const [sessionMessages, setSessionMessages] = useState<SessionMessage[]>([])
  const [memoryRefreshKey, setMemoryRefreshKey] = useState(0)

  const [casesLoading, setCasesLoading] = useState(true)
  const [caseDetailLoadedFor, setCaseDetailLoadedFor] = useState('')
  const [busy, setBusy] = useState(false)
  const [sending, setSending] = useState(false)

  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const detailLoading = Boolean(
    selectedCaseId && caseDetailLoadedFor !== selectedCaseId,
  )

  const selectedVersion = caseDetail?.case_id === selectedCaseId
    ? caseDetail.versions.find(
        (version) => version.case_version_id === selectedVersionId,
      ) ?? null
    : null

  const selectedSession = sessions.find(
    (session) => session.session_id === selectedSessionId,
  ) ?? null

  const lastSession = sessions.length > 0
    ? sessions[sessions.length - 1]
    : null

  const canCreateSession =
    activeRun?.status === 'active' &&
    (!lastSession || lastSession.status === 'completed')

  const allSessionsCompleted =
    sessions.length > 0 &&
    sessions.every((session) => session.status === 'completed')

  const canCompleteRun =
    activeRun?.status === 'active' && allSessionsCompleted

  const canSendMessage =
    activeRun?.status === 'active' &&
    selectedSession?.status === 'active' &&
    !sending &&
    !busy

  async function refreshMessages(sessionId: string) {
    const response = await listSessionMessages(sessionId, 200, 0)
    setSessionMessages(response.data)
  }

  async function refreshRunSessions(runId: string) {
    const response = await listRunSessions(runId)
    const ordered = [...response.data].sort(
      (a, b) => a.session_number - b.session_number,
    )

    setSessions(ordered)

    const preferred =
      ordered.find((session) => session.status === 'active') ??
      ordered[ordered.length - 1] ??
      null

    if (!preferred) {
      setSelectedSessionId('')
      setSessionMessages([])
      return ordered
    }

    setSelectedSessionId(preferred.session_id)
    await refreshMessages(preferred.session_id)

    return ordered
  }

  useEffect(() => {
    let mounted = true

    async function loadCatalogs() {
      setCasesLoading(true)

      const [caseResult, runResult] = await Promise.allSettled([
        listCases(),
        listSimulationRuns(),
      ])

      if (!mounted) return

      if (caseResult.status === 'fulfilled') {
        setCases(caseResult.value.data)

        if (caseResult.value.data.length > 0) {
          setSelectedCaseId(caseResult.value.data[0].case_id)
        }
      } else {
        setError(errorMessage(caseResult.reason, copy.genericError))
      }

      if (runResult.status === 'fulfilled') {
        setRuns(runResult.value.data)
      } else if (caseResult.status === 'fulfilled') {
        setError(errorMessage(runResult.reason, copy.genericError))
      }

      setCasesLoading(false)
    }

    void loadCatalogs()

    return () => {
      mounted = false
    }
  }, [copy.genericError])

  useEffect(() => {
    if (!selectedCaseId) return

    let mounted = true

    async function loadCase() {
      try {
        const response = await getCaseDetail(selectedCaseId)

        if (!mounted) return

        setCaseDetail(response.data)
        setSelectedVersionId(
          response.data.versions[0]?.case_version_id ?? '',
        )
      } catch (loadError) {
        if (mounted) {
          setError(errorMessage(loadError, copy.genericError))
        }
      } finally {
        if (mounted) {
          setCaseDetailLoadedFor(selectedCaseId)
        }
      }
    }

    void loadCase()

    return () => {
      mounted = false
    }
  }, [selectedCaseId, copy.genericError])

  async function openExistingRun(runId: string) {
    setError('')
    setNotice('')
    setSelectedRunId(runId)

    if (!runId) {
      setActiveRun(null)
      setSessions([])
      setSelectedSessionId('')
      setSessionMessages([])
      return
    }

    const run = runs.find((item) => item.run_id === runId)

    if (!run) return

    setBusy(true)
    setActiveRun(run)
    setSessions([])
    setSelectedSessionId('')
    setSessionMessages([])

    try {
      await refreshRunSessions(run.run_id)
    } catch (loadError) {
      setError(errorMessage(loadError, copy.genericError))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateRun() {
    if (!selectedCaseId || !selectedVersion) {
      setError(copy.selectCaseFirst)
      return
    }

    setBusy(true)
    setError('')
    setNotice('')

    try {
      const created = await createSimulationRun({
        case_id: selectedCaseId,
        case_version_id: selectedVersion.case_version_id,
        modality: selectedVersion.modality,
        language: selectedVersion.language,
        session_planning_policy: sessionPlanningPolicy,
      })

      setActiveRun(created.data)
      setSelectedRunId(created.data.run_id)
      setRuns((current) => [
        created.data,
        ...current.filter((run) => run.run_id !== created.data.run_id),
      ])

      const started = await startSimulationRun(created.data.run_id)

      setActiveRun(started.data)
      setRuns((current) =>
        current.map((run) =>
          run.run_id === started.data.run_id ? started.data : run,
        ),
      )

      await refreshRunSessions(started.data.run_id)
      setNotice(isPersian ? 'اجرا با موفقیت شروع شد.' : 'Run started successfully.')
    } catch (createError) {
      setError(errorMessage(createError, copy.genericError))
    } finally {
      setBusy(false)
    }
  }

  async function handleStartOrResumeRun() {
    if (!activeRun) return

    setBusy(true)
    setError('')
    setNotice('')

    try {
      const response = activeRun.status === 'initialized'
        ? await startSimulationRun(activeRun.run_id)
        : await resumeSimulationRun(activeRun.run_id)

      setActiveRun(response.data)
      setRuns((current) =>
        current.map((run) =>
          run.run_id === response.data.run_id ? response.data : run,
        ),
      )

      await refreshRunSessions(response.data.run_id)
    } catch (actionError) {
      setError(errorMessage(actionError, copy.genericError))
    } finally {
      setBusy(false)
    }
  }

  async function handleCreateSession() {
    if (!activeRun || !canCreateSession) return

    setBusy(true)
    setError('')
    setNotice('')

    try {
      await createSimulationSession(activeRun.run_id)
      await refreshRunSessions(activeRun.run_id)
      setMemoryRefreshKey((current) => current + 1)
    } catch (sessionError) {
      setError(errorMessage(sessionError, copy.genericError))
    } finally {
      setBusy(false)
    }
  }

  async function handleSelectSession(sessionId: string) {
    setSelectedSessionId(sessionId)
    setSessionMessages([])
    setError('')

    if (!sessionId) return

    setBusy(true)

    try {
      await refreshMessages(sessionId)
    } catch (loadError) {
      setError(errorMessage(loadError, copy.genericError))
    } finally {
      setBusy(false)
    }
  }

  async function handleCompleteSession() {
    if (!selectedSession || selectedSession.status !== 'active') return

    setBusy(true)
    setError('')
    setNotice('')

    try {
      await completeSimulationSession(selectedSession.session_id)

      if (activeRun) {
        await refreshRunSessions(activeRun.run_id)
      }
      setMemoryRefreshKey((current) => current + 1)

      setNotice(
        isPersian
          ? 'جلسه تکمیل شد و رونوشت آن قفل شد.'
          : 'Session completed. Its transcript is now sealed.',
      )
    } catch (completionError) {
      setError(errorMessage(completionError, copy.genericError))
    } finally {
      setBusy(false)
    }
  }

  async function handleCompleteRun() {
    if (!activeRun || !canCompleteRun) return

    setBusy(true)
    setError('')
    setNotice('')

    try {
      const response = await completeSimulationRun(activeRun.run_id)

      setActiveRun(response.data)
      setRuns((current) =>
        current.map((run) =>
          run.run_id === response.data.run_id ? response.data : run,
        ),
      )

      setNotice(
        isPersian ? 'اجرای شبیه‌سازی تکمیل شد.' : 'Simulation run completed.',
      )
    } catch (completionError) {
      setError(errorMessage(completionError, copy.genericError))
    } finally {
      setBusy(false)
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedSession || !canSendMessage || !draft.trim()) return

    const content = draft.trim()

    setSending(true)
    setError('')
    setNotice('')
    setDraft('')

    try {
      const response = await submitTherapistMessage(
        selectedSession.session_id,
        content,
        createIdempotencyKey(selectedSession.session_id),
      )

      if (response.status === 'processing') {
        setNotice(copy.interactionProcessing)

        let completed = false

        for (let attempt = 0; attempt < 150; attempt += 1) {
          await wait(2000)

          const statusResponse = await getInteractionRequestStatus(
            response.request_id,
          )

          const currentStatus = statusResponse.data.processing_status

          if (currentStatus === 'completed') {
            completed = true
            break
          }

          if (currentStatus === 'failed') {
            throw new Error(
              statusResponse.data.error_code ?? copy.interactionFailed,
            )
          }
        }

        if (!completed) {
          throw new Error(copy.processingTimeout)
        }
      }

      await refreshMessages(selectedSession.session_id)
      setMemoryRefreshKey((current) => current + 1)
      setNotice(copy.interactionDone)
    } catch (sendError) {
      try {
        await refreshMessages(selectedSession.session_id)
      } catch {
        // Preserve the original interaction error.
      }

      setError(errorMessage(sendError, copy.genericError))
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="secondary-view sessions-page" dir={isPersian ? 'rtl' : 'ltr'}>
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <MessageSquare size={15} />
            {copy.eyebrow}
          </div>
          <h1>{copy.title}</h1>
          <p>{copy.description}</p>
        </div>
      </div>

      <div className="sessions-disclaimer">
        <ShieldCheck size={17} />
        <span>{copy.disclaimer}</span>
      </div>

      {error && (
        <div className="sessions-alert sessions-alert-error" role="alert">
          <AlertCircle size={17} />
          <span>{error}</span>
        </div>
      )}

      {notice && (
        <div className="sessions-alert sessions-alert-notice" role="status">
          <Check size={17} />
          <span>{notice}</span>
        </div>
      )}

      <div className="sessions-grid">
        <section className="surface-card sessions-card">
          <div className="sessions-card-heading">
            <div>
              <h2>{copy.configuration}</h2>
              <p>{copy.createRun}</p>
            </div>
            <span className="sessions-card-icon">
              <Plus size={18} />
            </span>
          </div>

          <label className="sessions-field">
            <span>{copy.case}</span>
            <select
              value={selectedCaseId}
              onChange={(event) => setSelectedCaseId(event.target.value)}
              disabled={casesLoading || busy || cases.length === 0}
            >
              <option value="">
                {casesLoading ? copy.loading : copy.chooseCase}
              </option>
              {cases.map((item) => (
                <option key={item.case_id} value={item.case_id}>
                  {item.display_name} ({item.case_code})
                </option>
              ))}
            </select>
          </label>

          <label className="sessions-field">
            <span>{copy.version}</span>
            <select
              value={selectedVersionId}
              onChange={(event) => setSelectedVersionId(event.target.value)}
              disabled={detailLoading || busy || !caseDetail?.versions.length}
            >
              <option value="">
                {detailLoading ? copy.loading : copy.chooseVersion}
              </option>
              {caseDetail?.versions.map((version: CaseVersion) => (
                <option
                  key={version.case_version_id}
                  value={version.case_version_id}
                >
                  v{version.version_number} · {version.modality} · {version.language}
                </option>
              ))}
            </select>
          </label>

          <label className="sessions-field">
            <span>{copy.planningPolicy}</span>
            <select
              value={sessionPlanningPolicy}
              onChange={(event) => setSessionPlanningPolicy(event.target.value)}
              disabled={busy}
            >
              <option value="flexible">{copy.flexiblePlanning}</option>
              <option value="goal_based">{copy.goalBasedPlanning}</option>
              <option value="milestone_based">{copy.milestonePlanning}</option>
              <option value="open_ended">{copy.openEndedPlanning}</option>
            </select>
          </label>

          {detailLoading && (
            <div className="sessions-inline-loading">
              <LoaderCircle className="spin" size={15} />
              {copy.caseLoading}
            </div>
          )}

          {!casesLoading && cases.length === 0 && (
            <p className="sessions-empty">{copy.noCases}</p>
          )}

          {caseDetail && selectedVersion && (
            <div className="sessions-case-summary">
              <div className="sessions-case-meta">
                {selectedVersion.presentation.age !== null && (
                  <span>
                    <strong>{copy.age}:</strong> {selectedVersion.presentation.age}
                  </span>
                )}
                {selectedVersion.presentation.occupation && (
                  <span>
                    <strong>{copy.occupation}:</strong>{' '}
                    {selectedVersion.presentation.occupation}
                  </span>
                )}
              </div>

              {selectedVersion.presentation.presenting_concerns.length > 0 && (
                <div className="sessions-concerns">
                  <strong>{copy.concerns}</strong>
                  <ul>
                    {selectedVersion.presentation.presenting_concerns.map(
                      (concern, index) => (
                        <li key={`${index}-${concern}`}>{concern}</li>
                      ),
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}

          {caseDetail?.case_id === selectedCaseId &&
            caseDetail.versions.length === 0 && (
            <p className="sessions-empty">{copy.noVersions}</p>
          )}

          <button
            type="button"
            className="primary-button sessions-action-button"
            onClick={() => void handleCreateRun()}
            disabled={
              busy ||
              casesLoading ||
              detailLoading ||
              !selectedCaseId ||
              !selectedVersion
            }
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            {busy ? copy.creatingRun : copy.createRun}
          </button>

          <div className="sessions-history">
            <label className="sessions-field">
              <span>{copy.runHistory}</span>
              <select
                value={selectedRunId}
                onChange={(event) => void openExistingRun(event.target.value)}
                disabled={busy || sending}
              >
                <option value="">{copy.chooseRun}</option>
                {runs.map((run) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.run_id.slice(0, 8)} · {statusLabel(run.status, copy)} ·{' '}
                    {run.session_count}
                  </option>
                ))}
              </select>
            </label>

            {runs.length === 0 && (
              <p className="sessions-muted">{copy.noRuns}</p>
            )}
          </div>
        </section>

        <section className="surface-card sessions-card sessions-workspace-card">
          <div className="sessions-card-heading">
            <div>
              <h2>{copy.workspace}</h2>
              <p>{copy.sessions}: {sessions.length}</p>
            </div>
            <span className="sessions-card-icon">
              <MessageSquare size={18} />
            </span>
          </div>

          {!activeRun && (
            <div className="sessions-empty-state">
              <MessageSquare size={25} />
              <p>{copy.noRun}</p>
            </div>
          )}

          {activeRun && (
            <>
              <div className="sessions-run-summary">
                <div>
                  <span className="sessions-muted">{copy.runId}</span>
                  <strong dir="ltr">{activeRun.run_id}</strong>
                </div>
                <div>
                  <span className="sessions-muted">{copy.status}</span>
                  <span className={`sessions-status sessions-status-${activeRun.status}`}>
                    {statusLabel(activeRun.status, copy)}
                  </span>
                </div>
                <div>
                  <span className="sessions-muted">{copy.planningPolicy}</span>
                  <strong>
                    {planningPolicyLabel(
                      activeRun.session_planning_policy,
                      copy,
                    )}
                  </strong>
                </div>
                <div>
                  <span className="sessions-muted">{copy.protocol}</span>
                  <strong dir="ltr">
                    {activeRun.protocol_id} · {activeRun.protocol_version}
                  </strong>
                </div>
                <div>
                  <span className="sessions-muted">{copy.evaluationRubric}</span>
                  <strong dir="ltr">
                    {activeRun.evaluation_rubric_id} ·{' '}
                    {activeRun.evaluation_rubric_version}
                  </strong>
                </div>
              </div>

              {activeRun.status === 'initialized' && (
                <button
                  type="button"
                  className="primary-button sessions-action-button"
                  onClick={() => void handleStartOrResumeRun()}
                  disabled={busy}
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Play size={16} />
                  )}
                  {busy ? copy.startingRun : copy.startRun}
                </button>
              )}

              {activeRun.status === 'interrupted' && (
                <button
                  type="button"
                  className="primary-button sessions-action-button"
                  onClick={() => void handleStartOrResumeRun()}
                  disabled={busy}
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <RefreshCw size={16} />
                  )}
                  {busy ? copy.startingRun : copy.resumeRun}
                </button>
              )}

              <div className="sessions-session-heading">
                <strong>{copy.sessions}</strong>
                <span>{sessions.length}</span>
              </div>

              {sessions.length > 0 && (
                <div className="sessions-session-list">
                  {sessions.map((session) => (
                    <button
                      key={session.session_id}
                      type="button"
                      className={`sessions-session-item ${
                        selectedSessionId === session.session_id ? 'selected' : ''
                      }`}
                      onClick={() => void handleSelectSession(session.session_id)}
                      disabled={busy || sending}
                    >
                      <span className="sessions-session-number">
                        {session.session_number}
                      </span>
                      <span className="sessions-session-label">
                        {copy.session} {session.session_number}
                      </span>
                      <span
                        className={`sessions-status sessions-status-${session.status}`}
                      >
                        {statusLabel(session.status, copy)}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {canCreateSession && (
                <>
                  {sessions.length > 0 && (
                    <p className="sessions-guidance">{copy.createNextNote}</p>
                  )}
                  <button
                    type="button"
                    className="secondary-button sessions-action-button"
                    onClick={() => void handleCreateSession()}
                    disabled={busy}
                  >
                    {busy ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : (
                      <Plus size={16} />
                    )}
                    {busy ? copy.creatingSession : copy.createSession}
                  </button>
                </>
              )}

              {allSessionsCompleted && (
                <p className="sessions-guidance">{copy.sessionsCompletedNote}</p>
              )}

              {canCompleteRun && (
                <button
                  type="button"
                  className="primary-button sessions-action-button"
                  onClick={() => void handleCompleteRun()}
                  disabled={busy}
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <Check size={16} />
                  )}
                  {busy ? copy.completingRun : copy.completeRun}
                </button>
              )}

              {activeRun.status === 'completed' && (
                <p className="sessions-guidance">{copy.runCompletedNote}</p>
              )}
            </>
          )}
        </section>
      </div>

      {activeRun && selectedSession && (
        <section className="surface-card sessions-transcript-card">
          <div className="sessions-transcript-heading">
            <div>
              <h2>{copy.transcript}</h2>
              <p>
                {copy.session} {selectedSession.session_number} ·{' '}
                {statusLabel(selectedSession.status, copy)}
              </p>
            </div>

            <button
              type="button"
              className="secondary-button sessions-refresh-button"
              onClick={() => void refreshMessages(selectedSession.session_id)}
              disabled={busy || sending}
            >
              <RefreshCw size={15} />
              {copy.refresh}
            </button>
          </div>

          <div className="sessions-message-list" aria-live="polite">
            {sessionMessages.length === 0 && (
              <div className="sessions-empty-state">
                <MessageSquare size={23} />
                <p>{busy ? copy.loading : copy.noMessages}</p>
              </div>
            )}

            {sessionMessages.map((message) => {
              const isTherapist = [
                'therapist',
                'user',
                'trainee',
              ].includes(message.role.toLowerCase())

              return (
                <article
                  className={`sessions-message ${
                    isTherapist ? 'sessions-message-therapist' : 'sessions-message-patient'
                  }`}
                  key={message.message_id}
                >
                  <div className="sessions-message-meta">
                    <strong>
                      {isTherapist ? copy.therapist : copy.patient}
                    </strong>
                    <time dateTime={message.created_at}>
                      {new Date(message.created_at).toLocaleTimeString(
                        isPersian ? 'fa-IR' : 'en-US',
                        { hour: '2-digit', minute: '2-digit' },
                      )}
                    </time>
                  </div>
                  <p dir="auto">{message.content}</p>
                </article>
              )
            })}
          </div>

          {selectedSession.status === 'active' && activeRun.status === 'active' && (
            <form
              className="sessions-composer"
              onSubmit={(event) => void handleSendMessage(event)}
            >
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={copy.composer}
                rows={3}
                maxLength={100000}
                disabled={!canSendMessage}
              />

              <div className="sessions-composer-bottom">
                <span>
                  {sending ? copy.sending : copy.technicalNote}
                </span>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={!canSendMessage || !draft.trim()}
                >
                  {sending ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <Send size={15} />
                  )}
                  {sending ? copy.sending : copy.send}
                </button>
              </div>
            </form>
          )}

          {selectedSession.status === 'active' && activeRun.status === 'active' && (
            <div className="sessions-completion-row">
              <button
                type="button"
                className="secondary-button"
                onClick={() => void handleCompleteSession()}
                disabled={busy || sending}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Check size={15} />
                )}
                {busy ? copy.completingSession : copy.completeSession}
              </button>
            </div>
          )}

          {selectedSession.status === 'completed' && (
            <p className="sessions-guidance">{copy.sessionCompleteNote}</p>
          )}
        </section>
      )}

      {activeRun && (
        <MemoryReviewPanel
          key={activeRun.run_id}
          runId={activeRun.run_id}
          language={language}
          refreshKey={memoryRefreshKey}
        />
      )}

      {activeRun && (
        <EventReviewPanel
          key={activeRun.run_id}
          runId={activeRun.run_id}
          language={language}
          refreshKey={memoryRefreshKey}
        />
      )}

      {activeRun && (
        <TreatmentPlanPanel
          key={activeRun.run_id}
          runId={activeRun.run_id}
          language={language}
          refreshKey={memoryRefreshKey}
        />
      )}

      {activeRun && selectedSession?.status === 'completed' && (
        <EvaluationPanel
          key={selectedSession.session_id}
          sessionId={selectedSession.session_id}
          sessionStatus={selectedSession.status}
          transcript={sessionMessages}
          language={language}
        />
      )}
      {activeRun && (
        <LongitudinalEvaluationPanel
          key={activeRun.run_id}
          runId={activeRun.run_id}
          modality={activeRun.modality}
          completedSessionCount={
            sessions.filter((session) => session.status === 'completed').length
          }
          refreshKey={memoryRefreshKey}
          language={language}
        />
      )}
      {activeRun && (
        <RunAnalyticsPanel
          key={activeRun.run_id}
          runId={activeRun.run_id}
          refreshKey={memoryRefreshKey}
          language={language}
        />
      )}
    </section>
  )
}
