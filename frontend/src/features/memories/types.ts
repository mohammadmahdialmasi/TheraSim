export interface MemoryEvidence {
  message_id: string
  relationship_type: string
  start_offset: number | null
  end_offset: number | null
  excerpt: string | null
}

export interface MemoryRecord {
  memory_id: string
  run_id: string
  source_session_id: string | null
  memory_type: string
  information_class: string
  content: string
  confidence: number | null
  status: string
  memory_version: number
  memory_scope: string
  supersedes_memory_id: string | null
  evidence: MemoryEvidence[]
  created_at: string
  updated_at: string
}

export interface ApiEnvelope<T> {
  data: T
}

export interface MemoryReviewResponse {
  data: MemoryRecord
  review: {
    review_id: string
    memory_id: string
    decision: 'accepted' | 'rejected'
    reviewer_id: string
    rationale: string
    reviewed_at: string
  }
}
