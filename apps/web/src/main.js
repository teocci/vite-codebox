import './styles/variables.css'
import './styles/global.css'
import Viewer from './viewer/Viewer.js'
import WsClient from './net/WsClient.js'
import { validate, expand, contract, isPartOp, isViewerOp } from '@codeblox/shared/protocol.js'
import { tree } from '@codeblox/shared/examples.js'

const viewer = new Viewer(document.getElementById('app')).start()

/**
 * Offline fallback: apply commands straight to the world (Phase-1 behavior) when
 * no server is connected. Same validate + expand + diff shape the server uses, so
 * behavior matches whether online or off. When the server is up, the WsClient owns
 * the world and this is bypassed.
 */
const applyLocal = commands => {
  const list = Array.isArray(commands) ? commands : [commands]
  const added = []
  const removed = []
  const errors = []
  // `viewer` is taken by the viewer instance itself; these are the ops bound for
  // it. Collected rather than applied inline, so the offline path obeys the same
  // after-the-diff ordering rule as the ws path.
  const viewerOps = []
  let cleared = false
  let buildBegin = false

  for (const cmd of list) {
    const v = validate(cmd)
    if (!v.ok) {
      errors.push({ cmd, errors: v.errors })
      continue
    }
    if (cmd.op === 'clear') {
      cleared = true
      added.length = 0
      removed.length = 0
      continue
    }
    if (cmd.op === 'remove') {
      removed.push(cmd.id)
      continue
    }
    if (cmd.op === 'world_info') continue
    if (cmd.op === 'build_begin') {
      buildBegin = true
      continue
    }
    if (isViewerOp(cmd.op)) {
      viewerOps.push(cmd)
      continue
    }
    if (isPartOp(cmd.op)) added.push(...expand(cmd))
  }

  const r = viewer.world.applyDiff({ added, removed, cleared, buildBegin })
  viewer.applyViewerOps(viewerOps) // after the diff — the same rule WsClient applies
  if (errors.length) console.warn('[codeblox] rejected:', errors)
  return { ...r, errors, mode: 'local' }
}

const ws = new WsClient(viewer.world, {
  onStatus: s => viewer.hud.toast(s === 'online' ? 'server connected' : 'offline — local mode'),
  onViewer: ops => viewer.applyViewerOps(ops),
}).connect()

// Console driver. Routes to the server when connected, else applies locally.
const driver = {
  exec(cmds) {
    return ws.connected ? ws.exec(cmds) : applyLocal(cmds)
  },
  box(at, size, mat) {
    return this.exec({ op: 'box', at, size, mat })
  },
  sphere(at, r, mat) {
    return this.exec({ op: 'sphere', at, r, mat })
  },
  cylinder(at, r, h, mat) {
    return this.exec({ op: 'cylinder', at, r, h, mat })
  },
  fill(from, to, mat) {
    return this.exec({ op: 'fill', from, to, mat })
  },
  remove(id) {
    return this.exec({ op: 'remove', id })
  },
  clear() {
    return this.exec({ op: 'clear' })
  },
  tree(ox = 0, oz = 0) {
    return this.exec(tree(ox, oz))
  },
  view(n) {
    return this.exec({ op: 'view', n })
  },
  reframe() {
    return this.exec({ op: 'reframe' })
  },
  rotate(on) {
    return this.exec({ op: 'rotate', on })
  },
  grid(on) {
    return this.exec({ op: 'grid', on })
  },
  hud(on) {
    return this.exec({ op: 'hud', on })
  },
  info() {
    return ws.contract ?? contract()
  },
}

window.codeblox = driver
console.info('[codeblox] ready — codeblox.tree(300,0), codeblox.view(4), codeblox.clear(). Run `npm start` for the server.')
