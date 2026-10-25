"""Pinned local ECAPA embeddings, with no network or executable model config.

Architecture and preprocessing match the official Apache-2.0 SpeechBrain
spkrec-ecapa-voxceleb configuration. Only the embedding state_dict is loaded.
"""

import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path

REVISION = "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
SHA256 = "0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2"
BYTES = 83316686
PACKAGE_VERSION = "1.1.2"


def model_dir():
    return Path(
        os.environ.get(
            "MEMORA_ECAPA_MODEL_DIR",
            Path(__file__).resolve().parents[3] / ".memora/models/ecapa-voxceleb",
        )
    )


def availability():
    try:
        installed = importlib.util.find_spec("speechbrain") is not None
        installed = (
            installed and importlib.metadata.version("speechbrain") == PACKAGE_VERSION
        )
        manifest = json.loads((model_dir() / "manifest.json").read_text())
        if not isinstance(manifest, dict):
            raise ValueError("Invalid local manifest")
        ready = (
            installed
            and manifest.get("revision") == REVISION
            and manifest.get("sha256") == SHA256
            and manifest.get("license") == "Apache-2.0"
            and (model_dir() / "embedding_model.ckpt").stat().st_size == BYTES
        )
    except (OSError, ValueError, importlib.metadata.PackageNotFoundError):
        ready = False
    return {
        "available": bool(ready),
        "reason": ""
        if ready
        else "Le moteur local ECAPA et ses poids vérifiés doivent être préparés.",
    }


def verified_weights():
    if not availability()["available"]:
        raise ValueError(availability()["reason"])
    path = model_dir() / "embedding_model.ckpt"
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError("L’intégrité du modèle local ECAPA est invalide.")
    return path, SHA256


class Encoder:
    normalize_volume = False

    def __init__(self, weights):
        import torch
        from speechbrain.lobes.features import Fbank
        from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
        from speechbrain.processing.features import InputNormalization

        self.features = Fbank(n_mels=80).eval()
        self.normalizer = InputNormalization(
            norm_type="sentence", std_norm=False
        ).eval()
        self.model = ECAPA_TDNN(
            input_size=80,
            channels=[1024, 1024, 1024, 1024, 3072],
            kernel_sizes=[5, 3, 3, 3, 1],
            dilations=[1, 2, 3, 4, 1],
            attention_channels=128,
            lin_neurons=192,
        ).eval()
        self.model.load_state_dict(
            torch.load(weights, map_location="cpu", weights_only=True)
        )

    def embed_utterance(self, waveform):
        import torch

        with torch.inference_mode():
            signal = torch.from_numpy(waveform).float().unsqueeze(0)
            lengths = torch.ones(1)
            features = self.normalizer(self.features(signal), lengths)
            return self.model(features, lengths).squeeze().numpy()
