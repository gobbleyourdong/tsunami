/**
 * NavMesh pathfinding — A* on a polygon navigation mesh.
 * Nodes are polygon centroids, edges are shared polygon edges.
 */

import { Vec3, vec3 } from '../math/vec'

export interface NavNode {
  id: number
  position: Vec3  // centroid
  neighbors: number[]  // adjacent node ids
  polygon: Vec3[]  // vertices of this nav polygon
}

export class NavMesh {
  nodes: NavNode[] = []

  addNode(position: Vec3, polygon: Vec3[] = []): number {
    const id = this.nodes.length
    this.nodes.push({ id, position, neighbors: [], polygon })
    return id
  }

  connect(a: number, b: number): void {
    if (!this.nodes[a].neighbors.includes(b)) this.nodes[a].neighbors.push(b)
    if (!this.nodes[b].neighbors.includes(a)) this.nodes[b].neighbors.push(a)
  }

  /** Find nearest nav node to a world position. */
  findNearest(position: Vec3): number {
    let bestId = 0
    let bestDist = Infinity
    for (const node of this.nodes) {
      const d = vec3.distance(position, node.position)
      if (d < bestDist) {
        bestDist = d
        bestId = node.id
      }
    }
    return bestId
  }

  /** A* pathfinding between two nav nodes. Returns array of positions. */
  findPath(startId: number, endId: number): Vec3[] {
    if (startId === endId) return [this.nodes[startId].position]

    const openSet = new Set<number>([startId])
    const cameFrom = new Map<number, number>()
    const gScore = new Map<number, number>()
    const fScore = new Map<number, number>()

    gScore.set(startId, 0)
    fScore.set(startId, this.heuristic(startId, endId))

    while (openSet.size > 0) {
      // Pick node with lowest fScore
      let current = -1
      let bestF = Infinity
      for (const id of openSet) {
        const f = fScore.get(id) ?? Infinity
        if (f < bestF) {
          bestF = f
          current = id
        }
      }

      if (current === endId) {
        return this.reconstructPath(cameFrom, current)
      }

      openSet.delete(current)
      const currentNode = this.nodes[current]

      for (const neighborId of currentNode.neighbors) {
        const tentativeG = (gScore.get(current) ?? Infinity) +
          vec3.distance(currentNode.position, this.nodes[neighborId].position)

        if (tentativeG < (gScore.get(neighborId) ?? Infinity)) {
          cameFrom.set(neighborId, current)
          gScore.set(neighborId, tentativeG)
          fScore.set(neighborId, tentativeG + this.heuristic(neighborId, endId))
          openSet.add(neighborId)
        }
      }
    }

    return [] // no path found
  }

  /** High-level: find path between world positions. */
  findWorldPath(from: Vec3, to: Vec3): Vec3[] {
    const startId = this.findNearest(from)
    const endId = this.findNearest(to)
    const path = this.findPath(startId, endId)
    if (path.length === 0) return []

    // Replace first/last with exact world positions
    path[0] = from
    path[path.length - 1] = to
    return path
  }

  private heuristic(a: number, b: number): number {
    return vec3.distance(this.nodes[a].position, this.nodes[b].position)
  }

  private reconstructPath(cameFrom: Map<number, number>, current: number): Vec3[] {
    const path: Vec3[] = [this.nodes[current].position]
    while (cameFrom.has(current)) {
      current = cameFrom.get(current)!
      path.unshift(this.nodes[current].position)
    }
    return path
  }

  /** Generate a simple grid NavMesh for testing/prototyping. */
  static createGrid(width: number, depth: number, cellSize = 1): NavMesh {
    const mesh = new NavMesh()
    const cols = Math.floor(width / cellSize)
    const rows = Math.floor(depth / cellSize)

    // Create nodes
    for (let z = 0; z < rows; z++) {
      for (let x = 0; x < cols; x++) {
        const cx = (x + 0.5) * cellSize - width / 2
        const cz = (z + 0.5) * cellSize - depth / 2
        mesh.addNode([cx, 0, cz])
      }
    }

    // Connect neighbors (4-directional + diagonals)
    for (let z = 0; z < rows; z++) {
      for (let x = 0; x < cols; x++) {
        const id = z * cols + x
        if (x < cols - 1) mesh.connect(id, id + 1)
        if (z < rows - 1) mesh.connect(id, id + cols)
        if (x < cols - 1 && z < rows - 1) mesh.connect(id, id + cols + 1)
        if (x > 0 && z < rows - 1) mesh.connect(id, id + cols - 1)
      }
    }

    return mesh
  }
}
