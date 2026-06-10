from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.getenv("CASEWARE_DATA_DIR", PROJECT_ROOT / "data"))
ARTIFACTS_DIR = Path(os.getenv("CASEWARE_ARTIFACTS_DIR", PROJECT_ROOT / "artifacts"))
SQLITE_PATH = ARTIFACTS_DIR / "kb.sqlite"
VECTORS_PATH = ARTIFACTS_DIR / "vectors.npy"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
)
EMBEDDING_PROVIDER = os.getenv("CASEWARE_EMBEDDING_PROVIDER", "openai").lower()
LOCAL_EMBEDDING_MODEL = os.getenv(
    "CASEWARE_LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
)

CHUNK_SIZE = int(os.getenv("CASEWARE_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CASEWARE_CHUNK_OVERLAP", "100"))


def ensure_artifacts_dir() -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACTS_DIR


def require_openai_key() -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return OPENAI_API_KEY
