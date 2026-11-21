export function getSupportPreviewUrl(language) {
  return `/api/v1/support/preview?language=${encodeURIComponent(language)}`
}

export function formatSupportPreview(preview, language) {
  if (
    preview === null
    || typeof preview !== 'object'
    || preview.language !== language
  ) {
    throw new Error('Support preview language does not match the interface.')
  }

  return JSON.stringify(preview, null, 2)
}

export function createSupportExportRequest(language, token) {
  return {
    method: 'POST',
    headers: {
      Accept: 'application/zip',
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ confirmed: true, language }),
  }
}

export function getSupportArchiveFilename(contentDisposition, language) {
  const filenameMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
  return filenameMatch?.[1]
    ?? (language === 'fa'
      ? 'TheraSim-support-diagnostics-fa.zip'
      : 'TheraSim-support-diagnostics.zip')
}

export async function parseSupportArchiveResponse(response, language) {
  if (!response.ok) {
    throw new Error('Support diagnostics export failed.')
  }

  return {
    blob: await response.blob(),
    filename: getSupportArchiveFilename(
      response.headers.get('Content-Disposition') ?? '',
      language,
    ),
  }
}
