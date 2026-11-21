export interface ParsedApiBaseUrl {
  protocol: 'http' | 'https'
  host: string
  port: number
  apiBasePath: string
}

export function buildApiBaseUrl(
  host: string,
  portValue: string | number,
  apiBasePath: string,
  protocol?: 'http' | 'https',
): string

export function parseApiBaseUrl(value: string): ParsedApiBaseUrl
