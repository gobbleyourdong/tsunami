/**
 * Scene tree — nodes, transforms, parent-child hierarchy.
 * Godot-inspired: each node has a transform, children, and optional components.
 */

import { Mat4, Vec3, mat4 } from '../math/vec'

let nextId = 0

export class SceneNode {
  readonly id: number
  name: string
  parent: SceneNode | null = null
  children: SceneNode[] = []
  visible = true

  // Local transform
  position: Vec3 = [0, 0, 0]
  rotation: Vec3 = [0, 0, 0]  // Euler angles in radians (XYZ order)
  scale: Vec3 = [1, 1, 1]

  // Cached world transform
  localMatrix: Mat4 = mat4.create()
  worldMatrix: Mat4 = mat4.create()

  // Bounding sphere for frustum culling
  boundingRadius = 0

  // Arbitrary component data
  private components = new Map<string, unknown>()

  constructor(name?: string) {
    this.id = nextId++
    this.name = name ?? `node_${this.id}`
  }

  addChild(child: SceneNode): this {
    if (child.parent) {
      child.parent.removeChild(child)
    }
    child.parent = this
    this.children.push(child)
    return this
  }

  removeChild(child: SceneNode): this {
    const idx = this.children.indexOf(child)
    if (idx !== -1) {
      this.children.splice(idx, 1)
      child.parent = null
    }
    return this
  }

  detach(): void {
    if (this.parent) {
      this.parent.removeChild(this)
    }
  }

  /**
   * Update local matrix from position/rotation/scale,
   * then compute world matrix from parent chain.
   */
  updateTransform(): void {
    // Build local matrix: T * Ry * Rx * Rz * S
    mat4.identity(this.localMatrix)
    mat4.translate(this.localMatrix, this.localMatrix, this.position)
    mat4.rotateY(this.localMatrix, this.localMatrix, this.rotation[1])
    mat4.rotateX(this.localMatrix, this.localMatrix, this.rotation[0])

    // Z rotation (manual, reusing pattern from mat4)
    if (this.rotation[2] !== 0) {
      const s = Math.sin(this.rotation[2])
      const c = Math.cos(this.rotation[2])
      const m = this.localMatrix
      const a00 = m[0], a01 = m[1], a02 = m[2], a03 = m[3]
      const a10 = m[4], a11 = m[5], a12 = m[6], a13 = m[7]
      m[0] = a00 * c + a10 * s; m[1] = a01 * c + a11 * s
      m[2] = a02 * c + a12 * s; m[3] = a03 * c + a13 * s
      m[4] = a10 * c - a00 * s; m[5] = a11 * c - a01 * s
      m[6] = a12 * c - a02 * s; m[7] = a13 * c - a03 * s
    }

    mat4.scale(this.localMatrix, this.localMatrix, this.scale)

    // World matrix
    if (this.parent) {
      mat4.multiply(this.worldMatrix, this.parent.worldMatrix, this.localMatrix)
    } else {
      this.worldMatrix.set(this.localMatrix)
    }
  }

  /**
   * Recursively update transforms for entire subtree (depth-first).
   */
  updateWorldTransforms(): void {
    this.updateTransform()
    for (const child of this.children) {
      child.updateWorldTransforms()
    }
  }

  // --- Component system (simple key-value) ---

  setComponent<T>(key: string, value: T): this {
    this.components.set(key, value)
    return this
  }

  getComponent<T>(key: string): T | undefined {
    return this.components.get(key) as T | undefined
  }

  hasComponent(key: string): boolean {
    return this.components.has(key)
  }

  removeComponent(key: string): this {
    this.components.delete(key)
    return this
  }

  // --- Traversal ---

  traverse(callback: (node: SceneNode) => void): void {
    callback(this)
    for (const child of this.children) {
      child.traverse(callback)
    }
  }

  find(predicate: (node: SceneNode) => boolean): SceneNode | undefined {
    if (predicate(this)) return this
    for (const child of this.children) {
      const found = child.find(predicate)
      if (found) return found
    }
    return undefined
  }

  findByName(name: string): SceneNode | undefined {
    return this.find((n) => n.name === name)
  }

  getWorldPosition(): Vec3 {
    return [this.worldMatrix[12], this.worldMatrix[13], this.worldMatrix[14]]
  }
}
