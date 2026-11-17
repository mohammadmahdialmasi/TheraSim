export interface ApiEnvelope<T> {
  data: T
}

export interface Pagination {
  limit: number
  offset: number
  total: number
}

export interface CaseCatalogItem {
  case_id: string
  case_code: string
  display_name: string
  modality: string
  available_languages: string[]
  status: string
}

export interface CasePresentation {
  age: number | null
  occupation: string | null
  presenting_concerns: string[]
  initial_disclosure: string | null
}

export interface CaseVersion {
  case_version_id: string
  version_number: string
  modality: string
  language: string
  presentation: CasePresentation
}

export interface CaseDetail {
  case_id: string
  case_code: string
  display_name: string
  status: string
  versions: CaseVersion[]
}

export type RunStatus =
  | 'initialized'
  | 'active'
  | 'interrupted'
  | 'completed'
  | 'failed'

export interface SimulationRun {
  run_id: string
  case_id: string
  case_version_id: string
  modality: string
  language: string
  status: RunStatus
  session_count: number
  protocol_id: string
  protocol_version: string
  session_planning_policy: string
  evaluation_rubric_id: string
  evaluation_rubric_version: string
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface SimulationSession {
  session_id: string
  run_id: string
  session_number: number
  status: string
  started_at: string | null
  ended_at: string | null
  transcript_version: number
}

export interface SessionMessage {
  message_id: string
  sequence_number: number
  role: string
  content: string
  created_at: string
}

export interface MessageListResponse {
  data: SessionMessage[]
  pagination: Pagination
}

export interface InteractionSubmitResponse {
  status: 'processing' | 'completed'
  session_id: string
  request_id: string
  attempt_number: number
  therapist_message_id: string
  therapist_content: string
  patient_message_id: string | null
  patient_content: string | null
}

export interface InteractionRequestStatus {
  request_id: string
  session_id: string
  processing_status: 'in_progress' | 'completed' | 'failed'
  therapist_message_id: string | null
  patient_message_id: string | null
  error_code: string | null
  created_at: string
  completed_at: string | null
}
