"""Asset state-graph schema + YAML loader.

An entity (tree, knight, flame, chest, ...) is modeled as a state-graph:
  - BASE image (canonical reference)
  - STATES — each is a derivation from base (or from another state) via a
    single prompt. State images are static.
  - LOOPS — animations played WITHIN a state (wind sway, fire flicker).
  - TRANSITIONS — animations played BETWEEN states, driven by EVENTS.
                  A transition (from=on_fire, on=WATER, to=extinguished)
                  plays when game logic sends the WATER event to an
                  on_fire-state entity.

Every loop and transition references an animation primitive — a chain of
nudge edits (see tsunami/serving/qwen_image_server.py::AnimateRequest).
The runtime resolves primitive names to YAML files under
scaffolds/engine/asset_library/animations/.

Integrity invariants enforced at load time:
  1. Every state referenced in a transition (from/to) or loop exists in
     the entity's states dict.
  2. `derive_from` targets exist.
  3. State derivation graph is acyclic (no A←B←A cycles).
  4. `reverse_of` targets exist among the same entity's transitions.
  5. Every animation / overlay YAML referenced exists on disk.

Loaders fail loudly on violation — the v10 Production-Firing Audit
principle applied to asset graphs. A dangling ref at load time means
the graph can't run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# ── State definition ────────────────────────────────────────────────

class StateDef(BaseModel):
    """One state in an entity's graph.

    - `source="base"` marks the root state (no derivation; uses entity base).
    - `derive_from=<other_state>` + `prompt` derives this state via a
      SINGLE edit of that state. Derivation is not a chain — a derived
      state is a single-edit result.
    """
    source: Optional[str] = None
    derive_from: Optional[str] = None
    prompt: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    def is_root(self) -> bool:
        return self.source == "base"


# ── Animation primitive (loaded from asset_library/animations/*.yaml) ─

class PrimitiveNudge(BaseModel):
    """One nudge inside an animation primitive YAML. Mirrors the
    NudgeStep shape in qwen_image_server but kept separate so the
    animation module has no hard dependency on the serving module
    (loader can run on a machine with no torch installed)."""
    delta: str
    strength: float = Field(0.4, ge=0.0, le=1.0)
    guidance_scale: float = 4.0
    num_inference_steps: int = 30

    model_config = ConfigDict(extra="forbid")


class AnimationPrimitive(BaseModel):
    """An animation primitive — a chain of nudges named and reusable.

    Loaded from scaffolds/engine/asset_library/animations/<name>.yaml.
    Applied to a base frame via /v1/images/animate.
    """
    primitive: str
    category: str = Field(
        description="character | vfx | environment | prop — hint for tooling"
    )
    frame_count: int = Field(ge=1, le=32,
        description="must match len(nudges); validated at load")
    reversible: bool = Field(False,
        description="if true, playing nudges in reverse produces a valid "
                    "inverse animation (destroy ↔ form, etc.)")
    base_hint: Optional[str] = Field(None,
        description="human hint about what shape of base image this works on "
                    "(e.g. 'standing humanoid', 'solid object', 'flame source')")
    guidance: Optional[str] = Field(None,
        description="author's note to drones/operators consuming this primitive")
    nudges: list[PrimitiveNudge] = Field(min_length=1, max_length=32)

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, __context) -> None:
        """Invariant: frame_count == len(nudges)."""
        if self.frame_count != len(self.nudges):
            raise ValueError(
                f"primitive {self.primitive!r}: frame_count={self.frame_count} "
                f"but len(nudges)={len(self.nudges)}"
            )


# ── Transitions + entity graph ──────────────────────────────────────

class Transition(BaseModel):
    """One state → state edge driven by an event.

    A single transition is (from_state, event, to_state, animation).
    Multiple transitions can share a from_state + event if they route to
    different to_states under different game conditions (e.g. on_fire +
    WATER normally goes to extinguished, but if the fire was magical it
    goes to neutralized — two transitions sharing from+on, router picks
    at runtime via extra predicates). v1 keeps it simple: one (from,on) →
    one to.

    `reverse_of` points to another transition by name (<from>→<to> form).
    When set, this transition's animation is the named one played
    backwards. Saves writing a symmetric chain.
    """
    from_state: str = Field(alias="from")
    to_state: str = Field(alias="to")
    on: str = Field(description="event name that triggers this transition")
    animation: Optional[str] = Field(None,
        description="reference to an animation primitive YAML "
                    "(e.g. 'igniting_5' → asset_library/animations/igniting_5.yaml)")
    reverse_of: Optional[str] = Field(None,
        description="reference another transition by 'FROM→TO' identifier; "
                    "this transition replays that one's frames in reverse")
    overlay: Optional[str] = Field(None,
        description="optional VFX overlay animation that plays in-parallel "
                    "with the entity transition (e.g. water_splash_impact_3)")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def identifier(self) -> str:
        """Canonical name of this transition — from→to."""
        return f"{self.from_state}→{self.to_state}"


class LoopRef(BaseModel):
    """A loop entry in an entity graph — which primitive plays in which state."""
    state: str
    animation: str

    model_config = ConfigDict(extra="forbid")


class EntityGraph(BaseModel):
    """An entity's full state-graph.

    Loaded from scaffolds/engine/asset_library/entities/<entity>.yaml.
    Consumed by the runtime state-machine (game code sends events,
    runtime plays the right animation) and the bake tool (renders the
    full graph to a traditional sprite sheet).
    """
    entity: str
    base: str = Field(description="image path or asset_library key for the "
                                    "canonical base image")
    states: dict[str, StateDef]
    transitions: list[Transition] = Field(default_factory=list)
    loops: dict[str, LoopRef] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    def root_state(self) -> str:
        """Return the name of the state marked as the base/root."""
        roots = [name for name, s in self.states.items() if s.is_root()]
        if len(roots) != 1:
            raise ValueError(
                f"entity {self.entity!r} must have exactly one root state "
                f"(source=base); found {len(roots)}: {roots}"
            )
        return roots[0]


# ── Validation ──────────────────────────────────────────────────────

class StateGraphValidationError(Exception):
    """Raised when an entity graph fails integrity checks at load time."""


def validate_entity_graph(graph: EntityGraph,
                          animations_dir: Optional[Path] = None) -> None:
    """Run integrity checks. Raises StateGraphValidationError on any
    violation. Fails fast — multiple violations report only the first
    (keep load-time output readable; fix and retry).

    `animations_dir` if provided is scanned to confirm every `animation`
    and `overlay` reference exists on disk. When None, that check is
    skipped — useful for loader unit tests.
    """
    # 1. Exactly one root state
    try:
        graph.root_state()
    except ValueError as e:
        raise StateGraphValidationError(str(e)) from e

    state_names = set(graph.states.keys())

    # 2. derive_from references resolve
    for name, sdef in graph.states.items():
        if sdef.derive_from is not None:
            if sdef.derive_from not in state_names:
                raise StateGraphValidationError(
                    f"state {name!r}: derive_from={sdef.derive_from!r} "
                    f"is not a defined state; defined: {sorted(state_names)}"
                )
            if sdef.prompt is None:
                raise StateGraphValidationError(
                    f"state {name!r}: has derive_from but no prompt"
                )

    # 3. No derivation cycles
    def _derivation_chain(name: str, seen: frozenset) -> None:
        if name in seen:
            raise StateGraphValidationError(
                f"state derivation cycle involving {name!r}; "
                f"chain: {list(seen) + [name]}"
            )
        sdef = graph.states.get(name)
        if sdef and sdef.derive_from:
            _derivation_chain(sdef.derive_from, seen | {name})

    for name in state_names:
        _derivation_chain(name, frozenset())

    # 4. Transition from/to resolve + reverse_of resolves
    transition_ids = {t.identifier() for t in graph.transitions}
    for t in graph.transitions:
        if t.from_state not in state_names:
            raise StateGraphValidationError(
                f"transition {t.identifier()!r}: from={t.from_state!r} "
                f"not a defined state"
            )
        if t.to_state not in state_names:
            raise StateGraphValidationError(
                f"transition {t.identifier()!r}: to={t.to_state!r} "
                f"not a defined state"
            )
        if t.reverse_of is not None and t.reverse_of not in transition_ids:
            raise StateGraphValidationError(
                f"transition {t.identifier()!r}: reverse_of={t.reverse_of!r} "
                f"is not a defined transition; defined: {sorted(transition_ids)}"
            )
        if t.animation is None and t.reverse_of is None:
            raise StateGraphValidationError(
                f"transition {t.identifier()!r}: must have either animation "
                f"or reverse_of"
            )

    # 5. Loops reference valid states
    for loop_name, lref in graph.loops.items():
        if lref.state not in state_names:
            raise StateGraphValidationError(
                f"loop {loop_name!r}: state={lref.state!r} not defined"
            )

    # 6. Animation/overlay file references exist on disk (optional)
    if animations_dir is not None:
        refs: list[tuple[str, str]] = []
        for t in graph.transitions:
            if t.animation:
                refs.append((f"transition {t.identifier()}", t.animation))
            if t.overlay:
                refs.append((f"transition {t.identifier()} overlay", t.overlay))
        for lname, lref in graph.loops.items():
            refs.append((f"loop {lname}", lref.animation))
        for origin, ref in refs:
            # Accept bare name ('igniting_5') OR 'igniting_5.yaml'.
            stem = ref if ref.endswith(".yaml") else f"{ref}.yaml"
            if not (animations_dir / stem).is_file():
                raise StateGraphValidationError(
                    f"{origin}: animation reference {ref!r} → "
                    f"{animations_dir / stem} does not exist"
                )


# ── YAML loaders ────────────────────────────────────────────────────

def load_primitive(path: Path) -> AnimationPrimitive:
    """Load + validate an animation primitive YAML."""
    import yaml
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StateGraphValidationError(
            f"primitive YAML at {path} must be a mapping, got {type(data).__name__}"
        )
    return AnimationPrimitive.model_validate(data)


def load_entity_graph(path: Path,
                      animations_dir: Optional[Path] = None) -> EntityGraph:
    """Load + validate an entity state-graph YAML. If animations_dir is
    provided, also verify every animation/overlay reference resolves to
    an existing file (strictest mode — use for bake/CI)."""
    import yaml
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StateGraphValidationError(
            f"entity YAML at {path} must be a mapping, got {type(data).__name__}"
        )
    graph = EntityGraph.model_validate(data)
    validate_entity_graph(graph, animations_dir=animations_dir)
    return graph


__all__ = [
    "StateDef",
    "PrimitiveNudge",
    "AnimationPrimitive",
    "Transition",
    "LoopRef",
    "EntityGraph",
    "StateGraphValidationError",
    "validate_entity_graph",
    "load_primitive",
    "load_entity_graph",
]
