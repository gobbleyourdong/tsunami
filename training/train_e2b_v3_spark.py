#!/usr/bin/env python3
"""E2B on Spark — conservative config for 128GB unified memory.

batch=1, grad_accum=1, max_length=4096. No accumulation = no VRAM stacking.
"""
import json, logging, torch
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train")

from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

BASE_MODEL = "models/gemma-4-e2b-it"
DATA_PATH = "workspace/training_data/e4b_toolcall_train_v3.jsonl"
OUTPUT_DIR = "models/gemma-4-e2b-toolcall-v3"

INSTRUCTION_MARKER = "<|turn>user\n"
RESPONSE_MARKER = "<|turn>model\n"

data = []
with open(DATA_PATH) as f:
    for line in f:
        data.append(json.loads(line))
log.info(f"Loaded {len(data)} examples")

log.info("Loading model...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, dtype=torch.bfloat16, device_map={"":0}, trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

unwrapped = 0
for name, module in list(model.named_modules()):
    if type(module).__name__ == "Gemma4ClippableLinear" and hasattr(module, "linear"):
        parts = name.rsplit(".", 1)
        if len(parts) == 2:
            parent = dict(model.named_modules())[parts[0]]
            setattr(parent, parts[1], module.linear)
            unwrapped += 1
log.info(f"Unwrapped {unwrapped} layers")

model.gradient_checkpointing_enable()
model = get_peft_model(model, LoraConfig(
    r=32, lora_alpha=64,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
))

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
log.info(f"Trainable: {trainable:,}")

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

collator = ResponseOnlyCollator(tokenizer=tokenizer, mlm=False)
dataset = Dataset.from_list(data)

sft_config = SFTConfig(
    output_dir=OUTPUT_DIR, run_name="e2b_v3_spark",
    num_train_epochs=3,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=1,    # NO accumulation — single step per forward/backward
    learning_rate=5e-5, lr_scheduler_type="cosine", warmup_steps=20,
    bf16=True, logging_steps=10,
    save_strategy="steps", save_steps=100,
    report_to="none", max_grad_norm=0.3,
    optim="adamw_torch", weight_decay=0.01,
    max_length=4096, dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model, args=sft_config, train_dataset=dataset,
    processing_class=tokenizer, data_collator=collator,
)

log.info(f"=== E2B SPARK === batch=1, accum=1, max_len=4096, {len(data)} examples, 3 epochs")
trainer_stats = trainer.train()

trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
log.info(f"Done! Train loss: {trainer_stats.training_loss:.4f}")
