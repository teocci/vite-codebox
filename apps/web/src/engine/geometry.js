import { BoxGeometry, SphereGeometry, CylinderGeometry } from 'three'

/**
 * Unit geometries centered at the origin, sized 1 block. Parts scale them via the
 * per-instance matrix, so every part of a given kind shares one geometry (and one
 * InstancedMesh per family). The parent group applies BLOCK_SIZE.
 *
 * Sphere/cylinder use radius 0.5 so the diameter is 1 — scaling by the part's full
 * extent then yields the intended radius.
 *
 * The x and z cylinders exist because a scale cannot reorient an axis, and a wheel
 * is a cylinder about x. Baking the rotation into the vertex buffer keeps the
 * instance matrix rotation-free, so every part stays axis-aligned and its AABB
 * stays exact — the alternative, a per-instance quaternion, would force a
 * conservative AABB everywhere geometry is measured.
 */
const cylinder = () => new CylinderGeometry(0.5, 0.5, 1, 24)

export const makeGeometries = () => ({
  box: new BoxGeometry(1, 1, 1),
  sphere: new SphereGeometry(0.5, 24, 16),
  cylinder: cylinder(),
  cylinder_x: cylinder().rotateZ(Math.PI / 2),
  cylinder_z: cylinder().rotateX(Math.PI / 2),
})

export const GEOMETRY_KINDS = ['box', 'sphere', 'cylinder', 'cylinder_x', 'cylinder_z']
