"""MLSignalProvider (instrucao.md #72, #75, #76).

Prepared, but disabled by default and hardcoded off — enabling it is a deliberate,
versioned change an operator must make explicitly, never something the bot decides
on its own based on recent performance (#76: no self-optimization).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ModelMetadata:
    """instrucao.md #75 — every field a model MUST carry before it can ever be used
    in production. A model missing any of these can never be loaded (see ModelRegistry)."""

    model_id: str
    model_version: str
    training_dataset: str
    dataset_hash: str
    feature_schema: list[str]
    training_period: tuple[str, str]  # (start_iso, end_iso)
    validation_period: tuple[str, str]
    metrics: dict[str, float]
    artifact_hash: str
    created_at: datetime


class ModelNotVersionedError(Exception):
    """instrucao.md #75 — 'Modelo não versionado nunca poderá participar de produção.'"""


class MLSignalProvider:
    enabled: bool = False  # instrucao.md #72 — off by default, not read from config

    def __init__(self, model_metadata: ModelMetadata | None = None) -> None:
        self._metadata = model_metadata

    def predict(self, features: dict) -> None:
        if not self.enabled:
            return None
        if self._metadata is None:
            raise ModelNotVersionedError("no ModelMetadata registered — cannot serve predictions")
        raise NotImplementedError("model inference not implemented — no trained model exists yet")
