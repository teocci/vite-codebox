/**
 * Authoritative semantic world — the server's source of truth for parts. Pure
 * state with O(1) add/remove by id; the renderer's instance slots live only in
 * the viewer, never here. Ids are assigned here and travel to every viewer so
 * removals reference the same part everywhere.
 */
export default class WorldStore {
  constructor() {
    this.parts = new Map() // id -> { id, kind, center, size, material }
    this.nextId = 1
  }

  /** Store a normalized part, assigning an id. Returns the id. */
  add(part) {
    const id = this.nextId++
    this.parts.set(id, { id, ...part })
    return id
  }

  /** O(1) removal by id. Returns true if it existed. */
  remove(id) {
    return this.parts.delete(id)
  }

  clear() {
    this.parts.clear()
    this.nextId = 1
  }

  /** Full world as an array of parts (for the snapshot a new viewer receives). */
  snapshot() {
    return [...this.parts.values()]
  }

  get size() {
    return this.parts.size
  }
}
