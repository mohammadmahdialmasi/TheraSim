import assert from 'node:assert/strict'
import test from 'node:test'

import { verifySha256File } from '../src/lib/downloadTools.js'

test('downloaded file SHA-256 matches a release digest', async () => {
  const file = new Blob(['abc'])
  const digest =
    'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'

  assert.equal(await verifySha256File(file, digest), true)
  assert.equal(await verifySha256File(file, '0'.repeat(64)), false)
})

test('downloaded file checksum rejects malformed expected digests', async () => {
  await assert.rejects(
    verifySha256File(new Blob(['abc']), 'sha256:abc'),
    /not a SHA-256 digest/,
  )
})
