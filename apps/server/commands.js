import { validate, expand, isPartOp, isViewerOp } from '@codeblox/shared/protocol.js'

/**
 * Apply a command batch to the authoritative store, producing the normalized diff
 * broadcast to viewers. Mirrors the viewer's offline path exactly (same validate
 * + expand), so the server is authoritative without a second protocol definition.
 *
 * Returns { added: [{id,...part}], removed: [ids], cleared, buildBegin,
 * viewer: [cmds], errors: [{cmd,errors}] }.
 */
export const applyBatch = (store, batch = []) => {
  const added = []
  const removed = []
  const viewer = []
  const errors = []
  let cleared = false
  let buildBegin = false

  for (const cmd of batch) {
    const v = validate(cmd)
    if (!v.ok) {
      errors.push({ cmd, errors: v.errors })
      continue
    }
    if (cmd.op === 'clear') {
      store.clear()
      cleared = true
      added.length = 0
      removed.length = 0
      continue
    }
    if (cmd.op === 'remove') {
      if (store.remove(cmd.id)) removed.push(cmd.id)
      continue
    }
    if (cmd.op === 'world_info') continue
    // Pure signal: no store mutation, just relayed so viewers can group the
    // parts that follow into one build.
    if (cmd.op === 'build_begin') {
      buildBegin = true
      continue
    }
    // Relayed, never stored. Deliberately NOT reset by the `clear` arm the way
    // added/removed are: a clear erases the world, but it does not make "look
    // from view 1" moot.
    if (isViewerOp(cmd.op)) {
      viewer.push(cmd)
      continue
    }
    if (isPartOp(cmd.op)) {
      for (const part of expand(cmd)) {
        const id = store.add(part)
        added.push({ id, ...part })
      }
    }
  }

  return { added, removed, cleared, buildBegin, viewer, errors }
}
