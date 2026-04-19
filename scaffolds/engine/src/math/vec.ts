/**
 * Minimal math library — Vec3, Mat4 operations.
 * No dependencies. Column-major Float32Array layout (WebGPU/GL convention).
 */

export type Vec2 = [number, number]
export type Vec3 = [number, number, number]
export type Vec4 = [number, number, number, number]

export const vec3 = {
  create(): Vec3 {
    return [0, 0, 0]
  },

  fromValues(x: number, y: number, z: number): Vec3 {
    return [x, y, z]
  },

  add(out: Vec3, a: Vec3, b: Vec3): Vec3 {
    out[0] = a[0] + b[0]
    out[1] = a[1] + b[1]
    out[2] = a[2] + b[2]
    return out
  },

  sub(out: Vec3, a: Vec3, b: Vec3): Vec3 {
    out[0] = a[0] - b[0]
    out[1] = a[1] - b[1]
    out[2] = a[2] - b[2]
    return out
  },

  scale(out: Vec3, a: Vec3, s: number): Vec3 {
    out[0] = a[0] * s
    out[1] = a[1] * s
    out[2] = a[2] * s
    return out
  },

  dot(a: Vec3, b: Vec3): number {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
  },

  cross(out: Vec3, a: Vec3, b: Vec3): Vec3 {
    out[0] = a[1] * b[2] - a[2] * b[1]
    out[1] = a[2] * b[0] - a[0] * b[2]
    out[2] = a[0] * b[1] - a[1] * b[0]
    return out
  },

  length(a: Vec3): number {
    return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
  },

  normalize(out: Vec3, a: Vec3): Vec3 {
    const len = vec3.length(a)
    if (len > 0.00001) {
      out[0] = a[0] / len
      out[1] = a[1] / len
      out[2] = a[2] / len
    }
    return out
  },

  lerp(out: Vec3, a: Vec3, b: Vec3, t: number): Vec3 {
    out[0] = a[0] + (b[0] - a[0]) * t
    out[1] = a[1] + (b[1] - a[1]) * t
    out[2] = a[2] + (b[2] - a[2]) * t
    return out
  },

  distance(a: Vec3, b: Vec3): number {
    const dx = a[0] - b[0]
    const dy = a[1] - b[1]
    const dz = a[2] - b[2]
    return Math.sqrt(dx * dx + dy * dy + dz * dz)
  },

  transformMat4(out: Vec3, a: Vec3, m: Float32Array): Vec3 {
    const w = m[3] * a[0] + m[7] * a[1] + m[11] * a[2] + m[15]
    out[0] = (m[0] * a[0] + m[4] * a[1] + m[8] * a[2] + m[12]) / w
    out[1] = (m[1] * a[0] + m[5] * a[1] + m[9] * a[2] + m[13]) / w
    out[2] = (m[2] * a[0] + m[6] * a[1] + m[10] * a[2] + m[14]) / w
    return out
  },
}

export type Mat4 = Float32Array

export const mat4 = {
  create(): Mat4 {
    const m = new Float32Array(16)
    m[0] = 1; m[5] = 1; m[10] = 1; m[15] = 1
    return m
  },

  identity(out: Mat4): Mat4 {
    out.fill(0)
    out[0] = 1; out[5] = 1; out[10] = 1; out[15] = 1
    return out
  },

  perspective(out: Mat4, fovY: number, aspect: number, near: number, far: number): Mat4 {
    const f = 1.0 / Math.tan(fovY / 2)
    out.fill(0)
    out[0] = f / aspect
    out[5] = f
    out[10] = far / (near - far)
    out[11] = -1
    out[14] = (near * far) / (near - far)
    return out
  },

  ortho(out: Mat4, left: number, right: number, bottom: number, top: number, near: number, far: number): Mat4 {
    const lr = 1 / (left - right)
    const bt = 1 / (bottom - top)
    const nf = 1 / (near - far)
    out.fill(0)
    out[0] = -2 * lr
    out[5] = -2 * bt
    out[10] = nf
    out[12] = (left + right) * lr
    out[13] = (top + bottom) * bt
    out[14] = near * nf
    out[15] = 1
    return out
  },

  lookAt(out: Mat4, eye: Vec3, center: Vec3, up: Vec3): Mat4 {
    const zAxis = vec3.normalize(vec3.create(), vec3.sub(vec3.create(), eye, center))
    const xAxis = vec3.normalize(vec3.create(), vec3.cross(vec3.create(), up, zAxis))
    const yAxis = vec3.cross(vec3.create(), zAxis, xAxis)

    out[0] = xAxis[0]; out[1] = yAxis[0]; out[2] = zAxis[0]; out[3] = 0
    out[4] = xAxis[1]; out[5] = yAxis[1]; out[6] = zAxis[1]; out[7] = 0
    out[8] = xAxis[2]; out[9] = yAxis[2]; out[10] = zAxis[2]; out[11] = 0
    out[12] = -vec3.dot(xAxis, eye)
    out[13] = -vec3.dot(yAxis, eye)
    out[14] = -vec3.dot(zAxis, eye)
    out[15] = 1
    return out
  },

  multiply(out: Mat4, a: Mat4, b: Mat4): Mat4 {
    for (let col = 0; col < 4; col++) {
      for (let row = 0; row < 4; row++) {
        out[col * 4 + row] =
          a[row] * b[col * 4] +
          a[4 + row] * b[col * 4 + 1] +
          a[8 + row] * b[col * 4 + 2] +
          a[12 + row] * b[col * 4 + 3]
      }
    }
    return out
  },

  translate(out: Mat4, a: Mat4, v: Vec3): Mat4 {
    if (out !== a) {
      for (let i = 0; i < 12; i++) out[i] = a[i]
    }
    out[12] = a[0] * v[0] + a[4] * v[1] + a[8] * v[2] + a[12]
    out[13] = a[1] * v[0] + a[5] * v[1] + a[9] * v[2] + a[13]
    out[14] = a[2] * v[0] + a[6] * v[1] + a[10] * v[2] + a[14]
    out[15] = a[3] * v[0] + a[7] * v[1] + a[11] * v[2] + a[15]
    return out
  },

  scale(out: Mat4, a: Mat4, v: Vec3): Mat4 {
    out[0] = a[0] * v[0]; out[1] = a[1] * v[0]; out[2] = a[2] * v[0]; out[3] = a[3] * v[0]
    out[4] = a[4] * v[1]; out[5] = a[5] * v[1]; out[6] = a[6] * v[1]; out[7] = a[7] * v[1]
    out[8] = a[8] * v[2]; out[9] = a[9] * v[2]; out[10] = a[10] * v[2]; out[11] = a[11] * v[2]
    out[12] = a[12]; out[13] = a[13]; out[14] = a[14]; out[15] = a[15]
    return out
  },

  rotateY(out: Mat4, a: Mat4, angle: number): Mat4 {
    const s = Math.sin(angle)
    const c = Math.cos(angle)
    const a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3]
    const a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11]
    if (out !== a) {
      out[4] = a[4]; out[5] = a[5]; out[6] = a[6]; out[7] = a[7]
      out[12] = a[12]; out[13] = a[13]; out[14] = a[14]; out[15] = a[15]
    }
    out[0] = a00 * c - a20 * s; out[1] = a01 * c - a21 * s; out[2] = a02 * c - a22 * s; out[3] = a03 * c - a23 * s
    out[8] = a00 * s + a20 * c; out[9] = a01 * s + a21 * c; out[10] = a02 * s + a22 * c; out[11] = a03 * s + a23 * c
    return out
  },

  rotateX(out: Mat4, a: Mat4, angle: number): Mat4 {
    const s = Math.sin(angle)
    const c = Math.cos(angle)
    const a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7]
    const a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11]
    if (out !== a) {
      out[0] = a[0]; out[1] = a[1]; out[2] = a[2]; out[3] = a[3]
      out[12] = a[12]; out[13] = a[13]; out[14] = a[14]; out[15] = a[15]
    }
    out[4] = a10 * c + a20 * s; out[5] = a11 * c + a21 * s; out[6] = a12 * c + a22 * s; out[7] = a13 * c + a23 * s
    out[8] = a20 * c - a10 * s; out[9] = a21 * c - a11 * s; out[10] = a22 * c - a12 * s; out[11] = a23 * c - a13 * s
    return out
  },

  invert(out: Mat4, a: Mat4): Mat4 {
    const a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3]
    const a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7]
    const a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11]
    const a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15]

    const b00 = a00 * a11 - a01 * a10
    const b01 = a00 * a12 - a02 * a10
    const b02 = a00 * a13 - a03 * a10
    const b03 = a01 * a12 - a02 * a11
    const b04 = a01 * a13 - a03 * a11
    const b05 = a02 * a13 - a03 * a12
    const b06 = a20 * a31 - a21 * a30
    const b07 = a20 * a32 - a22 * a30
    const b08 = a20 * a33 - a23 * a30
    const b09 = a21 * a32 - a22 * a31
    const b10 = a21 * a33 - a23 * a31
    const b11 = a22 * a33 - a23 * a32

    let det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06
    if (Math.abs(det) < 1e-10) return out
    det = 1.0 / det

    out[0] = (a11 * b11 - a12 * b10 + a13 * b09) * det
    out[1] = (a02 * b10 - a01 * b11 - a03 * b09) * det
    out[2] = (a31 * b05 - a32 * b04 + a33 * b03) * det
    out[3] = (a22 * b04 - a21 * b05 - a23 * b03) * det
    out[4] = (a12 * b08 - a10 * b11 - a13 * b07) * det
    out[5] = (a00 * b11 - a02 * b08 + a03 * b07) * det
    out[6] = (a32 * b02 - a30 * b05 - a33 * b01) * det
    out[7] = (a20 * b05 - a22 * b02 + a23 * b01) * det
    out[8] = (a10 * b10 - a11 * b08 + a13 * b06) * det
    out[9] = (a01 * b08 - a00 * b10 - a03 * b06) * det
    out[10] = (a30 * b04 - a31 * b02 + a33 * b00) * det
    out[11] = (a21 * b02 - a20 * b04 - a23 * b00) * det
    out[12] = (a11 * b07 - a10 * b09 - a12 * b06) * det
    out[13] = (a00 * b09 - a01 * b07 + a02 * b06) * det
    out[14] = (a31 * b01 - a30 * b03 - a32 * b00) * det
    out[15] = (a20 * b03 - a21 * b01 + a22 * b00) * det
    return out
  },

  fromTranslation(out: Mat4, v: Vec3): Mat4 {
    mat4.identity(out)
    out[12] = v[0]; out[13] = v[1]; out[14] = v[2]
    return out
  },

  fromScaling(out: Mat4, v: Vec3): Mat4 {
    out.fill(0)
    out[0] = v[0]; out[5] = v[1]; out[10] = v[2]; out[15] = 1
    return out
  },

  transpose(out: Mat4, a: Mat4): Mat4 {
    if (out === a) {
      const swap = (i: number, j: number) => { const t = a[i]; out[i] = a[j]; out[j] = t }
      swap(1, 4); swap(2, 8); swap(3, 12); swap(6, 9); swap(7, 13); swap(11, 14)
    } else {
      out[0] = a[0]; out[1] = a[4]; out[2] = a[8]; out[3] = a[12]
      out[4] = a[1]; out[5] = a[5]; out[6] = a[9]; out[7] = a[13]
      out[8] = a[2]; out[9] = a[6]; out[10] = a[10]; out[11] = a[14]
      out[12] = a[3]; out[13] = a[7]; out[14] = a[11]; out[15] = a[15]
    }
    return out
  },
}
