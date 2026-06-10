from __future__ import annotations

from collections import Counter
from pathlib import Path

from caseware_kb.chunk import chunk_document
from caseware_kb.config import DATA_DIR, require_openai_key
from caseware_kb.embed import embed_texts
from caseware_kb.extract import discover_documents, extract_document
from caseware_kb.models import ExtractedDocument, TextChunk
from caseware_kb.store import save_knowledge_base


def run_ingest(data_dir: Path | None = None) -> dict:
    require_openai_key()
    root = (data_dir or DATA_DIR).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Data directory not found: {root}")

    documents: list[ExtractedDocument] = []
    warnings: list[str] = []

    for path in discover_documents(root):
        try:
            documents.append(extract_document(path, root))
        except RuntimeError as exc:
            warnings.append(f"{path.name}: {exc}")
        except Exception as exc:
            warnings.append(f"{path.name}: {exc}")

    all_chunks: list[TextChunk] = []
    for document in documents:
        all_chunks.extend(chunk_document(document))

    vectors = embed_texts([chunk.text for chunk in all_chunks])
    artifact_dir = save_knowledge_base(documents, all_chunks, vectors)

    from caseware_kb.embed import active_provider

    type_counts = Counter(doc.doc_type for doc in documents)
    order_ids = sorted({doc.order_id for doc in documents if doc.order_id})

    return {
        "artifact_dir": str(artifact_dir),
        "embedding_provider": active_provider(),
        "documents_indexed": len(documents),
        "chunks_indexed": len(all_chunks),
        "vector_dimensions": int(vectors.shape[1]) if vectors.size else 0,
        "documents_by_type": dict(type_counts),
        "distinct_order_ids": order_ids,
        "warnings": warnings,
    }
