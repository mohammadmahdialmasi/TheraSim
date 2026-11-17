export interface TreatmentPlanDefinition {
  initial_formulation: string
  goals: {
    goal_id: string
    description: string
    relevant_processes: string[]
    status: 'active' | 'paused' | 'achieved'
    progress_notes: string
  }[]
  objectives: {
    objective_id: string
    goal_id: string
    description: string
    status: 'active' | 'paused' | 'achieved'
    progress_indicator: string
  }[]
  interventions: {
    intervention_id: string
    description: string
    objective_ids: string[]
    status: 'proposed' | 'active' | 'paused' | 'completed'
  }[]
  outcome_measures: string[]
  review_after_session: number | null
}

export interface TreatmentPlanRevision {
  revision_id: string
  plan_id: string
  run_id: string
  revision_number: number
  based_on_revision_number: number | null
  modality: string
  protocol_id: string
  protocol_version: string
  definition: TreatmentPlanDefinition
  evidence: { kind: string; source_id: string }[]
  rationale: string
  status: string
  created_at: string
  review: {
    review_id: string
    revision_id: string
    run_id: string
    decision: string
    reviewer_id: string
    rationale: string
    reviewed_at: string
  } | null
}

export interface TreatmentPlanListResponse {
  current: TreatmentPlanRevision | null
  revisions: TreatmentPlanRevision[]
}

export interface PlanAdaptationEvidence {
  event_id: string
  event_type: string
  session_id: string | null
  summary: string
}

export interface PlanAdaptationGuidance {
  status: 'no_plan' | 'no_new_evidence' | 'insufficient_evidence' | 'actionable'
  recommendation: string
  rationale: string
  evidence: PlanAdaptationEvidence[]
}
