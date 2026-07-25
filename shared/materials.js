/**
 * Material palette — the single source of truth for names and colors. The names
 * are the agent's vocabulary (descriptive, not clever), and the server validates
 * every command's material against this list. Dependency-free (Node-importable).
 *
 * COLORS is the flat name -> hex map. FAMILIES tags the non-opaque materials by
 * render family (everything unlisted is opaque). buildPalette() merges them into
 * the resolved MATERIALS map used everywhere.
 */

import { DEFAULT_FAMILY } from './families.js'

// name -> color. 100 materials across 9 themed groups.
const COLORS = {
  // stone & masonry (14)
  granite: 0xd8d5cc,
  limestone: 0xe6e1d2,
  marble: 0xf2efe8,
  marble_veined: 0xe8e4dc,
  sandstone: 0xe0cfae,
  slate: 0xb4bcc4,
  slate_dark: 0x8a939c,
  basalt: 0x6e737a,
  obsidian: 0x2e3138,
  flint: 0x9aa0a4,
  chalk: 0xf4f2ea,
  cobble: 0xc4bfb4,
  brick: 0xc07458,
  brick_pale: 0xd8a48c,

  // timber & organic (12)
  oak: 0xc9a377,
  oak_dark: 0x9c7a52,
  walnut: 0x6e5138,
  ebony: 0x3a2f26,
  pine: 0xdcc49a,
  cedar: 0xb8825c,
  driftwood: 0xc6bfae,
  bamboo: 0xd6cf94,
  thatch: 0xdcc78a,
  thatch_dark: 0xbca868,
  wicker: 0xcfb488,
  cork: 0xc9a986,

  // roofing & tile (10)
  terracotta: 0xc86844,
  terracotta_old: 0xa85838,
  copper: 0xb87548,
  copper_verdigris: 0x6fae9c,
  lead: 0x9098a0,
  shingle: 0x8c7862,
  shingle_blue: 0x6c7f96,
  tile_green: 0x5f8a6a,
  tile_purple: 0x7a6690,
  tile_crimson: 0x9c4448,

  // precious & metal (10)
  gold: 0xe8be54,
  gold_pale: 0xf0d68c,
  gold_deep: 0xc89830,
  silver: 0xd8dce0,
  pewter: 0xa4a8ac,
  bronze: 0xb08048,
  iron: 0x74797e,
  iron_rust: 0x9c6448,
  steel: 0xbcc2c8,
  brass: 0xcbab5e,

  // glass & light (10)
  glass: 0xdae8ee,
  glass_rose: 0xeed4dc,
  glass_azure: 0xbcd8ee,
  glass_amber: 0xeed8b0,
  glass_emerald: 0xc0e0cc,
  glass_violet: 0xd8cce8,
  crystal: 0xeaf2f6,
  lantern: 0xf4d894,
  torch: 0xf0c068,
  moonstone: 0xe4e8f2,

  // gem & fantastical (12)
  amethyst: 0x9878c0,
  sapphire: 0x5878b8,
  emerald: 0x4c9c74,
  ruby: 0xb84860,
  topaz: 0xdca858,
  jade: 0x84b498,
  opal: 0xe0dcec,
  rose_quartz: 0xe8c0c8,
  malachite: 0x4c9080,
  lapis: 0x4464a8,
  garnet: 0x9c4058,
  pearl: 0xf0ece4,

  // dragon: scale & hide (14)
  scale_green: 0x5c8c58,
  scale_green_dk: 0x3e6440,
  scale_jade: 0x4c9078,
  scale_teal: 0x3c7c84,
  scale_azure: 0x4470a4,
  scale_violet: 0x7458a0,
  scale_crimson: 0xa04048,
  scale_rust: 0xa86844,
  scale_bronze: 0xa07848,
  scale_onyx: 0x38383c,
  scale_bone: 0xdcd4c0,
  scale_ash: 0x8c8880,
  belly: 0xdcc8a0,
  belly_pale: 0xe8dcc0,

  // horn, claw, membrane (8)
  horn: 0xd0c4a8,
  horn_dark: 0x8c8068,
  claw: 0x484440,
  claw_pale: 0xc8c0b0,
  membrane: 0xc08890,
  membrane_dark: 0x986870,
  membrane_dusk: 0xa8809c,
  spine: 0xb4a488,

  // flame & aura (10)
  flame: 0xf08840,
  flame_hot: 0xf8c060,
  flame_core: 0xfce8a8,
  flame_deep: 0xd85830,
  ember: 0xc04828,
  smoke: 0xa8a4a0,
  frost: 0xc8e4f0,
  frost_deep: 0x88b8d8,
  arcane: 0xa878d8,
  arcane_pale: 0xd8c0f0,
}

// Non-opaque materials by render family. Everything unlisted is opaque.
const FAMILIES = {
  glass: [
    'glass', 'glass_rose', 'glass_azure', 'glass_amber', 'glass_emerald',
    'glass_violet', 'crystal', 'moonstone',
  ],
  metal: [
    'copper', 'copper_verdigris', 'lead', 'gold', 'gold_pale', 'gold_deep',
    'silver', 'pewter', 'bronze', 'iron', 'iron_rust', 'steel', 'brass',
  ],
  emissive: [
    'lantern', 'torch', 'flame', 'flame_hot', 'flame_core', 'flame_deep',
    'ember', 'arcane', 'arcane_pale',
  ],
}

const buildPalette = (colors, families) => {
  const familyOf = {}
  for (const [family, names] of Object.entries(families)) {
    for (const name of names) familyOf[name] = family
  }
  const out = {}
  for (const [name, color] of Object.entries(colors)) {
    out[name] = { color, family: familyOf[name] ?? DEFAULT_FAMILY }
  }
  return out
}

/** Resolved palette: name -> { color, family }. */
export const MATERIALS = buildPalette(COLORS, FAMILIES)

/** All material names, in declaration order (the agent's vocabulary). */
export const MATERIAL_NAMES = Object.keys(COLORS)

/** Names grouped by family, for the FAMILIES source (used by tests/tools). */
export const MATERIAL_FAMILIES = FAMILIES

export const isMaterial = name => Object.prototype.hasOwnProperty.call(MATERIALS, name)

/** Hex color for a material name, or null if unknown. */
export const materialColor = name => (isMaterial(name) ? MATERIALS[name].color : null)

/** Render family for a material name, or null if unknown. */
export const materialFamily = name => (isMaterial(name) ? MATERIALS[name].family : null)
