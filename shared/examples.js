/**
 * Example builds — reusable command batches. Dependency-free so both the viewer
 * (starter/offline) and the server (boot seed) can use them, and the agent skill
 * (Phase 3) can cite them as worked examples. Each returns a plain command array
 * (validated by protocol.js), offset in blocks so several can be planted at once.
 */

/**
 * A stylized tree: one trunk cylinder plus a cluster of overlapping foliage
 * spheres. Built from the same ops an agent would emit. At blockSize 2 cm it
 * stands ~4.9 m tall. Pass block offsets to plant it elsewhere.
 */
export const tree = (ox = 0, oz = 0) => {
  const at = (x, y, z) => [x + ox, y, z + oz]
  return [
    // trunk: centered cylinder, base on the ground (spans y 0..140)
    { op: 'cylinder', at: at(0, 70, 0), r: 8, h: 140, mat: 'oak_dark' },
    // canopy: a big core sphere over the trunk top, then offset spheres around
    // and above it for an irregular, full crown
    { op: 'sphere', at: at(0, 190, 0), r: 55, mat: 'scale_green' },
    { op: 'sphere', at: at(48, 176, 26), r: 40, mat: 'scale_green_dk' },
    { op: 'sphere', at: at(-52, 182, -20), r: 42, mat: 'tile_green' },
    { op: 'sphere', at: at(22, 222, -34), r: 38, mat: 'jade' },
    { op: 'sphere', at: at(-30, 214, 32), r: 40, mat: 'scale_green' },
    { op: 'sphere', at: at(36, 206, -46), r: 34, mat: 'scale_green_dk' },
    { op: 'sphere', at: at(-42, 158, 34), r: 34, mat: 'tile_green' },
  ]
}
