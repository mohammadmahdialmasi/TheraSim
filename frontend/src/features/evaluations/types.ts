export interface EvaluationEvidence {
  evaluation_item_id: string
  message_id: string
  session_id: string | null
  session_number: number | null
  source_role: string | null
  source_message_content: string | null
  evidence_role: string
  start_offset: number | null
  end_offset: number | null
  evidence_excerpt: string | null
  evidence_note: string | null
}

export interface EvaluationSessionScope {
  session_id: string
  session_number: number
  transcript_sha256: string
}

export interface EvaluationItem {
  evaluation_item_id: string
  evaluation_id: string
  competency_id: string
  rating_code: string
  justification: string | null
  alternative_response: string | null
  limitations: string | null
  uncertainty_notes: string | null
  confidence: string | null
  strengths: string[]
  missing_evidence: string[]
  evidence: EvaluationEvidence[]
}

export interface EvaluationReview {
  review_id: string
  evaluation_id: string
  review_number: number
  reviewer_user_id: string
  reviewer_name: string
  decision: 'accepted' | 'revision_requested'
  feedback: string
  created_at: string
}

export interface EvaluationReport {
  evaluation_id: string
  run_id: string
  session_id: string | null
  evaluation_scope: string
  rubric_id: string
  rubric_version: string
  evaluation_revision: number
  status: string
  created_at: string
  stale: boolean
  overall_summary: string | null
  experimental: boolean
  human_review_required: boolean
  review_status: 'pending' | 'accepted' | 'revision_requested'
  reviews: EvaluationReview[]
  evaluator_model: string | null
  evaluator_prompt_version: string | null
  rubric_content_sha256: string | null
  session_scope: EvaluationSessionScope[]
  limitations: string[]
  items: EvaluationItem[]
}
