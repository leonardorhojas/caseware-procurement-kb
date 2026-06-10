from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from caseware_kb.config import ARTIFACTS_DIR, ensure_artifacts_dir
from caseware_kb.embed import active_provider, configure_from_manifest
from caseware_kb.models import ExtractedDocument, SearchHit, TextChunk

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    doc_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    title TEXT NOT NULL,
    order_id TEXT,
    period TEXT,
    page_count INTEGER NOT NULL,
    full_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    page INTEGER,
    text TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    embedding_index INTEGER NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_order_id ON documents(order_id);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
"""


class KnowledgeBase:
    def __init__(
        self,
        conn: sqlite3.Connection,
        vectors: np.ndarray,
        chunk_ids: list[str],
    ) -> None:
        self.conn = conn
        self.vectors = vectors
        self.chunk_ids = chunk_ids
        self._chunk_index = {chunk_id: idx for idx, chunk_id in enumerate(chunk_ids)}

    @classmethod
    def load(cls, artifacts_dir: Path | None = None) -> KnowledgeBase:
        base = artifacts_dir or ARTIFACTS_DIR
        sqlite_path = base / "kb.sqlite"
        vectors_path = base / "vectors.npy"
        manifest_path = base / "manifest.json"

        if not sqlite_path.exists() or not vectors_path.exists():
            raise FileNotFoundError(
                f"Knowledge base not found in {base}. Run: python scripts/ingest.py"
            )

        with manifest_path.open() as handle:
            manifest = json.load(handle)

        configure_from_manifest(manifest_path)
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        vectors = np.load(vectors_path)
        return cls(conn=conn, vectors=vectors, chunk_ids=manifest["chunk_ids"])

    def get_chunk(self, chunk_id: str) -> sqlite3.Row | None:
        row = self.conn.execute(
            """
            SELECT c.*, d.doc_type, d.file_path, d.order_id, d.title, d.period
            FROM chunks c
            JOIN documents d ON d.doc_id = c.doc_id
            WHERE c.chunk_id = ?
            """,
            (chunk_id,),
        ).fetchone()
        return row

    def get_document(self, doc_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()

    def chunk_vector(self, chunk_id: str) -> np.ndarray | None:
        index = self._chunk_index.get(chunk_id)
        if index is None:
            return None
        return self.vectors[index]

    def all_documents(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM documents ORDER BY doc_type, file_path"
        ).fetchall()


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def save_knowledge_base(
    documents: list[ExtractedDocument],
    chunks: list[TextChunk],
    vectors: np.ndarray,
    artifacts_dir: Path | None = None,
) -> Path:
    base = ensure_artifacts_dir() if artifacts_dir is None else artifacts_dir
    base.mkdir(parents=True, exist_ok=True)

    db_path = base / "kb.sqlite"
    vectors_path = base / "vectors.npy"
    manifest_path = base / "manifest.json"

    if db_path.exists():
        db_path.unlink()

    conn = _connect(db_path)
    try:
        for document in documents:
            conn.execute(
                """
                INSERT INTO documents (
                    doc_id, doc_type, file_path, title, order_id, period,
                    page_count, full_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.doc_id,
                    document.doc_type,
                    document.file_path,
                    document.title,
                    document.order_id,
                    document.period,
                    len(document.pages),
                    document.full_text,
                ),
            )

        chunk_ids = [chunk.chunk_id for chunk in chunks]
        for embedding_index, chunk in enumerate(chunks):
            conn.execute(
                """
                INSERT INTO chunks (
                    chunk_id, doc_id, page, text, char_start, char_end, embedding_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.doc_id,
                    chunk.page,
                    chunk.text,
                    chunk.char_start,
                    chunk.char_end,
                    embedding_index,
                ),
            )

        conn.commit()
    finally:
        conn.close()

    np.save(vectors_path, vectors)
    manifest_path.write_text(
        json.dumps(
            {
                "chunk_ids": chunk_ids,
                "document_count": len(documents),
                "chunk_count": len(chunks),
                "vector_dimensions": int(vectors.shape[1]) if vectors.size else 0,
                "embedding_provider": active_provider(),
            },
            indent=2,
        )
    )
    return base


def row_to_hit(row: sqlite3.Row, score: float, snippet: str | None = None) -> SearchHit:
    text = row["text"]
    return SearchHit(
        chunk_id=row["chunk_id"],
        doc_id=row["doc_id"],
        doc_type=row["doc_type"],
        file_path=row["file_path"],
        order_id=row["order_id"],
        page=row["page"],
        score=score,
        snippet=snippet or text[:240],
        text=text,
    )
