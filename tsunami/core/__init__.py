"""tsunami.core — delivery-gate probes.

Each probe is a single async function that mirrors the `vision_check`
contract:

    async def <name>_probe(...) -> dict:
        # returns {"passed": bool, "issues": str, "raw": str}

`passed` is True on success OR when the gate can't run (fall-through;
the drone isn't blocked by gate infrastructure failures).

Probes are parallel-safe: all listen on ephemeral ports picked per
invocation, all spawn child processes they own and kill on exit.

Pair-up (one probe per scaffold class):
    server_probe    — auth-app / fullstack (spawn + /health)
    openapi_probe   — api-only (spawn + /openapi.json schema-check)
    ws_probe        — realtime (spawn + two-client WS roundtrip)
    extension_probe — chrome-extension (manifest v3 schema + bundle)
    electron_probe  — electron-app (build without GUI launch)
    sse_probe       — ai-app (SSE stub + chunk-shape roundtrip)
"""
