/**
 * Canned review angles — the shared table behind the `view` op. Dependency-free
 * (no three.js), so `protocol.js` can import it the way it already imports
 * config.js and materials.js, and the *server* can range-check `n`.
 *
 * That range check is the reason this table moved out of CameraDirector: while
 * it was module-scoped there, `view 7` returned ok:true and did nothing —
 * indistinguishable from success to a blind agent.
 *
 * Each entry is [azimuth°, elevation°, name]. Together they cover front / side /
 * plan / back / massing — no blind side.
 */

export const VIEWS = {
  1: [45, 25, 'three-quarter'], // front hero
  2: [0, 12, 'front-low'], // front silhouette
  3: [90, 12, 'side-low'], // side silhouette
  4: [0, 89, 'top-down'], // plan
  5: [225, 25, 'rear three-quarter'], // the other side
  6: [40, 58, "bird's-eye"], // high angle — massing + footprint
}

/** Highest valid preset number; views are numbered 1..VIEW_COUNT. */
export const VIEW_COUNT = Object.keys(VIEWS).length
