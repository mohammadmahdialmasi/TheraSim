import { request } from '../../lib/api'

export interface RunAnalyticsSnapshot {
  data_scope: string
  run_id: string
  generated_at: string
  time_range_start: string | null
  time_range_end: string | null
  sessions: {
    session_id: string
    session_number: number
    status: string
    created_at: string
    ended_at: string | null
    transcript_hash: string | null
  }[]
  events: {
    event_id: string
    session_id: string | null
    event_type: string
    event_status: string
    created_at: string
  }[]
  event_counts: Record<string, number>
  memories: {
    memory_id: string
    source_session_id: string | null
    memory_type: string
    status: string
    memory_version: number
    created_at: string
  }[]
  memory_counts: Record<string, number>
  state_transitions: {
    transition_id: string
    session_id: string
    event_id: string | null
    variable_name: string
    validation_status: string
    confidence: number | null
    created_at: string
  }[]
  transition_counts: Record<string, number>
  plan_revisions: {
    revision_id: string
    revision_number: number
    status: string
    created_at: string
  }[]
  current_plan: {
    revision_id: string
    revision_number: number
    goal_status_counts: Record<string, number>
  } | null
  evaluations: {
    evaluation_id: string
    evaluation_scope: string
    session_id: string | null
    rubric_id: string
    rubric_version: string
    rubric_version_id: string
    rubric_content_hash: string | null
    status: string
    stale: boolean
    created_at: string
  }[]
  competency_trajectories: {
    rubric_id: string
    rubric_version: string
    rubric_version_id: string
    rubric_content_hash: string | null
    competency_id: string
    observations: {
      evaluation_id: string
      evaluation_revision: number
      evaluation_status: string
      session_id: string
      session_number: number
      rating_code: string
      confidence: 'low' | 'medium' | 'high' | null
      evidence_message_ids: string[]
      review_decisions: {
        review_id: string
        reviewer_user_id: string
        decision: 'accepted' | 'revision_requested'
        created_at: string
      }[]
    }[]
    missing_completed_sessions: {
      session_id: string
      session_number: number
      reason: string
    }[]
    summary: {
      observed_session_count: number
      evaluable_count: number
      non_evaluable_count: number
      missing_count: number
      evidence_coverage_rate: number | null
      confidence_distribution: Record<string, number>
      review_decision_counts: Record<string, number>
      raw_rating_code_change: {
        first_session_id: string
        first_session_number: number
        first_rating_code: string
        last_session_id: string
        last_session_number: number
        last_rating_code: string
        delta: number
      } | null
    }
  }[]
  limitations: string[]
}

export function getRunAnalytics(runId: string) {
  return request<RunAnalyticsSnapshot>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/analytics`,
  )
}
