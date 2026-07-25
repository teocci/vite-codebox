import { MeshStandardMaterial, MeshBasicMaterial } from 'three'
import { FAMILY } from '../../shared/families.js'

/**
 * Build the one THREE material for a render family. Per-instance color comes from
 * InstancedMesh.instanceColor (which three multiplies against material.color), so
 * every material here uses white as the base color.
 *
 * Emissive uses an unlit MeshBasicMaterial so the instance color renders full-
 * bright — a cheap "glow" without a custom shader or postprocessing.
 */
export const makeFamilyMaterial = family => {
  switch (family) {
    case FAMILY.GLASS:
      return new MeshStandardMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.42,
        roughness: 0.1,
        metalness: 0.0,
        depthWrite: false,
      })
    case FAMILY.METAL:
      return new MeshStandardMaterial({ color: 0xffffff, metalness: 0.85, roughness: 0.35 })
    case FAMILY.EMISSIVE:
      return new MeshBasicMaterial({ color: 0xffffff, toneMapped: false })
    case FAMILY.OPAQUE:
    default:
      return new MeshStandardMaterial({ color: 0xffffff, metalness: 0.0, roughness: 0.8 })
  }
}
