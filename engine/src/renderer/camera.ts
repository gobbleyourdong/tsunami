/**
 * Camera system — perspective and orthographic.
 * Input-driven orbit and fly modes. Frustum planes for culling.
 */

import { Mat4, Vec3, mat4, vec3 } from '../math/vec'

export type CameraMode = 'perspective' | 'orthographic'
export type ControlMode = 'orbit' | 'fly' | 'none'

export interface CameraOptions {
  mode?: CameraMode
  fov?: number        // degrees, perspective only
  near?: number
  far?: number
  orthoSize?: number  // half-height in world units, ortho only
  position?: Vec3
  target?: Vec3
  up?: Vec3
  controls?: ControlMode
}

export interface FrustumPlane {
  normal: Vec3
  distance: number
}

export class Camera {
  mode: CameraMode
  fov: number
  near: number
  far: number
  orthoSize: number
  position: Vec3
  target: Vec3
  up: Vec3
  controls: ControlMode

  // Derived matrices
  view: Float32Array = mat4.create()
  projection: Float32Array = mat4.create()
  viewProjection: Float32Array = mat4.create()
  inverseViewProjection: Float32Array = mat4.create()

  // Frustum for culling
  frustumPlanes: FrustumPlane[] = []

  // Orbit state
  private orbitYaw = 0
  private orbitPitch = 0.4
  private orbitDistance = 10

  // Fly state
  private flyYaw = 0
  private flyPitch = 0

  private aspect = 1

  constructor(options: CameraOptions = {}) {
    this.mode = options.mode ?? 'perspective'
    this.fov = options.fov ?? 60
    this.near = options.near ?? 0.1
    this.far = options.far ?? 1000
    this.orthoSize = options.orthoSize ?? 10
    this.position = options.position ?? [0, 5, 10]
    this.target = options.target ?? [0, 0, 0]
    this.up = options.up ?? [0, 1, 0]
    this.controls = options.controls ?? 'orbit'

    if (this.controls === 'orbit') {
      const dx = this.position[0] - this.target[0]
      const dy = this.position[1] - this.target[1]
      const dz = this.position[2] - this.target[2]
      this.orbitDistance = Math.sqrt(dx * dx + dy * dy + dz * dz)
      this.orbitYaw = Math.atan2(dx, dz)
      this.orbitPitch = Math.asin(dy / this.orbitDistance)
    }
  }

  setAspect(width: number, height: number): void {
    this.aspect = width / height
  }

  update(): void {
    if (this.controls === 'orbit') {
      // Recompute position from orbit params
      const cp = Math.cos(this.orbitPitch)
      this.position = [
        this.target[0] + this.orbitDistance * cp * Math.sin(this.orbitYaw),
        this.target[1] + this.orbitDistance * Math.sin(this.orbitPitch),
        this.target[2] + this.orbitDistance * cp * Math.cos(this.orbitYaw),
      ]
    }

    mat4.lookAt(this.view, this.position, this.target, this.up)

    if (this.mode === 'perspective') {
      mat4.perspective(
        this.projection,
        (this.fov * Math.PI) / 180,
        this.aspect,
        this.near,
        this.far
      )
    } else {
      const halfH = this.orthoSize
      const halfW = halfH * this.aspect
      mat4.ortho(this.projection, -halfW, halfW, -halfH, halfH, this.near, this.far)
    }

    mat4.multiply(this.viewProjection, this.projection, this.view)
    mat4.invert(this.inverseViewProjection, this.viewProjection)
    this.extractFrustumPlanes()
  }

  // --- Orbit controls ---
  orbitRotate(deltaYaw: number, deltaPitch: number): void {
    this.orbitYaw += deltaYaw
    this.orbitPitch = Math.max(-Math.PI / 2 + 0.01, Math.min(Math.PI / 2 - 0.01, this.orbitPitch + deltaPitch))
  }

  orbitZoom(delta: number): void {
    this.orbitDistance = Math.max(0.5, this.orbitDistance * (1 + delta))
  }

  orbitPan(dx: number, dy: number): void {
    const right = vec3.create()
    const up = vec3.create()
    // Extract right and up from view matrix
    right[0] = this.view[0]; right[1] = this.view[4]; right[2] = this.view[8]
    up[0] = this.view[1]; up[1] = this.view[5]; up[2] = this.view[9]
    const scale = this.orbitDistance * 0.002
    this.target[0] += (right[0] * -dx + up[0] * dy) * scale
    this.target[1] += (right[1] * -dx + up[1] * dy) * scale
    this.target[2] += (right[2] * -dx + up[2] * dy) * scale
  }

  // --- Fly controls ---
  flyRotate(deltaYaw: number, deltaPitch: number): void {
    this.flyYaw += deltaYaw
    this.flyPitch = Math.max(-Math.PI / 2 + 0.01, Math.min(Math.PI / 2 - 0.01, this.flyPitch + deltaPitch))
    // Update target from yaw/pitch
    const dir: Vec3 = [
      Math.cos(this.flyPitch) * Math.sin(this.flyYaw),
      Math.sin(this.flyPitch),
      Math.cos(this.flyPitch) * Math.cos(this.flyYaw),
    ]
    this.target = vec3.add(vec3.create(), this.position, dir)
  }

  flyMove(forward: number, right: number, up: number, speed: number): void {
    const dir = vec3.normalize(vec3.create(), vec3.sub(vec3.create(), this.target, this.position))
    const rightDir = vec3.normalize(vec3.create(), vec3.cross(vec3.create(), dir, this.up))
    this.position[0] += (dir[0] * forward + rightDir[0] * right) * speed
    this.position[1] += up * speed
    this.position[2] += (dir[2] * forward + rightDir[2] * right) * speed
    this.target[0] += (dir[0] * forward + rightDir[0] * right) * speed
    this.target[1] += up * speed
    this.target[2] += (dir[2] * forward + rightDir[2] * right) * speed
  }

  // --- Frustum culling ---
  private extractFrustumPlanes(): void {
    const m = this.viewProjection
    this.frustumPlanes = [
      this.normalizePlane(m[3] + m[0], m[7] + m[4], m[11] + m[8], m[15] + m[12]),  // left
      this.normalizePlane(m[3] - m[0], m[7] - m[4], m[11] - m[8], m[15] - m[12]),  // right
      this.normalizePlane(m[3] + m[1], m[7] + m[5], m[11] + m[9], m[15] + m[13]),  // bottom
      this.normalizePlane(m[3] - m[1], m[7] - m[5], m[11] - m[9], m[15] - m[13]),  // top
      this.normalizePlane(m[3] + m[2], m[7] + m[6], m[11] + m[10], m[15] + m[14]), // near
      this.normalizePlane(m[3] - m[2], m[7] - m[6], m[11] - m[10], m[15] - m[14]), // far
    ]
  }

  private normalizePlane(a: number, b: number, c: number, d: number): FrustumPlane {
    const len = Math.sqrt(a * a + b * b + c * c)
    return { normal: [a / len, b / len, c / len], distance: d / len }
  }

  isSphereFrustumVisible(center: Vec3, radius: number): boolean {
    for (const plane of this.frustumPlanes) {
      const dist =
        plane.normal[0] * center[0] +
        plane.normal[1] * center[1] +
        plane.normal[2] * center[2] +
        plane.distance
      if (dist < -radius) return false
    }
    return true
  }

  // --- Input binding ---
  bindToCanvas(canvas: HTMLCanvasElement): () => void {
    let isDown = false
    let button = -1
    let lastX = 0
    let lastY = 0
    const keys = new Set<string>()

    const onPointerDown = (e: PointerEvent) => {
      isDown = true
      button = e.button
      lastX = e.clientX
      lastY = e.clientY
      canvas.setPointerCapture(e.pointerId)
    }

    const onPointerMove = (e: PointerEvent) => {
      if (!isDown) return
      const dx = e.clientX - lastX
      const dy = e.clientY - lastY
      lastX = e.clientX
      lastY = e.clientY

      if (this.controls === 'orbit') {
        if (button === 0) this.orbitRotate(-dx * 0.005, -dy * 0.005)
        if (button === 1 || button === 2) this.orbitPan(dx, dy)
      } else if (this.controls === 'fly') {
        this.flyRotate(-dx * 0.003, -dy * 0.003)
      }
    }

    const onPointerUp = () => { isDown = false }

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      if (this.controls === 'orbit') this.orbitZoom(e.deltaY * 0.001)
    }

    const onKeyDown = (e: KeyboardEvent) => { keys.add(e.code) }
    const onKeyUp = (e: KeyboardEvent) => { keys.delete(e.code) }

    canvas.addEventListener('pointerdown', onPointerDown)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)

    // Fly mode key-based movement
    let animId = 0
    if (this.controls === 'fly') {
      const tick = () => {
        const speed = 0.15
        const fwd = (keys.has('KeyW') ? 1 : 0) - (keys.has('KeyS') ? 1 : 0)
        const rgt = (keys.has('KeyD') ? 1 : 0) - (keys.has('KeyA') ? 1 : 0)
        const up = (keys.has('Space') ? 1 : 0) - (keys.has('ShiftLeft') ? 1 : 0)
        if (fwd || rgt || up) this.flyMove(fwd, rgt, up, speed)
        animId = requestAnimationFrame(tick)
      }
      animId = requestAnimationFrame(tick)
    }

    // Return cleanup function
    return () => {
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('wheel', onWheel)
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      if (animId) cancelAnimationFrame(animId)
    }
  }
}
