# Plan: {goal}

## TOC
- [>] [Architecture](#architecture)
- [ ] [Schema](#schema)
- [ ] [Steps](#steps)
- [ ] [Validation](#validation)
- [ ] [Tests](#tests)
- [ ] [Build](#build)
- [ ] [Deliver](#deliver)

## Architecture
Multi-step form / wizard / signup flow. Tall forms with visible
validation and a step indicator. NATIVE React state — no
react-hook-form, no zod, no formik (keeps deliveries small and the
behavior obvious in tests). Submit is stubbed with `setTimeout`.

Compose in `src/App.tsx`. State shape: `useState<number>` for step,
`useState<FormData>` for fields, `useState<Errors>` for validation.

## Schema
Define one type at the top of `src/App.tsx`:
```ts
type FormData = { email: string; password: string; name: string; ... }
type Errors = Partial<Record<keyof FormData, string>>
```
Initialize `useState<FormData>(EMPTY_FORM)`. Pass `(field, value) => setForm(p => ({ ...p, [field]: value }))`
down to each step.

## Steps
One component per step in `src/components/Step<Name>.tsx`. Each accepts
`{ data, errors, onChange, onPrev, onNext }`. Render fields with the
shipped UI primitives:
- `Input label="..." error={errors.field} helperText="..." size="md" fullWidth`
- `Select label="..." value={data.field} onValueChange={...} options={...}`
- `Switch checked={data.field} onCheckedChange={...} label="..." color="primary"`
- Plan tier picker: `Card variant={selected ? "elevated" : "outline"} padding="lg" interactive onClick={...}`
- Step indicator at the top: `Badge variant="success|primary|secondary" pill` numbered + `Progress size="sm" color="primary"`.

Drone-natural prop coverage is locked into `__fixtures__/form_patterns.tsx` —
read it for canonical shapes.

## Validation
Per-field validators inline in the step component:
```ts
const emailErr = email && !/^\S+@\S+\.\S+$/.test(email) ? "Invalid email" : ""
const pwErr   = pw && pw.length < 8                      ? "At least 8 characters" : ""
```
Pass results to `<Input error={...}>`. Disable the Continue button
when any required field has an error or is empty.

Submit summary uses `<Alert variant="success" title="Account created">`
inside a `<Dialog>` for the success state. On failure, `<Alert variant="destructive">`.

## Tests
- `Empty email → Continue disabled`
- `Invalid email → error message visible, Continue disabled`
- `Valid form → step advances`
- `Back button → step decrements, data preserved`
- `Submit → success Dialog opens`
- `Switch toggle → state flips, label visible`

## Build
shell_exec cd {project_path} && npm run build

## Deliver
message_result with one-line description.
