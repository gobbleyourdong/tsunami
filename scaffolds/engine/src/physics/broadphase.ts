/**
 * Broadphase: spatial hash grid — O(1) neighbor lookup.
 * Uniform cells. Objects register by AABB, query returns potential pairs.
 */

import { Vec3 } from '../math/vec'

export interface AABB {
  min: Vec3
  max: Vec3
}

export function aabbOverlap(a: AABB, b: AABB): boolean {
  return (
    a.min[0] <= b.max[0] && a.max[0] >= b.min[0] &&
    a.min[1] <= b.max[1] && a.max[1] >= b.min[1] &&
    a.min[2] <= b.max[2] && a.max[2] >= b.min[2]
  )
}

export function computeAABB(position: Vec3, boundingRadius: number): AABB {
  return {
    min: [position[0] - boundingRadius, position[1] - boundingRadius, position[2] - boundingRadius],
    max: [position[0] + boundingRadius, position[1] + boundingRadius, position[2] + boundingRadius],
  }
}

export interface BroadphaseEntry {
  id: number
  aabb: AABB
}

export class SpatialHashGrid {
  private cellSize: number
  private invCellSize: number
  private cells = new Map<number, number[]>()  // hash → list of ids
  private entries = new Map<number, AABB>()    // id → aabb

  constructor(cellSize = 4) {
    this.cellSize = cellSize
    this.invCellSize = 1 / cellSize
  }

  private hash(cx: number, cy: number, cz: number): number {
    // Large primes for spatial hashing
    return ((cx * 92837111) ^ (cy * 689287499) ^ (cz * 283923481)) | 0
  }

  private getCellCoords(x: number, y: number, z: number): [number, number, number] {
    return [
      Math.floor(x * this.invCellSize),
      Math.floor(y * this.invCellSize),
      Math.floor(z * this.invCellSize),
    ]
  }

  /** Insert or update an entry. */
  insert(id: number, aabb: AABB): void {
    this.remove(id)
    this.entries.set(id, aabb)

    const [minX, minY, minZ] = this.getCellCoords(aabb.min[0], aabb.min[1], aabb.min[2])
    const [maxX, maxY, maxZ] = this.getCellCoords(aabb.max[0], aabb.max[1], aabb.max[2])

    for (let z = minZ; z <= maxZ; z++) {
      for (let y = minY; y <= maxY; y++) {
        for (let x = minX; x <= maxX; x++) {
          const h = this.hash(x, y, z)
          let cell = this.cells.get(h)
          if (!cell) {
            cell = []
            this.cells.set(h, cell)
          }
          cell.push(id)
        }
      }
    }
  }

  /** Remove an entry. */
  remove(id: number): void {
    const aabb = this.entries.get(id)
    if (!aabb) return
    this.entries.delete(id)

    const [minX, minY, minZ] = this.getCellCoords(aabb.min[0], aabb.min[1], aabb.min[2])
    const [maxX, maxY, maxZ] = this.getCellCoords(aabb.max[0], aabb.max[1], aabb.max[2])

    for (let z = minZ; z <= maxZ; z++) {
      for (let y = minY; y <= maxY; y++) {
        for (let x = minX; x <= maxX; x++) {
          const h = this.hash(x, y, z)
          const cell = this.cells.get(h)
          if (cell) {
            const idx = cell.indexOf(id)
            if (idx !== -1) cell.splice(idx, 1)
            if (cell.length === 0) this.cells.delete(h)
          }
        }
      }
    }
  }

  /** Get all potential overlapping pairs (broad check). */
  queryPairs(): [number, number][] {
    const pairs = new Set<string>()
    const result: [number, number][] = []

    for (const cell of this.cells.values()) {
      for (let i = 0; i < cell.length; i++) {
        for (let j = i + 1; j < cell.length; j++) {
          const a = Math.min(cell[i], cell[j])
          const b = Math.max(cell[i], cell[j])
          const key = `${a}:${b}`
          if (!pairs.has(key)) {
            pairs.add(key)
            const aabbA = this.entries.get(a)!
            const aabbB = this.entries.get(b)!
            if (aabbOverlap(aabbA, aabbB)) {
              result.push([a, b])
            }
          }
        }
      }
    }

    return result
  }

  /** Query all entries overlapping a given AABB. */
  query(aabb: AABB): number[] {
    const result = new Set<number>()
    const [minX, minY, minZ] = this.getCellCoords(aabb.min[0], aabb.min[1], aabb.min[2])
    const [maxX, maxY, maxZ] = this.getCellCoords(aabb.max[0], aabb.max[1], aabb.max[2])

    for (let z = minZ; z <= maxZ; z++) {
      for (let y = minY; y <= maxY; y++) {
        for (let x = minX; x <= maxX; x++) {
          const h = this.hash(x, y, z)
          const cell = this.cells.get(h)
          if (cell) {
            for (const id of cell) {
              const entryAABB = this.entries.get(id)
              if (entryAABB && aabbOverlap(aabb, entryAABB)) {
                result.add(id)
              }
            }
          }
        }
      }
    }

    return Array.from(result)
  }

  clear(): void {
    this.cells.clear()
    this.entries.clear()
  }
}
