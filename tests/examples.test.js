import { describe, it, expect } from 'vitest'
import { tree } from '@codeblox/shared/examples.js'
import { validate } from '@codeblox/shared/protocol.js'

describe('examples', () => {
  it('tree() produces only valid, in-bounds commands', () => {
    for (const cmd of tree()) {
      const r = validate(cmd)
      expect(r.ok, `${JSON.stringify(cmd)} -> ${r.errors.join(', ')}`).toBe(true)
    }
  })

  it('tree() has a trunk and a multi-sphere canopy', () => {
    const cmds = tree()
    expect(cmds.filter(c => c.op === 'cylinder')).toHaveLength(1)
    expect(cmds.filter(c => c.op === 'sphere').length).toBeGreaterThanOrEqual(5)
  })

  it('offsets plant the tree elsewhere, still valid', () => {
    for (const cmd of tree(300, -200)) {
      expect(validate(cmd).ok).toBe(true)
    }
  })
})
