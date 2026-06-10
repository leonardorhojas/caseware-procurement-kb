from __future__ import annotations

import numpy as np

from caseware_kb.embed import embed_query
from caseware_kb.models import SearchHit
from caseware_kb.store import KnowledgeBase, row_to_hit


def _build_filter_clause(
    doc_types: list[str] | None,
    order_id: str | None,
) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []

    if doc_types:
        placeholders = ", ".join("?" for _ in doc_types)
        clauses.append(f"d.doc_type IN ({placeholders})")
        params.extend(doc_types)

    if order_id:
        clauses.append("d.order_id = ?")
        params.append(order_id)

    if not clauses:
        return "", params

    return "WHERE " + " AND ".join(clauses), params


def semantic_search(
    kb: KnowledgeBase,
    query: str,
    top_k: int = 5,
    doc_types: list[str] | None = None,
    order_id: str | None = None,
) -> list[SearchHit]:
    if kb.vectors.size == 0:
        return []

    query_vector = embed_query(query)
    where_sql, params = _build_filter_clause(doc_types, order_id)

    rows = kb.conn.execute(
        f"""
        SELECT c.*, d.doc_type, d.file_path, d.order_id, d.title, d.period
        FROM chunks c
        JOIN documents d ON d.doc_id = c.doc_id
        {where_sql}
        ORDER BY c.embedding_index
        """,
        params,
    ).fetchall()

    if not rows:
        return []

    indices = [row["embedding_index"] for row in rows]
    matrix = kb.vectors[indices]
    scores = matrix @ query_vector

    ranked = sorted(
        zip(rows, scores.tolist()),
        key=lambda item: item[1],
        reverse=True,
    )[:top_k]

    hits: list[SearchHit] = []
    for row, score in ranked:
        hits.append(row_to_hit(row, float(score)))
    return hits


def keyword_search(
    kb: KnowledgeBase,
    query: str,
    top_k: int = 5,
    doc_types: list[str] | None = None,
    order_id: str | None = None,
) -> list[SearchHit]:
    terms = [term.strip().lower() for term in query.split() if term.strip()]
    if not terms:
        return []

    where_sql, params = _build_filter_clause(doc_types, order_id)
    extra = " AND ".join("LOWER(c.text) LIKE ?" for _ in terms)
    if where_sql:
        where_sql = f"{where_sql} AND {extra}"
    else:
        where_sql = f"WHERE {extra}"
    params.extend(f"%{term}%" for term in terms)

    rows = kb.conn.execute(
        f"""
        SELECT c.*, d.doc_type, d.file_path, d.order_id, d.title, d.period
        FROM chunks c
        JOIN documents d ON d.doc_id = c.doc_id
        {where_sql}
        LIMIT ?
        """,
        [*params, top_k * 3],
    ).fetchall()

    hits: list[SearchHit] = []
    for row in rows[:top_k]:
        hits.append(row_to_hit(row, score=1.0))
    return hits


def hybrid_search(
    kb: KnowledgeBase,
    query: str,
    top_k: int = 5,
    doc_types: list[str] | None = None,
    order_id: str | None = None,
) -> list[SearchHit]:
    semantic_hits = semantic_search(
        kb, query, top_k=top_k, doc_types=doc_types, order_id=order_id
    )
    if semantic_hits:
        return semantic_hits
    return keyword_search(
        kb, query, top_k=top_k, doc_types=doc_types, order_id=order_id
    )


def get_source_excerpt(kb: KnowledgeBase, chunk_id: str, max_chars: int = 1200) -> dict | None:
    row = kb.get_chunk(chunk_id)
    if row is None:
        return None

    text = row["text"]
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    return {
        "chunk_id": row["chunk_id"],
        "doc_id": row["doc_id"],
        "doc_type": row["doc_type"],
        "file_path": row["file_path"],
        "order_id": row["order_id"],
        "page": row["page"],
        "title": row["title"],
        "text": text,
    }
