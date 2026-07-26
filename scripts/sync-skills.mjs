/**
 * Mirror the codeblox-builder skill from .claude/ to the other agent hosts.
 *
 * The skill ships to three hosts and is authored once. Their frontmatter is
 * identical, so the mirrors need no per-host adaptation — every difference is
 * drift, which is why a plain copy is the right mechanism rather than a
 * templating step. `tests/skill-mirrors.test.js` is what makes drift fail; this
 * is what fixes it.
 *
 * Only codeblox-builder is mirrored. The dev-phase-* skills are chore-track
 * tooling for this repo's own workflow, not product shipped to an agent host.
 *
 * Run with `npm run sync:skills`. There is deliberately no --check mode: the
 * test already reports drift and runs on every `npm test`, so a second way to
 * ask the same question would be one more thing to keep honest.
 */
import { readdirSync, readFileSync, writeFileSync, mkdirSync, rmSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative, sep } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const SOURCE = join(root, '.claude/skills/codeblox-builder')
const MIRRORS = [
  join(root, '.codex/skills/codeblox-builder'),
  join(root, '.agents/skills/codeblox-builder'),
]

const IGNORED = new Set(['__pycache__', '.pytest_cache'])

const filesUnder = dir => {
  if (!existsSync(dir)) return []
  const found = []
  const visit = current => {
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      if (IGNORED.has(entry.name)) continue
      const full = join(current, entry.name)
      if (entry.isDirectory()) visit(full)
      else found.push(relative(dir, full).split(sep).join('/'))
    }
  }
  visit(dir)
  return found.sort()
}

const sourceFiles = filesUnder(SOURCE)

// A guard, not a formality: every step below deletes mirror files the source
// does not have, so an empty source would silently empty both mirrors.
if (sourceFiles.length === 0) {
  console.error(`[codeblox] refusing to sync: no files under ${relative(root, SOURCE)}`)
  process.exit(1)
}

for (const mirror of MIRRORS) {
  const name = relative(root, mirror).split(sep).join('/')
  const stale = filesUnder(mirror).filter(f => !sourceFiles.includes(f))
  const changed = sourceFiles.filter(f => {
    const target = join(mirror, f)
    return !existsSync(target) || !readFileSync(join(SOURCE, f)).equals(readFileSync(target))
  })

  if (stale.length === 0 && changed.length === 0) {
    console.log(`[codeblox] ${name} up to date (${sourceFiles.length} files)`)
    continue
  }

  for (const f of stale) rmSync(join(mirror, f))
  for (const f of changed) {
    const target = join(mirror, f)
    mkdirSync(dirname(target), { recursive: true })
    writeFileSync(target, readFileSync(join(SOURCE, f)))
  }
  console.log(`[codeblox] ${name} synced — ${changed.length} written, ${stale.length} removed`)
}
