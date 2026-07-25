import { WS } from '../../shared/config.js'

const BACKOFF_START = 500
const BACKOFF_MAX = 8000

/**
 * Viewer-side WebSocket client. Renders the server's world: applies the snapshot
 * on connect (settled, no drop animation) and live diffs afterwards (animated),
 * and forwards command batches. Auto-reconnects with backoff; on reconnect the
 * server resends a fresh snapshot, so no state is lost.
 */
export default class WsClient {
  constructor(world, { token, onStatus } = {}) {
    this.world = world
    this.token = token
    this.onStatus = onStatus
    // Connect to the host that served the page (works local and when deployed),
    // upgrading to wss under https; only the ws port comes from config.
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    this.url = `${proto}://${location.hostname}:${WS.port}`
    this.ws = null
    this.connected = false
    this.contract = null
    this._backoff = BACKOFF_START
  }

  connect() {
    let ws
    try {
      ws = new WebSocket(this.url)
    } catch {
      this._scheduleReconnect()
      return this
    }
    this.ws = ws
    ws.onopen = () => ws.send(JSON.stringify({ type: 'hello', token: this.token }))
    ws.onmessage = e => this._onMessage(JSON.parse(e.data))
    ws.onerror = () => {} // a close event follows; handle reconnect there
    ws.onclose = () => {
      const wasConnected = this.connected
      this.connected = false
      if (wasConnected) this.onStatus?.('offline')
      this._scheduleReconnect()
    }
    return this
  }

  _onMessage(msg) {
    switch (msg.type) {
      case 'welcome':
        this.connected = true
        this._backoff = BACKOFF_START
        this.contract = msg.contract
        // Full snapshot: reset, then place existing parts settled (they're already
        // at rest on the server — no mass drop-in on connect).
        this.world.applyDiff({ cleared: true })
        this.world.applyDiff({ added: msg.parts || [], animate: false })
        this.onStatus?.('online')
        break
      case 'diff':
        this.world.applyDiff({
          added: msg.added || [],
          removed: msg.removed || [],
          cleared: msg.cleared,
          animate: true,
        })
        break
      case 'ack':
        if (msg.errors?.length) console.warn('[codeblox] rejected:', msg.errors)
        break
      case 'error':
        console.error('[codeblox] server:', msg.message)
        break
    }
  }

  /** Send a command batch to the server. Returns a status marker (fire-and-forget). */
  exec(commands) {
    if (!this.connected) return { error: 'not connected' }
    const batch = Array.isArray(commands) ? commands : [commands]
    this.ws.send(JSON.stringify({ type: 'commands', batch }))
    return { sent: batch.length, mode: 'server' }
  }

  _scheduleReconnect() {
    setTimeout(() => this.connect(), this._backoff)
    this._backoff = Math.min(this._backoff * 2, BACKOFF_MAX)
  }
}
