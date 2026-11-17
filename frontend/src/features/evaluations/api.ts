import { request } from '../../lib/api'

import type { ApiEnvelope } from '../sessions/types'
import type { EvaluationReport, EvaluationReview } from './types'

export function listSessionEvaluations(sessionId: string) {
  return request<ApiEnvelope<EvaluationReport[]>>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/evaluations`,
  )
}

export function createSessionEvaluation(sessionId: string) {
  const query = new URLSearchParams({
    rubric_id: 'ACT_RUBRIC_V0',
    rubric_version: '0.2',
  })

  return request<ApiEnvelope<EvaluationReport>>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/evaluations?${query}`,
    { method: 'POST' },
    300000,
  )
}

export function listRunEvaluations(runId: string) {
  return request<ApiEnvelope<EvaluationReport[]>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/evaluations`,
  )
}

export function createRunEvaluation(runId: string) {
  const query = new URLSearchParams({
    rubric_id: 'ACT_LONGITUDINAL_RUBRIC_V0',
    rubric_version: '0.2',
  })

  return request<ApiEnvelope<EvaluationReport>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/evaluations?${query}`,
    { method: 'POST' },
    300000,
  )
}

export function addEvaluationReview(
  evaluationId: string,
  input: {
    decision: EvaluationReview['decision']
    feedback: string
  },
) {
  return request<{ data: EvaluationReview }>(
    `/api/v1/evaluations/${encodeURIComponent(evaluationId)}/reviews`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}
