export interface EventEvidence {
  message_id: string
  role: string
  excerpt: string | null
  annotation: string | null
}

export interface BehavioralEvent {
  event_id: string
  run_id: string
  session_id: string | null
  sequence_number: number
  event_type: string
  actor: string
  payload: Record<string, unknown>
  extraction_method: string
  extractor_version: string | null
  event_status: string
  created_at: string
  validated_at: string | null
  evidence: EventEvidence[]
}

export interface EventListResponse {
  data: BehavioralEvent[]
}

export interface EventReviewResponse {
  data: BehavioralEvent
  review: {
    review_id: string
    event_id: string
    run_id: string
    decision: 'accepted' | 'rejected'
    reviewer_id: string
    rationale: string
    reviewed_at: string
  }
}
