"""HuggingFace Trainer fine-tuning recipe — YAML-configured."""
from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments
import yaml


def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()
    model = AutoModelForSequenceClassification.from_pretrained(cfg["model_name"])

    args = TrainingArguments(
        output_dir=cfg["output_dir"],
        num_train_epochs=cfg["epochs"],
        per_device_train_batch_size=cfg["batch_size"],
        learning_rate=cfg["learning_rate"],
        save_strategy="epoch",
    )
    trainer = Trainer(model=model, args=args)
    trainer.train()
    trainer.save_model(cfg["output_dir"])


if __name__ == "__main__":
    main()
