/**
 * Stop the codeblox dev processes — the viewer, the ws server, and the
 * `concurrently` parent that `npm start` spawns.
 *
 * Ports come from config.yaml (via @codeblox/shared/config.js), so this never
 * hardcodes 5173/7799. Extra ports can be passed as arguments, which is how you
 * reach an ad-hoc server (e.g. an auth-required harness on another port).
 *
 *   npm run dev:stop                 # stop whatever holds the configured ports
 *   npm run dev:stop -- 7801         # ...plus 7801 (positionals DO forward)
 *   npm run dev:list                 # list owners, kill nothing
 *
 * WARNING — npm eats flags. This npm forwards only *positional* arguments after
 * `--`; every `--flag` is stripped. Verified: `npm run x -- --list --json 7801`
 * reaches the script as `["7801"]`. So a flag can never be passed through
 * `npm run`, and `npm run dev:stop -- --list` would kill everything while
 * looking like a dry run. That is why `dev:list` is its own npm script with the
 * flag baked in.
 *
 * Flags work normally when node runs the script directly:
 *   node scripts/js/dev-stop.mjs --list --json 7801
 *   node scripts/js/dev-stop.mjs --dry-run          # alias for --list
 *
 * Multiple owners are the normal case: a stale server from an earlier session
 * can hold a port while a fresh `npm start` runs, and the tree kill also takes
 * down the concurrently parent's children.
 */
import { execFileSync } from 'node:child_process'
import { pathToFileURL } from 'node:url'

import { WEB, WS } from '@codeblox/shared/config.js'

const IS_WINDOWS = process.platform === 'win32'

/** Ports the project binds by default, from config.yaml. */
export const configuredPorts = () => [WEB.port, WS.port]

/**
 * Parse `netstat -ano` output into the pids LISTENING on the given ports.
 * Only the local-address column is considered, so a foreign address using the
 * same port never matches.
 */
export function parseWindowsNetstat(output, ports) {
  const wanted = new Set(ports.map(Number))
  const found = new Map() // `${port}:${pid}` -> entry, to dedupe IPv4 + IPv6 rows

  for (const line of output.split('\n')) {
    const cols = line.trim().split(/\s+/)
    if (cols.length < 5 || cols[3] !== 'LISTENING') continue

    const port = portOf(cols[1])
    const pid = Number(cols[4])
    if (port === null || !wanted.has(port) || !Number.isInteger(pid)) continue
    found.set(`${port}:${pid}`, { port, pid })
  }
  return sortEntries([...found.values()])
}

/**
 * Parse `lsof -nP -iTCP -sTCP:LISTEN` output into the pids listening on the
 * given ports.
 */
export function parseUnixLsof(output, ports) {
  const wanted = new Set(ports.map(Number))
  const found = new Map()

  for (const line of output.split('\n')) {
    const cols = line.trim().split(/\s+/)
    if (cols.length < 9 || cols[0] === 'COMMAND') continue

    const pid = Number(cols[1])
    const port = portOf(cols[8])
    if (port === null || !wanted.has(port) || !Number.isInteger(pid)) continue
    found.set(`${port}:${pid}`, { port, pid })
  }
  return sortEntries([...found.values()])
}

/** Extract the port from an address like 127.0.0.1:5173 or [::1]:5173. */
const portOf = address => {
  const at = address.lastIndexOf(':')
  if (at < 0) return null
  const port = Number(address.slice(at + 1))
  return Number.isInteger(port) ? port : null
}

const sortEntries = entries =>
  entries.sort((a, b) => a.port - b.port || a.pid - b.pid)

/** Run a command, returning stdout; '' when the tool exits non-zero (no match). */
const capture = (cmd, args) => {
  try {
    return execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })
  } catch {
    return ''
  }
}

/** Find every process listening on the given ports. */
export const findOwners = ports =>
  IS_WINDOWS
    ? parseWindowsNetstat(capture('netstat', ['-ano']), ports)
    : parseUnixLsof(capture('lsof', ['-nP', '-iTCP', '-sTCP:LISTEN']), ports)

/**
 * Kill a pid and its children. The tree matters: `npm start` runs concurrently,
 * which owns the vite and server processes.
 */
const killTree = pid => {
  if (IS_WINDOWS) {
    capture('taskkill', ['/F', '/T', '/PID', String(pid)])
    return
  }
  try {
    process.kill(-pid, 'SIGKILL') // process group, when there is one
  } catch {
    try {
      process.kill(pid, 'SIGKILL')
    } catch {
      /* already gone */
    }
  }
}

/**
 * Parse CLI arguments. `--list` is the npm-safe spelling of `--dry-run`; both
 * mean "report the owners, kill nothing".
 */
export function parseArgs(argv) {
  return {
    listOnly: argv.includes('--list') || argv.includes('-l') || argv.includes('--dry-run'),
    asJSON: argv.includes('--json'),
    extraPorts: argv.filter(a => /^\d+$/.test(a)).map(Number),
  }
}

const main = () => {
  const { listOnly, asJSON, extraPorts } = parseArgs(process.argv.slice(2))
  const ports = [...new Set([...configuredPorts(), ...extraPorts])]

  const owners = findOwners(ports)
  if (!listOnly) {
    for (const pid of new Set(owners.map(o => o.pid))) killTree(pid)
  }

  const survivors = listOnly ? [] : findOwners(ports)
  const report = {
    ports,
    found: owners,
    stopped: listOnly ? [] : owners,
    survivors,
    ok: survivors.length === 0,
    listOnly,
  }

  if (asJSON) {
    console.log(JSON.stringify(report))
  } else if (owners.length === 0) {
    console.log(`[codeblox] nothing listening on ${ports.join(', ')}`)
  } else {
    const verb = listOnly ? 'would stop' : 'stopped'
    for (const { port, pid } of owners) console.log(`[codeblox] ${verb} pid ${pid} on port ${port}`)
    for (const { port, pid } of survivors) {
      console.error(`[codeblox] STILL RUNNING: pid ${pid} on port ${port}`)
    }
  }
  return report.ok ? 0 : 1
}

// Only run when invoked directly, so the parsers stay importable by the tests.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exit(main())
}
