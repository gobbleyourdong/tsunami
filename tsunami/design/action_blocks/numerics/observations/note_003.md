# Observation 003 — Directional contact is schema-level, not a mechanic

**Sources:** prompt_004 (Mario stomp), prompt_005 (SF2 block vs. hit),
game_001 (SMB), game_005 (Zelda sword swing), game_009 (Metroid),
game_010 (Chrono ATB directional). 3/10 prompts + 3/10 games explicitly
named this gap. All six describe asymmetric collision outcomes.

**Claim:** `TriggerName = 'pickup' | 'damage' | 'checkpoint' | 'heal' |
string` in schema.ts treats contact as a symmetric event. Mario stomp
(A-above-B → B dies), Zelda sword (A-sword-tip → B dies, A-body → A
takes damage), SF2 block (A-block-direction-matches → mitigate) cannot
be expressed. Every action-game genre needs this.

**Claim (stronger):** this is a schema revision, not a mechanic
addition. Adding more `TriggerName` strings doesn't help — the *contact
geometry* needs to be in the trigger spec.

**Proposed schema update:**

```ts
// before
type TriggerName = 'pickup' | 'damage' | ...

// after (proposed)
interface TriggerSpec {
  kind: 'pickup' | 'damage' | 'checkpoint' | 'heal' | 'stomp' | 'bump' | 'block' | string
  from_dir?: 'above' | 'below' | 'side' | 'front' | 'back' | 'any'
  on_contact?: ActionRef   // replaces or supplements the kind's default
  on_reverse?: ActionRef   // what happens to the OTHER entity
  exclusive?: boolean      // consume the trigger (pickup-style)
}
```

Archetype usage:
```ts
archetypes: {
  goomba: {
    mesh: 'box', ai: 'patrol',
    trigger: { kind: 'damage', from_dir: 'side',
               on_reverse: { kind: 'damage', archetype: 'goomba', amount: 1 }},
    tags: ['enemy']
  }
}
```

**Cost:** breaks backwards-compat with plain-string triggers. Migration:
allow `trigger: string` as sugar for `trigger: {kind: string}`.

**Coverage gain:** platformer + fighter + action-adventure genres all
become expressible at the trigger level. Combined with directional-
contact at mechanic level (`PlatformerController` handles jump-on-stomp
detection), covers Mario, Zelda, SF2, Metroid use cases named above.

**Recommendation:** promote to v1 schema revision. Bundle with grid mode
(note_002) — the two together unlock the biggest share of retro-corpus
expressibility.
