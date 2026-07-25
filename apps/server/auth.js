import { randomBytes } from 'node:crypto'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const DIR = '.codeblox'
const FILE = join(DIR, 'token')

/**
 * Resolve the server's bearer token. Precedence: CODEBLOX_TOKEN env (CI/prod) ->
 * .codeblox/token file -> generate a random one and persist it (0600). The token
 * is never stored in config.yaml (non-secret only) — this is the rule-13 file
 * backend with an env fallback.
 */
export const resolveToken = () => {
  if (process.env.CODEBLOX_TOKEN) return process.env.CODEBLOX_TOKEN
  if (existsSync(FILE)) return readFileSync(FILE, 'utf8').trim()
  const token = randomBytes(24).toString('hex')
  try {
    mkdirSync(DIR, { recursive: true })
    writeFileSync(FILE, token, { mode: 0o600 })
  } catch {
    /* best-effort persistence; the in-memory token still works this run */
  }
  return token
}

/**
 * Auth policy. When `required` is false (local dev) every connection is accepted.
 * When true, a connection must present the matching token in its hello.
 */
export const createAuth = ({ required = false, token } = {}) => {
  const secret = token ?? resolveToken()
  return {
    required,
    secret,
    check: t => !required || t === secret,
    masked: `${secret.slice(0, 6)}…${secret.slice(-4)}`,
  }
}
