import './styles/variables.css'
import './styles/global.css'
import Viewer from './viewer/Viewer.js'
import WsClient from './net/WsClient.js'
import { validate, expand, contract, isPartOp } from '@codeblox/shared/protocol.js'
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
    if (isPartOp(cmd.op)) added.push(...expand(cmd))
  }

  const r = viewer.world.applyDiff({ added, removed, cleared, buildBegin })
  if (errors.length) console.warn('[codeblox] rejected:', errors)
  return { ...r, errors, mode: 'local' }
}

const ws = new WsClient(viewer.world, {
  onStatus: s => viewer.hud.toast(s === 'online' ? 'server connected' : 'offline — local mode'),
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
  info() {
    return ws.contract ?? contract()
  },
}

window.codeblox = driver
console.info('[codeblox] ready — codeblox.tree(300,0), codeblox.clear(). Run `npm start` for the server.')
