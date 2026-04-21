"""PyTorch Lightning training loop."""
import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint
from omegaconf import OmegaConf


class LitModel(pl.LightningModule):
    def training_step(self, batch, batch_idx):
        return batch

    def configure_optimizers(self):
        pass


def main():
    cfg = OmegaConf.load("hparams.yaml")
    checkpoint_callback = ModelCheckpoint(dirpath="./ckpts", monitor="val_loss")
    trainer = pl.Trainer(max_epochs=cfg.epochs, callbacks=[checkpoint_callback])
    model = LitModel()
    trainer.fit(model)


if __name__ == "__main__":
    main()
