import { request } from '../../lib/api'

import type {
  PlanAdaptationGuidance,
  TreatmentPlanDefinition,
  TreatmentPlanListResponse,
  TreatmentPlanRevision,
} from './types'

export function getTreatmentPlan(runId: string) {
  return request<TreatmentPlanListResponse>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/treatment-plan`,
  )
}

export function getTreatmentPlanAdaptationGuidance(runId: string) {
  return request<{ data: PlanAdaptationGuidance }>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/treatment-plan/adaptation-guidance`,
  )
}

export function createInitialTreatmentPlan(
  runId: string,
  definition: TreatmentPlanDefinition,
) {
  return request<{ data: TreatmentPlanRevision }>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/treatment-plan`,
    {
      method: 'POST',
      body: JSON.stringify({ definition, rationale: 'Initial treatment plan' }),
    },
  )
}
export function proposeTreatmentPlanRevision(
  runId: string,
  revisionNumber: number,
  definition: TreatmentPlanDefinition,
  eventIds: string[],
  rationale: string,
) {
  return request<{ data: TreatmentPlanRevision }>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/treatment-plan/revisions`,
    {
      method: 'POST',
      body: JSON.stringify({
        expected_revision_number: revisionNumber,
        definition,
        evidence: eventIds.map((eventId) => ({
          kind: 'event',
          source_id: eventId,
        })),
        rationale,
      }),
    },
  )
}

export function reviewTreatmentPlanRevision(
  runId: string,
  revisionId: string,
  decision: 'accepted' | 'rejected',
  rationale: string,
) {
  return request(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/treatment-plan/revisions/${encodeURIComponent(revisionId)}/review`,
    {
      method: 'POST',
      body: JSON.stringify({ decision, rationale }),
    },
  )
}
