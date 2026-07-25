import { describe, it, expect, afterEach } from 'vitest'
import { WebSocket } from 'ws'
import { createServer } from '../apps/server/createServer.js'

const servers = []

const startServer = async opts => {
  const srv = createServer({ host: '127.0.0.1', port: 0, seed: false, ...opts })
  servers.push(srv)
  await srv.ready
  return srv
}

afterEach(async () => {
  while (servers.length) await servers.pop().close()
})

// Connect a ws client; resolves once welcomed, rejects if closed first (auth reject).
const connect = (port, token) =>
  new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`)
    const diffWaiters = []
    const ackWaiters = []
    let welcomed = false
    const client = {
      ws,
      welcome: null,
      lastAck: null,
      send: batch => ws.send(JSON.stringify({ type: 'commands', batch })),
      nextDiff: () => new Promise(r => diffWaiters.push(r)),
      nextAck: () => new Promise(r => ackWaiters.push(r)),
      close: () => ws.close(),
    }
    ws.on('open', () => ws.send(JSON.stringify({ type: 'hello', token })))
    ws.on('message', d => {
      const msg = JSON.parse(d)
      if (msg.type === 'welcome') {
        welcomed = true
        client.welcome = msg
        resolve(client)
      } else if (msg.type === 'diff') {
        diffWaiters.shift()?.(msg)
      } else if (msg.type === 'ack') {
        client.lastAck = msg
        ackWaiters.shift()?.(msg)
      }
    })
    ws.on('close', () => {
      if (!welcomed) reject(new Error('closed before welcome'))
    })
    ws.on('error', () => {})
  })

describe('ws server', () => {
  it('broadcasts a build to every connected client', async () => {
    const srv = await startServer()
    const a = await connect(srv.port())
    const b = await connect(srv.port())
    const aDiff = a.nextDiff()
    const bDiff = b.nextDiff()
    a.send([{ op: 'box', at: [0, 0, 0], size: [10, 20, 10], mat: 'oak' }])
    const [da, db] = await Promise.all([aDiff, bDiff])
    expect(da.added[0]).toMatchObject({ kind: 'box', material: 'oak' })
    expect(db.added[0].id).toBe(da.added[0].id) // same authoritative id everywhere
    expect(srv.store.size).toBe(1)
  })

  it('relays build_begin to every client without touching the store', async () => {
    const srv = await startServer()
    const a = await connect(srv.port())
    const b = await connect(srv.port())
    const aDiff = a.nextDiff()
    const bDiff = b.nextDiff()
    a.send([{ op: 'build_begin' }])
    const [da, db] = await Promise.all([aDiff, bDiff])

    // A pure signal: every viewer must see it (the reviewer's tab is often not
    // the one that sent the batch), and nothing may be built by it.
    expect(da.buildBegin).toBe(true)
    expect(db.buildBegin).toBe(true)
    expect(da.added).toHaveLength(0)
    expect(srv.store.size).toBe(0)
  })

  it('carries build_begin alongside the parts of the same batch', async () => {
    const srv = await startServer()
    const a = await connect(srv.port())
    const diff = a.nextDiff()
    a.send([{ op: 'build_begin' }, { op: 'box', at: [0, 0, 0], size: [2, 2, 2], mat: 'oak' }])
    const d = await diff
    expect(d.buildBegin).toBe(true)
    expect(d.added).toHaveLength(1)
  })

  it('leaves buildBegin false on an ordinary batch', async () => {
    const srv = await startServer()
    const a = await connect(srv.port())
    const ackP = a.nextAck()
    a.send([{ op: 'box', at: [0, 0, 0], size: [2, 2, 2], mat: 'oak' }])
    expect((await ackP).buildBegin).toBe(false)
  })

  it('rejects an unauthenticated connection when auth is required', async () => {
    const srv = await startServer({ authRequired: true, token: 'sekret' })
    await expect(connect(srv.port())).rejects.toThrow(/closed before welcome/)
    const ok = await connect(srv.port(), 'sekret')
    expect(ok.welcome).toBeTruthy()
  })

  it('acks an invalid command with errors and mutates nothing', async () => {
    const srv = await startServer()
    const a = await connect(srv.port())
    const ackP = a.nextAck()
    a.send([{ op: 'box', at: [0, 0, 0], size: [1, 1, 1], mat: 'bogus_material' }])
    const ack = await ackP
    expect(ack.errors.length).toBeGreaterThan(0)
    expect(ack.addedIds).toHaveLength(0)
    expect(srv.store.size).toBe(0)
  })

  it('gives a late-joining client the full snapshot + contract', async () => {
    const srv = await startServer()
    const a = await connect(srv.port())
    const aDiff = a.nextDiff()
    a.send([
      { op: 'box', at: [0, 0, 0], size: [4, 4, 4], mat: 'oak' },
      { op: 'sphere', at: [0, 20, 0], r: 3, mat: 'glass' },
    ])
    await aDiff
    const c = await connect(srv.port())
    expect(c.welcome.parts).toHaveLength(2)
    expect(c.welcome.contract.config.blockSize).toBe(0.02)
    expect(c.welcome.contract.palette.oak).toBeTruthy()
  })

  it('seeds the example tree into the snapshot', async () => {
    const srv = await startServer({ seed: true })
    const a = await connect(srv.port())
    expect(a.welcome.parts.length).toBeGreaterThan(5)
  })
})
