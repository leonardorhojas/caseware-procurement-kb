from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from openai import OpenAI

from caseware_kb.config import (
    ARTIFACTS_DIR,
    EMBEDDING_PROVIDER,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    require_openai_key,
)

_local_model = None
_active_provider: str | None = None


def active_provider() -> str:
    if _active_provider is None:
        raise RuntimeError("Embeddings have not been initialized yet")
    return _active_provider


def configure_from_manifest(manifest_path: Path | None = None) -> None:
    global _active_provider

    path = manifest_path or (ARTIFACTS_DIR / "manifest.json")
    if path.exists():
        manifest = json.loads(path.read_text())
        provider = manifest.get("embedding_provider")
        if provider in {"openai", "local"}:
            _active_provider = provider
            return

    if EMBEDDING_PROVIDER in {"openai", "local"}:
        _active_provider = EMBEDDING_PROVIDER


def _normalize(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return vectors
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _openai_client() -> OpenAI:
    return OpenAI(api_key=require_openai_key())


def _local_encode(texts: list[str]) -> np.ndarray:
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer

        _local_model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)
    vectors = _local_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return np.array(vectors, dtype=np.float32)


def _openai_encode(texts: list[str], batch_size: int = 64) -> np.ndarray:
    client = _openai_client()
    vectors: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=batch,
        )
        vectors.extend(item.embedding for item in response.data)

    return np.array(vectors, dtype=np.float32)


def _encode_with_provider(texts: list[str], provider: str, batch_size: int = 64) -> np.ndarray:
    if provider == "local":
        return _normalize(_local_encode(texts))
    return _normalize(_openai_encode(texts, batch_size=batch_size))


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    global _active_provider

    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    preferred = EMBEDDING_PROVIDER
    if preferred not in {"openai", "local"}:
        raise ValueError("CASEWARE_EMBEDDING_PROVIDER must be 'openai' or 'local'")

    if preferred == "local":
        _active_provider = "local"
        return _encode_with_provider(texts, "local")

    try:
        _active_provider = "openai"
        return _encode_with_provider(texts, "openai", batch_size=batch_size)
    except Exception as exc:
        message = str(exc).lower()
        if "quota" in message or "429" in message or "insufficient" in message:
            _active_provider = "local"
            print(
                "OpenAI embeddings unavailable (quota/rate limit). "
                f"Falling back to local model: {LOCAL_EMBEDDING_MODEL}"
            )
            return _encode_with_provider(texts, "local")
        raise


def embed_query(query: str) -> np.ndarray:
    global _active_provider

    if _active_provider is None:
        configure_from_manifest()

    provider = _active_provider or EMBEDDING_PROVIDER
    if provider not in {"openai", "local"}:
        provider = "local"

    if provider == "local":
        _active_provider = "local"
        return _encode_with_provider([query], "local")[0]

    try:
        _active_provider = "openai"
        return _encode_with_provider([query], "openai")[0]
    except Exception as exc:
        message = str(exc).lower()
        if "quota" in message or "429" in message or "insufficient" in message:
            _active_provider = "local"
            return _encode_with_provider([query], "local")[0]
        raise
