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
  listMemoryCandidates,
  listMemoryConsolidationSuggestions,
  proposeMemoryConsolidation,
  reviewMemoryCandidate,
} from './api'
import type {
  MemoryConsolidationSuggestion,
  MemoryRecord,
} from './types'

const text = {
  en: {
    title: 'Memory review',
    description:
      'Review proposed memories and their source evidence before they can influence later sessions.',
    reviewerWarning:
      'Consolidated memories remain proposals until reviewed. Similarity and contradiction flags are deterministic hints, not verified clinical conclusions.',
    consolidation: 'Cross-session consolidation',
    consolidationDescription:
      'Select related memories from different sessions and write a concise proposal. Original memories and evidence remain unchanged.',
    noSuggestions: 'No related cross-session memories were found.',
    selectSources: 'Select these sources',
    selectedSources: 'Selected source memories',
    proposedContent: 'Proposed consolidated memory',
    proposedContentPlaceholder:
      'Write a cautious summary supported by the selected source memories.',
    propose: 'Create review proposal',
    proposed: 'Consolidation proposal created for review.',
    related: 'Related',
    repeated: 'Repeated pattern',
    potential_contradiction: 'Potential contradiction',
    similarity: 'Text similarity',
    sourceMemories: 'Consolidation sources',
    sourceMemory: 'Source memory',
    sourceMemoryLabel: 'Memory',
    version: 'Version',
    selectAtLeastTwo: 'Select a suggestion and write a proposed memory.',
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
      'حافظه‌های تلفیقی تا زمان بازبینی فقط پیشنهاد هستند. شباهت و تناقض، نشانه‌های قطعی و بالینی نیستند.',
    consolidation: 'تلفیق بین جلسات',
    consolidationDescription:
      'خاطرات مرتبط از جلسات متفاوت را انتخاب و یک پیشنهاد کوتاه بنویس. خاطرات و شواهد اصلی بدون تغییر باقی می‌مانند.',
    noSuggestions: 'خاطره مرتبطی برای تلفیق بین جلسات پیدا نشد.',
    selectSources: 'انتخاب این منابع',
    selectedSources: 'خاطرات منبع انتخاب‌شده',
    proposedContent: 'پیشنهاد حافظه تلفیقی',
    proposedContentPlaceholder:
      'خلاصه‌ای محتاطانه و مستند بر پایه خاطرات انتخاب‌شده بنویس.',
    propose: 'ایجاد پیشنهاد برای بازبینی',
    proposed: 'پیشنهاد تلفیق برای بازبینی ایجاد شد.',
    related: 'مرتبط',
    repeated: 'الگوی تکرارشونده',
    potential_contradiction: 'تناقض احتمالی',
    similarity: 'شباهت متنی',
    sourceMemories: 'منابع تلفیق',
    sourceMemory: 'خاطره منبع',
    sourceMemoryLabel: 'خاطره',
    version: 'نسخه',
    selectAtLeastTwo: 'یک پیشنهاد را انتخاب و متن حافظه را بنویس.',
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
  const [notice, setNotice] = useState<
    'accepted' | 'rejected' | 'consolidated' | ''
  >('')
  const [suggestions, setSuggestions] = useState<
    MemoryConsolidationSuggestion[]
  >([])
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [consolidationContent, setConsolidationContent] = useState('')
  const [consolidating, setConsolidating] = useState(false)

  const loadCandidates = useCallback(async () => {
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const [response, suggestionResponse] = await Promise.all([
        listMemoryCandidates(runId),
        listMemoryConsolidationSuggestions(runId),
      ])
      setMemories(response.data)
      setSuggestions(suggestionResponse.data)
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

  async function handleConsolidate() {
    if (selectedSources.length < 2 || !consolidationContent.trim() || consolidating) {
      return
    }

    setConsolidating(true)
    setError('')
    setNotice('')
    try {
      await proposeMemoryConsolidation(
        runId,
        selectedSources,
        consolidationContent.trim(),
      )
      setSelectedSources([])
      setConsolidationContent('')
      await loadCandidates()
      setNotice('consolidated')
    } catch (proposalError) {
      setError(
        proposalError instanceof Error
          ? proposalError.message
          : 'memory_request_failed',
      )
    } finally {
      setConsolidating(false)
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
            {notice === 'accepted'
              ? copy.accepted
              : notice === 'rejected'
                ? copy.rejected
                : copy.proposed}
          </span>
        </div>
      )}

      <section className="memory-consolidation">
        <h3>{copy.consolidation}</h3>
        <p>{copy.consolidationDescription}</p>
        {suggestions.length === 0 ? (
          <p className="memory-review-state">{copy.noSuggestions}</p>
        ) : (
          <div className="memory-candidate-list">
            {suggestions.map((suggestion) => {
              const isSelected =
                selectedSources.length === suggestion.source_memory_ids.length &&
                suggestion.source_memory_ids.every((id) =>
                  selectedSources.includes(id),
                )
              return (
                <article
                  className="memory-candidate"
                  key={suggestion.source_memory_ids.join(':')}
                >
                  <div className="memory-candidate-meta">
                    <span>
                      {copy[
                        suggestion.relationship_type as
                          | 'related'
                          | 'repeated'
                          | 'potential_contradiction'
                      ] ?? copy.related}
                    </span>
                    <span>
                      {copy.similarity}: {Math.round(suggestion.similarity * 100)}%
                    </span>
                  </div>
                  <p dir="ltr">
                    {suggestion.source_memory_ids.join(' · ')}
                  </p>
                  <div className="memory-evidence">
                    {suggestion.sources.map((source) => (
                      <blockquote
                        key={`${suggestion.source_memory_ids.join(':')}-${source.source_memory_id}`}
                        dir="auto"
                      >
                        <strong>{copy.sourceMemoryLabel}</strong>
                        <p>{source.content}</p>
                        <footer>
                          <bdi dir="ltr">{source.source_memory_id}</bdi>
                          {' · '}
                          {copy.version}:{' '}
                          <bdi dir="ltr">
                            {source.source_memory_version}
                          </bdi>
                          {' · '}
                          {copy.session}:{' '}
                          <bdi dir="ltr">{source.source_session_id}</bdi>
                        </footer>
                      </blockquote>
                    ))}
                  </div>
                  <button
                    type="button"
                    className={isSelected ? 'primary-button' : 'secondary-button'}
                    onClick={() => {
                      setSelectedSources(suggestion.source_memory_ids)
                      setConsolidationContent('')
                    }}
                    disabled={consolidating}
                  >
                    {copy.selectSources}
                  </button>
                </article>
              )
            })}
          </div>
        )}
        {selectedSources.length > 0 && (
          <>
            <p className="memory-candidate-meta">
              {copy.selectedSources}:{' '}
              <bdi dir="ltr">{selectedSources.join(' · ')}</bdi>
            </p>
            <label className="memory-rationale">
              <span>{copy.proposedContent}</span>
              <textarea
                value={consolidationContent}
                onChange={(event) =>
                  setConsolidationContent(event.target.value)
                }
                placeholder={copy.proposedContentPlaceholder}
                maxLength={12000}
                rows={3}
                disabled={consolidating}
              />
            </label>
            <button
              type="button"
              className="primary-button"
              onClick={() => void handleConsolidate()}
              disabled={
                selectedSources.length < 2 ||
                !consolidationContent.trim() ||
                consolidating
              }
            >
              {consolidating ? (
                <LoaderCircle className="spin" size={15} />
              ) : null}
              {copy.propose}
            </button>
          </>
        )}
      </section>

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

              {memory.consolidation_sources.length > 0 && (
                <div className="memory-evidence">
                  <strong>{copy.sourceMemories}</strong>
                  {memory.consolidation_sources.map((source) => (
                    <blockquote
                      key={`${memory.memory_id}-${source.source_memory_id}`}
                      dir="auto"
                    >
                      <p>{source.content}</p>
                      <footer>
                        {copy.sourceMemory}:{' '}
                        <bdi dir="ltr">{source.source_memory_id}</bdi>
                        {' · '}
                        {copy.version}:{' '}
                        <bdi dir="ltr">{source.source_memory_version}</bdi>
                        {' · '}
                        {copy.session}:{' '}
                        <bdi dir="ltr">{source.source_session_id}</bdi>
                        {' · '}
                        {copy[
                          source.relationship_type as
                            | 'related'
                            | 'repeated'
                            | 'potential_contradiction'
                        ] ?? copy.related}
                      </footer>
                    </blockquote>
                  ))}
                </div>
              )}

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
