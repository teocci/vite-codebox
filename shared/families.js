/**
 * Render families group materials by how they draw, not by color. Each family
 * maps to one rendering configuration; per-instance color comes from the palette.
 * The viewer creates one InstancedMesh per (geometry x family).
 *
 * Dependency-free (no THREE import) so the server can import it. The values below
 * are plain data; the viewer turns them into THREE materials in engine/materials.js.
 */

export const FAMILY = {
  OPAQUE: 'opaque',
  GLASS: 'glass',
  METAL: 'metal',
  EMISSIVE: 'emissive',
}

export const DEFAULT_FAMILY = FAMILY.OPAQUE

export const FAMILY_NAMES = Object.values(FAMILY)

/** Shading hints per family (consumed by the viewer's material factory). */
export const FAMILY_MATERIAL = {
  [FAMILY.OPAQUE]: { transparent: false, opacity: 1, metalness: 0.0, roughness: 0.8, unlit: false },
  [FAMILY.GLASS]: { transparent: true, opacity: 0.42, metalness: 0.0, roughness: 0.1, unlit: false },
  [FAMILY.METAL]: { transparent: false, opacity: 1, metalness: 0.85, roughness: 0.35, unlit: false },
  [FAMILY.EMISSIVE]: { transparent: false, opacity: 1, metalness: 0.0, roughness: 0.6, unlit: true },
}

export const isFamily = name => FAMILY_NAMES.includes(name)
