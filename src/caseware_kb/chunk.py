from __future__ import annotations

from caseware_kb.config import CHUNK_OVERLAP, CHUNK_SIZE
from caseware_kb.models import ExtractedDocument, TextChunk


def chunk_document(document: ExtractedDocument) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    chunk_index = 0
    cursor = 0

    for page in document.pages:
        text = page.text.strip()
        if not text:
            continue

        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            piece = text[start:end].strip()
            if piece:
                chunk_id = f"{document.doc_id}_c{chunk_index}"
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        doc_id=document.doc_id,
                        page=page.page,
                        text=piece,
                        char_start=cursor + start,
                        char_end=cursor + end,
                    )
                )
                chunk_index += 1

            if end >= len(text):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)

        cursor += len(text) + 2

    if not chunks and document.full_text.strip():
        chunks.append(
            TextChunk(
                chunk_id=f"{document.doc_id}_c0",
                doc_id=document.doc_id,
                page=document.pages[0].page if document.pages else None,
                text=document.full_text.strip(),
                char_start=0,
                char_end=len(document.full_text),
            )
        )

    return chunks
