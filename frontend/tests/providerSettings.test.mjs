import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildApiBaseUrl,
  parseApiBaseUrl,
} from '../src/lib/providerSettings.js'

test('builds a loopback provider URL with a configurable port and path', () => {
  assert.equal(
    buildApiBaseUrl('127.0.0.1', '12345', '/v1'),
    'http://127.0.0.1:12345/v1',
  )
})

test('accepts the complete valid port range', () => {
  assert.equal(buildApiBaseUrl('localhost', 1, 'v1'), 'http://localhost:1/v1')
  assert.equal(
    buildApiBaseUrl('localhost', 65535, 'v1'),
    'http://localhost:65535/v1',
  )
})

test('rejects invalid ports and host URL injection', () => {
  for (const port of ['0', '65536', '12.5', '']) {
    assert.throws(() => buildApiBaseUrl('127.0.0.1', port, '/v1'))
  }
  assert.throws(() =>
    buildApiBaseUrl('user@127.0.0.1', '8080', '/v1'),
  )
})

test('parses editable fields without losing an IPv6 loopback host', () => {
  assert.deepEqual(
    parseApiBaseUrl('http://[::1]:8080/v1'),
    {
      protocol: 'http',
      host: '::1',
      port: 8080,
      apiBasePath: '/v1',
    },
  )
})

test('rejects API base URLs containing credentials or query values', () => {
  assert.throws(() =>
    parseApiBaseUrl('http://user:password@localhost:8080/v1'),
  )
  assert.throws(() => parseApiBaseUrl('http://localhost:8080/v1?token=x'))
})

test('requires HTTPS for non-loopback provider endpoints', () => {
  assert.throws(
    () => buildApiBaseUrl('models.example.test', 8080, '/v1', 'http'),
    /require HTTPS/,
  )
  assert.throws(
    () => parseApiBaseUrl('http://192.168.1.25:8000/v1'),
    /require HTTPS/,
  )
  assert.equal(
    buildApiBaseUrl('models.example.test', 8080, '/v1', 'https'),
    'https://models.example.test:8080/v1',
  )
  assert.equal(
    buildApiBaseUrl('localhost', 8080, '/v1'),
    'http://localhost:8080/v1',
  )
})
