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
import argparse
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

@app.get("/health")
def health():
    return {"status": "ok"}

class AdapterRequest(BaseModel):
    name: str  # adapter name or "none" to disable

@app.post("/v1/adapter")
async def swap_adapter(req: AdapterRequest):
    """Hot-swap LoRA adapter. 'none' disables all adapters (chat mode)."""
    try:
        if req.name == "none":
            if hasattr(model, 'disable_adapter_layers'):
                model.disable_adapter_layers()
                return {"status": "ok", "adapter": "none", "mode": "chat"}
            return {"status": "ok", "adapter": "none", "note": "no adapter was loaded"}
        elif hasattr(model, 'set_adapter'):
            model.set_adapter(req.name)
            return {"status": "ok", "adapter": req.name}
        elif hasattr(model, 'load_adapter'):
            model.load_adapter(req.name, adapter_name=req.name)
            model.set_adapter(req.name)
            return {"status": "ok", "adapter": req.name, "loaded_from_disk": True}
        else:
            return {"status": "error", "message": "model does not support adapters"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/v1/adapter/enable")
async def enable_adapter():
    """Re-enable adapter layers after disable."""
    if hasattr(model, 'enable_adapter_layers'):
        model.enable_adapter_layers()
        return {"status": "ok", "mode": "adapter"}
    return {"status": "error", "message": "no adapter support"}

import re

def _parse_gemma_args(args_str: str) -> dict:
    """Parse tool call arguments — handles both Gemma native AND JSON formats.

    Gemma native:  key:<|"|>value<|"|>, key:true, key:[<|"|>a<|"|>]
    JSON:          {"key": "value", "key2": true}

    The model sometimes outputs JSON args inside native tool_call tags,
    so we detect and handle both formats.
    """
    # Try JSON first — if it starts with { and is valid JSON, use that
    stripped = args_str.strip()
    if stripped.startswith('{'):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
    # Also try if the whole string is JSON without braces (unlikely but safe)
    if stripped.startswith('"') and ':' not in stripped[:20].replace('":"', ''):
        try:
            return json.loads('{' + stripped + '}')
        except (json.JSONDecodeError, ValueError):
            pass

    # Fall through to Gemma native parser
    args = {}
    i = 0
    n = len(args_str)

    while i < n:
        # Skip commas and whitespace between key:value pairs
        while i < n and args_str[i] in (',', ' ', '\n'):
            i += 1
        if i >= n:
            break

        # Read key (word characters)
        key_start = i
        while i < n and (args_str[i].isalnum() or args_str[i] == '_'):
            i += 1
        key = args_str[key_start:i]
        if not key:
            i += 1  # skip unrecognized char
            continue

        # Expect colon
        if i < n and args_str[i] == ':':
            i += 1
        else:
            continue

        # Parse value based on what follows
        if args_str[i:i+5] == '<|"|>':
            # String value
            val, i = _read_string(args_str, i)
            args[key] = val
        elif args_str[i] == '[':
            # Array value
            val, i = _read_array(args_str, i)
            args[key] = val
        elif args_str[i] == '{':
            # Nested object — read until matching }
            val, i = _read_object(args_str, i)
            args[key] = val
        elif args_str[i:i+4] == 'true':
            args[key] = True
            i += 4
        elif args_str[i:i+5] == 'false':
            args[key] = False
            i += 5
        elif args_str[i:i+4] == 'null':
            args[key] = None
            i += 4
        else:
            # Number or unknown — read until comma or end
            val_start = i
            while i < n and args_str[i] not in (',', '}', ']'):
                i += 1
            val_str = args_str[val_start:i].strip()
            try:
                args[key] = int(val_str)
            except ValueError:
                try:
                    args[key] = float(val_str)
                except ValueError:
                    args[key] = val_str  # keep as string

    return args


def _read_string(s: str, i: int) -> tuple:
    """Read a <|"|>...<|"|> quoted string starting at position i."""
    assert s[i:i+5] == '<|"|>', f"Expected <|\"|> at {i}, got {s[i:i+10]}"
    i += 5  # skip opening <|"|>
    start = i
    while i < len(s):
        if s[i:i+5] == '<|"|>':
            val = s[start:i]
            return val, i + 5  # skip closing <|"|>
        i += 1
    return s[start:], i  # unclosed string


def _read_array(s: str, i: int) -> tuple:
    """Read a [...] array starting at position i."""
    assert s[i] == '['
    i += 1  # skip [
    items = []
    while i < len(s):
        # Skip whitespace and commas
        while i < len(s) and s[i] in (',', ' ', '\n'):
            i += 1
        if i >= len(s) or s[i] == ']':
            i += 1  # skip ]
            return items, i
        # Read item
        if s[i:i+5] == '<|"|>':
            val, i = _read_string(s, i)
            items.append(val)
        elif s[i] == '{':
            val, i = _read_object(s, i)
            items.append(val)
        elif s[i] == '[':
            val, i = _read_array(s, i)
            items.append(val)
        elif s[i:i+4] == 'true':
            items.append(True); i += 4
        elif s[i:i+5] == 'false':
            items.append(False); i += 5
        else:
            # Number
            start = i
            while i < len(s) and s[i] not in (',', ']', '}'):
                i += 1
            val_str = s[start:i].strip()
            try:
                items.append(int(val_str))
            except ValueError:
                try:
                    items.append(float(val_str))
                except ValueError:
                    items.append(val_str)
    return items, i


def _read_object(s: str, i: int) -> tuple:
    """Read a {...} object starting at position i."""
    assert s[i] == '{'
    # Find matching closing brace (handle nesting)
    depth = 1
    start = i
    i += 1
    while i < len(s) and depth > 0:
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
        i += 1
    inner = s[start+1:i-1]
    return _parse_gemma_args(inner), i


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    start = time.time()

    # Normalize messages — preserve tool_calls/tool roles for multi-turn,
    # convert image_url to PIL for multimodal
    messages = []
    images = []
    for msg in req.messages:
        role = msg.get("role", "user")

        # Tool response messages — pass through with tool_call_id, wrap content
        if role == "tool":
            content_text = msg.get("content", "") or ""
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

        # Regular messages — normalize content for multimodal
        content = msg.get("content", "")
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

    # Generate
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=req.max_tokens,
            use_cache=True,
            temperature=req.temperature if req.temperature > 0 else 1.0,
            top_p=req.top_p,
            top_k=req.top_k,
            do_sample=req.temperature > 0,
        )

    # Decode response
    new_tokens = output[0][prompt_len:]
    text = processor.decode(new_tokens, skip_special_tokens=False)

    # Parse tool calls from native format
    log.info(f"RAW OUTPUT: {text!r}")

    # Strip Gemma 31B "thought channel" prefix (appears before tool calls in multi-turn)
    text = re.sub(r'<\|channel>thought\n<channel\|>', '', text)

    tool_calls = None
    content = text

    # Check for tool call tokens: <|tool_call>call:name{args}<tool_call|>
    # Model may use JSON double-brace {{...}} OR Gemma native {key:<|"|>val<|"|>}
    tc_matches = re.findall(
        r'<\|tool_call>call:(\w+)(\{\{.+?\}\}|\{.+?\})<tool_call\|>', text, re.DOTALL
    )
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

        # Convert to base64 PNG
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        elapsed = time.time() - start
        log.info(f"Image generated in {elapsed:.1f}s ({req.width}x{req.height}, {req.steps} steps)")

        # Restore language model if needed
        _restore_language_model()

        return {
            "created": int(time.time()),
            "data": [{
                "b64_json": b64,
                "revised_prompt": req.prompt,
            }],
            "timing": {"elapsed_s": round(elapsed, 2)},
        }
    except Exception as e:
        _restore_language_model()
        return {"error": str(e)}


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
    parser.add_argument("--image-model", default=None, help="Image generation model (e.g. black-forest-labs/FLUX.2-klein-4B)")
    parser.add_argument("--low-vram", action="store_true", help="Swap language/image models to save VRAM (for <16GB GPUs)")
    args = parser.parse_args()

    image_model_id = args.image_model
    _low_vram = args.low_vram

    import os

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
