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
  consolidation_sources: MemoryConsolidationSource[]
  created_at: string
  updated_at: string
}

export interface MemoryConsolidationSource {
  source_memory_id: string
  source_memory_version: number
  relationship_type: string
  content: string
  source_session_id: string
}

export interface MemoryConsolidationSuggestion {
  source_memory_ids: string[]
  relationship_type: string
  similarity: number
  sources: MemoryConsolidationSource[]
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

export interface MemoryConsolidationResponse {
  data: MemoryRecord
}
