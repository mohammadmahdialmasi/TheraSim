export type ProviderName = 'ollama' | 'lm_studio' | 'llama_cpp' | 'custom'

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

export interface ProviderEndpointSettings {
  name: ProviderName
  base_url: string
  host: string
  port: number
  api_base_path: string
  model: string
  patient_model: string
  evaluator_model: string
  api_key_configured: boolean
}

export interface ProviderSettingsResponse {
  active_provider: ProviderName
  local_only: boolean
  providers: ProviderEndpointSettings[]
  restart_required?: boolean
}

export interface ProviderConnectionTestResponse {
  provider: ProviderName
  connected: boolean
  success: boolean
  status:
    | 'connected'
    | 'model_available'
    | 'model_required'
    | 'model_unavailable'
    | 'authentication_failed'
    | 'timeout'
    | 'unavailable'
    | 'provider_error'
    | 'remote_blocked'
  model_listing_supported: boolean
  model_available: boolean | null
  models: ModelInfo[]
}

export interface UpdateAsset {
  name: string
  download_url: string
  sha256: string
  size_bytes: number | null
  checksum_source: string
}

export interface UpdateReleaseMetadata {
  status: 'available' | 'unavailable'
  version?: string
  published_at?: string
  notes?: string
  release_url?: string
  update_available?: boolean
  assets?: UpdateAsset[]
  message?: string
}

export interface UpdateMetadataResponse {
  current_version: string
  source_checkout: {
    available: boolean
    branch?: string
    commit?: string
    dirty?: boolean
    message?: string
  } | null
  release: UpdateReleaseMetadata
  automatic_installation: false
}

export interface ModelInfo {
  id: string
  owned_by: string
}

export interface ModelListResponse {
  provider: ProviderName
  models: ModelInfo[]
}

export interface HardwareGpu {
  vendor: string
  name: string
  total_vram_bytes: number
  available_vram_bytes: number
}

export interface HardwareAssessment {
  operating_system: {
    name: string
    version: string
    architecture: string
  }
  cpu: {
    name: string | null
    logical_processors: number | null
  }
  memory: {
    total_bytes: number | null
    available_bytes: number | null
  }
  gpus: HardwareGpu[]
  gpu_detection: string
  resource_profile: {
    system_ram_tier: string
    detected_nvidia_gpu_vram_tiers: string[]
    profile_is_a_compatibility_estimate: true
    recommendation: string
  }
  disk: {
    scope: string
    total_bytes: number | null
    free_bytes: number | null
  }
  ollama: {
    cli_available: boolean
    server_available: boolean | null
    server_version: string | null
    server_status: string
  }
  recommendation_status: string
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