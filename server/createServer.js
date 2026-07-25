import { WebSocketServer } from 'ws'
import { contract } from '../shared/protocol.js'
import { tree } from '../shared/examples.js'
import WorldStore from './WorldStore.js'
import { applyBatch } from './commands.js'
import { createAuth } from './auth.js'

const OPEN = 1 // ws.readyState

/**
 * Create an authoritative codeblox ws server. Exposed as a factory (not just a
 * running process) so tests can spin one up on an ephemeral port.
 *
 * Protocol:
 *   client -> { type:'hello', token? }         (first message; gates the connection)
 *   server -> { type:'welcome', contract, parts }   (contract + full snapshot)
 *   client -> { type:'commands', batch:[...] }
 *   server -> { type:'diff', added, removed, cleared }   (broadcast to all)
 *   server -> { type:'ack', addedIds, removed, cleared, errors }   (to the sender)
 *   server -> { type:'error', message }         (before an auth rejection close)
 */
export function createServer({ host = '127.0.0.1', port = 8787, authRequired = false, token, seed = false } = {}) {
  const store = new WorldStore()
  const auth = createAuth({ required: authRequired, token })
  if (seed) applyBatch(store, tree())

  const wss = new WebSocketServer({ host, port })
  const clients = new Set()

  const broadcast = obj => {
    const s = JSON.stringify(obj)
    for (const c of clients) if (c.readyState === OPEN) c.send(s)
  }

  wss.on('connection', ws => {
    ws.once('message', raw => {
      let hello
      try {
        hello = JSON.parse(raw)
      } catch {
        return ws.close(4000, 'bad hello')
      }
      if (hello?.type !== 'hello' || !auth.check(hello.token)) {
        try {
          ws.send(JSON.stringify({ type: 'error', message: 'unauthorized' }))
        } catch {
          /* socket may already be gone */
        }
        return ws.close(4001, 'unauthorized')
      }

      clients.add(ws)
      ws.send(JSON.stringify({ type: 'welcome', contract: contract(), parts: store.snapshot() }))

      ws.on('message', data => {
        let msg
        try {
          msg = JSON.parse(data)
        } catch {
          return
        }
        if (msg.type !== 'commands') return
        const r = applyBatch(store, msg.batch || [])
        broadcast({ type: 'diff', added: r.added, removed: r.removed, cleared: r.cleared })
        ws.send(JSON.stringify({
          type: 'ack',
          addedIds: r.added.map(a => a.id),
          removed: r.removed,
          cleared: r.cleared,
          errors: r.errors,
        }))
      })

      ws.on('close', () => clients.delete(ws))
    })
  })

  const ready = new Promise(resolve => wss.on('listening', resolve))

  return {
    wss,
    store,
    auth,
    ready,
    clientCount: () => clients.size,
    port: () => wss.address().port,
    close: () =>
      new Promise(resolve => {
        for (const c of wss.clients) c.terminate()
        wss.close(resolve)
      }),
  }
}
