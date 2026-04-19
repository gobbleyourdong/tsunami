# GAP — ai-app

## Purpose
LLM-chat app scaffold. Client chat UI + server streaming endpoint
to an OpenAI-compatible model (could be tsunami's own :8090).

## Wire state
- **Not routed.** No plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥2 deliveries**.

## Structural blockers (known)
- Streaming SSE plumbing: drone rarely gets the server→client stream
  shape right on first write (text/event-stream headers, data: lines,
  [DONE] sentinel).
- Model-endpoint config: hardcoded vs env. Drone picks both.

## Churn lever
1. Add `plan_scaffolds/ai-app.md` with explicit SSE format hint and
   `VITE_MODEL_ENDPOINT` env convention.
2. Route on `chat app / LLM interface / AI chatbot / assistant UI`.
3. Stream-gate: probe streams 3 tokens in ≤2s, assert chunk shape.
4. Ship: chat UI, completion playground, tiny agent shell.

## Out of scope
- Fine-tuning infrastructure (separate concern).
- Multi-turn memory beyond the conversation state (stick with in-RAM).

## Test suite (inference-free)
Mock model endpoint that streams canned SSE. Vitest for the client
chunk-parser. Parallel-safe via port env. Live-inference run (one) at
the end verifies against the real :8090.

## Success signal
User can type → first token appears in <500ms → stream completes →
transcript persists in state.
