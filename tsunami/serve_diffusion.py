#!/usr/bin/env python3
"""
TSUNAMI — SD-Turbo Image Generation Server

Lightweight image gen. No Docker. 2GB model. <1s per image.

    pip install diffusers torch transformers accelerate
    python serve_diffusion.py

That's it. Starts on :8091, generates 512x512 images from text prompts.
Uses stabilityai/sd-turbo (1 step, no cfg needed).
"""

import argparse
import io
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

pipe = None
MODEL_ID = "stabilityai/sd-turbo"


def load_model():
    global pipe
    import torch
    from diffusers import AutoPipelineForText2Image

    dtype = torch.float16
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        dtype = torch.float32
        print("WARNING: Running on CPU — generation will be slow (~30s)")

    print(f"Loading {MODEL_ID} on {device}...")
    pipe = AutoPipelineForText2Image.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        variant="fp16" if dtype == torch.float16 else None,
    )
    pipe.to(device)

    # Warmup
    print("Warmup generation...")
    pipe("test", num_inference_steps=1, guidance_scale=0.0)
    print(f"Ready on {device}. ~0.5s/image on GPU, ~30s on CPU.")


def generate(prompt, width=512, height=512, steps=1, seed=-1):
    import torch

    if seed < 0:
        seed = int(time.time()) % 2**32

    image = pipe(
        prompt=prompt,
        num_inference_steps=steps,
        guidance_scale=0.0,  # SD-Turbo doesn't use CFG
        width=width,
        height=height,
        generator=torch.Generator(device=pipe.device).manual_seed(seed),
    ).images[0]

    return image


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/generate":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))

            prompt = body.get("prompt", "")
            w = min(body.get("width", 512), 1024)
            h = min(body.get("height", 512), 1024)
            steps = body.get("steps", 1)
            seed = body.get("seed", -1)
            save_path = body.get("save_path", "")

            try:
                print(f"Generating: '{prompt[:60]}' ({w}x{h})")
                t0 = time.time()
                image = generate(prompt, w, h, steps, seed)
                elapsed = time.time() - t0
                print(f"Done in {elapsed:.1f}s")

                # Save to disk if path provided
                if save_path:
                    from pathlib import Path
                    p = Path(save_path)
                    p.parent.mkdir(parents=True, exist_ok=True)
                    image.save(str(p))

                # Return as PNG
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
            self._json_response(200, {"status": "ok", "model": MODEL_ID, "model_loaded": pipe is not None})
        else:
            self._json_response(404, {"error": "not found"})

    def _json_response(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        print(f"[sd-turbo] {args[0]}")


def main():
    parser = argparse.ArgumentParser(description="Tsunami SD-Turbo Server")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    load_model()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"SD-Turbo server on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
