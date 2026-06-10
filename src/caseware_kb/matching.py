from __future__ import annotations

import sqlite3

from caseware_kb.store import KnowledgeBase

DOC_TYPES = {
    "invoice",
    "purchase_order",
    "shipping_order",
    "inventory_report",
    "contract",
}


def get_order_documents(kb: KnowledgeBase, order_id: str) -> dict:
    rows = kb.conn.execute(
        """
        SELECT doc_id, doc_type, file_path, title, page_count
        FROM documents
        WHERE order_id = ?
        ORDER BY doc_type, file_path
        """,
        (order_id,),
    ).fetchall()

    grouped: dict[str, list[dict]] = {
        "invoice": [],
        "purchase_order": [],
        "shipping_order": [],
        "inventory_report": [],
        "contract": [],
        "other": [],
    }

    for row in rows:
        bucket = row["doc_type"] if row["doc_type"] in grouped else "other"
        grouped[bucket].append(
            {
                "doc_id": row["doc_id"],
                "file_path": row["file_path"],
                "title": row["title"],
                "page_count": row["page_count"],
            }
        )

    return {
        "order_id": order_id,
        "documents": grouped,
        "total_documents": len(rows),
    }


def find_document_gaps(kb: KnowledgeBase) -> dict:
    def ids_for(doc_type: str) -> set[str]:
        rows = kb.conn.execute(
            "SELECT DISTINCT order_id FROM documents WHERE doc_type = ? AND order_id IS NOT NULL",
            (doc_type,),
        ).fetchall()
        return {row["order_id"] for row in rows}

    invoice_ids = ids_for("invoice")
    po_ids = ids_for("purchase_order")
    shipping_ids = ids_for("shipping_order")

    invoices_without_po = sorted(invoice_ids - po_ids)
    pos_without_invoice = sorted(po_ids - invoice_ids)
    shipping_without_invoice = sorted(shipping_ids - invoice_ids)
    shipping_without_po = sorted(shipping_ids - po_ids)

    matched = sorted(invoice_ids & po_ids & shipping_ids)

    return {
        "invoices_without_purchase_order": invoices_without_po,
        "purchase_orders_without_invoice": pos_without_invoice,
        "shipping_orders_without_invoice": shipping_without_invoice,
        "shipping_orders_without_purchase_order": shipping_without_po,
        "fully_matched_order_ids": matched,
        "summary": {
            "invoice_order_ids": len(invoice_ids),
            "purchase_order_ids": len(po_ids),
            "shipping_order_ids": len(shipping_ids),
        },
    }


def list_inventory_reports(kb: KnowledgeBase) -> list[dict]:
    rows = kb.conn.execute(
        """
        SELECT doc_id, file_path, title, period, page_count
        FROM documents
        WHERE doc_type = 'inventory_report'
        ORDER BY period, file_path
        """
    ).fetchall()

    return [
        {
            "doc_id": row["doc_id"],
            "file_path": row["file_path"],
            "title": row["title"],
            "period": row["period"],
            "page_count": row["page_count"],
        }
        for row in rows
    ]


def get_documents_by_type(kb: KnowledgeBase, doc_type: str) -> list[sqlite3.Row]:
    if doc_type not in DOC_TYPES:
        raise ValueError(f"Unsupported doc_type: {doc_type}")
    return kb.conn.execute(
        "SELECT * FROM documents WHERE doc_type = ? ORDER BY file_path",
        (doc_type,),
    ).fetchall()
