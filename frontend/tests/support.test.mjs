import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const apiSource = readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8')
const appSource = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')

test('support preview fetches the backend with the selected language', () => {
  assert.match(apiSource, /\/api\/v1\/support\/preview\?language=/)
  assert.match(appSource, /getSupportPreview\(language\)/)
})

test('support export sends confirmed language and uses the server filename', () => {
  assert.match(apiSource, /JSON\.stringify\(\{ confirmed: true, language \}\)/)
  assert.match(apiSource, /TheraSim-support-diagnostics-fa\.zip/)
  assert.match(appSource, /download\.download = archive\.filename/)
})
