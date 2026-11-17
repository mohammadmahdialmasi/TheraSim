import { request } from '../../lib/api'

import type {
  ApiEnvelope,
  CaseCatalogItem,
  CaseDetail,
  InteractionRequestStatus,
  InteractionSubmitResponse,
  MessageListResponse,
  SimulationRun,
  SimulationSession,
} from './types'

export async function listCases() {
  return request<{
    data: CaseCatalogItem[]
    pagination: { limit: number; offset: number; total: number }
  }>('/api/v1/cases?limit=100&offset=0')
}

export async function getCaseDetail(caseId: string) {
  return request<ApiEnvelope<CaseDetail>>(
    `/api/v1/cases/${encodeURIComponent(caseId)}`,
  )
}

export async function listSimulationRuns() {
  return request<ApiEnvelope<SimulationRun[]>>(
    '/api/v1/simulation-runs?limit=100&offset=0',
  )
}

export async function createSimulationRun(payload: {
  case_id: string
  case_version_id: string
  modality: string
  language: string
  session_planning_policy: string
}) {
  return request<ApiEnvelope<SimulationRun>>(
    '/api/v1/simulation-runs',
    {
      method: 'POST',
      body: JSON.stringify({
        ...payload,
        protocol_id: 'ACT_EDUCATIONAL_SIMULATION',
        protocol_version: '0.1',
        evaluation_rubric_id: 'ACT_RUBRIC_V0',
        evaluation_rubric_version: '0.2',
      }),
    },
  )
}

async function runAction(runId: string, action: string) {
  return request<ApiEnvelope<SimulationRun>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/${action}`,
    { method: 'POST' },
  )
}

export function startSimulationRun(runId: string) {
  return runAction(runId, 'start')
}

export function interruptSimulationRun(runId: string) {
  return runAction(runId, 'interrupt')
}

export function resumeSimulationRun(runId: string) {
  return runAction(runId, 'resume')
}

export function completeSimulationRun(runId: string) {
  return runAction(runId, 'complete')
}

export async function listRunSessions(runId: string) {
  return request<ApiEnvelope<SimulationSession[]>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/sessions`,
  )
}

export async function createSimulationSession(runId: string) {
  return request<ApiEnvelope<SimulationSession>>(
    `/api/v1/simulation-runs/${encodeURIComponent(runId)}/sessions`,
    {
      method: 'POST',
      body: JSON.stringify({}),
    },
  )
}

export async function listSessionMessages(
  sessionId: string,
  limit = 200,
  offset = 0,
) {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  })

  return request<MessageListResponse>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/messages?${query}`,
  )
}

export async function completeSimulationSession(sessionId: string) {
  return request<ApiEnvelope<{
    session_id: string
    status: 'completed'
    transcript_version: number
    ended_at: string | null
  }>>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/complete`,
    {
      method: 'POST',
      body: JSON.stringify({ completion_reason: 'normal' }),
    },
  )
}

export async function submitTherapistMessage(
  sessionId: string,
  content: string,
  idempotencyKey: string,
) {
  return request<InteractionSubmitResponse>(
    `/api/v1/sessions/${encodeURIComponent(sessionId)}/messages`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({ content }),
    },
    300000,
  )
}

export async function getInteractionRequestStatus(requestId: string) {
  return request<ApiEnvelope<InteractionRequestStatus>>(
    `/api/v1/interaction-requests/${encodeURIComponent(requestId)}`,
  )
}
