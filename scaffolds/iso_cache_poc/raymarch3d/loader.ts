// loader.ts — JSON scene loader (subset). Reads sdf_modeling_research-
// style scene files and converts the explicit `parts[]` of each object
// into our GPUPrim list. Skips features we don't need yet:
//   - extends (preset inheritance)
//   - place_at_anchor (named anchor resolution)
//   - per-material complex slots (triplanar, surface_distance)
// Logs warnings to console for unsupported types; never throws.

import type { GPUPrim, PrimType, Quat } from './assets.ts';

const QUAT_IDENTITY: Quat = [0, 0, 0, 1];

// ─────────── Scene JSON shape (loose) ───────────

interface SceneJSON {
  scene_name?: string;
  summary?: string;
  objects?: ObjectEntry[];
}

interface ObjectEntry {
  place_at?: [number, number, number];
  place_at_anchor?: string;
  offset?: [number, number, number];
  spec: ObjectSpec;
}

interface ObjectSpec {
  name: string;
  archetype?: string;
  scale_meters?: number;
  palette?: Record<string, unknown>;
  parts?: PartSpec[];
  extends?: string;
}

interface PartSpec {
  id?: string;
  type?: string;
  params?: Record<string, unknown>;
  translate?: [number, number, number];
  material?: string | { type?: string };
}

// Map source material name → palette slot in our shader's palette buffer.
// Kept narrow on purpose; unknowns fall back to slot 4 (mossy stone).
const MATERIAL_TO_SLOT: Record<string, number> = {
  iron: 1,
  steel: 0,
  blade: 0,
  guard: 1,
  grip: 2,
  pommel: 3,
  brass: 3,
  wood: 8,
  wood_dark: 8,
  wood_grain: 8,
  oak: 8,
  glass: 0,
  stone: 4,
  rock: 4,
  crystal: 6,
  amethyst: 6,
  gold: 3,
  gold_dark: 3,
  gem_red: 6,
  leather: 2,
  leaf: 9,
  green: 9,
  default: 4,
};

// ─────────── Public entry ───────────

export async function loadSceneJSON(url: string): Promise<GPUPrim[]> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`loadSceneJSON: ${url} → HTTP ${res.status}`);
  const scene = (await res.json()) as SceneJSON;
  return sceneToPrims(scene);
}

export function sceneToPrims(scene: SceneJSON): GPUPrim[] {
  const out: GPUPrim[] = [];
  let nextGroup = 1;
  for (const obj of scene.objects ?? []) {
    if (obj.place_at_anchor && !obj.place_at) {
      // Anchor resolution unimplemented — render at origin (with offset).
      console.warn(`[loader] "${obj.spec?.name}" uses place_at_anchor; rendering at origin`);
    }
    if (!obj.spec?.parts || obj.spec.parts.length === 0) {
      console.warn(`[loader] "${obj.spec?.name}" has no explicit parts (extends preset?); skipping`);
      continue;
    }
    const place: [number, number, number] = obj.place_at ?? [0, 0, 0];
    const off = obj.offset ?? [0, 0, 0];
    const basePos: [number, number, number] = [
      place[0] + off[0],
      place[1] + off[1],
      place[2] + off[2],
    ];
    const scale = obj.spec.scale_meters ?? 1;
    // Group all of this object's parts under one blend group so they
    // smooth-union into a single object surface.
    const group = nextGroup++;
    for (const part of obj.spec.parts) {
      const prim = partToPrim(part, basePos, scale, group);
      if (prim) out.push(prim);
    }
  }
  return out;
}

// ─────────── Per-part conversion ───────────

function num(x: unknown, fallback: number): number {
  return typeof x === 'number' && Number.isFinite(x) ? x : fallback;
}

function vec3(x: unknown, fallback: [number, number, number]): [number, number, number] {
  if (Array.isArray(x) && x.length === 3 && x.every((v) => typeof v === 'number')) {
    return [x[0] as number, x[1] as number, x[2] as number];
  }
  return fallback;
}

function partToPrim(
  part: PartSpec,
  basePos: [number, number, number],
  scale: number,
  blendGroup: number,
): GPUPrim | null {
  const t = part.translate ?? [0, 0, 0];
  const offset: [number, number, number] = [
    basePos[0] + t[0] * scale,
    basePos[1] + t[1] * scale,
    basePos[2] + t[2] * scale,
  ];
  const matName = typeof part.material === 'string' ? part.material : 'default';
  const slot = MATERIAL_TO_SLOT[matName] ?? MATERIAL_TO_SLOT.default;
  const params = (part.params ?? {}) as Record<string, unknown>;

  switch (part.type) {
    case 'shape:sphere': {
      const r = num(params.radius, 0.1) * scale;
      return mkPrim(0, [r, 0, 0, 0], offset, blendGroup, slot);
    }
    case 'shape:box': {
      const half = vec3(params.half, [0.1, 0.1, 0.1]);
      return mkPrim(1, [half[0] * scale, half[1] * scale, half[2] * scale, 0], offset, blendGroup, slot);
    }
    case 'shape:rounded_box': {
      const half = vec3(params.half, [0.1, 0.1, 0.1]);
      const corner = num(params.corner_r, 0.01) * scale;
      return mkPrim(6, [half[0] * scale, half[1] * scale, half[2] * scale, corner], offset, blendGroup, slot);
    }
    case 'shape:cylinder': {
      const r = num(params.radius, 0.1) * scale;
      const h = num(params.height, 0.2) * scale;
      return mkPrim(3, [r, h * 0.5, 0, 0], offset, blendGroup, slot);
    }
    case 'shape:capsule': {
      const r = num(params.radius, 0.05) * scale;
      const len = num(params.length, 0.2) * scale;
      return mkPrim(2, [r, len * 0.5, 0, 0], offset, blendGroup, slot);
    }
    case 'shape:ellipsoid': {
      const r = vec3(params.radii, [0.1, 0.1, 0.1]);
      return mkPrim(4, [r[0] * scale, r[1] * scale, r[2] * scale, 0], offset, blendGroup, slot);
    }
    case 'shape:torus': {
      const major = num(params.major_radius, 0.1) * scale;
      const minor = num(params.minor_radius, 0.02) * scale;
      return mkPrim(5, [major, minor, 0, 0], offset, blendGroup, slot);
    }
    default:
      console.warn(`[loader] unsupported part type "${part.type}"`);
      return null;
  }
}

function mkPrim(
  type_: PrimType,
  params: [number, number, number, number],
  offset: [number, number, number],
  blendGroup: number,
  paletteSlot: number,
): GPUPrim {
  return {
    type_,
    blendGroup,
    blendRadius: 0.01,
    paletteSlot,
    params,
    offset,
    rotation: QUAT_IDENTITY,
  };
}

// ─────────── Built-in scene URLs (relative to the page) ───────────

export const SCENE_URLS: Record<string, string> = {
  'scene: sword on anvil': './scenes/sword_on_anvil.json',
  'scene: altar offering': './scenes/altar_offering.json',
};
