import { request } from '../../lib/api'

import type { EventListResponse, EventReviewResponse } from './types'

export function listPendingEvents(runId: string) {
  return request<EventListResponse>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/events?status=requires_review`,
  )
}

export function reviewEvent(
  runId: string,
  eventId: string,
  decision: 'accepted' | 'rejected',
  rationale: string,
) {
  return request<EventReviewResponse>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/events/${encodeURIComponent(eventId)}/review`,
    {
      method: 'POST',
      body: JSON.stringify({ decision, rationale }),
    },
  )
}
