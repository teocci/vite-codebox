import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, relative, sep } from 'node:path'

/**
 * The codeblox-builder skill is shipped to three agent hosts from one source.
 * Nothing enforced that before this test, and the copies went stale after P-7,
 * P-9 and P-10 — three times, silently, because a stale mirror looks exactly
 * like a fresh one until someone runs it. This is the thing that fails instead.
 *
 * Run `npm run sync:skills` to make it pass.
 */
const SOURCE = '.claude/skills/codeblox-builder'
const MIRRORS = ['.codex/skills/codeblox-builder', '.agents/skills/codeblox-builder']

// Build artefacts, not content — they differ per interpreter run and are not shipped.
const IGNORED = new Set(['__pycache__', '.pytest_cache'])

const filesUnder = root => {
  const found = []
  const visit = dir => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (IGNORED.has(entry.name)) continue
      const full = join(dir, entry.name)
      if (entry.isDirectory()) visit(full)
      else found.push(relative(root, full).split(sep).join('/'))
    }
  }
  visit(root)
  return found.sort()
}

const digest = path => createHash('sha256').update(readFileSync(path)).digest('hex')

describe.each(MIRRORS)('%s', mirror => {
  it('carries exactly the files the source has', () => {
    expect(filesUnder(mirror)).toEqual(filesUnder(SOURCE))
  })

  it('is byte-identical to the source', () => {
    // Report the drifted paths rather than a diff of every byte: the useful
    // signal is which files were missed, not what changed inside them.
    const shared = filesUnder(mirror).filter(f => filesUnder(SOURCE).includes(f))
    const drifted = shared.filter(f => digest(join(SOURCE, f)) !== digest(join(mirror, f)))
    expect(drifted).toEqual([])
  })
})
