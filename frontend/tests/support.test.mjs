import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createSupportExportRequest,
  formatSupportPreview,
  getSupportPreviewUrl,
  parseSupportArchiveResponse,
} from '../src/lib/supportDiagnostics.js'

const previewFor = (language) => ({
  schema_version: 1,
  generated_at: '2026-11-17T19:00:00+00:00',
  language,
  application: {
    name: 'TheraSim API',
    version: '0.3.0',
    backend_version: '0.3.0',
    frontend_version: '0.3.0',
  },
  runtime: {
    operating_system: 'Windows',
    operating_system_release: 'synthetic-release',
    architecture: 'x64',
    python_version: '3.13.0',
  },
  service: {
    api: 'FastAPI',
    health: 'ok',
    database_schema_versions: { operational: '1', restricted: '1' },
  },
  model_provider: {
    active_provider_type: 'ollama',
    model_identifier: null,
    connection_test_results: {},
  },
  privacy: {
    user_records_included: false,
    transcripts_included: false,
    case_content_included: false,
    logs_included: false,
    credentials_included: false,
    personal_information_included: false,
    provider_endpoints_included: false,
  },
})

for (const language of ['en', 'fa']) {
  test(`${language} support preview displays the matching sanitized report`, () => {
    const preview = previewFor(language)

    assert.equal(
      getSupportPreviewUrl(language),
      `/api/v1/support/preview?language=${language}`,
    )
    const displayedPreview = formatSupportPreview(preview, language)
    assert.deepEqual(JSON.parse(displayedPreview), preview)
    assert.match(displayedPreview, /"language":\s*"[^"]+"/)
    assert.match(displayedPreview, /"operating_system":\s*"Windows"/)
    assert.match(displayedPreview, /"health":\s*"ok"/)
  })
}

test('support preview refuses a report for a different interface language', () => {
  assert.throws(
    () => formatSupportPreview(previewFor('fa'), 'en'),
    /language does not match/,
  )
})

for (const [language, expectedFilename] of [
  ['en', 'TheraSim-support-diagnostics.zip'],
  ['fa', 'TheraSim-support-diagnostics-fa.zip'],
]) {
  test(`${language} support download uses the language-specific server filename`, async () => {
    const request = createSupportExportRequest(language, 'test-token')
    assert.equal(request.method, 'POST')
    assert.equal(request.headers.Authorization, 'Bearer test-token')
    assert.deepEqual(JSON.parse(request.body), {
      confirmed: true,
      language,
    })

    const response = new Response(new Blob(['synthetic archive']), {
      status: 200,
      headers: {
        'Content-Disposition': `attachment; filename="${expectedFilename}"`,
      },
    })
    const archive = await parseSupportArchiveResponse(response, language)

    assert.equal(archive.filename, expectedFilename)
    assert.equal(await archive.blob.text(), 'synthetic archive')
  })
}
