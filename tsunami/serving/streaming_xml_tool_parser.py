"""Streaming XML tool-call parser for Qwen3.6's HF-agents emission format.

Structural port of QwenLM/qwen-code's
`packages/core/src/core/openaiContentGenerator/streamingToolCallParser.ts`,
adapted for the XML format Qwen3.6 emits natively:

    <tool_call>
    <function=NAME>
    <parameter=KEY>VALUE</parameter>
    ...
    </function>
    </tool_call>

Differences from the upstream TS reference:

  * Qwen-code parses JSON deltas streamed over OpenAI-protocol SSE
    (`delta.tool_calls[i].function.arguments` arrives as JSON fragments).
    We parse XML blocks that arrive whole today (our proxy doesn't
    stream) but the per-index state machine is the same so that when
    we add streaming, the parser is already wired.
  * "inString" semantics map to "inside a <parameter=...> value body"
    — the equivalent unclosed-state that needs repair when truncated.
  * Index semantics: qwen-code receives an explicit `index` per SSE
    delta. Our XML has no explicit index, so we assign one per
    `<tool_call>` opened (most-recent-incomplete routing for
    continuation chunks without IDs is unchanged).

Problems this parser handles (same list as qwen-code's):

  * Chunks arrive with varying shapes (empty, partial XML, complete)
  * Tool calls may lack IDs, names, or have inconsistent indices
  * Multiple tool calls processed simultaneously with interleaved chunks
  * Index collisions when the same index is reused for different calls
  * Values fragmented across chunks and needing reconstruction
"""

from __future__ import annotations

import json as _json
import re
from dataclasses import dataclass, field


_TOOL_CALL_OPEN = "<tool_call>"
_TOOL_CALL_CLOSE = "</tool_call>"
_FN_OPEN_RE = re.compile(r"<function\s*=\s*([^>\s]+)\s*>", re.IGNORECASE)
_FN_CLOSE = "</function>"
_PARAM_OPEN_RE = re.compile(r"<parameter\s*=\s*([^>\s]+)\s*>", re.IGNORECASE)
_PARAM_CLOSE = "</parameter>"

# Whole-block extraction once repair has completed.
_BLOCK_RE = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL | re.IGNORECASE
)
_FN_BLOCK_RE = re.compile(
    r"<function\s*=\s*([^>\s]+)\s*>\s*(.*?)\s*</function>",
    re.DOTALL | re.IGNORECASE,
)
_PARAM_BLOCK_RE = re.compile(
    r"<parameter\s*=\s*([^>\s]+)\s*>\s*(.*?)\s*</parameter>",
    re.DOTALL | re.IGNORECASE,
)


def _coerce(v: str):
    s = v.strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if s.lower() == "null":
        return None
    try:
        return _json.loads(s)
    except Exception:
        return s


@dataclass
class ToolCallParseResult:
    """Mirrors qwen-code's ToolCallParseResult shape."""

    complete: bool
    value: dict | None = None
    error: Exception | None = None
    repaired: bool = False


@dataclass
class _IndexState:
    buffer: str = ""
    # Depth across nested openings: +1 per <tool_call>, <function=>, <parameter=>;
    # -1 per matching close. At depth 0 with a non-empty buffer the tool_call
    # is complete.
    depth: int = 0
    in_param_value: bool = False  # inside <parameter=...> body (analog of "inString")
    id: str | None = None
    name: str | None = None
    complete: bool = False


@dataclass
class CompletedToolCall:
    id: str | None
    name: str | None
    args: dict
    index: int


class StreamingXmlToolCallParser:
    """Per-index streaming parser for Qwen3.6 XML tool-call blocks.

    Usage (streaming):

        parser = StreamingXmlToolCallParser()
        for chunk in stream:
            parser.add_chunk(index=chunk.index, chunk=chunk.text,
                             id=chunk.id, name=chunk.name)
        calls = parser.get_completed_tool_calls()

    Usage (non-streaming / one-shot, our current proxy path):

        parser = StreamingXmlToolCallParser()
        parser.add_chunk(0, whole_content)
        calls = parser.get_completed_tool_calls()
        stripped = parser.get_stripped_content(whole_content)
    """

    def __init__(self) -> None:
        self._states: dict[int, _IndexState] = {}
        self._id_to_index: dict[str, int] = {}
        self._next_available_index: int = 0

    # ------------------------------------------------------------------
    # Streaming entry point (qwen-code addChunk equivalent)

    def add_chunk(
        self,
        index: int,
        chunk: str,
        id: str | None = None,
        name: str | None = None,
    ) -> ToolCallParseResult:
        """Absorb a chunk and return whether the tool_call is now complete.

        Mirrors qwen-code streamingToolCallParser.addChunk():
        - id collision → route to new index
        - no id → route to the most-recent-incomplete index at this slot
        - track depth + in_param_value across the chunk
        - when depth returns to 0 try to extract a complete tool_call
        """
        actual_index = self._route_index(index, id)
        state = self._states.setdefault(actual_index, _IndexState())

        if id:
            state.id = id
        if name:
            state.name = name

        state.buffer += chunk
        # Tags are multi-char, so a single chunk may split one mid-name
        # (`<para` + `meter=...>`). Recompute depth + in_param_value from
        # the whole buffer each call — cheap for our buffer sizes and
        # equivalent to qwen-code's per-char JSON counter running over a
        # multi-char-token language.
        self._recompute_from_buffer(state)

        if state.depth == 0 and state.buffer.strip():
            result = self._try_extract(state)
            if result.complete:
                state.complete = True
            return result
        return ToolCallParseResult(complete=False)

    # ------------------------------------------------------------------
    # One-shot / final extraction (qwen-code getCompletedToolCalls equivalent)

    def get_completed_tool_calls(self) -> list[CompletedToolCall]:
        """Emit every tool_call we've seen, repairing truncated state.

        Called once streaming is done (finish_reason set) OR once per
        one-shot invocation. Uses three parse strategies in order:
        1. Parse buffer as-is
        2. Auto-close unclosed param/function/tool_call tags and retry
        3. Extract whatever <parameter=...> blocks we can salvage
        """
        completed: list[CompletedToolCall] = []
        for index, state in self._states.items():
            if not state.buffer.strip():
                continue
            repaired_buffer = self._repair_unclosed(state.buffer)
            for tc in _extract_blocks(repaired_buffer):
                # Preserve metadata from streaming if any chunk carried id/name.
                if state.id and not tc.id:
                    tc.id = state.id
                tc.index = index
                completed.append(tc)
        return completed

    def has_incomplete_tool_calls(self) -> bool:
        """True iff any index has depth>0 or in_param_value=True at end-of-stream.

        Used by the proxy to decide whether to force a `length` finish
        reason (a stream was cut off mid-tool_call even if the upstream
        said "stop" / "tool_calls"). Name is either supplied via
        add_chunk(name=...) for OpenAI-protocol streams OR embedded in
        the buffer as `<function=X>` for pure content streams — accept
        either.
        """
        for state in self._states.values():
            has_name = bool(state.name) or bool(_FN_OPEN_RE.search(state.buffer))
            if not has_name:
                continue
            if state.depth > 0 or state.in_param_value:
                return True
        return False

    # ------------------------------------------------------------------
    # Non-streaming helpers

    def get_stripped_content(self, original: str) -> str:
        """Return `original` with all <tool_call>...</tool_call> blocks removed.

        Applies the same auto-close repair as get_completed_tool_calls so
        that a truncated tail is still recognised as a block and stripped.
        """
        repaired = self._repair_unclosed(original)
        remaining = repaired
        for m in _BLOCK_RE.finditer(repaired):
            remaining = remaining.replace(m.group(0), "", 1)
        return remaining.strip()

    def reset(self) -> None:
        self._states.clear()
        self._id_to_index.clear()
        self._next_available_index = 0

    def reset_index(self, index: int) -> None:
        self._states.pop(index, None)

    def get_buffer(self, index: int) -> str:
        s = self._states.get(index)
        return s.buffer if s else ""

    def get_state(self, index: int) -> dict:
        s = self._states.get(index)
        if not s:
            return {"depth": 0, "in_param_value": False, "complete": False}
        return {
            "depth": s.depth,
            "in_param_value": s.in_param_value,
            "complete": s.complete,
        }

    # ------------------------------------------------------------------
    # Internals

    def _route_index(self, index: int, id: str | None) -> int:
        """Port of qwen-code's id-collision + most-recent-incomplete routing."""
        if id:
            if id in self._id_to_index:
                return self._id_to_index[id]
            # New id — check if the slot is occupied by a different completed call
            existing = self._states.get(index)
            if existing and existing.buffer.strip() and existing.depth == 0 \
                    and existing.id and existing.id != id and existing.complete:
                index = self._find_next_available_index()
            self._id_to_index[id] = index
            return index
        # No id — continuation chunk. Route to incomplete buffer at this slot,
        # or the most-recent-incomplete if the slot is already complete.
        existing = self._states.get(index)
        if existing and existing.depth > 0:
            return index
        if existing and existing.complete:
            return self._find_most_recent_incomplete_index() or index
        return index

    def _find_next_available_index(self) -> int:
        while self._next_available_index in self._states:
            s = self._states[self._next_available_index]
            if not s.buffer.strip() or s.depth > 0 or not s.complete:
                return self._next_available_index
            self._next_available_index += 1
        idx = self._next_available_index
        self._next_available_index += 1
        return idx

    def _find_most_recent_incomplete_index(self) -> int | None:
        best: int | None = None
        for idx, s in self._states.items():
            if s.depth > 0 or (s.buffer.strip() and not s.complete):
                if best is None or idx > best:
                    best = idx
        return best

    def _recompute_from_buffer(self, state: _IndexState) -> None:
        """Scan the whole buffer to set depth + in_param_value.

        Depth = (count of all opening tags) - (count of all closing tags).
        in_param_value = True iff the last <parameter=...> open has no
        matching </parameter> after it in the buffer. Both computed from
        scratch each call so partial tags split across chunks resolve as
        soon as the rest of the tag arrives.
        """
        buf = state.buffer
        opens = (
            buf.count(_TOOL_CALL_OPEN)
            + len(_FN_OPEN_RE.findall(buf))
            + len(_PARAM_OPEN_RE.findall(buf))
        )
        closes = (
            buf.count(_TOOL_CALL_CLOSE)
            + buf.count(_FN_CLOSE)
            + buf.count(_PARAM_CLOSE)
        )
        state.depth = opens - closes
        # in_param_value: True iff the last <parameter=...> in the buffer
        # has no </parameter> after it.
        last_open_match = None
        for m in _PARAM_OPEN_RE.finditer(buf):
            last_open_match = m
        if last_open_match is None:
            state.in_param_value = False
        else:
            tail = buf[last_open_match.end():]
            state.in_param_value = _PARAM_CLOSE not in tail

    def _try_extract(self, state: _IndexState) -> ToolCallParseResult:
        """When depth returns to 0, see if we can extract a complete block."""
        buf = state.buffer
        m = _BLOCK_RE.search(buf)
        if not m:
            return ToolCallParseResult(complete=False)
        try:
            tc = _extract_blocks(buf)
            if tc:
                return ToolCallParseResult(complete=True,
                                           value={"name": tc[0].name,
                                                  "args": tc[0].args})
        except Exception as e:
            return ToolCallParseResult(complete=False, error=e)
        return ToolCallParseResult(complete=False)

    @staticmethod
    def _repair_unclosed(content: str) -> str:
        """Balance-audit repair: seal unclosed param/function/tool_call tags.

        Same repair rule as the old one-shot path, kept here so the
        streaming finalizer produces the same output for non-streaming
        consumers.
        """
        if _TOOL_CALL_OPEN in content and not _BLOCK_RE.search(content):
            last_open = content.rfind(_TOOL_CALL_OPEN)
            if last_open != -1:
                tail = content[last_open:]
                param_opens = len(_PARAM_OPEN_RE.findall(tail))
                param_closes = tail.count(_PARAM_CLOSE)
                if param_opens > param_closes:
                    tail += _PARAM_CLOSE * (param_opens - param_closes)
                fn_opens = len(_FN_OPEN_RE.findall(tail))
                fn_closes = tail.count(_FN_CLOSE)
                if fn_opens > fn_closes:
                    tail += _FN_CLOSE * (fn_opens - fn_closes)
                content = content[:last_open] + tail + _TOOL_CALL_CLOSE
        return content


def _extract_blocks(content: str) -> list[CompletedToolCall]:
    """Pull every <tool_call> block out of content into CompletedToolCall records."""
    out: list[CompletedToolCall] = []
    for block_match in _BLOCK_RE.finditer(content):
        inner = block_match.group(1).strip()
        if inner.startswith("{"):
            # JSON variant: {"name":"X","arguments":{...}}
            try:
                obj = _json.loads(inner)
                name = obj.get("name")
                args = obj.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = _json.loads(args)
                    except Exception:
                        pass
                out.append(CompletedToolCall(id=None, name=name,
                                             args=args if isinstance(args, dict) else {},
                                             index=0))
                continue
            except Exception:
                pass
        fn_match = _FN_BLOCK_RE.search(inner)
        if not fn_match:
            continue
        name = fn_match.group(1)
        fn_body = fn_match.group(2)
        args: dict = {}
        for pm in _PARAM_BLOCK_RE.finditer(fn_body):
            args[pm.group(1)] = _coerce(pm.group(2))
        out.append(CompletedToolCall(id=None, name=name, args=args, index=0))
    return out
