from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageText:
    page: int
    text: str


@dataclass
class ExtractedDocument:
    doc_id: str
    doc_type: str
    file_path: str
    title: str
    pages: list[PageText] = field(default_factory=list)
    order_id: str | None = None
    period: str | None = None

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())


@dataclass
class TextChunk:
    chunk_id: str
    doc_id: str
    page: int | None
    text: str
    char_start: int
    char_end: int


@dataclass
class SearchHit:
    chunk_id: str
    doc_id: str
    doc_type: str
    file_path: str
    order_id: str | None
    page: int | None
    score: float
    snippet: str
    text: str

    def to_citation(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "file_path": self.file_path,
            "order_id": self.order_id,
            "page": self.page,
            "score": round(self.score, 4),
            "snippet": self.snippet,
        }
