from __future__ import annotations

import hashlib
import re
from pathlib import Path

import fitz
from PIL import Image

from caseware_kb.models import ExtractedDocument, PageText

DOC_TYPE_BY_DIR = {
    "invoices": "invoice",
    "purchase_orders": "purchase_order",
    "shipping_orders": "shipping_order",
    "inventory_reports": "inventory_report",
    "contracts": "contract",
}

ORDER_ID_PATTERNS = [
    re.compile(r"invoice_(\d{4,5})", re.I),
    re.compile(r"order_(\d{4,5})", re.I),
    re.compile(r"purchase_orders_(\d{4,5})", re.I),
]

INVENTORY_PERIOD_PATTERN = re.compile(
    r"StockReport_(\d{4}-\d{2})_", re.I
)
ORDER_ID_IN_TEXT = re.compile(r"Order ID:\s*(\d{4,5})", re.I)

SUPPORTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}


def _doc_id_for_path(path: Path) -> str:
    digest = hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:12]
    return f"{path.stem}_{digest}"


def _infer_doc_type(path: Path, data_root: Path) -> str:
    rel_parts = path.relative_to(data_root).parts
    if not rel_parts:
        raise ValueError(f"Cannot infer doc type for {path}")
    folder = rel_parts[0]
    return DOC_TYPE_BY_DIR.get(folder, folder.rstrip("s"))


def _order_id_from_filename(name: str) -> str | None:
    for pattern in ORDER_ID_PATTERNS:
        match = pattern.search(name)
        if match:
            return match.group(1)
    return None


def _period_from_filename(name: str) -> str | None:
    match = INVENTORY_PERIOD_PATTERN.search(name)
    return match.group(1) if match else None


def _order_id_from_text(text: str) -> str | None:
    match = ORDER_ID_IN_TEXT.search(text)
    return match.group(1) if match else None


def _extract_pdf(path: Path) -> list[PageText]:
    pages: list[PageText] = []
    with fitz.open(path) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if not text:
                text = page.get_text().strip()
            pages.append(PageText(page=index, text=text))
    return pages


def _extract_image(path: Path) -> list[PageText]:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("pytesseract is required for image OCR") from exc

    try:
        text = pytesseract.image_to_string(Image.open(path))
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract OCR is not installed. Install with: brew install tesseract"
        ) from exc

    return [PageText(page=1, text=text.strip())]


def extract_document(path: Path, data_root: Path) -> ExtractedDocument:
    path = path.resolve()
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path}")

    doc_type = _infer_doc_type(path, data_root)
    pages = _extract_pdf(path) if suffix == ".pdf" else _extract_image(path)
    full_text = "\n".join(page.text for page in pages)

    order_id = _order_id_from_filename(path.name)
    if not order_id:
        order_id = _order_id_from_text(full_text)

    period = _period_from_filename(path.name)
    title = path.stem.replace("_", " ")

    return ExtractedDocument(
        doc_id=_doc_id_for_path(path),
        doc_type=doc_type,
        file_path=str(path),
        title=title,
        pages=pages,
        order_id=order_id,
        period=period,
    )


def discover_documents(data_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(data_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            if path.name.startswith("."):
                continue
            files.append(path)
    return files
