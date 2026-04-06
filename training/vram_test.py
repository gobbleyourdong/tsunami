#!/usr/bin/env python3
"""VRAM leak test — 20 steps with memory logging every step.
Sorts examples by length (longest first) to hit peak VRAM on step 1.
"""
import json, logging, torch, gc
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("vram_test")

from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling
from transformers import TrainerCallback
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

BASE_MODEL = "models/gemma-4-e2b-it"
DATA_PATH = "workspace/training_data/e4b_toolcall_train_v2.jsonl"
MAX_LENGTH = 8192

INSTRUCTION_MARKER = "<|turn>user\n"
RESPONSE_MARKER = "<|turn>model\n"

def gpu_mb():
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1024 / 1024
    return 0

def gpu_reserved_mb():
    if torch.cuda.is_available():
        return torch.cuda.memory_reserved() / 1024 / 1024
    return 0

# ==========================================
# VRAM LOGGING CALLBACK
# ==========================================
class VRAMLogger(TrainerCallback):
    def on_step_end(self, args, state, control, **kwargs):
        alloc = gpu_mb()
        reserved = gpu_reserved_mb()
        log.info(f"STEP {state.global_step:3d} | allocated: {alloc:,.0f} MB | reserved: {reserved:,.0f} MB | delta: {reserved - alloc:,.0f} MB frag")

# ==========================================
# LOAD DATA — sort by length, longest first
# ==========================================
data = []
with open(DATA_PATH) as f:
    for line in f:
        data.append(json.loads(line))
data.sort(key=lambda x: -len(x["text"]))  # longest first = peak VRAM on step 1
log.info(f"Loaded {len(data)} examples, longest first: {len(data[0]['text']):,} chars")
log.info(f"Shortest: {len(data[-1]['text']):,} chars")

# ==========================================
# LOAD MODEL
# ==========================================
log.info(f"Pre-load GPU: {gpu_mb():,.0f} MB")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Unwrap ClippableLinear
for name, module in list(model.named_modules()):
    if type(module).__name__ == "Gemma4ClippableLinear" and hasattr(module, "linear"):
        parts = name.rsplit(".", 1)
        if len(parts) == 2:
            parent = dict(model.named_modules())[parts[0]]
            setattr(parent, parts[1], module.linear)

log.info(f"Post-load GPU: {gpu_mb():,.0f} MB")

model.gradient_checkpointing_enable()
lora_config = LoraConfig(
    r=32, lora_alpha=64,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
log.info(f"Post-LoRA GPU: {gpu_mb():,.0f} MB")

# ==========================================
# RESPONSE-ONLY COLLATOR
# ==========================================
_inst_ids = tokenizer.encode(INSTRUCTION_MARKER, add_special_tokens=False)
_resp_ids = tokenizer.encode(RESPONSE_MARKER, add_special_tokens=False)
IGNORE_INDEX = -100

class ResponseOnlyCollator(DataCollatorForLanguageModeling):
    def __call__(self, features, return_tensors=None):
        batch = super().__call__(features, return_tensors=return_tensors)
        for i in range(len(batch["labels"])):
            input_ids = batch["input_ids"][i]
            labels = batch["labels"][i].clone()
            masked = torch.full_like(labels, IGNORE_INDEX)

            input_list = input_ids.tolist()
            in_response = False
            j = 0
            while j < len(input_list):
                if input_list[j:j+len(_resp_ids)] == _resp_ids:
                    in_response = True
                    j += len(_resp_ids)
                    continue
                if input_list[j:j+len(_inst_ids)] == _inst_ids:
                    in_response = False
                    j += len(_inst_ids)
                    continue
                if in_response and labels[j] != IGNORE_INDEX:
                    masked[j] = labels[j]
                j += 1

            batch["labels"][i] = masked
        return batch

collator = ResponseOnlyCollator(tokenizer=tokenizer, mlm=False, pad_to_multiple_of=MAX_LENGTH)

# ==========================================
# DATASET + CONFIG — 20 steps only
# ==========================================
dataset = Dataset.from_list(data)

sft_config = SFTConfig(
    output_dir="/tmp/vram_test",
    num_train_epochs=1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=2,
    learning_rate=5e-5,
    bf16=True,
    logging_steps=1,
    max_steps=20,
    save_strategy="no",
    report_to="none",
    optim="adamw_torch",
    max_length=MAX_LENGTH,
    dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model,
    args=sft_config,
    train_dataset=dataset,
    processing_class=tokenizer,
    data_collator=collator,
    callbacks=[VRAMLogger()],
)

log.info(f"Pre-train GPU: {gpu_mb():,.0f} MB")
log.info(f"Running 20 steps with VRAM logging...")
trainer.train()
log.info(f"Post-train GPU: {gpu_mb():,.0f} MB")
log.info("VRAM test complete — check STEP logs for leak pattern")
