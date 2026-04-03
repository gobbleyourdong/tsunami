/**
 * Scene — top-level container for nodes, rendering, and culling.
 */

import { SceneNode } from './node'
import { Camera } from '../renderer/camera'
import { Mesh } from './mesh'

export interface RenderItem {
  node: SceneNode
  mesh: Mesh
  worldMatrix: Float32Array
}

export class Scene {
  root: SceneNode

  constructor() {
    this.root = new SceneNode('root')
  }

  addNode(node: SceneNode): void {
    this.root.addChild(node)
  }

  removeNode(node: SceneNode): void {
    this.root.removeChild(node)
  }

  updateTransforms(): void {
    this.root.updateWorldTransforms()
  }

  /**
   * Collect visible renderable nodes, culled against camera frustum.
   */
  collectRenderItems(camera: Camera): RenderItem[] {
    const items: RenderItem[] = []

    this.root.traverse((node) => {
      if (!node.visible) return
      const mesh = node.getComponent<Mesh>('mesh')
      if (!mesh) return

      // Frustum cull using world position + bounding radius
      const worldPos = node.getWorldPosition()
      if (node.boundingRadius > 0) {
        // Account for node scale
        const maxScale = Math.max(
          Math.abs(node.scale[0]),
          Math.abs(node.scale[1]),
          Math.abs(node.scale[2])
        )
        const scaledRadius = node.boundingRadius * maxScale
        if (!camera.isSphereFrustumVisible(worldPos, scaledRadius)) return
      }

      items.push({
        node,
        mesh,
        worldMatrix: node.worldMatrix,
      })
    })

    return items
  }

  findByName(name: string): SceneNode | undefined {
    return this.root.findByName(name)
  }

  get nodeCount(): number {
    let count = 0
    this.root.traverse(() => count++)
    return count - 1 // exclude root
  }
}
