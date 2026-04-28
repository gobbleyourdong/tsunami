// assets.ts — primitive lists for the test 3D shapes.
//
// Each asset returns a flat list of GPU primitives ready to upload to the
// raymarch shader's storage buffer. Same primitive vocabulary as the
// engine's raymarch_renderer.ts (READ-ONLY upstream): sphere, box,
// roundedBox, capsule, cylinder, ellipsoid, torus.
//
// The flat-list-with-blend-groups model makes adding new assets trivial:
// describe each part as a primitive, group them with the same blendGroup
// + a small blendRadius for organic merging.

export type Quat = readonly [number, number, number, number]; // x,y,z,w

export const QUAT_IDENTITY: Quat = [0, 0, 0, 1];

export type PrimType = 0 | 1 | 2 | 3 | 4 | 5 | 6;
// 0 sphere, 1 box, 2 capsule, 3 cylinder, 4 ellipsoid, 5 torus, 6 roundedBox

export interface GPUPrim {
  type_: PrimType;
  blendGroup: number;       // 0 = standalone
  blendRadius: number;      // smin radius when shared with same group
  paletteSlot: number;      // index into palette buffer
  params: readonly [number, number, number, number];   // shape-specific
  offset: readonly [number, number, number];           // local position
  rotation: Quat;
}

// PRIM_STRIDE_FLOATS × 4 bytes per primitive in the GPU buffer.
//   slot 0  = vec4<f32>(type as f32, blendGroup as f32, blendRadius, paletteSlot as f32)
//   slot 1  = params.xyzw
//   slot 2  = offset.xyz, _pad
//   slot 3  = rotation.xyzw
// 16 floats = 64 bytes. (We pack u32 fields by reinterpreting via DataView.)
export const PRIM_STRIDE_FLOATS = 16;

export function packPrimitives(list: GPUPrim[]): ArrayBuffer {
  const buf = new ArrayBuffer(list.length * PRIM_STRIDE_FLOATS * 4);
  const f32 = new Float32Array(buf);
  const u32 = new Uint32Array(buf);
  for (let i = 0; i < list.length; i++) {
    const p = list[i];
    const base = i * PRIM_STRIDE_FLOATS;
    // slot 0 — pack u32 fields
    u32[base + 0] = p.type_;
    u32[base + 1] = p.blendGroup;
    f32[base + 2] = p.blendRadius;
    u32[base + 3] = p.paletteSlot;
    // slot 1 — params (4 floats)
    f32[base + 4] = p.params[0];
    f32[base + 5] = p.params[1];
    f32[base + 6] = p.params[2];
    f32[base + 7] = p.params[3];
    // slot 2 — offset + pad
    f32[base + 8]  = p.offset[0];
    f32[base + 9]  = p.offset[1];
    f32[base + 10] = p.offset[2];
    f32[base + 11] = 0;
    // slot 3 — rotation
    f32[base + 12] = p.rotation[0];
    f32[base + 13] = p.rotation[1];
    f32[base + 14] = p.rotation[2];
    f32[base + 15] = p.rotation[3];
  }
  return buf;
}

// Quaternion constructors (Y-up)
export function quatY(angleRad: number): Quat {
  const h = angleRad * 0.5;
  return [0, Math.sin(h), 0, Math.cos(h)];
}
export function quatX(angleRad: number): Quat {
  const h = angleRad * 0.5;
  return [Math.sin(h), 0, 0, Math.cos(h)];
}
export function quatZ(angleRad: number): Quat {
  const h = angleRad * 0.5;
  return [0, 0, Math.sin(h), Math.cos(h)];
}

// ─────────── PALETTE (RGBA in 0..1, vec4 per slot) ───────────

export const PALETTE: ReadonlyArray<readonly [number, number, number, number]> = [
  [0.82, 0.85, 0.88, 1], // 0 polished steel (sword blade)
  [0.42, 0.32, 0.18, 1], // 1 iron-with-patina (sword guard)
  [0.18, 0.14, 0.10, 1], // 2 oiled leather (sword grip)
  [0.78, 0.62, 0.28, 1], // 3 brass (sword pommel)
  [0.42, 0.40, 0.42, 1], // 4 mossy stone (rock body)
  [0.50, 0.48, 0.50, 1], // 5 lighter stone (rock highlight)
  [0.85, 0.75, 0.65, 1], // 6 skin
  [0.30, 0.20, 0.18, 1], // 7 dark hair
  [0.55, 0.45, 0.30, 1], // 8 wood (palm trunk)
  [0.20, 0.55, 0.25, 1], // 9 leaf green (palm fronds)
];

export function packPalette(): Float32Array {
  const buf = new Float32Array(PALETTE.length * 4);
  for (let i = 0; i < PALETTE.length; i++) {
    buf[i * 4 + 0] = PALETTE[i][0];
    buf[i * 4 + 1] = PALETTE[i][1];
    buf[i * 4 + 2] = PALETTE[i][2];
    buf[i * 4 + 3] = PALETTE[i][3];
  }
  return buf;
}

// ─────────── ASSETS ───────────

export function knightLongsword(): GPUPrim[] {
  // Vertical sword centered on the screen. blendGroup=1 with small smin
  // radius unifies blade+guard+grip+pommel into one organic shape.
  const G = 1;
  const K = 0.005;
  return [
    // Blade — capsule along Y, 0.85m long, 0.022m radius
    {
      type_: 2, blendGroup: G, blendRadius: K, paletteSlot: 0,
      params: [0.022, 0.42, 0, 0],
      offset: [0, 0.20, 0],
      rotation: QUAT_IDENTITY,
    },
    // Guard — wide flat box across the blade
    {
      type_: 6, blendGroup: G, blendRadius: K, paletteSlot: 1,
      params: [0.09, 0.012, 0.022, 0.005],
      offset: [0, -0.22, 0],
      rotation: QUAT_IDENTITY,
    },
    // Grip — capsule along Y, 0.16m long, 0.014m radius
    {
      type_: 2, blendGroup: G, blendRadius: K * 1.5, paletteSlot: 2,
      params: [0.014, 0.08, 0, 0],
      offset: [0, -0.31, 0],
      rotation: QUAT_IDENTITY,
    },
    // Pommel — sphere at the end of the grip
    {
      type_: 0, blendGroup: G, blendRadius: K * 2, paletteSlot: 3,
      params: [0.024, 0, 0, 0],
      offset: [0, -0.42, 0],
      rotation: QUAT_IDENTITY,
    },
  ];
}

export function rockChunk(seed = 0): GPUPrim[] {
  // Rock = smooth-union of one box + one displaced sphere.
  const G = 2;
  const rng = (n: number): number => {
    const x = Math.sin(seed * 127.1 + n * 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  return [
    {
      type_: 1, blendGroup: G, blendRadius: 0.15, paletteSlot: 4,
      params: [0.30 + rng(1) * 0.2, 0.15 + rng(2) * 0.1, 0.25 + rng(3) * 0.15, 0],
      offset: [0, 0, 0],
      rotation: QUAT_IDENTITY,
    },
    {
      type_: 0, blendGroup: G, blendRadius: 0.15, paletteSlot: 5,
      params: [0.15 + rng(4) * 0.15, 0, 0, 0],
      offset: [rng(5) * 0.3 - 0.15, rng(6) * 0.1, rng(7) * 0.2 - 0.1],
      rotation: QUAT_IDENTITY,
    },
  ];
}

export function chibiHead(): GPUPrim[] {
  const G = 3;
  return [
    {
      type_: 4, blendGroup: G, blendRadius: 0.02, paletteSlot: 6,
      params: [0.19, 0.21, 0.19, 0],
      offset: [0, 0, 0],
      rotation: QUAT_IDENTITY,
    },
    // Hair as a slightly-larger ellipsoid above the skull
    {
      type_: 4, blendGroup: G, blendRadius: 0.04, paletteSlot: 7,
      params: [0.20, 0.13, 0.20, 0],
      offset: [0, 0.08, 0],
      rotation: QUAT_IDENTITY,
    },
  ];
}

export function palmTree(): GPUPrim[] {
  // Trunk is a tall capsule; fronds are 5 capsules splayed at the top.
  const G_TRUNK = 4;
  const G_FRONDS = 5;
  const list: GPUPrim[] = [];
  // Trunk
  list.push({
    type_: 2, blendGroup: G_TRUNK, blendRadius: 0.02, paletteSlot: 8,
    params: [0.05, 0.45, 0, 0],
    offset: [0, 0, 0],
    rotation: QUAT_IDENTITY,
  });
  // Coconut at top of trunk
  list.push({
    type_: 0, blendGroup: G_TRUNK, blendRadius: 0.05, paletteSlot: 8,
    params: [0.07, 0, 0, 0],
    offset: [0, 0.5, 0],
    rotation: QUAT_IDENTITY,
  });
  // Fronds — 5 capsules splayed outward from the top
  for (let i = 0; i < 5; i++) {
    const ang = (i / 5) * Math.PI * 2 + 0.1;
    const tilt = -0.7;             // tilt down/outward
    const len = 0.35;
    // Frond is a capsule oriented along Y in local space; rotate via quat.
    // Combine: rotateZ(tilt) then rotateY(ang). Multiply quaternions.
    const qz = quatZ(tilt);
    const qy = quatY(ang);
    // Hamilton product q = qy * qz
    const q: Quat = [
      qy[3] * qz[0] + qy[0] * qz[3] + qy[1] * qz[2] - qy[2] * qz[1],
      qy[3] * qz[1] - qy[0] * qz[2] + qy[1] * qz[3] + qy[2] * qz[0],
      qy[3] * qz[2] + qy[0] * qz[1] - qy[1] * qz[0] + qy[2] * qz[3],
      qy[3] * qz[3] - qy[0] * qz[0] - qy[1] * qz[1] - qy[2] * qz[2],
    ];
    // Position: the capsule's local center; offset upward + outward.
    const offX = Math.cos(ang) * 0.15;
    const offZ = Math.sin(ang) * 0.15;
    list.push({
      type_: 2, blendGroup: G_FRONDS, blendRadius: 0.03, paletteSlot: 9,
      params: [0.025, len * 0.5, 0, 0],
      offset: [offX, 0.55, offZ],
      rotation: q,
    });
  }
  return list;
}

export const ASSETS: Record<string, () => GPUPrim[]> = {
  'sword (knight longsword)': knightLongsword,
  'rock chunk': () => rockChunk(0),
  'rock chunk #2': () => rockChunk(7),
  'chibi head': chibiHead,
  'palm tree': palmTree,
};
