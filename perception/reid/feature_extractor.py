"""
Lightweight Person Re-Identification Feature Extractor.

Extracts appearance embeddings from person bounding box crops using a
pretrained torchvision backbone (ResNet18). Embeddings are L2-normalised
so cosine similarity reduces to dot-product.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms as T

logger = logging.getLogger("perception.reid")


class PersonFeatureExtractor:
    """Extracts L2-normalised person appearance embeddings from image crops."""

    def __init__(self, device: Optional[str] = None, embedding_dim: int = 128):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = torch.device(device)

        # Lightweight backbone pretrained on ImageNet
        backbone = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
        # Replace final fc with embedding projection
        in_features = backbone.fc.in_features
        backbone.fc = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(inplace=True),
            nn.Linear(256, embedding_dim),
        )
        backbone.eval()
        self._model = backbone.to(self._device)

        # ImageNet normalisation
        self._transform = T.Compose([
            T.ToPILImage(),
            T.Resize((128, 256)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        self._embedding_dim = embedding_dim

        logger.info("[ReID] Feature extractor ready on %s (dim=%d)", self._device, embedding_dim)

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    @torch.no_grad()
    def extract(self, person_crop: np.ndarray) -> np.ndarray:
        """
        Extract and L2-normalise embedding from a person crop image.

        Args:
            person_crop: BGR uint8 numpy array (H, W, 3) from OpenCV.

        Returns:
            L2-normalised float32 numpy array of shape (embedding_dim,).
        """
        # Convert BGR to RGB
        rgb = person_crop[..., ::-1].copy()

        tensor = self._transform(rgb).unsqueeze(0).to(self._device)
        embedding = self._model(tensor)  # (1, embedding_dim)
        embedding = nn.functional.normalize(embedding, p=2, dim=1)
        return embedding.squeeze(0).cpu().numpy().astype(np.float32)

    @torch.no_grad()
    def extract_batch(self, crops: list[np.ndarray]) -> np.ndarray:
        """Extract embeddings for a batch of person crops."""
        if not crops:
            return np.empty((0, self._embedding_dim), dtype=np.float32)
        tensors = torch.stack([self._transform(c[..., ::-1].copy()) for c in crops]).to(self._device)
        embeddings = self._model(tensors)
        embeddings = nn.functional.normalize(embeddings, p=2, dim=1)
        return embeddings.cpu().numpy().astype(np.float32)