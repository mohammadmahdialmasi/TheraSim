import type {
  ChatResponse,
  HealthResponse,
  ModelListResponse,
  ProviderCatalog,
  ProviderName,
} from '../types'
import { clearAuthToken, getAuthToken } from './authSession'

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
    `/api/v1/support/preview?language=${encodeURIComponent(language)}`,
  )
}

export async function downloadSupportArchive(
  language: 'en' | 'fa',
): Promise<{ blob: Blob; filename: string }> {
  const token = getAuthToken()
  const response = await fetch('/api/v1/support/export', {
    method: 'POST',
    headers: {
      Accept: 'application/zip',
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ confirmed: true, language }),
  })
  if (!response.ok) {
    if (response.status === 401) {
      clearAuthToken()
      window.dispatchEvent(new Event('therasim:auth-expired'))
    }
    throw new Error('Support diagnostics export failed.')
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i)
  const filename = filenameMatch?.[1]
    ?? (language === 'fa'
      ? 'TheraSim-support-diagnostics-fa.zip'
      : 'TheraSim-support-diagnostics.zip')
  return { blob, filename }
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
