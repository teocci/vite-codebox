import { describe, it, expect } from 'vitest'
import { parseWindowsNetstat, parseUnixLsof, parseArgs } from '../scripts/dev-stop.mjs'

describe('parseArgs', () => {
  // `npm run dev:stop -- --dry-run` forwards only the other flags: npm claims
  // --dry-run as its own. --list is the npm-safe spelling and must always work.
  it('treats --list as list-only', () => {
    expect(parseArgs(['--list']).listOnly).toBe(true)
  })

  it('still honours --dry-run for direct node invocation', () => {
    expect(parseArgs(['--dry-run']).listOnly).toBe(true)
  })

  it('defaults to actually stopping', () => {
    expect(parseArgs([]).listOnly).toBe(false)
  })

  it('collects extra ports given as bare numbers', () => {
    expect(parseArgs(['7801', '--json']).extraPorts).toEqual([7801])
  })

  it('reads the json flag', () => {
    expect(parseArgs(['--json']).asJSON).toBe(true)
    expect(parseArgs([]).asJSON).toBe(false)
  })
})

// Real `netstat -ano` output: header lines, unrelated ports, IPv4 + IPv6 rows for
// the same listener, and an ESTABLISHED row whose foreign port must not match.
const NETSTAT = `
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1234
  TCP    127.0.0.1:5173         0.0.0.0:0              LISTENING       58060
  TCP    [::1]:5173             [::]:0                 LISTENING       58060
  TCP    127.0.0.1:7799         0.0.0.0:0              LISTENING       66924
  TCP    192.168.1.9:51000      140.82.113.4:7799      ESTABLISHED     9999
  TCP    127.0.0.1:15173        0.0.0.0:0              LISTENING       7777
`

const LSOF = `COMMAND   PID  USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
node    58060 teocci   23u  IPv4 0x1234      0t0  TCP 127.0.0.1:5173 (LISTEN)
node    66924 teocci   24u  IPv4 0x5678      0t0  TCP 127.0.0.1:7799 (LISTEN)
node    58060 teocci   25u  IPv6 0x9abc      0t0  TCP [::1]:5173 (LISTEN)
`

describe('parseWindowsNetstat', () => {
  it('finds the pid listening on a requested port', () => {
    expect(parseWindowsNetstat(NETSTAT, [7799])).toEqual([{ port: 7799, pid: 66924 }])
  })

  it('deduplicates a listener bound on both IPv4 and IPv6', () => {
    expect(parseWindowsNetstat(NETSTAT, [5173])).toEqual([{ port: 5173, pid: 58060 }])
  })

  it('ignores a foreign address that happens to use the port', () => {
    const pids = parseWindowsNetstat(NETSTAT, [7799]).map(p => p.pid)
    expect(pids).not.toContain(9999)
  })

  it('does not treat 15173 as a match for 5173', () => {
    const pids = parseWindowsNetstat(NETSTAT, [5173]).map(p => p.pid)
    expect(pids).not.toContain(7777)
  })

  it('handles several ports at once', () => {
    expect(parseWindowsNetstat(NETSTAT, [5173, 7799])).toEqual([
      { port: 5173, pid: 58060 },
      { port: 7799, pid: 66924 },
    ])
  })

  it('returns nothing when no port matches', () => {
    expect(parseWindowsNetstat(NETSTAT, [9100])).toEqual([])
  })
})

describe('parseUnixLsof', () => {
  it('finds the pid listening on a requested port', () => {
    expect(parseUnixLsof(LSOF, [7799])).toEqual([{ port: 7799, pid: 66924 }])
  })

  it('deduplicates a listener bound on both IPv4 and IPv6', () => {
    expect(parseUnixLsof(LSOF, [5173])).toEqual([{ port: 5173, pid: 58060 }])
  })

  it('skips the header row', () => {
    const pids = parseUnixLsof(LSOF, [5173, 7799]).map(p => p.pid)
    expect(pids.every(Number.isInteger)).toBe(true)
  })

  it('returns nothing when no port matches', () => {
    expect(parseUnixLsof(LSOF, [9100])).toEqual([])
  })
})
