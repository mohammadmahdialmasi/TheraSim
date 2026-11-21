/**
 * Compare the SHA-256 digest of a user-selected file with trusted release metadata.
 * The file stays in the browser; this function never uploads or persists it.
 * @param {File} file
 * @param {string} expectedDigest
 */
export async function verifySha256File(file, expectedDigest) {
  const normalizedDigest = expectedDigest.trim().toLowerCase()
  if (!/^[a-f0-9]{64}$/.test(normalizedDigest)) {
    throw new Error('The expected checksum is not a SHA-256 digest.')
  }
  const bytes = await file.arrayBuffer()
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes)
  const actualDigest = [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
  return actualDigest === normalizedDigest
}
