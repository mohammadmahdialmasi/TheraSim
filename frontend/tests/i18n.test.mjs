import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import {
  getInitialLanguage,
  persistLanguage,
  resolveTranslation,
} from '../src/i18n.ts'

const sourceRoot = fileURLToPath(new URL('../src', import.meta.url))
const catalogSource = readFileSync(join(sourceRoot, 'i18n.ts'), 'utf8')

function extractCatalogFrom(source, language) {
  const marker = `  ${language}: {`
  const markerIndex = source.indexOf(marker)
  assert.notEqual(markerIndex, -1, `Missing ${language} catalog`)

  const openBrace = source.indexOf('{', markerIndex)
  let depth = 1
  let quote = ''
  let escaped = false
  let closeBrace = -1

  for (let index = openBrace + 1; index < source.length; index += 1) {
    const character = source[index]
    if (quote) {
      if (escaped) escaped = false
      else if (character === '\\') escaped = true
      else if (character === quote) quote = ''
      continue
    }

    if (character === "'" || character === '"' || character === '`') {
      quote = character
    } else if (character === '{') {
      depth += 1
    } else if (character === '}') {
      depth -= 1
      if (depth === 0) {
        closeBrace = index
        break
      }
    }
  }

  assert.notEqual(closeBrace, -1, `Unclosed ${language} catalog`)
  const body = source.slice(openBrace + 1, closeBrace)
  return [...body.matchAll(/^\s{4}([A-Za-z]\w*):/gm)].map((match) => match[1])
}

function extractCatalog(language) {
  return extractCatalogFrom(catalogSource, language)
}

function listSourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return listSourceFiles(path)
    return /\.(?:ts|tsx)$/.test(entry.name) && entry.name !== 'i18n.ts'
      ? [path]
      : []
  })
}

test('English and Persian translation catalogs have identical unique keys', () => {
  const english = extractCatalog('en')
  const persian = extractCatalog('fa')
  assert.equal(new Set(english).size, english.length, 'Duplicate English keys')
  assert.equal(new Set(persian).size, persian.length, 'Duplicate Persian keys')
  assert.deepEqual([...persian].sort(), [...english].sort())
})

test('every central translation key is used by the application', () => {
  const keys = extractCatalog('en')
  const applicationSource = listSourceFiles(sourceRoot)
    .map((path) => readFileSync(path, 'utf8'))
    .join('\n')

  const unused = keys.filter((key) => {
    const memberAccess = new RegExp(
      `\\b(?:t|labels|copy)\\??\\.${key}\\b`,
    )
    const keyReference = new RegExp(`['"\`]${key}['"\`]`)
    return !memberAccess.test(applicationSource)
      && !keyReference.test(applicationSource)
  })

  assert.deepEqual(unused, [], `Unused translation keys: ${unused.join(', ')}`)
})

test('feature-level English and Persian catalogs have matching used keys', () => {
  for (const path of listSourceFiles(sourceRoot)) {
    const source = readFileSync(path, 'utf8')
    if (!/const\s+(?:copy|text)\s*=\s*\{/.test(source)) continue

    const english = extractCatalogFrom(source, 'en')
    const persian = extractCatalogFrom(source, 'fa')
    assert.deepEqual(
      [...persian].sort(),
      [...english].sort(),
      `Language keys differ in ${path}`,
    )

    const unused = english.filter((key) => {
      const access = new RegExp(
        `\\b(?:copy|labels|text)\\??\\s*(?:\\[[^\\]]+\\])?\\s*\\.\\s*${key}\\b`,
      )
      const keyReference = new RegExp(`['"\`]${key}['"\`]`)
      return !access.test(source) && !keyReference.test(source)
    })

    assert.deepEqual(unused, [], `Unused translations in ${path}: ${unused.join(', ')}`)
  }
})

test('missing Persian translation falls back to English, then its key', () => {
  assert.equal(
    resolveTranslation({}, { updateCheck: 'Check for updates' }, 'updateCheck'),
    'Check for updates',
  )
  assert.equal(resolveTranslation({}, {}, 'unknownKey'), 'unknownKey')
})

test('language preference loads and persists with a safe English fallback', () => {
  const values = new Map([['therasim-language', 'fa']])
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  }

  assert.equal(getInitialLanguage(storage), 'fa')
  persistLanguage('en', storage)
  assert.equal(values.get('therasim-language'), 'en')
  assert.equal(getInitialLanguage({
    getItem: () => { throw new Error('storage disabled') },
  }), 'en')
})
