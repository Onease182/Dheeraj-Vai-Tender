"""Fixed-section PDF splitting + per-page compression for generated bids.
Ported from the desktop app's pdf_export.py — pure PyMuPDF logic, no
GUI/framework dependency, so this is a direct port.

Splits a generated bid PDF into one file per document section (JV
Agreement, Power of Attorney, Letter of Technical Bid, ... one block of
four per partner), each compressed to under 1MB, named after its section.
"""

import logging
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)

MAX_SIZE_BYTES = 1_000_000  # < 1 MB per split file

BASE_SECTIONS = [
    "JV Agreement",
    "Power of Attorney",
    "Letter of Technical Bid",
    "Letter of Price Bid",
]
SINGLE_BIDDER_SKIP_SECTIONS = {"JV Agreement", "Power of Attorney"}
PER_PARTNER_SECTIONS = [
    "Power of Attorney",
    "Self Declaration Certificate",
    "Running Contract Self Declaration",
    "Pending Litigation",
]
PARTNER_LABELS = ["Lead Partner", "First Partner", "Second Partner"]

MULTI_PAGE_SECTIONS = {
    "Letter of Technical Bid": 2,
    "Letter of Price Bid": 2,
}


def build_section_spec(partner_count):
    is_single = partner_count <= 1
    base_sections = [section for section in BASE_SECTIONS if not (is_single and section in SINGLE_BIDDER_SKIP_SECTIONS)]
    spec = [(section, MULTI_PAGE_SECTIONS.get(section, 1)) for section in base_sections]
    for label in PARTNER_LABELS[: max(1, min(partner_count, 3))]:
        for section in PER_PARTNER_SECTIONS:
            title = f"{label} - {section}"
            spec.append((title, MULTI_PAGE_SECTIONS.get(section, 1)))
    return spec


def _safe_filename(title, index):
    cleaned = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    cleaned = cleaned or f"Page {index}"
    return f"{index:02d} - {cleaned}.pdf"


def _compress_pages_under_limit(src_doc, start_page, page_count, max_bytes=MAX_SIZE_BYTES):
    end_page = start_page + page_count - 1

    merged = fitz.open()
    merged.insert_pdf(src_doc, from_page=start_page, to_page=end_page)
    data = merged.tobytes(deflate=True, garbage=4)
    merged.close()
    if len(data) <= max_bytes:
        return data

    for dpi in (150, 120, 96, 72, 55, 40):
        img_pdf = fitz.open()
        for p in range(start_page, end_page + 1):
            page = src_doc[p]
            pix = page.get_pixmap(dpi=dpi)
            rect = fitz.Rect(0, 0, pix.width, pix.height)
            img_page = img_pdf.new_page(width=pix.width, height=pix.height)
            img_page.insert_image(rect, pixmap=pix)
        data = img_pdf.tobytes(deflate=True, garbage=4)
        img_pdf.close()
        if len(data) <= max_bytes:
            return data

    return data


def split_and_compress(pdf_path, partner_count, output_dir):
    """Returns (written_paths, warnings)."""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    spec = build_section_spec(partner_count)
    expected_pages = sum(count for _, count in spec)
    warnings = []
    written = []

    with fitz.open(str(pdf_path)) as doc:
        page_count = len(doc)

        if page_count != expected_pages:
            message = (
                f"Expected {expected_pages} pages for a {partner_count}-partner "
                f"bid but the generated PDF has {page_count}. Splitting will "
                "continue in best-effort mode; please review the output."
            )
            warnings.append(message)
            logger.warning(message)

        cursor = 0
        file_index = 1
        for title, count in spec:
            if cursor >= page_count:
                break
            actual_count = min(count, page_count - cursor)
            data = _compress_pages_under_limit(doc, cursor, actual_count)
            out_path = output_dir / _safe_filename(title, file_index)
            out_path.write_bytes(data)
            written.append(out_path)
            cursor += actual_count
            file_index += 1

        while cursor < page_count:
            data = _compress_pages_under_limit(doc, cursor, 1)
            out_path = output_dir / _safe_filename(f"Extra Page {cursor + 1}", file_index)
            out_path.write_bytes(data)
            written.append(out_path)
            cursor += 1
            file_index += 1

    return written, warnings
