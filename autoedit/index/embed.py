"""SigLIP image/text embeddings via open_clip, on the NVIDIA GPU when available. Runs locally, no API."""

import numpy as np


class Embedder:
    """Loads the model on creation (slow: ~10-20 s); torch is imported only here."""

    def __init__(self, model: str, pretrained: str, device: str = "auto"):
        import open_clip
        import torch

        self._torch = torch
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.device_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(model, pretrained=pretrained,
                                                                               device=device)
        self.dtype = torch.float16 if device == "cuda" else torch.float32
        self.model = self.model.to(self.dtype).eval()
        self.tokenizer = open_clip.get_tokenizer(model)

    def _normalize(self, x) -> np.ndarray:
        x = x.float()
        return (x / x.norm(dim=-1, keepdim=True)).cpu().numpy()

    def images(self, frames: list[np.ndarray]) -> np.ndarray:
        from PIL import Image

        batch = self._torch.stack([self.preprocess(Image.fromarray(f)) for f in frames])
        with self._torch.no_grad():
            return self._normalize(self.model.encode_image(batch.to(self.device, self.dtype)))

    def text(self, query: str) -> np.ndarray:
        with self._torch.no_grad():
            return self._normalize(self.model.encode_text(self.tokenizer([query]).to(self.device)))[0]
