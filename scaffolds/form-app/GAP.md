# GAP — form-app

## Purpose
Multi-step form / wizard / signup flow. Tall forms with validation,
progress indicators, conditional fields. Native React state (no
react-hook-form default — keeps scope tight).

## Wire state
- **Not routed.** Scaffold exists; no plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥3 vision-PASS deliveries**.

## Structural blockers (known)
- Form validation conventions (zod vs yup vs native) — drone picks
  inconsistently.
- Multi-step state: useReducer vs useState[] — both viable but drone
  defaults to sprawling useState chains.
- No plan_scaffold.

## Churn lever
1. Add `plan_scaffolds/form-app.md` — sections: Schema, Steps,
   Validation, Navigation, Submit.
2. Route on `signup flow / wizard / multi-step form / onboarding
   form / survey`.
3. Pin validation approach: native HTML5 validation + one custom
   validator per field. No form library by default.
4. Ship: 3-step signup, onboarding survey, account setup wizard.

## Out of scope
- Backend submission (stub with setTimeout).
- File uploads (separate scaffold).

## Test suite (inference-free)
Fixtures exercise validation states + step transitions. `vitest` for
reducer logic, `npm run build` for compile. Parallel-safe.

## Success signal
Forms ship with visible validation errors, step indicator, and no
accessibility warnings (aria-invalid, labels).
