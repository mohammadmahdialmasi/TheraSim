import type {
  ChatResponse,
  HealthResponse,
  HardwareAssessment,
  ModelListResponse,
  ProviderCatalog,
  ProviderConnectionTestResponse,
  ProviderSettingsResponse,
  ProviderName,
  UpdateMetadataResponse,
} from '../types'
import { clearAuthToken, getAuthToken } from './authSession'
import {
  createSupportExportRequest,
  getSupportPreviewUrl,
  parseSupportArchiveResponse,
} from './supportDiagnostics'

export async function request<T>(
  url: string,
  options: RequestInit = {},
  timeoutMs = 20000,
): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)

  try {
    const token = getAuthToken()
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.body
          ? { 'Content-Type': 'application/json' }
          : {}),
        ...options.headers,
      },
    })

    const payload: unknown = await response.json().catch(() => null)

    if (!response.ok) {
      if (
        response.status === 401 &&
        !url.includes('/api/v1/auth/login') &&
        !url.includes('/api/v1/auth/initialize')
      ) {
        clearAuthToken()
        window.dispatchEvent(new Event('therasim:auth-expired'))
      }
      let message = `Request failed (${response.status})`

      if (
        payload !== null &&
        typeof payload === 'object' &&
        'detail' in payload &&
        typeof payload.detail === 'string'
      ) {
        message = payload.detail
      }

      throw new Error(message)
    }

    return payload as T
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error('The local model request timed out.', { cause: error })
    }

    throw error
  } finally {
    window.clearTimeout(timer)
  }
}

export function getHealth() {
  return request<HealthResponse>('/health')
}

export function getProviders() {
  return request<ProviderCatalog>('/api/v1/llm/providers')
}

export function getModels(provider: ProviderName) {
  return request<ModelListResponse>(
    `/api/v1/llm/models/${provider}`,
  )
}

export function getHardwareAssessment() {
  return request<HardwareAssessment>('/api/v1/llm/hardware')
}

export function getProviderSettings() {
  return request<ProviderSettingsResponse>(
    '/api/v1/llm/providers/settings',
  )
}

export function saveProviderSettings(
  payload: {
    active_provider: ProviderName
    local_only: boolean
    confirm_remote_endpoints: boolean
    providers: Array<{
      name: ProviderName
      base_url: string
      model: string
      patient_model: string
      evaluator_model: string
      api_key?: string
      clear_api_key?: boolean
    }>
  },
) {
  return request<ProviderSettingsResponse>(
    '/api/v1/llm/providers/settings',
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export function testProviderConnection(
  provider: ProviderName,
  baseUrl: string,
  model: string,
  apiKey?: string,
) {
  return request<ProviderConnectionTestResponse>(
    `/api/v1/llm/providers/${provider}/test`,
    {
      method: 'POST',
      body: JSON.stringify({
        base_url: baseUrl,
        ...(model ? { model } : {}),
        ...(apiKey !== undefined ? { api_key: apiKey } : {}),
      }),
    },
    30000,
  )
}

export function getUpdateMetadata() {
  return request<UpdateMetadataResponse>(
    '/api/v1/updates/check',
    {},
    10000,
  )
}

export interface SupportPreviewResponse {
  language: 'en' | 'fa'
  application: Record<string, unknown>
  runtime: Record<string, unknown>
  service: Record<string, unknown>
  model_provider: Record<string, unknown>
  privacy: Record<string, boolean>
  [key: string]: unknown
}

export function getSupportPreview(language: 'en' | 'fa') {
  return request<SupportPreviewResponse>(
    getSupportPreviewUrl(language),
  )
}

export async function downloadSupportArchive(
  language: 'en' | 'fa',
): Promise<{ blob: Blob; filename: string }> {
  const token = getAuthToken()
  const response = await fetch(
    '/api/v1/support/export',
    createSupportExportRequest(language, token),
  )
  if (!response.ok) {
    if (response.status === 401) {
      clearAuthToken()
      window.dispatchEvent(new Event('therasim:auth-expired'))
    }
    throw new Error('Support diagnostics export failed.')
  }
  return parseSupportArchiveResponse(response, language)
}

export function sendChat(
  provider: ProviderName,
  model: string,
  messages: Array<{
    role: 'user' | 'assistant'
    content: string
  }>,
  options: {
    temperature?: number
    maxTokens?: number
  } = {},
) {
  return request<ChatResponse>(
    '/api/v1/llm/chat',
    {
      method: 'POST',
      body: JSON.stringify({
        provider,
        model,
        messages,
        temperature: options.temperature ?? 0.3,
        max_tokens: options.maxTokens ?? 1024,
      }),
    },
    300000,
  )
}
