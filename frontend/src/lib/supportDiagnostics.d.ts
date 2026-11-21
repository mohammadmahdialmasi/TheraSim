export type SupportLanguage = 'en' | 'fa'

export interface SupportPreview {
  language: SupportLanguage
  [key: string]: unknown
}

export function getSupportPreviewUrl(language: SupportLanguage): string
export function formatSupportPreview(
  preview: SupportPreview,
  language: SupportLanguage,
): string
export function createSupportExportRequest(
  language: SupportLanguage,
  token?: string | null,
): RequestInit
export function getSupportArchiveFilename(
  contentDisposition: string,
  language: SupportLanguage,
): string
export function parseSupportArchiveResponse(
  response: Response,
  language: SupportLanguage,
): Promise<{ blob: Blob; filename: string }>
