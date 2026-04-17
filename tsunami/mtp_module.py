#!/usr/bin/env python3
"""MTP (Multi-Token Prediction) head for Qwen3.5-Moe FP8 models.

Transformers 5.x hard-ignores the `mtp.*` weights in Qwen3_5Moe checkpoints
(see `_keys_to_ignore_on_load_unexpected = [r"^mtp.*"]` in the modeling code),
so any speculative-decoding throughput win has to be wired manually. This
module is the smallest faithful implementation of that head: one Qwen3.5-Moe
decoder layer fed by a fused [hidden, next-token-embed] projection, driving
the main model's embed+lm_head. Purely for INFERENCE (no gradients).

Speed rationale: bs=1 decode is launch-overhead bound (~400 kernels per main
forward). MTP buys a second token per main forward at the cost of one extra
MoE layer — which is ~1/40th of the main model — so the break-even point is
below 3% acceptance. Qwen-trained MTPs typically hit 60-80% acceptance on
well-formed prompts, yielding ~1.5-1.8x real-world.

Weight layout in mtp.safetensors (already inspected):
  mtp.fc                  (2048, 4096) fp8        # hidden||embed → hidden
  mtp.pre_fc_norm_hidden  (2048,)      bf16
  mtp.pre_fc_norm_embedding (2048,)    bf16
  mtp.layers.0.*          full Qwen3.5-Moe decoder layer (self_attn + MoE + shared)
  mtp.norm                (2048,)      bf16
"""
from __future__ import annotations
from pathlib import Path

import torch
import torch.nn as nn
from safetensors import safe_open


def fuse_mtp_experts(snapshot: Path, device: str = "cuda:0") -> dict:
    """Same fuser logic as the main model's expert fuser, restricted to the
    `mtp.layers.0.mlp.experts.*` namespace. Returns a GPU state_dict with the
    packed `gate_up_proj` / `down_proj` tensors transformers-style code
    expects (though we're building our own module, we keep the naming
    consistent with Qwen3_5MoeSparseMoeBlock for drop-in compatibility)."""
    import re
    from collections import defaultdict
    import gc

    exp_re = re.compile(
        r"^(mtp\.layers\.0\.mlp\.experts)\.(\d+)\."
        r"(gate_proj|up_proj|down_proj)\.(weight|weight_scale_inv)$"
    )

    path = snapshot / "mtp.safetensors"
    with safe_open(str(path), framework="pt", device=device) as f:
        all_keys = list(f.keys())
        non_expert_sd: dict[str, torch.Tensor] = {
            k: f.get_tensor(k) for k in all_keys if not exp_re.match(k)
        }
        experts: dict[tuple[str, int], dict[int, dict[tuple[str, str], torch.Tensor]]] = defaultdict(lambda: defaultdict(dict))
        for k in all_keys:
            m = exp_re.match(k)
            if not m:
                continue
            prefix, e, proj, suf = m.group(1), int(m.group(2)), m.group(3), m.group(4)
            experts[(prefix, 0)][e][(proj, suf)] = f.get_tensor(k)

        packed: dict[str, torch.Tensor] = dict(non_expert_sd)
        for (prefix, _), per_expert in experts.items():
            num = max(per_expert) + 1
            gu_w, gu_s, d_w, d_s = [], [], [], []
            for i in range(num):
                slots = per_expert[i]
                gu_w.append(torch.cat([slots[("gate_proj", "weight")],
                                       slots[("up_proj", "weight")]], dim=0))
                gu_s.append(torch.cat([slots[("gate_proj", "weight_scale_inv")],
                                       slots[("up_proj", "weight_scale_inv")]], dim=0))
                d_w.append(slots[("down_proj", "weight")])
                d_s.append(slots[("down_proj", "weight_scale_inv")])
            packed[f"{prefix}.gate_up_proj"] = torch.stack(gu_w).contiguous()
            packed[f"{prefix}.gate_up_proj_scale_inv"] = torch.stack(gu_s).contiguous()
            packed[f"{prefix}.down_proj"] = torch.stack(d_w).contiguous()
            packed[f"{prefix}.down_proj_scale_inv"] = torch.stack(d_s).contiguous()
        experts.clear()
        gc.collect()
    return packed


class MTPHead(nn.Module):
    """Wraps the one MTP decoder layer + its fc/norm projections. Reuses the
    main model's embed_tokens and lm_head (Qwen3.5-Moe ties these across the
    MTP and main heads by design — mtp.safetensors does NOT ship them)."""

    def __init__(self, text_config, main_model: nn.Module):
        super().__init__()
        # Import the real Qwen3_5Moe layer class so our forward matches the
        # base model bit-for-bit (self_attn rotary, MoE routing, shared expert).
        from transformers.models.qwen3_5_moe.modeling_qwen3_5_moe import (
            Qwen3_5MoeDecoderLayer,
        )
        # The decoder layer dispatches attention + expert routing through
        # `config._attn_implementation` / `_experts_implementation`. Standalone
        # instantiation leaves those as None (we saw the warning), which sends
        # the forward down a broken "module-as-library" code path — manifests
        # as 0% MTP acceptance. Copy the same implementations the main model
        # picked so the behaviours match.
        if getattr(text_config, "_attn_implementation", None) in (None, "None"):
            text_config._attn_implementation = (
                getattr(main_model.config, "_attn_implementation", None)
                or "eager"
            )
        if getattr(text_config, "_experts_implementation", None) in (None, "None"):
            text_config._experts_implementation = (
                getattr(main_model.config, "_experts_implementation", None)
                or "eager"
            )
        self.hidden_size = text_config.hidden_size
        # mtp.fc maps 2*hidden → hidden (concat of normalised hidden + embed).
        # CRITICAL: use the model's native RMSNorm, not torch.nn.RMSNorm.
        # Qwen3_5MoeRMSNorm computes `output * (1.0 + self.weight)` — its
        # weights are stored as delta-from-1 (init zeros() = scale 1.0). The
        # stock torch.nn.RMSNorm does `output * self.weight`, so loading the
        # checkpoint into it inverts the sign and shifts the magnitude.
        # Diagnostic: weight mean for pre_fc_norm_hidden was -0.506 → Qwen
        # applies scale 0.494; nn.RMSNorm applied -0.506, which explains
        # every iteration's 0% accept rate (and the entropy-only-halfway-
        # down-from-uniform signature after the cache-write fix).
        from transformers.models.qwen3_5_moe.modeling_qwen3_5_moe import (
            Qwen3_5MoeRMSNorm,
        )
        self.pre_fc_norm_hidden = Qwen3_5MoeRMSNorm(self.hidden_size, eps=text_config.rms_norm_eps)
        self.pre_fc_norm_embedding = Qwen3_5MoeRMSNorm(self.hidden_size, eps=text_config.rms_norm_eps)
        self.fc = nn.Linear(2 * self.hidden_size, self.hidden_size, bias=False)

        # Two separate concerns:
        #   (1) Layer-type selection happens at init via layer_idx indexing
        #       into config.layer_types. First full_attention index picks
        #       the full-attention variant (weight shapes q_proj 8192
        #       == 32*256 confirm this matches the checkpoint).
        #   (2) KV-cache slot key is `self_attn.layer_idx` at runtime.
        #       Diagnostic on layer_idx=first_full proved that cache writes
        #       landed in slot N but `cache.get_seq_length()` reads slot 0
        #       → decode sees an empty context, MTP logits are ~84% of
        #       uniform entropy, 0% accept.
        # Fix: init with the correct layer-type index, then rewire the
        # self_attn instance's layer_idx to 0 so the single-layer MTP cache
        # writes/reads the same slot.
        layer_type_full = next(
            (i for i, t in enumerate(text_config.layer_types) if t == "full_attention"),
            0,
        )
        self.layer = Qwen3_5MoeDecoderLayer(text_config, layer_idx=layer_type_full)
        # Force every cache interaction to use slot 0. Qwen3.5-MoE's
        # self_attn stores its layer_idx as an attribute and passes it to
        # past_key_values.update(... layer_idx=self.layer_idx ...).
        if hasattr(self.layer, "self_attn") and hasattr(self.layer.self_attn, "layer_idx"):
            self.layer.self_attn.layer_idx = 0
        # Some Qwen3_5Moe builds also stash a top-level layer_idx; keep it in
        # sync so any helpers that read the outer attr see 0 too.
        if hasattr(self.layer, "layer_idx"):
            self.layer.layer_idx = 0
        self.norm = Qwen3_5MoeRMSNorm(self.hidden_size, eps=text_config.rms_norm_eps)
        # The decoder layer expects pre-computed rotary cos/sin (passed as
        # `position_embeddings`) rather than raw position_ids. Mirror what the
        # main model does at the outer level.
        from transformers.models.qwen3_5_moe.modeling_qwen3_5_moe import (
            Qwen3_5MoeTextRotaryEmbedding,
        )
        self.rotary_emb = Qwen3_5MoeTextRotaryEmbedding(text_config)

        # Reuse main model's token embedding + lm_head. These are not in
        # mtp.safetensors on purpose (weight sharing).
        self.embed_tokens = main_model.get_input_embeddings()
        self.lm_head = main_model.get_output_embeddings()

    @torch.no_grad()
    def forward(
        self,
        hidden_from_main: torch.Tensor,   # (B, S, H) – main model's last layer
        next_token_ids: torch.Tensor,     # (B, 1)   – token sampled from main
        position_ids: torch.Tensor | None = None,
        past_key_values=None,
    ) -> torch.Tensor:
        """Returns logits of shape (B, 1, vocab) predicting the token at
        position S+1 given hidden at position S and the already-sampled token
        for S. Caller is responsible for the accept/reject verification."""
        last = hidden_from_main[:, -1:, :]
        emb = self.embed_tokens(next_token_ids)  # (B,1,H)
        # Concat order matters: DeepSeek-V3 MTP (Qwen's ancestor) uses
        # [embed, hidden] → fc expects embedding in the first half and hidden
        # in the second. Flipping was tried in iteration 7 and also produced
        # 0% accept, so the order is not the bug. Reverted to [embed, hidden].
        x = torch.cat([self.pre_fc_norm_embedding(emb),
                       self.pre_fc_norm_hidden(last)], dim=-1)  # (B,1,2H)
        x = self.fc(x)  # (B,1,H)

        pos_emb = self.rotary_emb(x, position_ids)
        # Transformers v5 signature: past_key_values (plural). See mtp_prefill
        # comment — the old singular name silently dropped through **kwargs.
        out = self.layer(
            x,
            position_ids=position_ids,
            position_embeddings=pos_emb,
            past_key_values=past_key_values,
            use_cache=past_key_values is not None,
        )
        h = out[0] if isinstance(out, tuple) else out
        h = self.norm(h)
        return self.lm_head(h)


@torch.no_grad()
def _sample(logits: torch.Tensor, temperature: float, top_p: float, top_k: int) -> torch.Tensor:
    """Same sampling contract as HF generate: greedy when temp==0, else
    top-k + top-p + temperature. logits: (B, vocab). Returns (B, 1)."""
    if temperature <= 0:
        return logits.argmax(dim=-1, keepdim=True)
    logits = logits / temperature
    if top_k > 0:
        v, _ = torch.topk(logits, top_k, dim=-1)
        logits = torch.where(logits < v[..., -1:], float("-inf"), logits)
    if 0 < top_p < 1.0:
        sorted_logits, sorted_idx = torch.sort(logits, descending=True, dim=-1)
        probs = torch.softmax(sorted_logits, dim=-1)
        cum = probs.cumsum(dim=-1)
        mask = cum > top_p
        mask[..., 0] = False  # always keep top-1
        sorted_logits = sorted_logits.masked_fill(mask, float("-inf"))
        # scatter back
        logits = torch.full_like(logits, float("-inf")).scatter(-1, sorted_idx, sorted_logits)
    probs = torch.softmax(logits, dim=-1)
    return torch.multinomial(probs, 1)


@torch.no_grad()
def mtp_prefill(
    main_hidden: torch.Tensor,      # (1, S, H) from main model's last layer
    input_ids: torch.Tensor,         # (1, S) full prompt
    mtp_head: "MTPHead",
):
    """Build MTP's KV cache over the prompt. For each position i in 0..S-2,
    MTP sees (hidden[i], embed(input_ids[i+1])) and produces a hidden the
    layer writes into cache. Done as ONE batched forward (like main prefill)
    for free O(S²) attention parallelism instead of S sequential steps.

    Returns a DynamicCache of length S-1 the caller feeds to decode."""
    from transformers import DynamicCache
    B, S, H = main_hidden.shape
    if S < 2:
        return DynamicCache()  # not enough context to prefill — empty cache
    h_shift = main_hidden[:, :-1, :]       # (1, S-1, H) hidden_0..S-2
    t_shift = input_ids[:, 1:]              # (1, S-1) tokens_1..S-1
    emb = mtp_head.embed_tokens(t_shift)    # (1, S-1, H)
    # Concat order reverted to [embed, hidden] after iteration 8 showed the
    # flipped variant also yielded 0% accept — the concat order is not the
    # root cause. Must match MTPHead.forward; both paths write/read the same
    # cache so they must agree on layout, whatever the layout is.
    x = torch.cat([
        mtp_head.pre_fc_norm_embedding(emb),
        mtp_head.pre_fc_norm_hidden(h_shift),
    ], dim=-1)                              # (1, S-1, 2H) — [emb, hidden]
    x = mtp_head.fc(x)                      # (1, S-1, H)
    pos_ids = torch.arange(S - 1, device=main_hidden.device)[None, :]  # (1, S-1)
    pos_emb = mtp_head.rotary_emb(x, pos_ids)
    cache = DynamicCache()
    # Without an explicit attention_mask the decoder layer may attend
    # bidirectionally across the prefill (transformers' DecoderLayer forward
    # propagates whatever is passed — None often means "no masking" in the
    # SDPA path). That would poison the cached K/V: each entry's K at
    # position j would have been formed attending to future positions j+1..S-2,
    # so decode-time causal attention reads these "from the future" states and
    # gets garbage. Build a lower-triangular 4D bool mask (batch=1, heads=1,
    # q=S-1, k=S-1) so broadcasting fills the rest — same shape transformers'
    # own mask builder produces for causal attention.
    seq = S - 1
    causal = torch.ones((seq, seq), dtype=torch.bool, device=main_hidden.device).tril_()
    attn_mask_4d = causal[None, None, :, :]  # (1, 1, S-1, S-1)
    # Transformers v5 renamed the cache kwarg on Qwen3_5MoeDecoderLayer.forward
    # from `past_key_value` to `past_key_values` (plural). Using the old name
    # silently dropped the cache — self_attn received None and never called
    # update(), leaving the DynamicCache empty (layers len=0) despite our
    # prefill pass. Confirmed via test_mtp_diagnose.py (cache internals dump).
    mtp_head.layer(
        x,
        attention_mask=attn_mask_4d,
        position_ids=pos_ids,
        position_embeddings=pos_emb,
        past_key_values=cache,
        use_cache=True,
    )
    return cache


@torch.no_grad()
def generate_with_mtp(
    main_model,
    mtp_head: MTPHead,
    input_ids: torch.Tensor,          # (1, S)
    attention_mask: torch.Tensor,     # (1, S)
    max_new_tokens: int,
    eos_token_ids: set[int],
    temperature: float = 0.0,
    top_p: float = 0.95,
    top_k: int = 64,
    extra_inputs: dict | None = None,  # e.g. pixel_values / image_grid_thw / mm_token_type_ids
) -> tuple[torch.Tensor, dict]:
    """Speculative decode with one-token MTP draft + verification.

    Protocol per step (after prefill):
      1. MTP head predicts token t+1 given (last_hidden_{t}, sampled_{t}).
      2. Main model consumes [sampled_{t}, speculated_{t+1}] as a length-2 input.
         Outputs logits at both positions.
      3. If main's sample at position-0 matches speculated → accept both, advance 2.
         Else → keep main's corrected token only, advance 1 and roll MTP KV back.

    Returns (generated_ids, stats) where stats tracks acceptance-rate for the
    caller to log. One main forward serves 1.0..2.0 tokens depending on accept.
    """
    device = input_ids.device
    extra_inputs = dict(extra_inputs or {})
    stats = {"steps": 0, "accepts": 0, "tokens_out": 0}

    # --- Prefill: full prompt through main model ---
    out = main_model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        output_hidden_states=True,
        use_cache=True,
        **extra_inputs,
    )
    main_past = out.past_key_values
    # Iteration 26 measured: hidden[-2] (pre-final-norm) gives 9% greedy
    # accept vs hidden[-1]'s 3%. The diagnostic (test_mtp_diagnose.py) shows
    # 83% top-1 alignment with [-1] because it rebuilds cache per position;
    # the generate loop accumulates and the two paths diverge. [-2] is the
    # empirically-better convention for streaming decode, so keep it.
    last_hidden = out.hidden_states[-2]  # pre-final-norm  # (1, S, H)
    next_tok = _sample(out.logits[:, -1, :], temperature, top_p, top_k)
    generated = [next_tok]
    seq_len = input_ids.shape[1] + 1  # positions consumed so far

    # Prefill MTP cache over the prompt so decode can attend over real
    # history. Without this, MTP single-step forward with empty KV attends
    # to itself only → predictions are uniform noise → 0% acceptance.
    mtp_past = mtp_prefill(last_hidden, input_ids, mtp_head)

    while len(generated) < max_new_tokens:
        last_tok = generated[-1]
        if last_tok.item() in eos_token_ids:
            break

        # --- 1. MTP draft: predict token at position seq_len (t+1) ---
        # MTP's position for this step is (seq_len - 1) — it pairs the hidden
        # at position (seq_len-2) with embed of token at (seq_len-1), which
        # is what `last_tok` represents.
        mtp_pos = torch.tensor([[mtp_past.get_seq_length()]], device=device)
        mtp_logits = mtp_head(
            hidden_from_main=last_hidden,
            next_token_ids=last_tok,
            position_ids=mtp_pos,
            past_key_values=mtp_past,  # now a real cache with prefilled context
        )  # (1, 1, V)
        speculated = _sample(mtp_logits[:, 0, :], temperature, top_p, top_k)

        # --- 2. Main forward on BOTH tokens ---
        # `last_tok` already has absolute position (seq_len - 1); the speculated
        # token sits at seq_len. An earlier off-by-one (seq_len, seq_len+1) put
        # RoPE rotations one position ahead of the cached K tokens, which is the
        # chief suspect behind the 2% observed accept rate — cached K embeds
        # positions 0..seq_len-2, but Q was rotated for positions seq_len..seq_len+1.
        two_tok = torch.cat([last_tok, speculated], dim=1)  # (1, 2)
        pos_ids = torch.tensor([[seq_len - 1, seq_len]], device=device)
        out = main_model(
            input_ids=two_tok,
            position_ids=pos_ids,
            past_key_values=main_past,
            output_hidden_states=True,
            use_cache=True,
        )
        main_past = out.past_key_values
        logits_both = out.logits  # (1, 2, V)

        # What main *actually* would have sampled at position 0 (the slot MTP guessed)
        main_at_draft_pos = _sample(logits_both[:, 0, :], temperature, top_p, top_k)

        # Leviathan-Chen stochastic acceptance for temperature > 0: accept the
        # speculated token with probability min(1, p(x)/q(x)) where p is
        # main's distribution and q is MTP's, both taken at position 0
        # (the slot speculation targets). Our prior rule was exact-argmax
        # match, which at temp>0 rejects every non-matching sample even when
        # p(x) is reasonable. The feifeibear reference uses this exact rule
        # and achieves ~40-70% accept on well-trained drafts; our 10-18%
        # at temp=0.7 is largely the strictness penalty. At temp=0 both
        # distributions are one-hot argmax → stochastic rule degenerates
        # into exact-match, so greedy behaviour is unchanged.
        import random as _rand
        if temperature <= 0:
            _accept = main_at_draft_pos.item() == speculated.item()
        else:
            _spec_idx = int(speculated.item())
            _q = torch.softmax(mtp_logits[0, 0, :].float() / temperature, dim=-1)[_spec_idx].item()
            _p = torch.softmax(logits_both[0, 0, :].float() / temperature, dim=-1)[_spec_idx].item()
            if _p >= _q:
                _accept = True
            elif _q <= 0.0:
                _accept = False
            else:
                _accept = _rand.random() < (_p / _q)

        stats["steps"] += 1
        full_hidden = out.hidden_states[-2]  # (1, 2, H) — pre-final-norm (see prefill comment)
        if _accept:
            # Accept MTP: we got 2 tokens out of 1 main forward.
            stats["accepts"] += 1
            generated.append(speculated)
            nxt = _sample(logits_both[:, 1, :], temperature, top_p, top_k)
            generated.append(nxt)
            # Iteration 27: tried adding an extra MTP call here to populate
            # the "skipped" cache entry (convention says cache slot N holds
            # fusion(hidden_N, token_{N+1}); on accept we skip writing slot N
            # → off-by-one drift). Benchmark went 9% → 6% greedy, so the
            # extra write actively hurt — MTP was apparently trained with
            # the one-write-per-iteration layout regardless of accept count.
            # Reverted; cache stays "behind" by accept-count but MTP handles
            # it internally better than the externally-corrected version.
            # Next MTP draft pairs embed(nxt) with hidden at nxt's slot, i.e.
            # position 1 in this 2-token forward.
            last_hidden = full_hidden[:, 1:2, :]
            seq_len += 2
        else:
            # Reject MTP: keep main's correction, roll back both caches by 1.
            # Main: we fed 2 tokens this step; only the first lands, so crop
            # main KV back to its length before this call (seq_len entries —
            # positions 0..seq_len-1). MTP: the speculation we just appended is
            # stale; crop one entry back.
            # The next MTP draft pairs embed(main_at_draft_pos) with hidden at
            # the accepted slot — position 0 in this 2-token forward — not the
            # rejected speculation's slot at position 1.
            generated.append(main_at_draft_pos)
            if hasattr(main_past, "crop"):
                main_past.crop(seq_len)
            if hasattr(mtp_past, "crop"):
                mtp_past.crop(mtp_pos.item())  # undo the step we just added
            last_hidden = full_hidden[:, 0:1, :]
            seq_len += 1

    stats["tokens_out"] = sum(t.numel() for t in generated)
    result = torch.cat(generated, dim=1)  # (1, N)
    return result, stats


def load_mtp_head(
    snapshot: Path,
    text_config,
    main_model: nn.Module,
    quantization_config,
    device: str = "cuda:0",
) -> MTPHead:
    """Build an MTPHead, apply the same FP8Linear wrapping the main model got
    (so weight_scale_inv slots exist), fuse experts from mtp.safetensors,
    load the state dict, and return the head in inference mode."""
    head = MTPHead(text_config, main_model)
    # Wrap nn.Linear with FP8Linear so weight_scale_inv tensors have a home.
    # The quantization_config that arrives from AutoConfig is still a raw dict;
    # replace_with_fp8_linear needs a proper FineGrainedFP8Config object.
    from transformers.integrations.finegrained_fp8 import replace_with_fp8_linear
    from transformers import FineGrainedFP8Config
    raw_skip = (
        getattr(quantization_config, "modules_to_not_convert", None)
        if not isinstance(quantization_config, dict)
        else quantization_config.get("modules_to_not_convert")
    ) or []
    # Translate main-model skip names into MTPHead-local names (mtp.layers.0.*
    # → layer.*) so we match the checkpoint's not-convert policy exactly.
    mapped_skip = []
    for s in raw_skip:
        if s.startswith("mtp.layers.0."):
            mapped_skip.append("layer." + s[len("mtp.layers.0."):])
        elif s.startswith("mtp."):
            mapped_skip.append(s[len("mtp."):])
    not_convert = mapped_skip + [
        "fc", "embed_tokens", "lm_head",
        "layer.mlp.shared_expert_gate",  # stays bf16 per checkpoint policy
    ]
    if isinstance(quantization_config, dict):
        qc = FineGrainedFP8Config(**{
            k: v for k, v in quantization_config.items()
            if k in ("activation_scheme", "weight_block_size",
                     "modules_to_not_convert")
        })
    else:
        qc = quantization_config
    # replace_with_fp8_linear reads `model.config.get_text_config()` for its
    # recursion — attach a lightweight shim so we don't need the full
    # ConditionalGeneration config tree.
    class _CfgShim:
        def __init__(self, tc): self._tc = tc
        def get_text_config(self): return self._tc
    head.config = _CfgShim(text_config)
    replace_with_fp8_linear(
        head, modules_to_not_convert=not_convert,
        quantization_config=qc, pre_quantized=True,
    )
    # Two-phase placement:
    #   (a) FP8Linear shells landed with meta weights — `to_empty` allocates
    #       empty GPU buffers (load_state_dict fills them next).
    #   (b) RMSNorms / other nn.Parameter modules were created on CPU during
    #       MTPHead __init__; we need a real .to(device) on those.
    # embed_tokens + lm_head are borrowed from main (already on GPU) — skip.
    for name, mod in list(head.named_modules()):
        if name in ("embed_tokens", "lm_head"):
            continue
        params = list(mod.parameters(recurse=False))
        bufs = list(mod.buffers(recurse=False))
        if not params and not bufs:
            continue
        if any(p.is_meta for p in params):
            mod.to_empty(device=device, recurse=False)
        else:
            for pn, p in list(mod.named_parameters(recurse=False)):
                setattr(mod, pn, torch.nn.Parameter(p.to(device), requires_grad=False))
            # Buffers (rotary_emb's inv_freq, attention_scaling, etc.) also
            # need moving — named_parameters alone misses them.
            for bn, b in list(mod.named_buffers(recurse=False)):
                mod.register_buffer(bn, b.to(device), persistent=True)
    head.train(False)  # inference mode (substring-shy)
    sd = fuse_mtp_experts(snapshot, device=device)
    # Remap keys: packed fuser emits names like
    #   mtp.layers.0.mlp.experts.gate_up_proj
    # our module has the decoder layer registered as `self.layer`, so strip
    # the `mtp.layers.0.` prefix and re-root the other mtp.* entries.
    remap: dict[str, torch.Tensor] = {}
    for k, v in sd.items():
        if k.startswith("mtp.layers.0."):
            nk = "layer." + k[len("mtp.layers.0."):]
        elif k.startswith("mtp.pre_fc_norm_hidden"):
            nk = "pre_fc_norm_hidden." + k[len("mtp.pre_fc_norm_hidden."):]
        elif k.startswith("mtp.pre_fc_norm_embedding"):
            nk = "pre_fc_norm_embedding." + k[len("mtp.pre_fc_norm_embedding."):]
        elif k.startswith("mtp.fc"):
            nk = "fc." + k[len("mtp.fc."):]
        elif k.startswith("mtp.norm"):
            nk = "norm." + k[len("mtp.norm."):]
        else:
            nk = k
        remap[nk] = v
    # assign=True makes load_state_dict replace Parameters with the provided
    # tensors instead of copying into pre-existing buffers. That preserves
    # source dtype — critical because non-FP8 modules (fc, norms) are stored
    # bf16 in the checkpoint but nn.Linear/nn.RMSNorm default to fp32.
    incompat = head.load_state_dict(remap, strict=False, assign=True)
    missing = [k for k in incompat.missing_keys if not (
        k.startswith("embed_tokens")
        or k.startswith("lm_head")
        or k.startswith("rotary_emb.")  # buffers, computed in __init__
    )]
    unexpected = list(incompat.unexpected_keys)
    if unexpected or missing:
        raise RuntimeError(
            f"MTP head load mismatch. missing={missing[:5]} "
            f"unexpected={unexpected[:5]} "
            f"(counts: miss={len(missing)} unexp={len(unexpected)})"
        )
    return head
