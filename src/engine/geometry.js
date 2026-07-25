import { BoxGeometry, SphereGeometry, CylinderGeometry } from 'three'

/**
 * Unit geometries centered at the origin, sized 1 block. Parts scale them via the
 * per-instance matrix, so every part of a given kind shares one geometry (and one
 * InstancedMesh per family). The parent group applies BLOCK_SIZE.
 *
 * Sphere/cylinder use radius 0.5 so the diameter is 1 — scaling by the part's full
 * extent then yields the intended radius.
 */
export const makeGeometries = () => ({
  box: new BoxGeometry(1, 1, 1),
  sphere: new SphereGeometry(0.5, 24, 16),
  cylinder: new CylinderGeometry(0.5, 0.5, 1, 24),
})

export const GEOMETRY_KINDS = ['box', 'sphere', 'cylinder']
