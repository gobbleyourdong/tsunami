#!/usr/bin/env python3
"""
TSUNAMI — Image Generation Server
Serves Qwen-Image-2512 via diffusers on GPU.

Run inside NVIDIA Docker:
    docker run --gpus all -d --ipc=host \
      -v /home/jb/ComfyUI/CelebV-HQ/ark:/ark \
      -p 8091:8091 \
      --name tsunami-diffusion \
      nvcr.io/nvidia/pytorch:25.11-py3 \
      bash -c "pip install -q diffusers transformers accelerate && python3 /ark/serve_diffusion.py"
"""

import argparse
import io
import json
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

pipe = None


def load_model(model_dir=None, gguf_path=None):
    global pipe
    import torch
    from pathlib import Path

    _default_models = Path(__file__).parent / "models"
    if model_dir is None:
        model_dir = str(_default_models / "Qwen-Image-2512")
    if gguf_path is None:
        gguf_path = str(_default_models / "qwen-image-2512-Q4_K_M.gguf")

    dtype = torch.bfloat16

    if Path(gguf_path).exists() and Path(model_dir).exists():
        from diffusers import QwenImagePipeline, QwenImageTransformer2DModel, GGUFQuantizationConfig
        print(f"Loading transformer from GGUF: {gguf_path}")
        transformer = QwenImageTransformer2DModel.from_single_file(
            gguf_path,
            quantization_config=GGUFQuantizationConfig(compute_dtype=dtype),
            torch_dtype=dtype,
            config=model_dir,
            subfolder="transformer",
        )
        print(f"Loading pipeline from local: {model_dir}")
        pipe = QwenImagePipeline.from_pretrained(
            model_dir, transformer=transformer, torch_dtype=dtype,
        )
    else:
        from diffusers import DiffusionPipeline
        print(f"Local models not found, loading from HF...")
        pipe = DiffusionPipeline.from_pretrained("Qwen/Qwen-Image-2512", torch_dtype=dtype)

    pipe.to("cuda")
    print("Model loaded on GPU.")


def generate(prompt, negative_prompt="", width=1024, height=1024, steps=30, cfg=4.0, seed=-1):
    import torch

    if seed < 0:
        seed = int(time.time()) % 2**32

    image = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt or None,
        width=width,
        height=height,
        num_inference_steps=steps,
        true_cfg_scale=cfg,
        generator=torch.Generator(device="cuda").manual_seed(seed),
    ).images[0]

    return image


ASPECT_RATIOS = {
    "1:1": (1328, 1328),
    "16:9": (1664, 928),
    "9:16": (928, 1664),
    "4:3": (1472, 1104),
    "3:4": (1104, 1472),
    "3:2": (1584, 1056),
    "2:3": (1056, 1584),
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/generate":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            prompt = body.get("prompt", "")
            negative = body.get("negative_prompt", "")
            aspect = body.get("aspect_ratio", "1:1")
            steps = body.get("steps", 30)
            cfg = body.get("cfg", 4.0)
            seed = body.get("seed", -1)
            save_path = body.get("save_path", "")

            w, h = ASPECT_RATIOS.get(aspect, (1024, 1024))
            w = body.get("width", w)
            h = body.get("height", h)

            try:
                print(f"Generating: '{prompt[:60]}' ({w}x{h}, {steps} steps)")
                t0 = time.time()
                image = generate(prompt, negative, w, h, steps, cfg, seed)
                elapsed = time.time() - t0
                print(f"Done in {elapsed:.1f}s")

                # Save to disk if path provided
                if save_path:
                    p = Path(save_path)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    image.save(str(p))

                # Return as PNG bytes
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                png_bytes = buf.getvalue()

                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png_bytes)))
                self.send_header("X-Generation-Time", f"{elapsed:.1f}")
                self.end_headers()
                self.wfile.write(png_bytes)

            except Exception as e:
                self._json_response(500, {"error": str(e)})
        else:
            self._json_response(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {"status": "ok", "model_loaded": pipe is not None})
        else:
            self._json_response(404, {"error": "not found"})

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[diffusion] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="TSUNAMI Diffusion Server")
    parser.add_argument("--model-dir", default="/ark/models/Qwen-Image-2512")
    parser.add_argument("--gguf", default="/ark/models/qwen-image-2512-Q4_K_M.gguf")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    load_model(model_dir=args.model_dir, gguf_path=args.gguf)

    server = HTTPServer((args.host, args.port), Handler)
    print(f"Diffusion server on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
