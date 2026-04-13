#!/usr/bin/env python3
"""Serve Tsunami model via transformers — text + vision + image generation.

Usage:
  python3 serve_transformers.py --model google/gemma-4-e4b-it --port 8090
  python3 serve_transformers.py --model google/gemma-4-e4b-it --image-model black-forest-labs/FLUX.2-klein-4B --port 8090

Provides OpenAI-compatible endpoints:
  POST /v1/chat/completions    — text + vision (language model)
  POST /v1/images/generate     — image generation (FLUX Klein)
  POST /v1/adapter             — hot-swap LoRA adapters
  GET  /health                 — health check
"""
# Earliest-possible bind probe — must happen BEFORE torch/transformers imports
# (those take ~6s of CPU on first run, during which a duplicate would appear
# alive to outside observers). Fail in <1s if the port is taken.
import sys as _sys
if not any(_a in ("-h", "--help") for _a in _sys.argv):
    import socket as _socket
    _port, _host = 8090, "0.0.0.0"
    for _i, _a in enumerate(_sys.argv):
        if _a == "--port" and _i + 1 < len(_sys.argv):
            try: _port = int(_sys.argv[_i + 1])
            except ValueError: pass
        elif _a.startswith("--port="):
            try: _port = int(_a.split("=", 1)[1])
            except ValueError: pass
        elif _a == "--host" and _i + 1 < len(_sys.argv):
            _host = _sys.argv[_i + 1]
        elif _a.startswith("--host="):
            _host = _a.split("=", 1)[1]
    _probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    # SO_REUSEADDR lets us bind even when the previous server left the port
    # in TIME_WAIT (common after kill-and-restart cycles). Without this, you
    # get "[Errno 98] Address already in use" for up to 60s after a kill.
    _probe.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    try:
        _probe.bind((_host, _port))
    except OSError as _e:
        print(f"Port {_port} unavailable ({_e}). Aborting before model load.", file=_sys.stderr)
        _sys.exit(1)
    finally:
        _probe.close()

import argparse
import asyncio
import base64
import io
import json
import logging
import time
import uuid
from pathlib import Path

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoProcessor, AutoModelForImageTextToText
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("serve")

app = FastAPI()
model = None
processor = None
image_pipe = None
image_model_id = None
_low_vram = False  # if True, swap language/image models to save memory

class ChatRequest(BaseModel):
    model: str = "tsunami"
    messages: list
    tools: list = []
    tool_choice: str = "auto"
    max_tokens: int = 2048
    temperature: float = 0.3
    top_p: float = 0.95
    top_k: int = 64
    user: str = ""  # OpenAI API convention — used for per-client fairness queueing
    adapter: str | None = None  # per-request LoRA adapter selection (None = leave current; "none" = base)


# Fairness layer. QA-2 documented the pathology: one chatty client fires 5
# requests, a sparse client waits behind all 5 (FCFS starvation). The 9d46f4f
# async-unwedge kept /health responsive but didn't add fairness.
#
# Two-tier gate:
#   - _user_sems[user] (capacity 1): a single user can have at most one request
#     in-flight at a time. A 2nd request from the same user waits here, NOT in
#     the GPU queue — so other users keep interleaving.
#   - _gpu_sem (capacity 1): only one model.generate / pipe() runs on the GPU
#     at a time. Prevents OOM / throughput collapse from concurrent CUDA
#     contexts. asyncio.Semaphore releases waiters FIFO, which becomes a fair
#     round-robin across users once they're past their own gate.
_user_sems: dict[str, asyncio.Semaphore] = {}
_gpu_sem = asyncio.Semaphore(1)

# Current LoRA adapter (global model state). Piggybacks on _gpu_sem for
# serialization — every swap happens inside the same async-with that serializes
# generate, so we never swap while another request is mid-generation. Updated
# by both the /v1/adapter endpoint and the per-request ChatRequest.adapter
# field (QA feature request — lets each QA instance pick its adapter without
# instance-side coordination).
_current_adapter: str | None = None

from tsunami.adapter_swap import apply_adapter_swap as _apply_adapter_swap


def _apply_adapter_swap_locked(name: str) -> str:
    """Swap the global adapter. Caller MUST hold _gpu_sem (or equivalent
    single-writer guarantee) to avoid mid-generation state churn.

    Thin wrapper around `tsunami.adapter_swap.apply_adapter_swap` that threads
    the module-level `model` and `_current_adapter` globals. Never raises.
    """
    global _current_adapter
    status, _current_adapter = _apply_adapter_swap(model, name, _current_adapter)
    return status


def _get_user_sem(user: str) -> asyncio.Semaphore:
    sem = _user_sems.get(user)
    if sem is None:
        sem = asyncio.Semaphore(1)
        _user_sems[user] = sem
    return sem

@app.get("/health")
def health():
    return {"status": "ok"}

class AdapterRequest(BaseModel):
    name: str  # adapter name or "none" to disable

@app.post("/v1/adapter")
async def swap_adapter(req: AdapterRequest):
    """Hot-swap LoRA adapter. 'none' disables all adapters (chat mode).

    Goes through the same gpu_sem path as per-request swaps (ChatRequest.adapter)
    so manual and per-request swaps never race mid-generate. Both code paths
    update `_current_adapter` via `_apply_adapter_swap_locked`.
    """
    async with _gpu_sem:
        status = _apply_adapter_swap_locked(req.name)
    if status == "unsupported":
        return {"status": "error", "message": "model does not support adapters"}
    if status.startswith("error:"):
        return {"status": "error", "message": status[6:]}
    return {"status": "ok", "adapter": req.name, "note": status}

@app.post("/v1/adapter/enable")
async def enable_adapter():
    """Re-enable adapter layers after disable."""
    if hasattr(model, 'enable_adapter_layers'):
        model.enable_adapter_layers()
        return {"status": "ok", "mode": "adapter"}
    return {"status": "error", "message": "no adapter support"}

import re

# Parser pulled into tsunami/gemma_args.py so tests can import without the
# bind-probe / torch import chain. Module-level aliases kept for any existing
# references in this file or downstream.
from tsunami.gemma_args import (
    parse_gemma_args as _parse_gemma_args,
    _read_string,
    _read_array,
    _read_object,
)


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    # Fairness gate first — a user waiting on their own prior request doesn't
    # enter the GPU queue and can't crowd out other users. See _user_sems.
    _user_sem = _get_user_sem(req.user or "default")
    async with _user_sem:
        return await _chat_completions_impl(req)


from tsunami.chat_template_safety import escape_role_tokens as _escape_role_tokens


async def _chat_completions_impl(req: ChatRequest):
    start = time.time()
    # Tag log lines with the OpenAI `user` field so concurrent QA builds
    # can be disambiguated in tsunami_8090.log (QA-2 iter 17 observation).
    _utag = f"[user={req.user or 'default'}] "

    # Normalize messages — preserve tool_calls/tool roles for multi-turn,
    # convert image_url to PIL for multimodal
    messages = []
    images = []
    for msg in req.messages:
        role = msg.get("role", "user")

        # Tool response messages — pass through with tool_call_id, wrap content
        if role == "tool":
            content_text = _escape_role_tokens(msg.get("content", "") or "")
            out = {"role": "tool", "content": [{"type": "text", "text": content_text}]}
            if "tool_call_id" in msg:
                out["tool_call_id"] = msg["tool_call_id"]
            if "name" in msg:
                out["name"] = msg["name"]
            messages.append(out)
            continue

        # Assistant messages with tool_calls — preserve them, wrap content as list
        if role == "assistant" and "tool_calls" in msg:
            content_text = msg.get("content", "") or ""
            out = {"role": "assistant", "content": [{"type": "text", "text": content_text}], "tool_calls": msg["tool_calls"]}
            messages.append(out)
            continue

        # Regular messages — normalize content for multimodal. For user role,
        # escape Gemma role tokens to block chat-template injection (Fire 38).
        content = msg.get("content", "")
        if role == "user" and isinstance(content, str):
            content = _escape_role_tokens(content)
        if isinstance(content, str):
            messages.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        b64 = url.split(",", 1)[1]
                        from PIL import Image
                        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                        images.append(img)
                        parts.append({"type": "image", "image": img})
                else:
                    # Escape role tokens in text parts of user content (Fire 38)
                    if role == "user" and part.get("type") == "text" and isinstance(part.get("text"), str):
                        part = {**part, "text": _escape_role_tokens(part["text"])}
                    parts.append(part)
            messages.append({"role": role, "content": parts})
        else:
            messages.append(msg)

    # Apply chat template
    inputs = processor.apply_chat_template(
        messages,
        tools=req.tools if req.tools else None,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    # Bug #5 fix: Gemma4 template skips <|turn>model\n after tool_response
    # because tool responses are embedded in the model turn. But we need the
    # model to CONTINUE generating after seeing the tool result. Detect this
    # case and append the model turn tokens manually.
    input_ids = inputs["input_ids"]
    # Decode last ~20 tokens to check if we're missing the generation prompt
    tail = processor.decode(input_ids[0, -20:], skip_special_tokens=False)
    if '<tool_response|>' in tail and '<|turn>model' not in tail.split('<tool_response|>')[-1]:
        # Append <|turn>model\n tokens
        model_turn_tokens = processor.tokenizer.encode("<|turn>model\n", add_special_tokens=False)
        import torch as _torch
        model_turn_ids = _torch.tensor([model_turn_tokens], device=input_ids.device)
        inputs["input_ids"] = _torch.cat([input_ids, model_turn_ids], dim=1)
        if "attention_mask" in inputs:
            extra_mask = _torch.ones(1, len(model_turn_tokens), device=input_ids.device, dtype=inputs["attention_mask"].dtype)
            inputs["attention_mask"] = _torch.cat([inputs["attention_mask"], extra_mask], dim=1)

    prompt_len = inputs["input_ids"].shape[1]

    # Generate. Wrap in asyncio.to_thread so the event loop stays free to dispatch
    # other requests (notably /health) — otherwise long generations make the whole
    # server look wedged from outside, which is QA-3's "backend wedges, all endpoints
    # timeout" HIGH bug.  _gpu_sem serializes GPU access across users so
    # concurrent-forward-pass CUDA contention can't starve throughput.
    def _generate():
        with torch.no_grad():
            return model.generate(
                **inputs,
                max_new_tokens=req.max_tokens,
                use_cache=True,
                temperature=req.temperature if req.temperature > 0 else 1.0,
                top_p=req.top_p,
                top_k=req.top_k,
                do_sample=req.temperature > 0,
            )
    async with _gpu_sem:
        # Per-request adapter selection — swap BEFORE generate, inside the
        # gpu_sem that already serializes model access. Back-to-back requests
        # with same adapter short-circuit via the `== _current_adapter` check
        # in _apply_adapter_swap_locked; alternating adapters cost one swap
        # per transition (adapters already in VRAM once --adapters-dir
        # preloaded them).
        if req.adapter:
            swap_status = _apply_adapter_swap_locked(req.adapter)
            if swap_status not in ("no-change", "unsupported"):
                log.info(f"{_utag}adapter: {swap_status}")
        output = await asyncio.to_thread(_generate)

    # Decode response
    new_tokens = output[0][prompt_len:]
    text = processor.decode(new_tokens, skip_special_tokens=False)

    # Parse tool calls from native format
    log.info(f"{_utag}RAW OUTPUT: {text!r}")

    # Strip Gemma 31B "thought channel" prefix (appears before tool calls in multi-turn)
    text = re.sub(r'<\|channel>thought\n<channel\|>', '', text)

    tool_calls = None
    content = text

    # Find tool calls: <|tool_call>call:NAME{ARGS}(<tool_call|>|<|tool_response>)
    # The previous regex `\{.+?\}` was non-greedy and terminated at the FIRST `}` —
    # but `{` and `}` appear inside JSX strings (e.g. `{prevTime - 100}`), so any
    # file_edit / file_write call carrying TSX code was silently dropped.
    # Use a brace-counter that respects Gemma `<|"|>...<|"|>` and JSON `"..."` strings.
    tc_matches = []
    _scan = 0
    while True:
        _m = re.search(r'<\|tool_call>call:(\w+)\s*', text[_scan:])
        if not _m:
            break
        _name = _m.group(1)
        _arg_start = _scan + _m.end()
        if _arg_start >= len(text) or text[_arg_start] != '{':
            _scan = _arg_start
            continue
        # Walk braces, skipping over string contents
        _depth = 0
        _i = _arg_start
        _ok = False
        while _i < len(text):
            if text[_i:_i+5] == '<|"|>':  # Gemma string open
                _i += 5
                while _i < len(text) and text[_i:_i+5] != '<|"|>':
                    _i += 1
                if _i + 5 > len(text):
                    break
                _i += 5
                continue
            _c = text[_i]
            if _c == '"':  # JSON string
                _i += 1
                while _i < len(text) and text[_i] != '"':
                    if text[_i] == '\\' and _i + 1 < len(text):
                        _i += 2
                    else:
                        _i += 1
                _i += 1
                continue
            if _c == '{':
                _depth += 1
            elif _c == '}':
                _depth -= 1
                if _depth == 0:
                    _arg_end = _i + 1
                    _ok = True
                    break
            _i += 1
        if not _ok:
            _scan = _arg_start + 1
            continue
        # Accept either canonical close or the model's <|tool_response> drift
        _rest = text[_arg_end:_arg_end + 20]
        if _rest.startswith('<tool_call|>'):
            _term_len = 12
        elif _rest.startswith('<|tool_response>') or _rest.startswith('<|tool_response|>'):
            _term_len = 0  # don't consume — let the response block parse separately
            log.warning(f"{_utag}Tool call {_name} closed with <|tool_response> (drift); accepting")
        else:
            _scan = _arg_end
            continue
        tc_matches.append((_name, text[_arg_start:_arg_end]))
        _scan = _arg_end + _term_len

    if tc_matches:
        tool_calls = []
        for name, args_raw in tc_matches:
            # Strip double-brace wrapper: {{"k":"v"}} -> {"k":"v"}
            if args_raw.startswith('{{') and args_raw.endswith('}}'):
                inner = args_raw[1:-1]
            else:
                inner = args_raw

            # Try JSON parse first (model often uses standard JSON)
            try:
                args = json.loads(inner)
            except (json.JSONDecodeError, ValueError):
                # Fall back to Gemma native format parser
                args = _parse_gemma_args(inner.strip('{}'))

            tool_calls.append({
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
                "id": uuid.uuid4().hex[:16],
            })
        content = ""

    # Fallback: Python-call style (`name(arg=val, arg="...")`) — v90 drops to this
    # pretraining-prior on short prompts (chat turns) where SFT coverage was thin.
    # Catches it before the agent loops on empty tool_calls. The 11-tool registry
    # is the canonical whitelist — don't fabricate unknown tool names.
    if not tc_matches:
        _known = {"project_init", "file_write", "file_read", "file_edit", "shell_exec",
                  "search_web", "undertow", "riptide", "generate_image",
                  "message_result", "message_chat"}
        _fallback = re.search(r'\b(' + '|'.join(_known) + r')\(([^)]*)\)', text)
        if _fallback:
            _name = _fallback.group(1)
            _body = _fallback.group(2)
            # Parse k=v pairs — tolerate quoted strings with commas inside
            args = {}
            for _kv in re.finditer(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,)]+)', _body):
                _k = _kv.group(1)
                _v = _kv.group(2).strip()
                if (_v.startswith('"') and _v.endswith('"')) or (_v.startswith("'") and _v.endswith("'")):
                    _v = _v[1:-1]
                elif _v.lower() == "true":
                    _v = True
                elif _v.lower() == "false":
                    _v = False
                args[_k] = _v
            log.warning(f"{_utag}Python-call fallback matched {_name}({list(args.keys())})")
            tool_calls = [{
                "type": "function",
                "function": {"name": _name, "arguments": json.dumps(args)},
                "id": uuid.uuid4().hex[:16],
            }]
            content = ""

    # Clean up content
    content = re.sub(r'<\|.*?\|>', '', content).strip()
    if content.endswith("<turn|>"):
        content = content[:-7].strip()

    elapsed = time.time() - start
    completion_tokens = len(new_tokens)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            },
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_len,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_len + completion_tokens,
        },
    }


class ImageRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    steps: int = 4
    guidance_scale: float = 1.0
    user: str = ""  # per-client fairness — see _user_sems comment


def _load_image_model():
    """Load FLUX Klein on first use. On low-VRAM, offload language model first."""
    global image_pipe, model
    if image_pipe is not None:
        return image_pipe

    if not image_model_id:
        return None

    if _low_vram and model is not None:
        log.info("Low VRAM: offloading language model to CPU for image generation")
        model.to("cpu")
        torch.cuda.empty_cache()

    log.info(f"Loading image model: {image_model_id}")
    try:
        from diffusers import FluxPipeline
        image_pipe = FluxPipeline.from_pretrained(
            image_model_id,
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
        )
        image_pipe.to("cuda")
        log.info("Image model loaded")
    except Exception as e:
        log.error(f"Failed to load image model: {e}")
        # Try FP8 quantized fallback
        try:
            image_pipe = FluxPipeline.from_pretrained(
                image_model_id,
                torch_dtype=torch.float8_e4m3fn,
                trust_remote_code=True,
            )
            image_pipe.to("cuda")
            log.info("Image model loaded (FP8 fallback)")
        except Exception as e2:
            log.error(f"FP8 fallback also failed: {e2}")
            return None
    return image_pipe


def _restore_language_model():
    """After image generation on low-VRAM, move language model back to GPU."""
    global image_pipe, model
    if _low_vram and model is not None:
        log.info("Low VRAM: offloading image model, restoring language model to GPU")
        if image_pipe is not None:
            image_pipe.to("cpu")
            torch.cuda.empty_cache()
        model.to("cuda:0")


@app.post("/v1/images/generate")
async def generate_image(req: ImageRequest):
    # Same fairness gate as chat_completions — per-user then global GPU.
    _user_sem = _get_user_sem(req.user or "default")
    async with _user_sem, _gpu_sem:
        return await _generate_image_impl(req)


async def _generate_image_impl(req: ImageRequest):
    # Tag log lines with the OpenAI `user` field — matches chat_completions.
    _utag = f"[user={req.user or 'default'}] "
    # Run the whole generation off the event loop so /health stays responsive
    # while image generation is in progress. Same wedge fix as chat_completions.
    def _do_image_gen():
        pipe = _load_image_model()
        if pipe is None:
            return {"error": "No image model configured. Start with --image-model"}
        start = time.time()
        try:
            result = pipe(
                prompt=req.prompt,
                width=req.width,
                height=req.height,
                num_inference_steps=req.steps,
                guidance_scale=req.guidance_scale,
            )
            image = result.images[0]
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            elapsed = time.time() - start
            log.info(f"{_utag}Image generated in {elapsed:.1f}s ({req.width}x{req.height}, {req.steps} steps)")
            _restore_language_model()
            return {
                "created": int(time.time()),
                "data": [{"b64_json": b64, "revised_prompt": req.prompt}],
                "timing": {"elapsed_s": round(elapsed, 2)},
            }
        except Exception as e:
            _restore_language_model()
            return {"error": str(e)}
    return await asyncio.to_thread(_do_image_gen)


def main():
    global model, processor, image_model_id, _low_vram

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="google/gemma-4-e4b-it", help="Base model (HF name or path)")
    parser.add_argument("--adapter", default=None, help="LoRA adapter path (load on top of base)")
    parser.add_argument("--adapters-dir", default=None, help="Directory of adapters to preload (each subdir with adapter_config.json)")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--load-in-8bit", action="store_true", help="8-bit quantization via bitsandbytes")
    parser.add_argument("--load-in-4bit", action="store_true", help="4-bit quantization via bitsandbytes")
    parser.add_argument("--image-model", default="Tongyi-MAI/Z-Image-Turbo",
                        help="Image generation model. Options: "
                             "Tongyi-MAI/Z-Image-Turbo (default, best text rendering), "
                             "black-forest-labs/FLUX.2-klein-4B (faster, smaller). "
                             "Set to 'none' to disable image generation.")
    parser.add_argument("--low-vram", action="store_true", help="Swap language/image models to save VRAM (for <16GB GPUs)")
    args = parser.parse_args()

    image_model_id = args.image_model if args.image_model != "none" else None
    _low_vram = args.low_vram

    import os

    # (Bind probe ran at module top — before torch/transformers imports — so
    # duplicate spawns die in <1s, not 6s of import-time CPU.)

    # Auto-detect device: CUDA > MPS > CPU
    if torch.cuda.is_available():
        device_map = "cuda:0"
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        try:
            torch.cuda.set_per_process_memory_fraction(0.95)
        except Exception:
            pass
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device_map = "mps"
    else:
        device_map = "cpu"

    log.info(f"Loading {args.model} on {device_map}...")
    load_kwargs = dict(
        torch_dtype=torch.bfloat16 if device_map != "cpu" else torch.float32,
        device_map=device_map,
        trust_remote_code=True,
    )
    if args.load_in_8bit:
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        del load_kwargs["torch_dtype"]  # quantization handles dtype
        log.info("Loading in 8-bit quantization")
    elif args.load_in_4bit:
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16
        )
        del load_kwargs["torch_dtype"]
        log.info("Loading in 4-bit quantization")
    processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(args.model, **load_kwargs)
    log.info(f"Base model loaded on {model.device}")

    # Load LoRA adapter(s)
    if args.adapter or args.adapters_dir:
        from peft import PeftModel

        if args.adapter:
            # Single adapter from --adapter — name from directory
            adapter_name = Path(args.adapter).name
            model = PeftModel.from_pretrained(model, args.adapter, adapter_name=adapter_name)
            log.info(f"Adapter loaded: {args.adapter} (name='{adapter_name}')")

        if args.adapters_dir:
            # Load all adapters from subdirectories
            adapters_path = Path(args.adapters_dir)
            loaded = []
            for d in sorted(adapters_path.iterdir()):
                if d.is_dir() and (d / "adapter_config.json").exists():
                    name = d.name
                    if name == "default" or (args.adapter and str(d) == args.adapter):
                        continue  # skip if already loaded
                    try:
                        if not hasattr(model, 'load_adapter'):
                            # First adapter — wrap with PeftModel
                            model = PeftModel.from_pretrained(model, str(d), adapter_name=name)
                        else:
                            model.load_adapter(str(d), adapter_name=name)
                        loaded.append(name)
                    except Exception as e:
                        log.warning(f"Failed to load adapter {name}: {e}")
            if loaded:
                log.info(f"Adapters loaded from {args.adapters_dir}: {loaded}")

            # Set the --adapter as active if provided
            if args.adapter and hasattr(model, 'set_adapter'):
                model.set_adapter(Path(args.adapter).name)
            elif loaded and hasattr(model, 'set_adapter'):
                model.set_adapter(loaded[0])

    # List available adapters
    if hasattr(model, 'peft_config'):
        log.info(f"Available adapters: {list(model.peft_config.keys())}")
        log.info("Swap via POST /v1/adapter {{\"name\": \"<adapter_name>\"}} or 'none' for base chat")

    log.info(f"Starting server on port {args.port}...")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
