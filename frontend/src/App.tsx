import brandLogo from './assets/brand-logo.svg'
import {
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

import { translations, type Language, type Translation } from './i18n'
import { therapyModules, plannedTherapyCategories } from './data/therapyModules'
import { SessionsPage } from './features/sessions/SessionsPage'
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
  getModels,
  getProviders,
  sendChat,
} from './lib/api'

import type {
  ChatMessage,
  ConnectionState,
  ModelInfo,
  ProviderCatalog,
  ProviderInfo,
  ProviderName,
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

const providerNames: ProviderName[] = ['ollama', 'lm_studio']

const providerLabels: Record<ProviderName, string> = {
  ollama: 'Ollama',
  lm_studio: 'LM Studio',
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
  'به زبان فارسی و در حداکثر ۸۰ کلمه توضیح بده پذیرش (Acceptance) در درمان مبتنی بر پذیرش و تعهد (ACT) چه تفاوتی با تسلیم‌شدن دارد. یک مثال روزمره و غیرتشخیصی بیاور. پاسخ را با دو بخش «تعریف» و «مثال» تنظیم کن.'

function getInitialLanguage(): Language {
  try {
    return window.localStorage.getItem('therasim-language') === 'fa'
      ? 'fa'
      : 'en'
  } catch {
    return 'en'
  }
}

function errorMessage(error: unknown, fallback: string): string {
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

function App() {
  const [language, setLanguage] = useState<Language>(getInitialLanguage)
  const t = translations[language]
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

  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [provider, setProvider] = useState<ProviderName>('ollama')

  const [modelsByProvider, setModelsByProvider] =
    useState<Record<ProviderName, ModelInfo[]>>({
      ollama: [],
      lm_studio: [],
    })

  const [providerStates, setProviderStates] =
    useState<Record<ProviderName, ConnectionState>>({
      ollama: 'checking',
      lm_studio: 'checking',
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

  const currentModels = modelsByProvider[provider]
  const currentProviderState = providerStates[provider]

  useEffect(() => {
    document.documentElement.lang = language
    document.documentElement.dir = direction

    try {
      window.localStorage.setItem('therasim-language', language)
    } catch {
      // The interface still works if browser storage is unavailable.
    }
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
              errorMessage(requestError, t.noStartupConnection),
            )
            setAuthMode('unavailable')
          }
        }
      } catch (requestError) {
        if (!active) return
        setAuthError(errorMessage(requestError, t.noStartupConnection))
        setAuthMode('unavailable')
      }
    }

    void checkAuthentication()

    return () => {
      active = false
    }
  }, [authRetryKey, t.noStartupConnection])

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
      }

      const nextStates: Record<ProviderName, ConnectionState> = {
        ollama: 'offline',
        lm_studio: 'offline',
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
        )?.id ?? nextModels[catalog.active_provider][0]?.id ?? '',
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
      const message = errorMessage(requestError, t.noStartupConnection)
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
      setAuthError(errorMessage(requestError, t.noStartupConnection))
    } finally {
      clearAuthToken()
      setAuthenticatedUser(null)
      setAuthMode('login')
    }
  }

  function changeProvider(nextProvider: ProviderName) {
    setProvider(nextProvider)
    setSelectedModel(
      modelsByProvider[nextProvider][0]?.id ?? '',
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
            TheraSim · 0.1.0
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
              providers={providers}
              providerStates={providerStates}
              backendStatus={backendStatus}
              startupError={startupError}
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
          value={`${connectedProviderCount} / ${providers.length || 2}`}
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
                <strong>{providerLabels[name]}</strong>
                <span>
                  {name === 'ollama'
                    ? '127.0.0.1:11434'
                    : '127.0.0.1:1234'}
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
  t,
}: {
  icon: LucideIcon
  label: string
  value: string
  description: string
  status?: ConnectionState
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

      <div className="metric-value">{value}</div>
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
                    {providerLabels[item.name]}
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
                disabled={chatModels.length === 0}
              >
                {chatModels.length === 0 && (
                  <option value="">{t.noModels}</option>
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

      <section className="surface-card chat-panel">
        <div className="chat-header">
          <div className="chat-heading">
            <span className="chat-avatar">
              <BrainCircuit size={20} />
            </span>
            <div>
              <h3>{t.chatTitle}</h3>
              <p>{selectedModel || providerLabels[provider]}</p>
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
                  <span>{providerLabels[result.provider]}</span>
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
          <p>{modules.length} modules</p>
        </div>
      </div>

      <div className="therapy-grid">
        {modules.map((module) => (
          <article className="therapy-card" key={module.id}>
            <div className="therapy-card-top">
              <span className="therapy-code">{module.code}</span>
              <span className="module-status designing">
                {t.modulePreparing}
              </span>
            </div>
            <h3>
              {module.id === 'act'
                ? 'Acceptance and Commitment Therapy (ACT)'
                : module.name}
            </h3>
            <p>{module.description}</p>
            <div className="therapy-card-footer">
              <span>{t.moduleVersion} {module.version}</span>
              <span>{t.firstModule}</span>
            </div>
          </article>
        ))}
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

function SettingsPage({
  t,
  providers,
  providerStates,
  backendStatus,
  startupError,
}: {
  t: Translation
  providers: ProviderInfo[]
  providerStates: Record<ProviderName, ConnectionState>
  backendStatus: ConnectionState
  startupError: string
}) {
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
            <small>127.0.0.1:8000</small>
          </div>
          <span className={`connection-label ${backendStatus}`}>
            <StatusDot status={backendStatus} />
            {statusText(backendStatus, t)}
          </span>
        </div>

        {providers.map((item) => (
          <div className="settings-row" key={item.name}>
            <div>
              <strong>{providerLabels[item.name]}</strong>
              <small>{item.base_url}</small>
            </div>
            <span className={`connection-label ${providerStates[item.name]}`}>
              <StatusDot status={providerStates[item.name]} />
              {statusText(providerStates[item.name], t)}
            </span>
          </div>
        ))}

        {startupError && (
          <div className="error-banner" role="alert">
            {startupError}
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
