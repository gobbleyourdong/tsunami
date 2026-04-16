# Vendored from city96/ComfyUI-GGUF (Apache-2.0) — pure math, no comfy deps
from .ops import GGMLTensor, GGMLLinear, dequantize_tensor, replace_linear_with_ggml
from .loader import (
    load_gguf,
    load_qwen3_gguf,
    load_gemma_gguf,
    load_lumina2_gguf,
    load_ernie_image_gguf,
    load_mistral3_lang_gguf,
    describe_gguf,
)
