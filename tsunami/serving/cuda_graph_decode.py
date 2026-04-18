"""Low-level CUDA graph capture for the decode step.

Per ~/agentic_speed/refs/kernels_digest_2026-04.md §top-10 item #7:
SGLang's "piecewise CUDA graph + speculative decoding" landed 2026-04-17
with ">=20% decode latency win". The 48.6 tok/s community number for
Qwen3.5-35B-A3B FP8 on GB10 (tier2/fa3.md) is CUDA-graph based.

torch.compile(mode="reduce-overhead") was attempted first but is
impractical on a 35B MoE — a test on this machine went 14+ min at
100% CPU with no completion. The framework's dynamo+inductor
compile path is trying to fuse the whole MoE graph which is too
large to optimize in reasonable time.

This module takes the lower-level torch.cuda.CUDAGraph path
instead: capture one decode step into a graph, replay per token.
No compile, no kernel fusion, just elimination of Python and
kernel-launch overhead per step.

Constraints:
  * All input tensor SHAPES must be static across calls (shape
    changes break graph replay). We use pre-allocated fixed-size
    buffers and copy new values in-place.
  * All input tensor POINTERS must be stable. Same as above.
  * StaticCache is required — its KV tensors are pre-allocated to
    max_cache_len so pointers don't change. DynamicCache won't work.
  * MoE routing (top-k expert selection) is OK: the control flow
    (which kernels fire) is the same each step; only tensor
    CONTENTS change. Graph capture records launches, not data.

Scaffolding. Not yet integrated into lean_decode — next loop cycle
validates on a short decode before wiring.
"""

from __future__ import annotations

from typing import Optional

import torch


class CudaGraphedDecodeStep:
    """Capture model.forward() once, replay per decode step.

    Usage:
        g = CudaGraphedDecodeStep(model, max_cache_len=8192, device="cuda:0")
        g.capture(past_key_values, pos=prefill_len)
        for step in range(max_new):
            logits = g.step(tok=last_tok, pos=prefill_len + step)
            next_tok = sample(logits)
    """

    def __init__(self, model, max_cache_len: int, device: str = "cuda:0") -> None:
        self.model = model
        self.device = torch.device(device)
        self.max_cache_len = max_cache_len

        # Static input buffers — same addresses every step, contents
        # mutate via .copy_() / .fill_().
        self._input_ids = torch.zeros(1, 1, dtype=torch.long, device=self.device)
        self._attn_mask = torch.ones(1, max_cache_len, dtype=torch.long, device=self.device)
        self._pos = torch.zeros(1, 1, dtype=torch.long, device=self.device)
        self._cache_pos = torch.zeros(1, dtype=torch.long, device=self.device)

        self._graph: Optional[torch.cuda.CUDAGraph] = None
        self._captured_logits: Optional[torch.Tensor] = None
        self._past: object = None  # ref to the static cache we captured against

    def _forward(self):
        """The exact sequence captured / replayed each step."""
        with torch.inference_mode():
            return self.model(
                input_ids=self._input_ids,
                attention_mask=self._attn_mask,
                position_ids=self._pos,
                cache_position=self._cache_pos,
                past_key_values=self._past,
                use_cache=True,
                return_dict=True,
            )

    def capture(self, past_key_values, pos: int, warmup_iters: int = 3) -> None:
        """Warm up the stream then capture one forward call.

        past_key_values must be a StaticCache or similar with fixed
        tensor pointers across updates. DynamicCache will break on
        replay because the cache grows via torch.cat (new allocation).
        """
        self._past = past_key_values
        self._pos.fill_(pos)
        self._cache_pos.fill_(pos)

        # Stream warmup — per torch docs, run the capture sequence a
        # few times on a side stream before graph capture so allocator
        # caching and autotuner state are stable. Without this, the
        # captured graph can reference allocator state that doesn't
        # exist on replay.
        s = torch.cuda.Stream()
        s.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(s):
            for _ in range(warmup_iters):
                _ = self._forward()
        torch.cuda.current_stream().wait_stream(s)
        torch.cuda.synchronize()

        # Actual capture.
        self._graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(self._graph):
            out = self._forward()
        # Save reference to the logits tensor — on replay, the graph
        # writes new values to this same tensor in-place.
        self._captured_logits = out.logits

    def step(self, tok: torch.Tensor, pos: int) -> torch.Tensor:
        """Replay the captured graph with new input. Returns last-row logits.

        tok: (1,) or (1,1) int64 token id.
        pos: absolute position of the new token (cache slot to write + 1).
        """
        if self._graph is None:
            raise RuntimeError("capture() must be called before step()")
        # Update input buffers in-place; pointers are stable so the
        # graph replays correctly.
        self._input_ids.copy_(tok.view(1, 1))
        self._pos.fill_(pos)
        self._cache_pos.fill_(pos)
        self._graph.replay()
        # The captured logits tensor was updated by the replay.
        return self._captured_logits[:, -1, :]

    def reset(self) -> None:
        """Release the graph + captured tensors (e.g., between sessions)."""
        self._graph = None
        self._captured_logits = None
        self._past = None
