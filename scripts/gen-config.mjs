/**
 * Compile config.yaml into packages/shared/config.values.js — a plain ESM module
 * that both the browser viewer (via Vite) and the Node server import identically
 * as @codeblox/shared/config.values.js. This is how file-based YAML config reaches
 * the browser, which cannot read files at runtime, without any environment
 * variables.
 *
 * Run automatically via the install / predev / prebuild / pretest npm hooks.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { load } from 'js-yaml'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const yamlPath = join(root, 'config.yaml')
const outPath = join(root, 'packages', 'shared', 'config.values.js')

const raw = existsSync(yamlPath) ? (load(readFileSync(yamlPath, 'utf8')) ?? {}) : {}

const values = {
  blockSize: raw.blockSize ?? 0.02,
  extent: raw.world?.extent ?? 32,
  // 'auto' (the default) means "derive from extent" — resolved by shared/config.js.
  gridStep: raw.world?.gridStep ?? 'auto',
  web: {
    host: raw.web?.host ?? 'localhost',
    port: raw.web?.port ?? 5173,
  },
  ws: {
    host: raw.ws?.host ?? '127.0.0.1',
    port: raw.ws?.port ?? 7799,
    seed: raw.ws?.seed ?? true,
    authRequired: raw.ws?.auth?.required ?? false,
  },
}

const banner = '// AUTO-GENERATED from config.yaml by scripts/gen-config.mjs — do not edit by hand.\n'
writeFileSync(outPath, banner + 'export default ' + JSON.stringify(values, null, 2) + '\n')

console.log('[codeblox] config.yaml -> packages/shared/config.values.js', values)
