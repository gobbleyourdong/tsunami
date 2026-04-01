# Building — Plan, Research, Build, Test

## 1. Plan into files

Before writing code, decompose the build into plan files:

```
workspace/deliverables/your-project/plan/
├── environment.md   # scene setup, layout, camera, materials
├── physics.md       # gravity, collision, movement rules
├── controls.md      # what each key/click does
├── scoring.md       # points, lives, win/lose conditions
├── visuals.md       # effects, animations, theme
```

Each file describes ONE dimension. Write what it should do, not how to code it.
These files are the spec AND the test criteria. The undertow reads them.

Skip files that don't apply (a calculator doesn't need physics.md).

## 2. Research on GitHub

Search for real implementations: `search_web(query, search_type="code")`
Read the actual source. Study the patterns. Don't guess at APIs.

## 3. Build from researched patterns

Use what you found. Don't improvise.

## 4. Test with undertow

```
undertow(path="index.html", expect="description of the core user journey")
```

Read the report. Fix failures. Test again. Repeat until the core journey works.
Motion detection catches dead physics. Key/click checks catch broken controls.

## 5. Deliver only when it works

Not when it renders. When it PLAYS / FUNCTIONS / RESPONDS.
