"""
Model backend interfaces — swap generation backend without changing the pipeline.

Each backend implements generate_image(prompt, width, height, steps, seed) → PIL Image.
Add your API key and uncomment to use.

Usage:
  python sprite_pipeline.py --model gemini character "knight with sword"
  python sprite_pipeline.py --model fal-nano character "knight with sword"
"""

from PIL import Image


class ModelBackend:
    """Base interface for all generation backends."""
    name: str = "base"

    def generate(self, prompt: str, width: int = 512, height: int = 512,
                 steps: int = 4, seed: int = -1) -> Image.Image:
        raise NotImplementedError


class SDTurboBackend(ModelBackend):
    """Local SD Turbo via diffusers. Already implemented in sprite_pipeline.py."""
    name = "sd-turbo"
    _pipe = None

    def generate(self, prompt: str, width: int = 512, height: int = 512,
                 steps: int = 4, seed: int = -1) -> Image.Image:
        import torch
        from diffusers import AutoPipelineForText2Image

        if self._pipe is None:
            self._pipe = AutoPipelineForText2Image.from_pretrained(
                "stabilityai/sd-turbo", torch_dtype=torch.float16, variant="fp16"
            ).to("cuda")

        generator = torch.Generator(device="cuda").manual_seed(seed) if seed >= 0 else None
        return self._pipe(
            prompt=prompt, num_inference_steps=steps, guidance_scale=0.0,
            width=width, height=height, generator=generator,
        ).images[0]


class GeminiBackend(ModelBackend):
    """Google Gemini image generation via AI Studio API.
    Set GEMINI_API_KEY environment variable.
    """
    name = "gemini"

    def generate(self, prompt: str, width: int = 512, height: int = 512,
                 steps: int = 4, seed: int = -1) -> Image.Image:
        import os
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Set GEMINI_API_KEY environment variable")

        # TODO: Implement when API access available
        # import google.generativeai as genai
        # genai.configure(api_key=api_key)
        # model = genai.GenerativeModel("gemini-2.0-flash")
        # response = model.generate_content(prompt)
        # return Image.open(io.BytesIO(response.image.data))

        raise NotImplementedError("Gemini backend — add API key and uncomment implementation")


class FalBackend(ModelBackend):
    """fal.ai Nano Banana 2 via REST API.
    Set FAL_KEY environment variable.
    """
    name = "fal-nano"

    def generate(self, prompt: str, width: int = 512, height: int = 512,
                 steps: int = 4, seed: int = -1) -> Image.Image:
        import os
        api_key = os.environ.get("FAL_KEY")
        if not api_key:
            raise RuntimeError("Set FAL_KEY environment variable")

        # TODO: Implement when API access available
        # import requests, io
        # resp = requests.post(
        #     "https://fal.run/fal-ai/nano-banana-2",
        #     headers={"Authorization": f"Key {api_key}"},
        #     json={"prompt": prompt, "image_size": {"width": width, "height": height}},
        # )
        # img_url = resp.json()["images"][0]["url"]
        # return Image.open(io.BytesIO(requests.get(img_url).content))

        raise NotImplementedError("fal.ai backend — add API key and uncomment implementation")


class GPTImageBackend(ModelBackend):
    """OpenAI GPT Image 1.5 via API.
    Set OPENAI_API_KEY environment variable.
    """
    name = "gpt-image"

    def generate(self, prompt: str, width: int = 512, height: int = 512,
                 steps: int = 4, seed: int = -1) -> Image.Image:
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Set OPENAI_API_KEY environment variable")

        # TODO: Implement when API access available
        # import openai, io, base64
        # client = openai.OpenAI(api_key=api_key)
        # response = client.images.generate(
        #     model="gpt-image-1.5", prompt=prompt,
        #     size=f"{width}x{height}", response_format="b64_json",
        # )
        # img_data = base64.b64decode(response.data[0].b64_json)
        # return Image.open(io.BytesIO(img_data))

        raise NotImplementedError("GPT Image backend — add API key and uncomment implementation")


# Registry
BACKENDS = {
    "sd-turbo": SDTurboBackend,
    "gemini": GeminiBackend,
    "fal-nano": FalBackend,
    "gpt-image": GPTImageBackend,
}

def get_backend(name: str) -> ModelBackend:
    cls = BACKENDS.get(name)
    if not cls:
        raise ValueError(f"Unknown backend '{name}'. Available: {', '.join(BACKENDS.keys())}")
    return cls()
