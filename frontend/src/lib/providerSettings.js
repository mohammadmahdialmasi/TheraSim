/**
 * Validate and compose an HTTP(S) OpenAI-compatible API base URL.
 * @param {string} host
 * @param {string | number} portValue
 * @param {string} apiBasePath
 * @param {'http' | 'https'} [protocol]
 */
export function buildApiBaseUrl(
  host,
  portValue,
  apiBasePath,
  protocol = 'http',
) {
  const portText = String(portValue).trim()
  if (!/^\d+$/.test(portText)) {
    throw new Error('Port must be a whole number between 1 and 65535.')
  }
  const port = Number(portText)
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('Port must be a whole number between 1 and 65535.')
  }

  const normalizedHost = host.trim().replace(/^\[|\]$/g, '')
  if (!normalizedHost || /[\\/@?#\s]/.test(normalizedHost)) {
    throw new Error('Enter a hostname or IP address without a URL path.')
  }
  const authorityHost = normalizedHost.includes(':')
    ? `[${normalizedHost}]`
    : normalizedHost
  const path = apiBasePath.trim()
  if (/[?#]/.test(path)) {
    throw new Error('API base path must not contain a query or fragment.')
  }

  const url = new URL(
    `${protocol}://${authorityHost}:${port}${path.startsWith('/') ? path : `/${path}`}`,
  )
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('Only HTTP and HTTPS provider URLs are supported.')
  }
  if (url.protocol === 'http:' && !isLoopbackHostname(url.hostname)) {
    throw new Error('Non-loopback HTTP endpoints require HTTPS.')
  }
  return url.toString().replace(/\/+$/, '')
}

/**
 * Parse an API base URL into editable connection fields.
 * @param {string} value
 */
export function parseApiBaseUrl(value) {
  const url = new URL(value)
  if (
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error('Enter a valid HTTP(S) API base URL.')
  }
  if (url.protocol === 'http:' && !isLoopbackHostname(url.hostname)) {
    throw new Error('Non-loopback HTTP endpoints require HTTPS.')
  }
  return {
    protocol: /** @type {'http' | 'https'} */ (url.protocol.slice(0, -1)),
    host: url.hostname.replace(/^\[|\]$/g, ''),
    port: Number(url.port || (url.protocol === 'https:' ? 443 : 80)),
    apiBasePath: url.pathname.replace(/\/+$/, ''),
  }
}

function isLoopbackHostname(hostname) {
  const normalized = hostname
    .replace(/^\[|\]$/g, '')
    .replace(/\.$/, '')
    .toLowerCase()
  if (normalized === 'localhost' || normalized === '::1') return true

  const octets = normalized.split('.').map(Number)
  return octets.length === 4
    && octets[0] === 127
    && octets.every((octet) => Number.isInteger(octet) && octet >= 0 && octet <= 255)
}
