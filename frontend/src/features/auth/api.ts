import { request } from '../../lib/api'

export interface AuthenticatedUser {
  user_id: string
  reviewer_name: string
}

export interface AuthSession {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: AuthenticatedUser
}

export function getAuthStatus() {
  return request<{ data: { initialized: boolean } }>(
    '/api/v1/auth/status',
  )
}

export function initializeLocalAccount(
  reviewerName: string,
  password: string,
) {
  return request<{ data: AuthSession }>(
    '/api/v1/auth/initialize',
    {
      method: 'POST',
      body: JSON.stringify({
        reviewer_name: reviewerName,
        password,
      }),
    },
  )
}

export function loginLocalAccount(password: string) {
  return request<{ data: AuthSession }>(
    '/api/v1/auth/login',
    {
      method: 'POST',
      body: JSON.stringify({ password }),
    },
  )
}

export function getCurrentUser() {
  return request<{ data: AuthenticatedUser }>('/api/v1/auth/me')
}

export function logoutLocalAccount() {
  return request<{ data: { logged_out: boolean } }>(
    '/api/v1/auth/logout',
    { method: 'POST' },
  )
}
