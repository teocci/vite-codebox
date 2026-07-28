import { describe, it, expect } from 'vitest'
import { extentMetresText, extentBlocksText } from '../apps/web/src/viewer/Hud.js'
import { BLOCK_SIZE } from '@codeblox/shared/config.js'

// The Golden Gate build at true 1:1 — the case that pushed the panel across the
// viewport as one 41-character value.
const BRIDGE = [136850, 11350, 136850]

describe('hud extent rows', () => {
  it('splits the two unit systems into two values', () => {
    expect(extentMetresText(BRIDGE)).toBe('2737 × 227 × 2737 m')
    expect(extentBlocksText(BRIDGE)).toBe('136850 × 11350 × 136850')
  })

  it('keeps every number exact rather than abbreviating it', () => {
    // The scale gate compares a build against the real subject's dimensions, so
    // "2.7k m" would be uncheckable. Bounding the panel is a layout problem and
    // is solved in CSS, not by dropping digits.
    for (const text of [extentMetresText(BRIDGE), extentBlocksText(BRIDGE)]) {
      expect(text).not.toMatch(/\d[kKMG]/) // a magnitude suffix, e.g. 2.7k
      expect(text).not.toMatch(/…|\.\.\./)
    }
    expect(extentMetresText(BRIDGE)).toContain('2737')
    expect(extentBlocksText(BRIDGE)).toContain('136850')
  })

  it('gives every separator a break opportunity so a long triple can wrap', () => {
    // This is what makes the max-width a cap rather than an overflow: without
    // the spaces the triple is one unbreakable word and no cap can hold it.
    for (const text of [extentMetresText(BRIDGE), extentBlocksText(BRIDGE)]) {
      expect(text).toContain(' × ')
      expect(text).not.toMatch(/\d×/)
    }
  })

  it('rounds blocks to integers and metres to one decimal', () => {
    expect(extentBlocksText([1.4, 2.5, 3.6])).toBe('1 × 3 × 4')
    // 3 blocks at 2 cm = 0.06 m — a value that only reads as exact with the
    // decimal kept.
    expect(extentMetresText([3, 50, 3])).toBe('0.1 × 1 × 0.1 m')
  })

  it('holds the 50x relationship the two rows exist because of', () => {
    // BLOCK_SIZE is 0.02, so the block triple is by construction 1/BLOCK_SIZE
    // the metre triple — the reason no single row can ever hold both.
    expect(1 / BLOCK_SIZE).toBe(50)
    expect(BRIDGE[0] * BLOCK_SIZE).toBe(2737)
  })
})
