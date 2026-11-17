import { request } from '../../lib/api'

import type {
  ApiEnvelope,
  MemoryConsolidationResponse,
  MemoryConsolidationSuggestion,
  MemoryRecord,
  MemoryReviewResponse,
} from './types'

export function listMemoryCandidates(runId: string) {
  return request<ApiEnvelope<MemoryRecord[]>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/memories?status=requires_review`,
  )
}

export function listMemoryConsolidationSuggestions(runId: string) {
  return request<ApiEnvelope<MemoryConsolidationSuggestion[]>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/memories/consolidation-suggestions`,
  )
}

export function proposeMemoryConsolidation(
  runId: string,
  sourceMemoryIds: string[],
  content: string,
) {
  return request<MemoryConsolidationResponse>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/memories/consolidations`,
    {
      method: 'POST',
      body: JSON.stringify({
        source_memory_ids: sourceMemoryIds,
        content,
      }),
    },
  )
}

export function reviewMemoryCandidate(
  runId: string,
  memoryId: string,
  decision: 'accepted' | 'rejected',
  rationale: string,
) {
  return request<MemoryReviewResponse>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/memories/${encodeURIComponent(memoryId)}/review`,
    {
      method: 'POST',
      body: JSON.stringify({ decision, rationale }),
    },
  )
}
