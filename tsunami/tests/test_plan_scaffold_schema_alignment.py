"""Round L 2026-04-20: gap #17 — plan_scaffolds/gamedev.md example
diverged from scaffolds/engine/src/design/schema.ts.

The plan teaches the wave to emit `entities: [...]` but the engine
validator only reads `raw.archetypes ?? {}` — entities never get
validated against tag_requirement or catalog_composition. Round L's
wave emitted a structurally-perfect design with "entities" (a list)
and the validator reported 0 archetypes + tag_requirement failure
on CheckpointProgression.

These tests lock the alignment: the plan example must use schema-
matched field names. When schema.ts changes a root field (e.g.
renames `archetypes` or drops `flow`), these tests catch the drift
and force a plan update in the same PR.

Until Fix #17a lands, these tests will FAIL — they define the target
state, not the current state. Run them in CI to catch regression
after the fix is deployed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

PLAN = REPO / "tsunami" / "plan_scaffolds" / "gamedev.md"
SCHEMA = REPO / "scaffolds" / "engine" / "src" / "design" / "schema.ts"


def _read_text(path: Path) -> str:
    return path.read_text() if path.is_file() else ""


def _schema_root_fields() -> set[str]:
    """Extract the root DesignScript field names from schema.ts.
    Parses the `export interface DesignScript { ... }` block."""
    src = _read_text(SCHEMA)
    m = re.search(
        r"export\s+interface\s+DesignScript\s*\{([^}]+)\}",
        src, re.DOTALL,
    )
    if not m:
        return set()
    body = m.group(1)
    fields: set[str] = set()
    # Match identifiers followed by `:` or `?:` at the start of a line
    # (TypeScript interface field syntax).
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        fm = re.match(r"(\w+)\??\s*:", line)
        if fm:
            fields.add(fm.group(1))
    return fields


def test_schema_has_archetypes_not_entities():
    """Schema's root interface must have archetypes; should not
    have an `entities` top-level field. Sanity-anchors the plan test."""
    fields = _schema_root_fields()
    assert "archetypes" in fields, (
        f"schema.ts DesignScript interface missing 'archetypes' — "
        f"saw fields: {sorted(fields)}"
    )
    assert "entities" not in fields, (
        "schema.ts DesignScript has 'entities' at root — plan can use it; "
        "this test's premise (plan says entities, schema says archetypes) "
        "is wrong. Revisit gap #17 classification."
    )


def test_plan_example_uses_archetypes_field():
    """Gap #17 target state: plan_scaffolds/gamedev.md design example
    must use `"archetypes"` not `"entities"` at the root. FAILS until
    Fix #17a lands — FAILING IS THE POINT until then."""
    plan = _read_text(PLAN)
    assert plan, f"plan file missing: {PLAN}"
    # Look inside a JSON code block for the design example.
    # Find ```json ... ``` blocks.
    blocks = re.findall(r"```json\s*\n(.*?)\n```", plan, re.DOTALL)
    assert blocks, "no JSON code blocks in gamedev.md"
    # Check EVERY JSON block — at least one must have archetypes at root.
    # Also no block should have a root "entities" field (case-sensitive,
    # with quotes) — indicates plan teaches the wrong shape.
    has_archetypes_root = False
    has_entities_root = False
    for b in blocks:
        # Rough match on top-level key appearance at indent 0 or 2.
        if re.search(r'^\s{0,4}"archetypes"\s*:', b, re.MULTILINE):
            has_archetypes_root = True
        if re.search(r'^\s{0,4}"entities"\s*:', b, re.MULTILINE):
            has_entities_root = True
    assert has_archetypes_root, (
        "plan_scaffolds/gamedev.md JSON examples missing root "
        '"archetypes" field — Fix #17a not deployed yet. The plan must '
        "teach the wave to emit archetypes (the schema-canonical shape) "
        "not entities."
    )
    assert not has_entities_root, (
        "plan_scaffolds/gamedev.md still teaches root-level 'entities' — "
        "Fix #17a regression. Schema requires archetypes, not entities."
    )


def test_plan_example_mentions_schema_root_fields():
    """The plan's design example should reference the key schema root
    fields: archetypes, mechanics, flow. Catches the drift where the
    plan invents its own shape (e.g. `scenes: [...]` which schema
    doesn't have at root)."""
    plan = _read_text(PLAN)
    # Required schema-canonical field names
    required = ("archetypes", "mechanics", "flow")
    for field in required:
        # Appear somewhere in the plan (quoted JSON key form)
        assert f'"{field}"' in plan, (
            f"plan_scaffolds/gamedev.md doesn't mention schema root field "
            f'"{field}". Fix #17a: every schema root field should appear '
            f"in the plan's design example so the wave knows about it."
        )


def test_plan_does_not_teach_nonexistent_root_fields():
    """Plan should not invent root fields that schema doesn't define.
    Round L captured the wave emitting `scenes: [{id, entities, mechanics}]`
    (React-mental-model leakage) because the plan had a `scenes` block
    that wasn't schema-canonical. Schema uses `flow: FlowNode` instead
    — scenes are NAMES inside flow, not objects at root."""
    plan = _read_text(PLAN)
    schema_fields = _schema_root_fields()
    # Fields that Round L captured the wave inventing (React-style)
    suspect_fields = ("scenes",)  # Can expand over time as drifts emerge
    for sf in suspect_fields:
        # If the plan has a root-level JSON key for a non-schema field,
        # that's a drift. Look in JSON blocks for `"<field>":` at
        # shallow indent (0-4 spaces = root or first-level).
        blocks = re.findall(r"```json\s*\n(.*?)\n```", plan, re.DOTALL)
        for b in blocks:
            has_root_suspect = bool(
                re.search(rf'^\s{{0,4}}"{sf}"\s*:', b, re.MULTILINE)
            )
            if has_root_suspect and sf not in schema_fields:
                raise AssertionError(
                    f'plan_scaffolds/gamedev.md teaches root field "{sf}" '
                    f"but schema.ts DesignScript doesn't define it. Known "
                    f"schema root fields: {sorted(schema_fields)}. Round L "
                    f"captured this as gap #17 manifesting as scene-shape drift."
                )


def main():
    tests = [
        test_schema_has_archetypes_not_entities,
        test_plan_example_uses_archetypes_field,
        test_plan_example_mentions_schema_root_fields,
        test_plan_does_not_teach_nonexistent_root_fields,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print()
    if failed:
        print(f"RESULT: {len(failed)}/{len(tests)} failed: {failed}")
        print()
        print("NOTE: This suite intentionally fails until Fix #17a "
              "(plan_scaffolds/gamedev.md alignment with schema.ts) "
              "ships. See SIGMA_AUDIT.md §23.5 for context.")
        sys.exit(1)
    print(f"RESULT: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
