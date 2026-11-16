export type ProviderName = 'ollama' | 'lm_studio'

export type ViewKey =
  | 'dashboard'
  | 'studio'
  | 'therapies'
  | 'sessions'
  | 'scenarios'
  | 'evaluation'
  | 'settings'

export type ConnectionState = 'checking' | 'online' | 'offline'

export interface HealthResponse {
  status: string
  service: string
  version: string
}

export interface ProviderInfo {
  name: ProviderName
  base_url: string
  default_model: string | null
  is_active: boolean
}

export interface ProviderCatalog {
  active_provider: ProviderName
  providers: ProviderInfo[]
}

export interface ModelInfo {
  id: string
  owned_by: string
}

export interface ModelListResponse {
  provider: ProviderName
  models: ModelInfo[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  provider: ProviderName
  model: string
  message: {
    role: string
    content: string
  }
  finish_reason?: string | null
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  } | null
}

export interface TherapyModule {
  id: string
  code: string
  name: string
  description: string
  status: 'designing' | 'planned' | 'available'
  version?: string
}