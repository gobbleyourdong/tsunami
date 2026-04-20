"""ai-app delivery gate — SSE streaming contract check (no real LLM).

The ai-app scaffold is a chat / completion UI that consumes
Server-Sent Events from a model endpoint. Whether the drone's client
correctly parses an SSE stream — chunk framing, `data: [DONE]`
sentinel, keepalives, partial-line reassembly — is verifiable without
ever hitting a live LLM.

Strategy:
  1. Spawn a tiny stub SSE server inside this process (stdlib
     `http.server` on an ephemeral port) that emits a canned stream
     of N tokens at a controlled cadence.
  2. Have the drone's client configuration (`VITE_MODEL_ENDPOINT` or
     equivalent) point at the stub — callers inject this via env.
  3. As a probe of the *contract*, we also read the stub ourselves
     with httpx and assert: ≥3 data chunks within `deadline_s`, each
     in the `data: {json}` shape, ending with `[DONE]` sentinel.

This catches: missing `Content-Type: text/event-stream`, wrong chunk
separator, client failing to handle `[DONE]`. Client-side rendering
is covered elsewhere (vision gate against a mocked stream).
"""

from __future__ import annotations

import asyncio
import http.server
import json
import socketserver
import threading
import time
from pathlib import Path

import httpx

from ._probe_common import free_port, result, skip


# Canned token stream. Realistic enough that a real client parser
# exercises the same paths it would on an OpenAI-compatible endpoint.
DEFAULT_TOKENS = ["Hello", ", ", "world", "!"]


class _StubSSEServer:
    """One-shot SSE stub. Binds a socket, serves exactly one
    /v1/chat/completions POST with a canned stream, shuts down.
    """

    def __init__(self, tokens: list[str], chunk_interval_s: float):
        self.tokens = tokens
        self.chunk_interval_s = chunk_interval_s
        self.port = free_port()
        self._server: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        tokens = self.tokens
        interval = self.chunk_interval_s

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args, **kwargs):  # mute
                return

            def _stream_sse(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    for tok in tokens:
                        chunk = {
                            "id": "stub",
                            "object": "chat.completion.chunk",
                            "choices": [{
                                "index": 0,
                                "delta": {"content": tok},
                                "finish_reason": None,
                            }],
                        }
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                        self.wfile.flush()
                        time.sleep(interval)
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass  # client disconnected early; fine for a probe

            def do_POST(self):
                if self.path.startswith("/v1/chat/completions"):
                    # Drain request body so the client doesn't see a
                    # half-written state when we start streaming.
                    ln = int(self.headers.get("Content-Length") or 0)
                    if ln:
                        self.rfile.read(ln)
                    self._stream_sse()
                else:
                    self.send_error(404)

            def do_GET(self):
                # Some drone clients GET /stream instead of POSTing chat.
                if self.path.startswith(("/stream", "/sse", "/events")):
                    self._stream_sse()
                else:
                    self.send_error(404)

        self._server = socketserver.ThreadingTCPServer(
            ("127.0.0.1", self.port), Handler,
        )
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


async def _consume_sse(url: str, deadline_s: float) -> dict:
    """httpx client that reads the stub and classifies what arrived."""
    data_chunks: list[str] = []
    saw_done = False
    first_chunk_at: float | None = None
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=deadline_s + 1.0) as client:
            async with client.stream("POST", url + "/v1/chat/completions",
                                      json={"model": "stub", "messages": [],
                                            "stream": True}) as r:
                if r.status_code != 200:
                    return {"ok": False, "reason": f"stub returned {r.status_code}",
                            "chunks": 0}
                ct = r.headers.get("content-type", "")
                if "event-stream" not in ct:
                    return {"ok": False,
                            "reason": f"wrong Content-Type: {ct!r}",
                            "chunks": 0}
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        payload = line[6:]
                        if first_chunk_at is None:
                            first_chunk_at = time.monotonic() - start
                        if payload.strip() == "[DONE]":
                            saw_done = True
                            break
                        data_chunks.append(payload)
                    if time.monotonic() - start > deadline_s:
                        break
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {e}",
                "chunks": len(data_chunks)}

    return {
        "ok": True,
        "chunks": len(data_chunks),
        "saw_done": saw_done,
        "first_chunk_ms": round((first_chunk_at or 0) * 1000),
        "samples": data_chunks[:2],
    }


async def sse_probe(
    project_dir: Path | None = None,
    tokens: list[str] | None = None,
    chunk_interval_s: float = 0.05,
    min_chunks: int = 3,
    deadline_s: float = 2.0,
) -> dict:
    """Verify SSE streaming contract against a local stub.

    `project_dir` is accepted for API symmetry with the other probes
    (and so callers can extend to verify client-side parsing in
    future); the stub itself is self-contained. `min_chunks` defaults
    to 3 per the ai-app GAP spec.
    """
    stub_tokens = tokens or DEFAULT_TOKENS
    if len(stub_tokens) < min_chunks:
        return skip(f"caller configured {len(stub_tokens)} tokens < min_chunks={min_chunks}")

    stub = _StubSSEServer(stub_tokens, chunk_interval_s)
    try:
        stub.start()
    except OSError as e:
        return skip(f"could not bind stub SSE port: {e}")

    try:
        outcome = await _consume_sse(stub.base_url, deadline_s=deadline_s)
    finally:
        stub.stop()

    if not outcome.get("ok"):
        return result(False, f"SSE stub contract failed: {outcome.get('reason')}",
                      raw=json.dumps(outcome))

    issues: list[str] = []
    if outcome["chunks"] < min_chunks:
        issues.append(f"received {outcome['chunks']} chunks, expected ≥{min_chunks}")
    if not outcome["saw_done"]:
        issues.append("stream ended without [DONE] sentinel — clients won't know to finalise")
    if outcome["first_chunk_ms"] > int(deadline_s * 1000):
        issues.append(f"first chunk took {outcome['first_chunk_ms']} ms (> deadline)")

    return result(not issues, "; ".join(issues), raw=json.dumps(outcome))


__all__ = ["sse_probe", "DEFAULT_TOKENS"]
