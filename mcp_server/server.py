#!/usr/bin/env python3
"""MCP server for the Caseware procurement knowledge base."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from caseware_kb.embed import configure_from_manifest  # noqa: E402
from caseware_kb.matching import find_document_gaps as match_find_gaps  # noqa: E402
from caseware_kb.matching import get_order_documents as match_get_order_docs  # noqa: E402
from caseware_kb.matching import list_inventory_reports as match_list_inventory  # noqa: E402
from caseware_kb.retrieve import get_source_excerpt as retrieve_source_excerpt  # noqa: E402
from caseware_kb.retrieve import hybrid_search as retrieve_hybrid_search  # noqa: E402
from caseware_kb.store import KnowledgeBase  # noqa: E402

mcp = FastMCP(
    "caseware-procurement-kb",
    instructions=(
        "Query a local procurement and inventory knowledge base containing "
        "invoices, purchase orders, shipping orders, inventory reports, and contracts. "
        "Use get_order_documents for order lookups, find_document_gaps for missing POs, "
        "and search_knowledge_base for semantic questions."
    ),
)

_kb: KnowledgeBase | None = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        configure_from_manifest()
        _kb = KnowledgeBase.load()
    return _kb


def _json(data: object) -> str:
    return json.dumps(data, indent=2)


@mcp.tool(
    name="search_knowledge_base",
    description="Semantic search over indexed document chunks with optional filters.",
)
def search_knowledge_base(
    query: str,
    top_k: int = 5,
    doc_type: str | None = None,
    order_id: str | None = None,
) -> str:
    doc_types = [doc_type] if doc_type else None
    hits = retrieve_hybrid_search(
        get_kb(),
        query=query,
        top_k=top_k,
        doc_types=doc_types,
        order_id=order_id,
    )
    return _json(
        {
            "query": query,
            "results": [hit.to_citation() for hit in hits],
        }
    )


@mcp.tool(
    name="get_order_documents",
    description="Return all indexed documents linked to a specific order ID.",
)
def get_order_documents(order_id: str) -> str:
    return _json(match_get_order_docs(get_kb(), order_id))


@mcp.tool(
    name="find_document_gaps",
    description="Find mismatches between invoices, purchase orders, and shipping orders.",
)
def find_document_gaps() -> str:
    return _json(match_find_gaps(get_kb()))


@mcp.tool(
    name="list_inventory_reports",
    description="List available inventory reports and the periods they cover.",
)
def list_inventory_reports() -> str:
    return _json({"reports": match_list_inventory(get_kb())})


@mcp.tool(
    name="get_source_excerpt",
    description="Fetch the full text excerpt for a chunk returned by search.",
)
def get_source_excerpt(chunk_id: str) -> str:
    excerpt = retrieve_source_excerpt(get_kb(), chunk_id)
    if excerpt is None:
        return _json({"error": f"Chunk not found: {chunk_id}"})
    return _json(excerpt)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
