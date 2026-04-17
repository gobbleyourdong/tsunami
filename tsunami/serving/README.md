# tsunami/serving/

Native-transformers model-serving tier. Three processes, all launched by the
top-level `tsu` script; none use GGUF or llama-server.

## Active servers

| File | Port | Model | Purpose |
|------|------|-------|---------|
| `serve_qwen36_fp8.py` | :8095 | Qwen/Qwen3.6-35B-A3B-FP8 | Text + vision + coding + tool-calling |
| `embed_server.py` | :8093 | Qwen/Qwen3-Embedding-0.6B | OpenAI `/v1/embeddings` |
| *(external)* `tsunami/tools/ernie_server.py` | :8092 | baidu/ERNIE-Image-Turbo | Image generation (swap-capable to Base) |

The `:8090` tsunami proxy (`tsunami/serve_transformers.py`) fans requests
out to these three and stays outside this directory because it also
hosts the undertow + daemon logic.

## Supporting modules

| File | Purpose |
|------|---------|
| `mtp_module.py` | Multi-token-prediction head for Qwen3.6-35B-A3B. **Not yet in prod** — current 9% greedy / 22-37% sample accept combined with the single-layer MoE/LM-head overhead (~25 ms per draft call) makes MTP net-slower than plain `model.generate` (15.6 vs 23.1 tok/s at 9% accept). Kept under `tests/test_mtp_generate.py` as a research target until accept-rate clears ~40% breakeven or per-draft latency drops by 3-5×. |
| `vendor/deepseek_fp8_kernel.py` | DeepSeek reference Triton FP8 GEMM, replaces the `kernels-community/finegrained-fp8` build which asserts on Qwen3.6's block-128 + `moe_intermediate_size=512` shape. |

## Tools

| File | Purpose |
|------|---------|
| `convert_qwen36moe_fp8_to_packed.py` | One-shot: fuse per-expert gate_proj/up_proj/down_proj into the packed `gate_up_proj` / `down_proj` that transformers v5's qwen3_5_moe modeling expects. Writes a safetensors cache in `~/.cache/sigma_fuse/`. |
| `smoke_qwen36_fp8.py` | Health + single `/v1/chat/completions` round-trip against `:8095`. |
| `launch_qwen36_fp8.sh` | Foreground launcher for the server (alternative to `tsu up`). |
| `profile_decode.py` | `torch.profiler` over a warm 32-token decode step — breaks down where the ms go. |
| `host_bench_qwen36.py` | CPU-side latency bench (request → first token). |

## Tests

`tests/test_mtp_generate.py` — end-to-end MTP draft + verify with plain-generate
baseline. Primary accept-rate measurement.

`tests/test_mtp_diagnose.py` — surgical per-position diagnostic. Loads main
+ MTP, prints top-5 distributions for both at each position, entropy, cache
internals, and weight sanity. Use when chasing new MTP alignment hypotheses.

## Session history

See top-level commits `b8aa201`, `e9cd225`, `3c1dfff`, `a5a13ec`, `834cfa4`
for the evolution: static-cache patches, lazy mmap fuse, pinned-thread
warmup, MTP bug fixes (three root causes), stochastic acceptance, stack
consolidation onto this directory.
