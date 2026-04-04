/**
 * Quaternion operations — needed for skeletal animation.
 * [x, y, z, w] layout. All operations are non-allocating (write to out param).
 */

export type Quat = [number, number, number, number]

export const quat = {
  create(): Quat {
    return [0, 0, 0, 1]
  },

  identity(out: Quat): Quat {
    out[0] = 0; out[1] = 0; out[2] = 0; out[3] = 1
    return out
  },

  fromValues(x: number, y: number, z: number, w: number): Quat {
    return [x, y, z, w]
  },

  multiply(out: Quat, a: Quat, b: Quat): Quat {
    const ax = a[0], ay = a[1], az = a[2], aw = a[3]
    const bx = b[0], by = b[1], bz = b[2], bw = b[3]
    out[0] = aw * bx + ax * bw + ay * bz - az * by
    out[1] = aw * by - ax * bz + ay * bw + az * bx
    out[2] = aw * bz + ax * by - ay * bx + az * bw
    out[3] = aw * bw - ax * bx - ay * by - az * bz
    return out
  },

  slerp(out: Quat, a: Quat, b: Quat, t: number): Quat {
    let bx = b[0], by = b[1], bz = b[2], bw = b[3]

    let cosHalf = a[0] * bx + a[1] * by + a[2] * bz + a[3] * bw
    if (cosHalf < 0) {
      cosHalf = -cosHalf
      bx = -bx; by = -by; bz = -bz; bw = -bw
    }

    if (cosHalf >= 1.0) {
      out[0] = a[0]; out[1] = a[1]; out[2] = a[2]; out[3] = a[3]
      return out
    }

    const halfAngle = Math.acos(cosHalf)
    const sinHalf = Math.sqrt(1.0 - cosHalf * cosHalf)

    if (Math.abs(sinHalf) < 0.001) {
      out[0] = a[0] * 0.5 + bx * 0.5
      out[1] = a[1] * 0.5 + by * 0.5
      out[2] = a[2] * 0.5 + bz * 0.5
      out[3] = a[3] * 0.5 + bw * 0.5
      return out
    }

    const ra = Math.sin((1 - t) * halfAngle) / sinHalf
    const rb = Math.sin(t * halfAngle) / sinHalf

    out[0] = a[0] * ra + bx * rb
    out[1] = a[1] * ra + by * rb
    out[2] = a[2] * ra + bz * rb
    out[3] = a[3] * ra + bw * rb
    return out
  },

  normalize(out: Quat, a: Quat): Quat {
    const len = Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2] + a[3] * a[3])
    if (len > 0.00001) {
      const inv = 1 / len
      out[0] = a[0] * inv; out[1] = a[1] * inv; out[2] = a[2] * inv; out[3] = a[3] * inv
    }
    return out
  },

  invert(out: Quat, a: Quat): Quat {
    const dot = a[0] * a[0] + a[1] * a[1] + a[2] * a[2] + a[3] * a[3]
    const invDot = dot > 0 ? 1.0 / dot : 0
    out[0] = -a[0] * invDot
    out[1] = -a[1] * invDot
    out[2] = -a[2] * invDot
    out[3] = a[3] * invDot
    return out
  },

  fromEuler(out: Quat, x: number, y: number, z: number): Quat {
    const hx = x * 0.5, hy = y * 0.5, hz = z * 0.5
    const sx = Math.sin(hx), cx = Math.cos(hx)
    const sy = Math.sin(hy), cy = Math.cos(hy)
    const sz = Math.sin(hz), cz = Math.cos(hz)
    out[0] = sx * cy * cz + cx * sy * sz
    out[1] = cx * sy * cz - sx * cy * sz
    out[2] = cx * cy * sz + sx * sy * cz
    out[3] = cx * cy * cz - sx * sy * sz
    return out
  },

  /** Convert quaternion to a 4x4 rotation matrix (column-major Float32Array). */
  toMat4(out: Float32Array, q: Quat): Float32Array {
    const x = q[0], y = q[1], z = q[2], w = q[3]
    const x2 = x + x, y2 = y + y, z2 = z + z
    const xx = x * x2, xy = x * y2, xz = x * z2
    const yy = y * y2, yz = y * z2, zz = z * z2
    const wx = w * x2, wy = w * y2, wz = w * z2

    out[0] = 1 - (yy + zz); out[1] = xy + wz;       out[2] = xz - wy;       out[3] = 0
    out[4] = xy - wz;       out[5] = 1 - (xx + zz); out[6] = yz + wx;       out[7] = 0
    out[8] = xz + wy;       out[9] = yz - wx;       out[10] = 1 - (xx + yy); out[11] = 0
    out[12] = 0;             out[13] = 0;             out[14] = 0;             out[15] = 1
    return out
  },

  dot(a: Quat, b: Quat): number {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
  },

  length(a: Quat): number {
    return Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2] + a[3] * a[3])
  },
}
