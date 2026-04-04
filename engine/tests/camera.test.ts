import { describe, it, expect } from 'vitest'
import { Camera } from '../src/renderer/camera'

describe('Camera', () => {
  it('creates with default values', () => {
    const cam = new Camera()
    expect(cam.mode).toBe('perspective')
    expect(cam.controls).toBe('orbit')
    expect(cam.fov).toBe(60)
    expect(cam.near).toBe(0.1)
    expect(cam.far).toBe(1000)
  })

  it('creates orthographic camera', () => {
    const cam = new Camera({ mode: 'orthographic', orthoSize: 20 })
    expect(cam.mode).toBe('orthographic')
    expect(cam.orthoSize).toBe(20)
  })

  it('generates view-projection matrices on update', () => {
    const cam = new Camera({
      position: [0, 5, 10],
      target: [0, 0, 0],
    })
    cam.setAspect(1280, 720)
    cam.update()

    // viewProjection should not be identity
    expect(cam.viewProjection[0]).not.toBe(1)
    expect(cam.viewProjection[5]).not.toBe(1)
  })

  it('extracts frustum planes on update', () => {
    const cam = new Camera()
    cam.setAspect(1280, 720)
    cam.update()
    expect(cam.frustumPlanes.length).toBe(6)
    for (const plane of cam.frustumPlanes) {
      const len = Math.sqrt(
        plane.normal[0] ** 2 + plane.normal[1] ** 2 + plane.normal[2] ** 2
      )
      expect(len).toBeCloseTo(1, 3)
    }
  })

  it('frustum culls objects behind camera', () => {
    const cam = new Camera({
      position: [0, 0, 5],
      target: [0, 0, 0],
    })
    cam.setAspect(1, 1)
    cam.update()

    // Object in front of camera should be visible
    expect(cam.isSphereFrustumVisible([0, 0, 0], 1)).toBe(true)

    // Object far behind camera should not be visible
    expect(cam.isSphereFrustumVisible([0, 0, 100], 1)).toBe(false)
  })

  it('orbit zoom changes distance', () => {
    const cam = new Camera({
      position: [0, 0, 10],
      target: [0, 0, 0],
      controls: 'orbit',
    })
    const initialDist = Math.sqrt(
      cam.position[0] ** 2 + cam.position[1] ** 2 + cam.position[2] ** 2
    )

    cam.orbitZoom(0.1) // zoom out
    cam.update()

    const newDist = Math.sqrt(
      cam.position[0] ** 2 + cam.position[1] ** 2 + cam.position[2] ** 2
    )
    expect(newDist).toBeGreaterThan(initialDist)
  })

  it('fly move changes position', () => {
    const cam = new Camera({
      position: [0, 0, 5],
      target: [0, 0, 0],
      controls: 'fly',
    })
    const initialZ = cam.position[2]

    cam.flyMove(1, 0, 0, 1.0) // move forward
    expect(cam.position[2]).toBeLessThan(initialZ) // moved toward target
  })
})

describe('Camera frame loop integration', () => {
  it('aspect ratio affects projection', () => {
    const cam = new Camera({ mode: 'perspective', fov: 60 })

    cam.setAspect(1920, 1080)
    cam.update()
    const wide = cam.projection[0]

    cam.setAspect(1080, 1920)
    cam.update()
    const tall = cam.projection[0]

    // Wider aspect should have smaller x scale
    expect(wide).toBeLessThan(tall)
  })
})
