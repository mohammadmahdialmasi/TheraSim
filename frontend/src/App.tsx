import brandLogo from './assets/brand-logo.svg'
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react'

import {
  Activity,
  ArrowLeft,
  ArrowUp,
  BookOpen,
  BrainCircuit,
  Check,
  ChevronDown,
  ClipboardCheck,
  Cpu,
  Database,
  Download,
  FlaskConical,
  Languages,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  MessageSquareText,
  Play,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  UserRound,
  Wifi,
  X,
} from 'lucide-react'

import type { LucideIcon } from 'lucide-react'

import {
  getInitialLanguage,
  getTranslationCatalog,
  persistLanguage,
  type Language,
  type Translation,
} from './i18n'
import { therapyModules, plannedTherapyCategories } from './data/therapyModules'
import { SessionsPage } from './features/sessions/SessionsPage'
import { SupportExport } from './features/settings/SupportExport'
import { AuthPage } from './features/auth/AuthPage'
import {
  getAuthStatus,
  getCurrentUser,
  initializeLocalAccount,
  loginLocalAccount,
  logoutLocalAccount,
  type AuthenticatedUser,
} from './features/auth/api'
import {
  clearAuthToken,
  getAuthToken,
  setAuthToken,
} from './lib/authSession'

import {
  getHealth,
  getHardwareAssessment,
  getModels,
  getProviders,
  getUpdateMetadata,
  getProviderSettings,
  saveProviderSettings,
  sendChat,
  testProviderConnection,
} from './lib/api'
import {
  buildApiBaseUrl,
  parseApiBaseUrl,
} from './lib/providerSettings'
import { verifySha256File } from './lib/downloadTools'

import type {
  ChatMessage,
  ConnectionState,
  HardwareAssessment,
  ModelInfo,
  ProviderCatalog,
  ProviderInfo,
  ProviderEndpointSettings,
  ProviderSettingsResponse,
  ProviderName,
  UpdateMetadataResponse,
  TherapyModule,
  ViewKey,
} from './types'

import './App.css'

type TranslationKey = keyof Translation

interface NavigationItem {
  id: ViewKey
  label: TranslationKey
  icon: LucideIcon
}

const providerNames: ProviderName[] = [
  'ollama',
  'lm_studio',
  'llama_cpp',
  'custom',
]

const providerLabelKeys: Record<ProviderName, TranslationKey> = {
  ollama: 'providerOllama',
  lm_studio: 'providerLmStudio',
  llama_cpp: 'providerLlamaCpp',
  custom: 'providerCustom',
}

const pageTitleKeys: Record<ViewKey, TranslationKey> = {
  dashboard: 'dashboard',
  studio: 'studio',
  therapies: 'therapies',
  sessions: 'sessions',
  scenarios: 'scenarios',
  evaluation: 'evaluation',
  settings: 'settings',
}

const navigationGroups: Array<{
  title: TranslationKey
  items: NavigationItem[]
}> = [
  {
    title: 'workspace',
    items: [
      { id: 'dashboard', label: 'dashboard', icon: LayoutDashboard },
      { id: 'studio', label: 'studio', icon: MessageSquareText },
    ],
  },
  {
    title: 'clinical',
    items: [
      { id: 'therapies', label: 'therapies', icon: BookOpen },
      { id: 'sessions', label: 'sessions', icon: BrainCircuit },
      { id: 'scenarios', label: 'scenarios', icon: Database },
      { id: 'evaluation', label: 'evaluation', icon: ClipboardCheck },
    ],
  },
  {
    title: 'system',
    items: [
      { id: 'settings', label: 'settings', icon: Settings2 },
    ],
  },
]

interface BenchmarkResult {
  provider: ProviderName
  model: string
  status: 'passed' | 'language_mismatch' | 'failed'
  elapsedSeconds: number
  answerLength: number
  hasPersian: boolean
  preview: string
  error?: string
}

interface BenchmarkState {
  running: boolean
  completed: number
  total: number
  results: BenchmarkResult[]
}

const initialBenchmark: BenchmarkState = {
  running: false,
  completed: 0,
  total: 0,
  results: [],
}

const benchmarkPrompt =
  'به زبان فارسی و در حداکثر ۸۰ کلمه توضیح دهید پذیرش (Acceptance) در درمان مبتنی بر پذیرش و تعهد (ACT) چه تفاوتی با تسلیم‌شدن دارد. یک مثال روزمره و غیرتشخیصی بیاورید. پاسخ را در دو بخش «تعریف» و «مثال» تنظیم کنید.'

function errorMessage(
  error: unknown,
  fallback: string,
  language: Language,
): string {
  if (language === 'fa') return fallback
  return error instanceof Error ? error.message : fallback
}

function statusText(
  status: ConnectionState,
  t: Translation,
) {
  if (status === 'online') return t.connected
  if (status === 'offline') return t.disconnected
  return t.checking
}

function StatusDot({ status }: { status: ConnectionState }) {
  return (
    <span
      className={`status-dot status-${status}`}
      aria-label={status}
    />
  )
}

function formatHardwareBytes(
  bytes: number | null,
  unavailable = 'Unavailable',
): string {
  if (bytes === null || !Number.isFinite(bytes) || bytes < 0) {
    return unavailable
  }
  return `${(bytes / (1024 ** 3)).toFixed(1)} GiB`
}

function App() {
  const [language, setLanguage] = useState<Language>(getInitialLanguage)
  const t = getTranslationCatalog(language)
  const direction = language === 'fa' ? 'rtl' : 'ltr'
  const [authMode, setAuthMode] = useState<
    'checking' | 'initialize' | 'login' | 'authenticated' | 'unavailable'
  >('checking')
  const [authError, setAuthError] = useState('')
  const [authRetryKey, setAuthRetryKey] = useState(0)
  const [authenticatedUser, setAuthenticatedUser] =
    useState<AuthenticatedUser | null>(null)

  const [view, setView] = useState<ViewKey>('dashboard')
  const [backendStatus, setBackendStatus] =
    useState<ConnectionState>('checking')
  const [appVersion, setAppVersion] = useState('')

  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [provider, setProvider] = useState<ProviderName>('ollama')

  const [modelsByProvider, setModelsByProvider] =
    useState<Record<ProviderName, ModelInfo[]>>({
      ollama: [],
      lm_studio: [],
      llama_cpp: [],
      custom: [],
    })

  const [providerStates, setProviderStates] =
    useState<Record<ProviderName, ConnectionState>>({
      ollama: 'checking',
      lm_studio: 'checking',
      llama_cpp: 'checking',
      custom: 'checking',
    })

  const [selectedModel, setSelectedModel] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [chatError, setChatError] = useState('')
  const [startupError, setStartupError] = useState('')

  const [benchmark, setBenchmark] =
    useState<BenchmarkState>(initialBenchmark)
  const [hardwareAssessment, setHardwareAssessment] =
    useState<HardwareAssessment | null>(null)
  const [hardwareAssessmentLoading, setHardwareAssessmentLoading] =
    useState(false)
  const [hardwareAssessmentFailed, setHardwareAssessmentFailed] =
    useState(false)

  const currentModels = modelsByProvider[provider]
  const currentProviderState = providerStates[provider]

  useEffect(() => {
    document.documentElement.lang = language
    document.documentElement.dir = direction

    persistLanguage(language)
  }, [language, direction])

  useEffect(() => {
    let active = true

    async function checkAuthentication() {
      try {
        const status = await getAuthStatus()
        if (!active) return

        if (!status.data.initialized) {
          clearAuthToken()
          setAuthMode('initialize')
          return
        }

        const token = getAuthToken()
        if (!token) {
          setAuthMode('login')
          return
        }

        try {
          const currentUser = await getCurrentUser()
          if (!active) return
          setAuthenticatedUser(currentUser.data)
          setAuthMode('authenticated')
        } catch (requestError) {
          if (!active) return
          if (
            requestError instanceof Error &&
            requestError.message === 'authentication_required'
          ) {
            clearAuthToken()
            setAuthMode('login')
          } else {
            setAuthError(
              errorMessage(requestError, t.noStartupConnection, language),
            )
            setAuthMode('unavailable')
          }
        }
      } catch (requestError) {
        if (!active) return
        setAuthError(errorMessage(requestError, t.noStartupConnection, language))
        setAuthMode('unavailable')
      }
    }

    void checkAuthentication()

    return () => {
      active = false
    }
  }, [authRetryKey, language, t.noStartupConnection])

  useEffect(() => {
    function handleAuthExpired() {
      setAuthenticatedUser(null)
      setAuthError(
        language === 'fa'
          ? 'نشست ورود منقضی شد؛ دوباره وارد شو.'
          : 'Your sign-in session expired. Please sign in again.',
      )
      setAuthMode('login')
    }

    window.addEventListener('therasim:auth-expired', handleAuthExpired)
    return () =>
      window.removeEventListener('therasim:auth-expired', handleAuthExpired)
  }, [language])

  // Load backend and both local providers once at startup.
  useEffect(() => {
    if (authMode !== 'authenticated') return
    let active = true

    async function initialize() {
      const [healthResult, catalogResult] = await Promise.allSettled([
        getHealth(),
        getProviders(),
      ])

      if (!active) return

      if (healthResult.status === 'fulfilled') {
        setAppVersion(healthResult.value.version)
        setBackendStatus(
          healthResult.value.status === 'ok' ? 'online' : 'offline',
        )
      } else {
        setBackendStatus('offline')
      }

      if (catalogResult.status === 'rejected') {
        setStartupError(t.noStartupConnection)
        return
      }

      const catalog: ProviderCatalog = catalogResult.value

      setProviders(catalog.providers)
      setProvider(catalog.active_provider)
      setStartupError('')

      const checks = await Promise.all(
        catalog.providers.map(async (item) => {
          try {
            const result = await getModels(item.name)

            return {
              name: item.name,
              models: result.models,
              status: 'online' as const,
            }
          } catch {
            return {
              name: item.name,
              models: [],
              status: 'offline' as const,
            }
          }
        }),
      )

      if (!active) return

      const nextModels: Record<ProviderName, ModelInfo[]> = {
        ollama: [],
        lm_studio: [],
        llama_cpp: [],
        custom: [],
      }

      const nextStates: Record<ProviderName, ConnectionState> = {
        ollama: 'offline',
        lm_studio: 'offline',
        llama_cpp: 'offline',
        custom: 'offline',
      }

      for (const result of checks) {
        nextModels[result.name] = result.models
        nextStates[result.name] = result.status
      }

      setModelsByProvider(nextModels)
      setProviderStates(nextStates)

      const preferred = catalog.providers.find(
        (item) => item.name === catalog.active_provider,
      )?.default_model

      setSelectedModel(
        nextModels[catalog.active_provider].find(
          (item) => item.id === preferred,
        )?.id ?? preferred ?? nextModels[catalog.active_provider][0]?.id ?? '',
      )
    }

    void initialize()

    return () => {
      active = false
    }
  }, [authMode, t.noStartupConnection])

  async function handleAuthenticate(
    reviewerName: string,
    password: string,
  ) {
    setAuthError('')
    try {
      const response = authMode === 'initialize'
        ? await initializeLocalAccount(reviewerName, password)
        : await loginLocalAccount(password)
      setAuthToken(response.data.access_token)
      setAuthenticatedUser(response.data.user)
      setAuthMode('authenticated')
    } catch (requestError) {
      const message = errorMessage(requestError, t.noStartupConnection, language)
      setAuthError(
        message === 'invalid_credentials'
          ? (language === 'fa'
            ? 'گذرواژه نامعتبر است.'
            : 'The password is incorrect.')
          : message,
      )
    }
  }

  function retryAuthentication() {
    setAuthError('')
    setAuthMode('checking')
    setAuthRetryKey((current) => current + 1)
  }

  async function handleLogout() {
    try {
      await logoutLocalAccount()
    } catch (requestError) {
      setAuthError(errorMessage(requestError, t.noStartupConnection, language))
    } finally {
      clearAuthToken()
      setAuthenticatedUser(null)
      setAuthMode('login')
    }
  }

  function changeProvider(nextProvider: ProviderName) {
    setProvider(nextProvider)
    setSelectedModel(
      providers.find((item) => item.name === nextProvider)?.default_model ??
        modelsByProvider[nextProvider][0]?.id ??
        '',
    )
    setChatError('')
  }

  async function refreshModels() {
    setRefreshing(true)

    setProviderStates((current) => ({
      ...current,
      [provider]: 'checking',
    }))

    try {
      const result = await getModels(provider)

      setModelsByProvider((current) => ({
        ...current,
        [provider]: result.models,
      }))

      setProviderStates((current) => ({
        ...current,
        [provider]: 'online',
      }))

      setSelectedModel((current) =>
        result.models.some((model) => model.id === current)
          ? current
          : result.models[0]?.id ?? '',
      )
    } catch {
      setProviderStates((current) => ({
        ...current,
        [provider]: 'offline',
      }))
    } finally {
      setRefreshing(false)
    }
  }

  async function loadHardwareAssessment() {
    setHardwareAssessmentLoading(true)
    setHardwareAssessmentFailed(false)
    try {
      setHardwareAssessment(await getHardwareAssessment())
    } catch {
      setHardwareAssessmentFailed(true)
    } finally {
      setHardwareAssessmentLoading(false)
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const text = draft.trim()

    if (
      !text ||
      !selectedModel ||
      backendStatus !== 'online' ||
      sending
    ) {
      return
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
    }

    const conversation = [...messages, userMessage]

    setMessages(conversation)
    setDraft('')
    setChatError('')
    setSending(true)

    try {
      const response = await sendChat(
        provider,
        selectedModel,
        conversation.map(({ role, content }) => ({
          role,
          content,
        })),
      )

      if (!response.message?.content?.trim()) {
        throw new Error(t.emptyAnswer)
      }

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.message.content,
        },
      ])
    } catch (error) {
      setChatError(
        error instanceof Error ? error.message : t.providerError,
      )
    } finally {
      setSending(false)
    }
  }

  function handleComposerKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (
      event.key === 'Enter' &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  function clearConversation() {
    setMessages([])
    setDraft('')
    setChatError('')
  }

  async function runModelBenchmark() {
    const targets = providerNames
      .flatMap((name) =>
        modelsByProvider[name]
          .filter((model) => !/(embedding|embed)/i.test(model.id))
          .map((model) => ({
            provider: name,
            model: model.id,
          })),
      )
      .sort((a, b) => {
        const aHeavy = /(?:27|30|32)b/i.test(a.model) ? 1 : 0
        const bHeavy = /(?:27|30|32)b/i.test(b.model) ? 1 : 0
        return aHeavy - bHeavy
      })

    setBenchmark({
      running: true,
      completed: 0,
      total: targets.length,
      results: [],
    })

    if (targets.length === 0) {
      setBenchmark({
        running: false,
        completed: 0,
        total: 0,
        results: [],
      })
      return
    }

    const results: BenchmarkResult[] = []

    // Sequential execution avoids running several local models at once.
    for (let index = 0; index < targets.length; index += 1) {
      const target = targets[index]
      const startedAt = performance.now()

      let result: BenchmarkResult

      try {
        const response = await sendChat(
          target.provider,
          target.model,
          [{ role: 'user', content: benchmarkPrompt }],
          {
            temperature: 0.2,
            maxTokens: 256,
          },
        )

        const answer = response.message.content.trim()
        const hasPersian = /[\u0600-\u06FF]/.test(answer)

        result = {
          provider: target.provider,
          model: target.model,
          status: !answer
            ? 'failed'
            : hasPersian
              ? 'passed'
              : 'language_mismatch',
          elapsedSeconds: (performance.now() - startedAt) / 1000,
          answerLength: answer.length,
          hasPersian,
          preview: answer.slice(0, 180),
        }
      } catch (error) {
        result = {
          provider: target.provider,
          model: target.model,
          status: 'failed',
          elapsedSeconds: (performance.now() - startedAt) / 1000,
          answerLength: 0,
          hasPersian: false,
          preview: '',
          error: error instanceof Error
            ? error.message.slice(0, 220)
            : 'Unknown provider error',
        }
      }

      results.push(result)

      setBenchmark({
        running: true,
        completed: index + 1,
        total: targets.length,
        results: [...results],
      })
    }

    setBenchmark({
      running: false,
      completed: targets.length,
      total: targets.length,
      results,
    })
  }

  function exportBenchmark() {
    const report = {
      project: 'TheraSim',
      test_type: 'technical_model_smoke_test',
      generated_at: new Date().toISOString(),
      prompt: benchmarkPrompt,
      note: 'Technical smoke test only. Not a clinical validity or therapeutic quality assessment.',
      results: benchmark.results,
    }

    const blob = new Blob(
      [JSON.stringify(report, null, 2)],
      { type: 'application/json;charset=utf-8' },
    )

    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = `therasim-model-test-${Date.now()}.json`
    link.click()

    URL.revokeObjectURL(url)
  }

  const availableModelCount = providerNames.reduce(
    (total, name) =>
      total + modelsByProvider[name].filter(
        (model) => !/(embedding|embed)/i.test(model.id),
      ).length,
    0,
  )

  const connectedProviderCount = providerNames.filter(
    (name) => providerStates[name] === 'online',
  ).length

  const pageTitle = t[pageTitleKeys[view]]

  if (authMode !== 'authenticated') {
    return (
      <AuthPage
        language={language}
        mode={authMode}
        error={authError}
        onAuthenticate={handleAuthenticate}
        onRetry={retryAuthentication}
        onToggleLanguage={() =>
          setLanguage((current) => current === 'fa' ? 'en' : 'fa')
        }
      />
    )
  }

  return (
    <div className="app-shell" dir={direction}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <img
              src={brandLogo}
              alt="TheraSim"
              className="brand-logo-image"
            />
          </div>
          <div className="brand-text">
            <strong>TheraSim</strong>
            <span>{t.appSubtitle}</span>
          </div>
        </div>

        <div className="sidebar-rule" />

        <div className="sidebar-navigation">
          {navigationGroups.map((group) => (
            <div className="nav-group" key={group.title}>
              <div className="nav-caption">{t[group.title]}</div>

              <nav className="navigation">
                {group.items.map((item) => {
                  const Icon = item.icon
                  const active = view === item.id

                  return (
                    <button
                      type="button"
                      key={item.id}
                      className={`nav-item ${active ? 'active' : ''}`}
                      onClick={() => setView(item.id)}
                      aria-current={active ? 'page' : undefined}
                    >
                      <Icon size={18} strokeWidth={1.8} />
                      <span>{t[item.label]}</span>
                      {active && <span className="nav-indicator" />}
                    </button>
                  )
                })}
              </nav>
            </div>
          ))}
        </div>

        <div className="sidebar-bottom">
          <div className="privacy-card">
            <ShieldCheck size={19} />
            <div>
              <strong>{t.localPrivacy}</strong>
              <p>{t.localPrivacyDescription}</p>
            </div>
          </div>

          <div className="sidebar-version">
            <span className="version-indicator" />
            TheraSim · 0.2.1
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb">
            <span>TheraSim</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{pageTitle}</strong>
          </div>

          <div className="topbar-tools">
            {authenticatedUser && (
              <>
                <span className="auth-reviewer-name">
                  {authenticatedUser.reviewer_name}
                </span>
                <button
                  type="button"
                  className="language-switch"
                  onClick={() => void handleLogout()}
                  aria-label={language === 'fa' ? 'خروج' : 'Sign out'}
                >
                  <LogOut size={17} />
                  <span>{language === 'fa' ? 'خروج' : 'Sign out'}</span>
                </button>
                <div className="topbar-separator" />
              </>
            )}
            <div className={`backend-chip ${backendStatus}`}>
              <StatusDot status={backendStatus} />
              {backendStatus === 'online'
                ? t.backendOnline
                : backendStatus === 'checking'
                  ? t.backendChecking
                  : t.backendOffline}
            </div>

            <div className="topbar-separator" />

            <button
              type="button"
              className="language-switch"
              onClick={() =>
                setLanguage((current) => current === 'en' ? 'fa' : 'en')
              }
              title={t.switchLanguage}
              aria-label={t.switchLanguage}
            >
              <Languages size={17} />
              <span>{t.switchLanguage}</span>
            </button>
          </div>
        </header>

        <main className="page-content">
          {view === 'dashboard' && (
            <Dashboard
              t={t}
              backendStatus={backendStatus}
              connectedProviderCount={connectedProviderCount}
              availableModelCount={availableModelCount}
              providerStates={providerStates}
              providers={providers}
              onOpenStudio={() => setView('studio')}
              onOpenTherapies={() => setView('therapies')}
              onOpenSettings={() => setView('settings')}
            />
          )}

          {view === 'studio' && (
            <Studio
              t={t}
              providers={providers}
              provider={provider}
              onProviderChange={(value) => changeProvider(value)}
              models={currentModels}
              selectedModel={selectedModel}
              onModelChange={setSelectedModel}
              providerState={currentProviderState}
              backendStatus={backendStatus}
              refreshing={refreshing}
              onRefresh={refreshModels}
              messages={messages}
              draft={draft}
              onDraftChange={setDraft}
              onSend={sendMessage}
              onComposerKeyDown={handleComposerKeyDown}
              sending={sending}
              error={chatError}
              onDismissError={() => setChatError('')}
              onClear={clearConversation}
              benchmark={benchmark}
              onRunBenchmark={runModelBenchmark}
              onExportBenchmark={exportBenchmark}
              hardwareAssessment={hardwareAssessment}
              hardwareAssessmentLoading={hardwareAssessmentLoading}
              hardwareAssessmentFailed={hardwareAssessmentFailed}
              onAssessHardware={loadHardwareAssessment}
            />
          )}

          {view === 'therapies' && (
            <TherapiesPage
              t={t}
              modules={therapyModules}
              onOpenStudio={() => setView('studio')}
            />
          )}

          {view === 'sessions' && (
            <SessionsPage language={language} />
          )}

          {view === 'scenarios' && (
            <ComingSoonPage
              t={t}
              icon={Database}
              title={t.scenarios}
            />
          )}

          {view === 'evaluation' && (
            <ComingSoonPage
              t={t}
              icon={ClipboardCheck}
              title={t.evaluation}
            />
          )}

          {view === 'settings' && (
            <SettingsPage
              t={t}
              language={language}
              appVersion={appVersion}
              backendStatus={backendStatus}
              startupError={startupError}
              onProviderSaved={(saved) => {
                setProvider(saved.active_provider)
                const active = saved.providers.find(
                  (item) => item.name === saved.active_provider,
                )
                setSelectedModel(active?.model ?? '')
                void getProviders()
                  .then((catalog) => setProviders(catalog.providers))
                  .catch(() => setStartupError(t.noStartupConnection))
              }}
            />
          )}
        </main>

        <footer className="app-footer">
          <span>{`TheraSim · ${t.localFirstFramework}`}</span>
          <span>
            <ShieldCheck size={14} />
            {t.localPrivacy}
          </span>
        </footer>
      </div>
    </div>
  )
}

/* ---------------- Dashboard ---------------- */

function Dashboard({
  t,
  backendStatus,
  connectedProviderCount,
  availableModelCount,
  providerStates,
  providers,
  onOpenStudio,
  onOpenTherapies,
  onOpenSettings,
}: {
  t: Translation
  backendStatus: ConnectionState
  connectedProviderCount: number
  availableModelCount: number
  providerStates: Record<ProviderName, ConnectionState>
  providers: ProviderInfo[]
  onOpenStudio: () => void
  onOpenTherapies: () => void
  onOpenSettings: () => void
}) {
  return (
    <section className="dashboard-view">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <Sparkles size={15} />
            {t.appEyebrow}
          </div>
          <h1>{t.dashboardTitle}</h1>
          <p>{t.dashboardDescription}</p>
        </div>

        <button
          type="button"
          className="primary-button"
          onClick={onOpenStudio}
        >
          <MessageSquareText size={17} />
          {t.startTesting}
          <ArrowLeft size={16} />
        </button>
      </div>

      <section className="hero-panel">
        <div className="hero-copy">
          <div className="hero-overline">
            <span />
            {t.heroEyebrow}
          </div>

          <h2>
            {t.heroTitle}
            <br />
            {t.heroTitleSecond}
          </h2>

          <p>{t.heroDescription}</p>

          <button
            type="button"
            className="hero-button"
            onClick={onOpenTherapies}
          >
            {t.exploreTherapies}
            <ArrowLeft size={16} />
          </button>
        </div>

        <div className="hero-art" aria-hidden="true">
          <div className="hero-circle circle-outer" />
          <div className="hero-circle circle-inner" />
          <div className="hero-core">
            <BrainCircuit size={58} strokeWidth={1.3} />
          </div>
          <span className="hero-node hero-node-one">
            <Cpu size={17} />
          </span>
          <span className="hero-node hero-node-two">
            <Database size={17} />
          </span>
          <span className="hero-node hero-node-three">
            <Activity size={17} />
          </span>
        </div>
      </section>

      <div className="section-heading">
        <div>
          <h2>{t.systemOverview}</h2>
          <p>{t.currentStatus}</p>
        </div>
      </div>

      <div className="metrics-grid">
        <MetricCard
          icon={Activity}
          label={t.metricBackendLabel}
          value={
            backendStatus === 'online'
              ? t.connected
              : backendStatus === 'checking'
                ? t.checking
                : t.disconnected
          }
          description={t.backendDescription}
          status={backendStatus}
          t={t}
        />

        <MetricCard
          icon={Cpu}
          label={t.metricProvidersLabel}
          value={`${connectedProviderCount} / ${providers.length || providerNames.length}`}
          valueDirection="ltr"
          description={t.providerDescription}
          t={t}
        />

        <MetricCard
          icon={Database}
          label={t.metricChatModelsLabel}
          value={String(availableModelCount)}
          description={t.modelsDescription}
          t={t}
        />
      </div>

      <div className="dashboard-columns">
        <section className="surface-card">
          <div className="card-heading">
            <span className="heading-icon">
              <Cpu size={19} />
            </span>
            <div>
              <h3>{t.providerHeading}</h3>
              <p>{t.providerSubheading}</p>
            </div>
            <button
              type="button"
              className="heading-link"
              onClick={onOpenSettings}
            >
              {t.details}
              <ArrowLeft size={14} />
            </button>
          </div>

          {providerNames.map((name) => (
            <div className="provider-row" key={name}>
              <span className="provider-symbol">
                {name === 'ollama' ? <Cpu size={19} /> : <Wifi size={19} />}
              </span>
              <div className="provider-copy">
                <strong>{t[providerLabelKeys[name]]}</strong>
                <span dir="ltr">
                  {providers.find((item) => item.name === name)?.base_url
                    ?? (name === 'ollama'
                      ? 'http://127.0.0.1:11434/v1'
                      : 'http://127.0.0.1:1234/v1')}
                </span>
              </div>
              <span className={`connection-label ${providerStates[name]}`}>
                <StatusDot status={providerStates[name]} />
                {statusText(providerStates[name], t)}
              </span>
            </div>
          ))}
        </section>

        <section className="surface-card">
          <div className="card-heading">
            <span className="heading-icon">
              <Sparkles size={19} />
            </span>
            <div>
              <h3>{t.workflowHeading}</h3>
              <p>{t.workflowSubheading}</p>
            </div>
          </div>

          <button
            type="button"
            className="action-row"
            onClick={onOpenStudio}
          >
            <span className="action-icon">
              <MessageSquareText size={18} />
            </span>
            <span className="action-copy">
              <strong>{t.modelTestAction}</strong>
              <small>{t.modelTestDescription}</small>
            </span>
            <ArrowLeft size={16} />
          </button>

          <button
            type="button"
            className="action-row"
            onClick={onOpenTherapies}
          >
            <span className="action-icon">
              <BookOpen size={18} />
            </span>
            <span className="action-copy">
              <strong>{t.therapyAction}</strong>
              <small>{t.therapyActionDescription}</small>
            </span>
            <ArrowLeft size={16} />
          </button>

          <div className="action-row muted-action">
            <span className="action-icon">
              <ClipboardCheck size={18} />
            </span>
            <span className="action-copy">
              <strong>{t.evaluationAction}</strong>
              <small>{t.inDevelopment}</small>
            </span>
            <span className="future-label">{t.future}</span>
          </div>
        </section>
      </div>
    </section>
  )
}

function MetricCard({
  icon: Icon,
  label,
  value,
  description,
  status,
  valueDirection,
  t,
}: {
  icon: LucideIcon
  label: string
  value: string
  description: string
  status?: ConnectionState
  valueDirection?: 'ltr'
  t: Translation
}) {
  return (
    <article className="metric-card">
      <div className="metric-top">
        <span className="metric-icon">
          <Icon size={20} />
        </span>
        <span className="metric-tag">{label}</span>
      </div>

      <div className="metric-value" dir={valueDirection}>{value}</div>
      <div className="metric-description">{description}</div>

      {status && (
        <div className="metric-foot">
          <StatusDot status={status} />
          {statusText(status, t)}
        </div>
      )}
    </article>
  )
}

/* ---------------- Model laboratory ---------------- */

function Studio({
  t,
  providers,
  provider,
  onProviderChange,
  models,
  selectedModel,
  onModelChange,
  providerState,
  backendStatus,
  refreshing,
  onRefresh,
  messages,
  draft,
  onDraftChange,
  onSend,
  onComposerKeyDown,
  sending,
  error,
  onDismissError,
  onClear,
  benchmark,
  onRunBenchmark,
  onExportBenchmark,
  hardwareAssessment,
  hardwareAssessmentLoading,
  hardwareAssessmentFailed,
  onAssessHardware,
}: {
  t: Translation
  providers: ProviderInfo[]
  provider: ProviderName
  onProviderChange: (value: ProviderName) => void
  models: ModelInfo[]
  selectedModel: string
  onModelChange: (value: string) => void
  providerState: ConnectionState
  backendStatus: ConnectionState
  refreshing: boolean
  onRefresh: () => void
  messages: ChatMessage[]
  draft: string
  onDraftChange: (value: string) => void
  onSend: (event: FormEvent<HTMLFormElement>) => void
  onComposerKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  sending: boolean
  error: string
  onDismissError: () => void
  onClear: () => void
  benchmark: BenchmarkState
  onRunBenchmark: () => void
  onExportBenchmark: () => void
  hardwareAssessment: HardwareAssessment | null
  hardwareAssessmentLoading: boolean
  hardwareAssessmentFailed: boolean
  onAssessHardware: () => void
}) {
  const messageEndRef = useRef<HTMLDivElement>(null)

  const chatModels = models.filter(
    (model) => !/(embedding|embed)/i.test(model.id),
  )

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [messages, sending])

  const statusDescription =
    providerState === 'checking'
      ? t.loadingModels
      : providerState === 'offline'
        ? t.providerError
        : chatModels.length === 0
          ? t.providerNoModels
          : `${chatModels.length} ${t.modelsFound}`

  const benchmarkPassed = benchmark.results.filter(
    (result) => result.status === 'passed',
  ).length

  return (
    <section className="studio-view">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <FlaskConical size={15} />
            {t.localModelWorkspace}
          </div>
          <h1>{t.studioTitle}</h1>
          <p>{t.studioDescription}</p>
        </div>

        <button
          type="button"
          className="secondary-button"
          onClick={onClear}
        >
          <X size={16} />
          {t.newChat}
        </button>
      </div>

      <section className="surface-card model-settings">
        <div className="card-heading">
          <span className="heading-icon">
            <Settings2 size={19} />
          </span>
          <div>
            <h3>{t.executionSettings}</h3>
            <p>{t.executionSettingsDescription}</p>
          </div>
          <span className="local-pill">
            <ShieldCheck size={14} />
            {t.localInference}
          </span>
        </div>

        <div className="model-fields">
          <label className="field">
            <span>{t.provider}</span>
            <div className="select-box">
              <select
                value={provider}
                onChange={(event) =>
                  onProviderChange(event.target.value as ProviderName)
                }
                disabled={providers.length === 0}
              >
                {providers.map((item) => (
                  <option key={item.name} value={item.name}>
                    {t[providerLabelKeys[item.name]]}
                  </option>
                ))}
              </select>
              <ChevronDown size={16} />
            </div>
          </label>

          <label className="field model-select">
            <span>{t.model}</span>
            <div className="select-box">
              <select
                value={selectedModel}
                onChange={(event) => onModelChange(event.target.value)}
                disabled={chatModels.length === 0 && !selectedModel}
              >
                {chatModels.length === 0 && !selectedModel && (
                  <option value="">{t.noModels}</option>
                )}
                {selectedModel && !chatModels.some(
                  (item) => item.id === selectedModel,
                ) && (
                  <option value={selectedModel}>{selectedModel}</option>
                )}
                {chatModels.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id}
                  </option>
                ))}
              </select>
              <ChevronDown size={16} />
            </div>
          </label>

          <button
            type="button"
            className="refresh-button"
            onClick={onRefresh}
            disabled={refreshing || !provider}
            title={t.refresh}
            aria-label={t.refresh}
          >
            <RefreshCw className={refreshing ? 'spin' : ''} size={17} />
          </button>
        </div>

        <div className="model-status-line">
          <div className={`connection-label ${providerState}`}>
            <StatusDot status={providerState} />
            {statusDescription}
          </div>
          <span className="selected-model-name">
            {selectedModel || t.selectModel}
          </span>
        </div>
      </section>

      <section className="surface-card hardware-assessment">
        <div className="benchmark-heading">
          <div className="card-heading">
            <span className="heading-icon">
              <Cpu size={19} />
            </span>
            <div>
              <h3>{t.hardwareAssessmentTitle}</h3>
              <p>{t.hardwareAssessmentDescription}</p>
            </div>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={onAssessHardware}
            disabled={hardwareAssessmentLoading || backendStatus !== 'online'}
          >
            {hardwareAssessmentLoading
              ? t.hardwareAssessmentLoading
              : t.hardwareAssessmentButton}
          </button>
        </div>

        {hardwareAssessmentFailed && (
          <div className="hardware-error" role="alert">
            {t.hardwareAssessmentFailed}
          </div>
        )}

        {hardwareAssessment && (
          <dl className="hardware-facts">
            <div>
              <dt>{t.hardwareOperatingSystem}</dt>
              <dd>
                {hardwareAssessment.operating_system.name}{' '}
                {hardwareAssessment.operating_system.version} (
                {hardwareAssessment.operating_system.architecture})
              </dd>
            </div>
            <div>
              <dt>{t.hardwareCpu}</dt>
              <dd>
                {hardwareAssessment.cpu.name || t.hardwareUnavailable}
                {hardwareAssessment.cpu.logical_processors !== null &&
                  ` · ${hardwareAssessment.cpu.logical_processors} ${t.hardwareLogicalProcessors}`}
              </dd>
            </div>
            <div>
              <dt>{t.hardwareMemory}</dt>
              <dd>
                {formatHardwareBytes(
                  hardwareAssessment.memory.total_bytes,
                  t.hardwareUnavailable,
                )}{' '}
                ({t.hardwareAvailable}:{' '}
                {formatHardwareBytes(
                  hardwareAssessment.memory.available_bytes,
                  t.hardwareUnavailable,
                )})
              </dd>
            </div>
            <div>
              <dt>{t.hardwareGpu}</dt>
              <dd>
                {hardwareAssessment.gpus.length > 0
                  ? hardwareAssessment.gpus
                    .map((gpu) =>
                      `${gpu.name} (${formatHardwareBytes(gpu.total_vram_bytes, t.hardwareUnavailable)}; ${t.hardwareAvailable}: ${formatHardwareBytes(gpu.available_vram_bytes, t.hardwareUnavailable)})`,
                    )
                    .join(', ')
                  : t.hardwareGpuUnknown}
              </dd>
            </div>
            <div>
              <dt>{t.hardwareDisk}</dt>
              <dd>
                {formatHardwareBytes(
                  hardwareAssessment.disk.free_bytes,
                  t.hardwareUnavailable,
                )}{' '}
                {t.hardwareFreeOf}{' '}
                {formatHardwareBytes(
                  hardwareAssessment.disk.total_bytes,
                  t.hardwareUnavailable,
                )}
              </dd>
            </div>
            <div>
              <dt>{t.hardwareOllama}</dt>
              <dd>
                {hardwareAssessment.ollama.server_available === true
                  ? `${t.connected}${hardwareAssessment.ollama.server_version
                    ? ` · ${hardwareAssessment.ollama.server_version}`
                    : ''}`
                  : hardwareAssessment.ollama.server_available === false
                    ? t.unavailable
                    : t.hardwareUnavailable}
              </dd>
            </div>
          </dl>
        )}

        <p className="hardware-guidance">{t.hardwareModelGuidance}</p>
      </section>

      <section className="surface-card chat-panel">
        <div className="chat-header">
          <div className="chat-heading">
            <span className="chat-avatar">
              <BrainCircuit size={20} />
            </span>
            <div>
              <h3>{t.chatTitle}</h3>
              <p>{selectedModel || t[providerLabelKeys[provider]]}</p>
            </div>
          </div>
          <span className="request-mode">{t.chatMode}</span>
        </div>

        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="empty-symbol">
                <MessageSquareText size={31} />
              </div>
              <h3>{t.chatWelcome}</h3>
              <p>{t.chatWelcomeDescription}</p>

              <div className="suggestion-list">
                {[t.suggestionOne, t.suggestionTwo, t.suggestionThree].map(
                  (suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => onDraftChange(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ),
                )}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <div
              className={`message-row ${message.role}`}
              key={message.id}
            >
              <div className="message-avatar">
                {message.role === 'assistant' ? (
                  <BrainCircuit size={17} />
                ) : (
                  <UserRound size={17} />
                )}
              </div>

              <div className="message-bubble">
                <div className="message-author">
                  {message.role === 'assistant' ? t.assistantLabel : t.userLabel}
                </div>
                <div className="message-content" dir="auto">
                  {message.content}
                </div>
              </div>
            </div>
          ))}

          {sending && (
            <div className="message-row assistant">
              <div className="message-avatar">
                <BrainCircuit size={17} />
              </div>
              <div className="message-bubble loading-message">
                <LoaderCircle size={17} className="spin" />
                {t.sending}
              </div>
            </div>
          )}

          <div ref={messageEndRef} />
        </div>

        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button
              type="button"
              onClick={onDismissError}
              title={t.clearError}
              aria-label={t.clearError}
            >
              <X size={15} />
            </button>
          </div>
        )}

        {backendStatus !== 'online' && (
          <div className="warning-banner">
            {t.backendRequired}
          </div>
        )}

        <form className="composer" onSubmit={onSend}>
          <textarea
            rows={2}
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={onComposerKeyDown}
            placeholder={t.composerPlaceholder}
            dir="auto"
            disabled={
              !selectedModel ||
              sending ||
              backendStatus !== 'online'
            }
          />

          <div className="composer-bottom">
            <span>{t.enterHint}</span>
            <button
              className="send-button"
              type="submit"
              disabled={
                !draft.trim() ||
                !selectedModel ||
                sending ||
                backendStatus !== 'online'
              }
              aria-label={t.send}
              title={t.send}
            >
              {sending ? (
                <LoaderCircle className="spin" size={18} />
              ) : (
                <ArrowUp size={19} />
              )}
            </button>
          </div>
        </form>
      </section>

      <section className="surface-card benchmark-panel">
        <div className="benchmark-heading">
          <div className="card-heading">
            <span className="heading-icon">
              <Activity size={19} />
            </span>
            <div>
              <h3>{t.benchmarkTitle}</h3>
              <p>{t.benchmarkDescription}</p>
            </div>
          </div>

          <button
            type="button"
            className="primary-button benchmark-button"
            onClick={onRunBenchmark}
            disabled={benchmark.running}
          >
            {benchmark.running ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Play size={16} />
            )}
            {benchmark.running ? t.benchmarkRunning : t.benchmarkRun}
          </button>
        </div>

        <div className="benchmark-note">
          <ShieldCheck size={15} />
          {t.benchmarkSequential}
        </div>

        <div className="benchmark-prompt">
          <strong>{t.benchmarkPrompt}</strong>
          <span>{t.benchmarkSkipped}</span>
        </div>

        {benchmark.total > 0 && (
          <div className="benchmark-progress">
            <div className="progress-label">
              <span>
                {t.benchmarkProgress}: {benchmark.completed} / {benchmark.total}
              </span>
              <span>
                {benchmark.running
                  ? t.benchmarkRunning
                  : `${benchmarkPassed} / ${benchmark.total} ${t.benchmarkPassed}`}
              </span>
            </div>
            <div className="progress-track">
              <div
                className="progress-value"
                style={{
                  width: `${(benchmark.completed / benchmark.total) * 100}%`,
                }}
              />
            </div>
          </div>
        )}

        {benchmark.results.length > 0 && (
          <div className="benchmark-results">
            <div className="results-heading">
              <strong>{t.benchmarkResult}</strong>
              <button
                type="button"
                className="export-button"
                onClick={onExportBenchmark}
              >
                <Download size={14} />
                {t.benchmarkExport}
              </button>
            </div>

            {benchmark.results.map((result) => (
              <article
                className="benchmark-result-row"
                key={`${result.provider}-${result.model}`}
              >
                <div className="result-main">
                  <div className={`result-state ${result.status}`}>
                    {result.status === 'passed' && <Check size={13} />}
                    {result.status === 'passed'
                      ? t.benchmarkPassed
                      : result.status === 'language_mismatch'
                        ? t.benchmarkLanguageMismatch
                        : t.benchmarkFailed}
                  </div>
                  <strong>{result.model}</strong>
                  <span>{t[providerLabelKeys[result.provider]]}</span>
                  {result.error && (
                    <small className="result-error">{result.error}</small>
                  )}
                  {result.preview && (
                    <p className="result-preview" dir="auto">
                      {result.preview}
                    </p>
                  )}
                </div>

                <div className="result-metrics">
                  <span>
                    <strong>{result.elapsedSeconds.toFixed(1)}s</strong>
                    <small>{t.benchmarkDuration}</small>
                  </span>
                  <span>
                    <strong>{result.answerLength}</strong>
                    <small>{t.benchmarkLength}</small>
                  </span>
                  <span>
                    <strong>
                      {result.hasPersian
                        ? t.benchmarkYes
                        : t.benchmarkNo}
                    </strong>
                    <small>{t.benchmarkLanguage}</small>
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}

        {benchmark.total === 0 && !benchmark.running && (
          <div className="benchmark-empty">
            {t.benchmarkNoResults}
          </div>
        )}

        <div className="benchmark-disclaimer">
          {t.benchmarkTechnicalNote}
        </div>
      </section>

      <p className="studio-disclaimer">
        <ShieldCheck size={15} />
        {t.studioDisclaimer}
      </p>
    </section>
  )
}

/* ---------------- Therapy registry ---------------- */

function TherapiesPage({
  t,
  modules,
  onOpenStudio,
}: {
  t: Translation
  modules: TherapyModule[]
  onOpenStudio: () => void
}) {
  const categories = plannedTherapyCategories.map(
    (key) => t[key],
  )

  return (
    <section className="secondary-view">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <BookOpen size={15} />
            {t.modularTherapyArchitecture}
          </div>
          <h1>{t.therapiesTitle}</h1>
          <p>{t.therapiesDescription}</p>
        </div>
      </div>

      <div className="therapy-intro">
        <div className="therapy-intro-icon">
          <BrainCircuit size={22} />
        </div>
        <div>
          <h2>{t.therapiesArchitecture}</h2>
          <p>{t.therapiesArchitectureDescription}</p>
        </div>
      </div>

      <div className="section-heading">
        <div>
          <h2>{t.registeredModules}</h2>
          <p>{modules.length} {t.moduleCount}</p>
        </div>
      </div>

      <div className="therapy-grid">
        {modules.map((module) => {
          const isRunnable = module.status === 'available'
          return (
            <article className="therapy-card" key={module.id}>
              <div className="therapy-card-top">
                <span className="therapy-code">{module.code}</span>
                <span className={`module-status ${isRunnable ? 'available' : 'designing'}`}>
                  {isRunnable ? t.moduleRunnable : t.modulePreparing}
                </span>
              </div>
              <h3>
                {module.id === 'act'
                  ? t.actModuleName
                  : module.name}
              </h3>
              <p>
                {module.id === 'act'
                  ? t.actModuleDescription
                  : module.description}
              </p>
              <div className="therapy-card-footer">
                <span>{t.moduleVersion} {module.version}</span>
                <span>{isRunnable ? t.onlyRunnableModule : t.firstModule}</span>
              </div>
            </article>
          )
        })}
      </div>

      <section className="planned-panel">
        <h3>{t.futureCategories}</h3>
        <p>{t.futureCategoriesDescription}</p>
        <div className="category-chips">
          {categories.map((category) => (
            <span key={category}>{category}</span>
          ))}
        </div>
      </section>

      <button
        type="button"
        className="primary-button"
        onClick={onOpenStudio}
      >
        {t.backToStudio}
        <ArrowLeft size={16} />
      </button>
    </section>
  )
}

/* ---------------- Planned pages ---------------- */

function ComingSoonPage({
  t,
  icon: Icon,
  title,
}: {
  t: Translation
  icon: LucideIcon
  title: string
}) {
  return (
    <section className="placeholder-view">
      <div className="placeholder-icon">
        <Icon size={34} />
      </div>
      <span className="eyebrow">{t.roadmap}</span>
      <h1>{title}</h1>
      <p>{t.pageInDevelopment}</p>
      <div className="placeholder-state">
        <span />
        {t.inDevelopment}
      </div>
      <div className="placeholder-note">
        {t.pageInDevelopmentDescription}
      </div>
    </section>
  )
}

/* ---------------- Settings ---------------- */

interface ProviderDraft extends ProviderEndpointSettings {
  protocol: 'http' | 'https'
  portText: string
  api_key: string
  clear_api_key: boolean
}

function providerSettingsToDrafts(
  response: ProviderSettingsResponse,
): Record<ProviderName, ProviderDraft> {
  const drafts = {} as Record<ProviderName, ProviderDraft>
  for (const item of response.providers) {
    const parsed = parseApiBaseUrl(item.base_url)
    drafts[item.name] = {
      ...item,
      protocol: parsed.protocol,
      portText: String(item.port),
      api_key: '',
      clear_api_key: false,
    }
  }
  return drafts
}

function providerValidationMessage(error: unknown, t: Translation) {
  return error instanceof Error
    && error.message === 'Non-loopback HTTP endpoints require HTTPS.'
    ? t.remoteHttpRequiresHttps
    : t.invalidProviderSettings
}

function SettingsPage({
  t,
  language,
  appVersion,
  backendStatus,
  startupError,
  onProviderSaved,
}: {
  t: Translation
  language: Language
  appVersion: string
  backendStatus: ConnectionState
  startupError: string
  onProviderSaved: (settings: ProviderSettingsResponse) => void
}) {
  const backendAddress = window.location.port === '5173'
    ? '127.0.0.1:8000'
    : window.location.host
  const [settings, setSettings] = useState<ProviderSettingsResponse | null>(null)
  const [drafts, setDrafts] =
    useState<Record<ProviderName, ProviderDraft> | null>(null)
  const [activeProvider, setActiveProvider] = useState<ProviderName>('ollama')
  const [localOnlyMode, setLocalOnlyMode] = useState(true)
  const [remoteEndpointConfirmed, setRemoteEndpointConfirmed] = useState(false)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionState>('checking')
  const [connectionMessage, setConnectionMessage] = useState('')
  const [modelListingSupported, setModelListingSupported] =
    useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [validationError, setValidationError] = useState('')
  const [updateBusy, setUpdateBusy] = useState(false)
  const [updateError, setUpdateError] = useState('')
  const [updateInfo, setUpdateInfo] =
    useState<UpdateMetadataResponse | null>(null)
  const [verificationMessage, setVerificationMessage] = useState('')
  const [verificationBusy, setVerificationBusy] = useState(false)

  const loadModels = useCallback(async (
    providerName: ProviderName,
    baseUrl: string,
    model: string,
    apiKey?: string,
  ) => {
    setTesting(true)
    setConnectionStatus('checking')
    setConnectionMessage('')
    setError('')
    try {
      const result = await testProviderConnection(
        providerName,
        baseUrl,
        model,
        apiKey,
      )
      setModels(result.models)
      setModelListingSupported(result.model_listing_supported)
      setConnectionStatus(result.success ? 'online' : 'offline')
      setConnectionMessage({
        connected: model ? t.providerModelAvailable : t.providerConnectionSucceeded,
        model_available: t.providerModelAvailable,
        model_required: t.providerModelRequired,
        model_unavailable: t.providerModelUnavailable,
        authentication_failed: t.providerAuthenticationFailed,
        timeout: t.providerTimeout,
        unavailable: t.providerUnavailable,
        provider_error: t.providerError,
        remote_blocked: t.providerRemoteBlocked,
      }[result.status])
    } catch {
      setModels([])
      setModelListingSupported(null)
      setConnectionStatus('offline')
      setConnectionMessage(t.providerConnectionFailed)
    } finally {
      setTesting(false)
    }
  }, [
    t.providerAuthenticationFailed,
    t.providerConnectionFailed,
    t.providerConnectionSucceeded,
    t.providerError,
    t.providerModelAvailable,
    t.providerModelRequired,
    t.providerModelUnavailable,
    t.providerRemoteBlocked,
    t.providerTimeout,
    t.providerUnavailable,
  ])

  useEffect(() => {
    let active = true
    void getProviderSettings()
      .then((response) => {
        if (!active) return
        setSettings(response)
        setDrafts(providerSettingsToDrafts(response))
        setActiveProvider(response.active_provider)
        setLocalOnlyMode(response.local_only)
        const selected = response.providers.find(
          (item) => item.name === response.active_provider,
        )
        if (selected) {
          void loadModels(
            response.active_provider,
            selected.base_url,
            selected.model,
          )
        }
      })
      .catch(() => {
        if (active) setError(t.settingsLoadFailed)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [loadModels, t.settingsLoadFailed])

  const currentDraft = drafts?.[activeProvider]

  function updateDraft(
    providerName: ProviderName,
    update: Partial<ProviderDraft>,
  ) {
    setDrafts((current) => current
      ? {
          ...current,
          [providerName]: {
            ...current[providerName],
            ...update,
          },
        }
      : current)
    setError('')
    setSuccess('')
  }

  function handleProviderChange(providerName: ProviderName) {
    setActiveProvider(providerName)
    setModels([])
    setModelListingSupported(null)
    setValidationError('')
    const draft = drafts?.[providerName]
    if (draft) void loadModels(providerName, draft.base_url, draft.model)
  }

  function updateHostPortPath(
    field: 'host' | 'portText' | 'api_base_path' | 'protocol',
    value: string,
  ) {
    if (!currentDraft) return
    const update: Partial<ProviderDraft> = { [field]: value }
    const next = { ...currentDraft, ...update }
    try {
      const baseUrl = buildApiBaseUrl(
        next.host,
        next.portText,
        next.api_base_path,
        next.protocol,
      )
      update.base_url = baseUrl
      setValidationError('')
    } catch (validationError) {
      setValidationError(providerValidationMessage(validationError, t))
    }
    updateDraft(activeProvider, update)
  }

  function handleBaseUrlChange(value: string) {
    if (!currentDraft) return
    const update: Partial<ProviderDraft> = { base_url: value }
    try {
      const parsed = parseApiBaseUrl(value)
      update.protocol = parsed.protocol
      update.host = parsed.host
      update.port = parsed.port
      update.portText = String(parsed.port)
      update.api_base_path = parsed.apiBasePath
      setValidationError('')
    } catch (validationError) {
      setValidationError(providerValidationMessage(validationError, t))
    }
    updateDraft(activeProvider, update)
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!drafts) return
    setError('')
    setSuccess('')
    if (!localOnlyMode && !remoteEndpointConfirmed) {
      setError(t.remoteConfirmationRequired)
      return
    }

    let baseUrl: string
    try {
      const fieldBaseUrl = buildApiBaseUrl(
        currentDraft?.host ?? '',
        currentDraft?.portText ?? '',
        currentDraft?.api_base_path ?? '',
        currentDraft?.protocol ?? 'http',
      )
      const parsedBaseUrl = parseApiBaseUrl(currentDraft?.base_url ?? '')
      const enteredBaseUrl = buildApiBaseUrl(
        parsedBaseUrl.host,
        parsedBaseUrl.port,
        parsedBaseUrl.apiBasePath,
        parsedBaseUrl.protocol,
      )
      if (fieldBaseUrl !== enteredBaseUrl) {
        throw new Error('Endpoint fields do not match the API base URL.')
      }
      baseUrl = fieldBaseUrl
      setValidationError('')
    } catch (validationError) {
      const message = providerValidationMessage(validationError, t)
      setValidationError(message)
      setError(message)
      return
    }

    setSaving(true)
    try {
      const result = await saveProviderSettings({
        active_provider: activeProvider,
        local_only: localOnlyMode,
        confirm_remote_endpoints: !localOnlyMode && remoteEndpointConfirmed,
        providers: providerNames.map((name) => {
          const draft = drafts[name]
          return {
            name,
            base_url: name === activeProvider ? baseUrl : draft.base_url,
            model: draft.model,
            patient_model: draft.patient_model,
            evaluator_model: draft.evaluator_model,
            ...(draft.api_key
              ? { api_key: draft.api_key }
              : {}),
            ...(draft.clear_api_key
              ? { clear_api_key: true }
              : {}),
          }
        }),
      })
      setSettings(result)
      setDrafts(providerSettingsToDrafts(result))
      setLocalOnlyMode(result.local_only)
      setRemoteEndpointConfirmed(false)
      setSuccess(
        result.restart_required
          ? `${t.providerSettingsSaved} ${t.providerRestartRequired}`
          : t.providerSettingsSaved,
      )
      onProviderSaved(result)
      const savedActive = result.providers.find(
        (item) => item.name === result.active_provider,
      )
      if (savedActive) {
        void loadModels(
          result.active_provider,
          savedActive.base_url,
          savedActive.model,
        )
      }
    } catch {
      setError(t.providerSaveFailed)
    } finally {
      setSaving(false)
    }
  }

  async function testCurrentConnection() {
    if (!currentDraft) return
    let baseUrl: string
    try {
      baseUrl = buildApiBaseUrl(
        currentDraft.host,
        currentDraft.portText,
        currentDraft.api_base_path,
        currentDraft.protocol,
      )
      setValidationError('')
    } catch (validationError) {
      const message = providerValidationMessage(validationError, t)
      setValidationError(message)
      setError(message)
      return
    }
    const apiKey = currentDraft.clear_api_key
      ? ''
      : currentDraft.api_key || undefined
    await loadModels(activeProvider, baseUrl, currentDraft.model, apiKey)
  }

  async function checkForUpdates() {
    setUpdateBusy(true)
    setUpdateError('')
    setVerificationMessage('')
    try {
      setUpdateInfo(await getUpdateMetadata())
    } catch {
      setUpdateError(t.updateUnavailable)
    } finally {
      setUpdateBusy(false)
    }
  }

  async function verifySelectedFile(file?: File) {
    const asset = updateInfo?.release.assets?.[0]
    if (!asset || !file) return
    setVerificationBusy(true)
    setVerificationMessage('')
    try {
      const matches = await verifySha256File(file, asset.sha256)
      setVerificationMessage(matches ? t.updateVerified : t.updateVerifyFailed)
    } catch {
      setVerificationMessage(t.updateVerifyFailed)
    } finally {
      setVerificationBusy(false)
    }
  }

  return (
    <section className="secondary-view">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <Settings2 size={15} />
            {t.systemConfiguration}
          </div>
          <h1>{t.settings}</h1>
          <p>{t.currentConfiguration}</p>
        </div>
      </div>

      <section className="surface-card settings-card">
        <div className="settings-row">
          <div>
            <strong>{t.backendService}</strong>
            <small dir="ltr">{backendAddress}</small>
          </div>
          <span className={`connection-label ${backendStatus}`}>
            <StatusDot status={backendStatus} />
            {statusText(backendStatus, t)}
          </span>
        </div>

        {startupError && (
          <div className="error-banner" role="alert">
            {startupError}
          </div>
        )}
      </section>

      <form className="surface-card provider-settings-form" onSubmit={(event) => void saveSettings(event)}>
        <div className="card-heading">
          <span className="heading-icon"><Cpu size={19} /></span>
          <div>
            <h3>{t.providerSettingsTitle}</h3>
            <p>{t.providerSettingsDescription}</p>
          </div>
        </div>

        {loading && <p role="status">{t.settingsLoading}</p>}

        {!loading && settings && drafts && currentDraft && (
          <>
            <div className="provider-settings-grid">
              <label className="field">
                <span>{t.activeProvider}</span>
                <div className="select-box">
                  <select
                    value={activeProvider}
                    onChange={(event) =>
                      handleProviderChange(event.target.value as ProviderName)
                    }
                  >
                    {providerNames.map((name) => (
                      <option key={name} value={name}>
                        {t[providerLabelKeys[name]]}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={16} />
                </div>
              </label>

              <label className="field">
                <span>{t.endpointProtocol}</span>
                <div className="select-box">
                  <select
                    value={currentDraft.protocol}
                    onChange={(event) =>
                      updateHostPortPath(
                        'protocol',
                        event.target.value as 'http' | 'https',
                      )
                    }
                  >
                    <option value="http">HTTP</option>
                    <option value="https">HTTPS</option>
                  </select>
                  <ChevronDown size={16} />
                </div>
              </label>

              <label className="field">
                <span>{t.endpointHost}</span>
                <input
                  autoComplete="off"
                  dir="ltr"
                  value={currentDraft.host}
                  onChange={(event) =>
                    updateHostPortPath('host', event.target.value)
                  }
                />
              </label>

              <label className="field">
                <span>{t.endpointPort}</span>
                <input
                  inputMode="numeric"
                  min={1}
                  max={65535}
                  type="number"
                  dir="ltr"
                  value={currentDraft.portText}
                  onChange={(event) =>
                    updateHostPortPath('portText', event.target.value)
                  }
                />
              </label>

              <label className="field">
                <span>{t.apiBasePath}</span>
                <input
                  dir="ltr"
                  value={currentDraft.api_base_path}
                  onChange={(event) =>
                    updateHostPortPath('api_base_path', event.target.value)
                  }
                />
              </label>

              <label className="field provider-base-url">
                <span>{t.apiBaseUrl}</span>
                <input
                  autoComplete="url"
                  dir="ltr"
                  value={currentDraft.base_url}
                  onChange={(event) => handleBaseUrlChange(event.target.value)}
                />
              </label>

              <label className="field">
                <span>{t.modelName}</span>
                <input
                  list="provider-model-options"
                  dir="auto"
                  value={currentDraft.model}
                  onChange={(event) =>
                    updateDraft(activeProvider, { model: event.target.value })
                  }
                />
                <datalist id="provider-model-options">
                  {models.map((model) => (
                    <option key={model.id} value={model.id} />
                  ))}
                </datalist>
                <small>{t.modelNameHelp}</small>
              </label>

              <label className="field">
                <span>{t.patientAgentModel}</span>
                <input
                  list="provider-model-options"
                  dir="auto"
                  value={currentDraft.patient_model}
                  onChange={(event) =>
                    updateDraft(activeProvider, {
                      patient_model: event.target.value,
                    })
                  }
                />
                <small>{t.roleModelHelp}</small>
              </label>

              <label className="field">
                <span>{t.evaluatorAgentModel}</span>
                <input
                  list="provider-model-options"
                  dir="auto"
                  value={currentDraft.evaluator_model}
                  onChange={(event) =>
                    updateDraft(activeProvider, {
                      evaluator_model: event.target.value,
                    })
                  }
                />
                <small>{t.roleModelHelp}</small>
              </label>

              <label className="field">
                <span>{t.apiKey}</span>
                <input
                  autoComplete="new-password"
                  type="password"
                  value={currentDraft.api_key}
                  onChange={(event) =>
                    updateDraft(activeProvider, {
                      api_key: event.target.value,
                      clear_api_key: false,
                    })
                  }
                />
                <small>{t.apiKeyHelp}</small>
              </label>
            </div>

            <label className="provider-api-key-clear">
              <input
                type="checkbox"
                checked={localOnlyMode}
                onChange={(event) => {
                  setLocalOnlyMode(event.target.checked)
                  setRemoteEndpointConfirmed(false)
                }}
              />
              <span>
                <strong>{t.localOnlyMode}</strong>
                <small>{t.localOnlyModeHelp}</small>
              </span>
            </label>

            {!localOnlyMode && (
              <label className="provider-api-key-clear">
                <input
                  type="checkbox"
                  checked={remoteEndpointConfirmed}
                  onChange={(event) =>
                    setRemoteEndpointConfirmed(event.target.checked)
                  }
                />
                <span>
                  <strong>{t.allowRemoteEndpoint}</strong>
                  <small>{t.allowRemoteEndpointHelp}</small>
                </span>
              </label>
            )}

            {currentDraft.api_key_configured && (
              <label className="provider-api-key-clear">
                <input
                  type="checkbox"
                  checked={currentDraft.clear_api_key}
                  onChange={(event) =>
                    updateDraft(activeProvider, {
                      clear_api_key: event.target.checked,
                      api_key: '',
                    })
                  }
                />
                <span>{t.clearApiKey}</span>
              </label>
            )}

            <p className="provider-settings-note">{t.modelsSupported}</p>
            <p className="provider-settings-note">{t.providerEndpointPrivacy}</p>

            {validationError && (
              <p className="provider-settings-error" role="alert">
                {validationError}
              </p>
            )}
            {error && <div className="error-banner" role="alert">{error}</div>}
            {success && <div className="provider-settings-success" role="status">{success}</div>}

            {connectionMessage && (
              <div
                className={`provider-settings-result ${connectionStatus}`}
                role="status"
                aria-live="polite"
              >
                {connectionMessage}
              </div>
            )}
            {connectionStatus === 'checking' && testing && (
              <p role="status">{t.testingConnection}</p>
            )}
            {models.length === 0 && modelListingSupported && !testing && (
              <p className="provider-settings-note">{t.noModelsListed}</p>
            )}

            <div className="provider-settings-actions">
              <span className={`connection-label ${connectionStatus}`}>
                <StatusDot status={connectionStatus} />
                {statusText(connectionStatus, t)}
              </span>
              <button
                type="button"
                className="secondary-button"
                onClick={() => void testCurrentConnection()}
                disabled={testing || saving}
              >
                {testing
                  ? <LoaderCircle className="spin" size={16} />
                  : <Wifi size={16} />}
                {testing ? t.testingConnection : t.testConnection}
              </button>
              <button
                type="submit"
                className="primary-button"
                disabled={saving || testing}
              >
                {saving
                  ? <LoaderCircle className="spin" size={16} />
                  : <Check size={16} />}
                {saving ? t.savingProviderSettings : t.saveProviderSettings}
              </button>
            </div>
          </>
        )}
      </form>

      <SupportExport language={language} t={t} />

      <section className="surface-card support-card">
        <div className="card-heading">
          <span className="heading-icon"><RefreshCw size={19} /></span>
          <div>
            <h3>{t.updateTitle}</h3>
            <p>{t.updateDescription}</p>
          </div>
        </div>
        <p className="provider-settings-note">
          {t.updateInstalledVersion}:{' '}
          <bdi dir="ltr">{updateInfo?.current_version || appVersion || '—'}</bdi>
        </p>
        <p className="provider-settings-note">{t.updateNoAutoInstall}</p>
        <button
          type="button"
          className="secondary-button"
          disabled={updateBusy}
          onClick={() => void checkForUpdates()}
        >
          {updateBusy
            ? <LoaderCircle className="spin" size={16} />
            : <RefreshCw size={16} />}
          {updateBusy ? t.updateChecking : t.updateCheck}
        </button>
        {updateError && <p role="alert" className="provider-settings-error">{updateError}</p>}
        {updateInfo && (
          <div className="update-metadata" aria-live="polite">
            {updateInfo.release.status === 'unavailable' ? (
              <p role="status">{t.updateUnavailable}</p>
            ) : (
              <>
                <p role="status">
                  {updateInfo.release.update_available
                    ? t.updateAvailable
                    : t.updateCurrent}
                </p>
                <p>
                  {t.updateVersion}:{' '}
                  <bdi dir="ltr">{updateInfo.release.version}</bdi>
                </p>
                <p>
                  {t.updatePublished}:{' '}
                  <bdi dir="ltr">{updateInfo.release.published_at}</bdi>
                </p>
                {updateInfo.release.release_url && (
                  <a
                    className="secondary-button"
                    href={updateInfo.release.release_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t.updateDownload}
                  </a>
                )}
                {updateInfo.release.notes && (
                  <details>
                    <summary>{t.updateNotes}</summary>
                    <pre dir="auto">{updateInfo.release.notes}</pre>
                  </details>
                )}
                {updateInfo.release.assets?.[0] ? (
                  <div className="update-asset">
                    <p>{t.updateChecksum}</p>
                    <code dir="ltr">{updateInfo.release.assets[0].sha256}</code>
                    <p className="provider-settings-note">{t.updateVerifyPrompt}</p>
                    <label className="secondary-button">
                      {t.updateVerifyFile}
                      <input
                        type="file"
                        accept=".zip,application/zip"
                        onChange={(event) =>
                          void verifySelectedFile(event.currentTarget.files?.[0])
                        }
                      />
                    </label>
                    {verificationBusy && <p role="status">{t.updateChecking}</p>}
                    {verificationMessage && (
                      <p role="status" className="provider-settings-result">
                        {verificationMessage}
                      </p>
                    )}
                  </div>
                ) : (
                  <p>{t.updateNoVerifiedAsset}</p>
                )}
              </>
            )}
            {updateInfo.source_checkout?.available ? (
              <div className="source-checkout-info">
                <strong>{t.updateSourceCheckout}</strong>
                <p>{t.updateBranch}: <bdi dir="ltr">{updateInfo.source_checkout.branch}</bdi></p>
                <p>{t.updateCommit}: <bdi dir="ltr">{updateInfo.source_checkout.commit}</bdi></p>
                <p>
                  {t.updateDirty}:{' '}
                  {updateInfo.source_checkout.dirty ? t.updateDirtyYes : t.updateDirtyNo}
                </p>
              </div>
            ) : updateInfo.source_checkout ? (
              <p>{t.updateSourceUnavailable}</p>
            ) : null}
          </div>
        )}
      </section>

      <section className="settings-info">
        <ShieldCheck size={21} />
        <div>
          <strong>{t.systemPrivacy}</strong>
          <p>{t.systemPrivacyDescription}</p>
        </div>
      </section>
    </section>
  )
}

export default App
