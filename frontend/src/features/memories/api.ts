import { request } from '../../lib/api'

import type {
  ApiEnvelope,
  MemoryRecord,
  MemoryReviewResponse,
} from './types'

export function listMemoryCandidates(runId: string) {
  return request<ApiEnvelope<MemoryRecord[]>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/memories?status=requires_review`,
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
