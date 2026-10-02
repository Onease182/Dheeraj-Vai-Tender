"""
Newspaper e-paper scraper pipeline.

Phase 1 (automated): Downloads PDF editions of Gorkhapatra & Kantipur,
extracts pages that likely contain tender notices using keyword matching.

Phase 2 (semi-manual): Extracted text is saved as unverified Tender rows
for admin review via the dashboard (is_verified=False).

Requires: httpx, PyMuPDF (fitz) — both already in requirements.txt.
OCR for image-based PDFs requires pytesseract + tesseract binary (optional).
"""
import logging
import re
from datetime import datetime, date
from io import BytesIO
from typing import Iterator

import httpx
import fitz  # PyMuPDF

from sqlalchemy.orm import Session

from app.models.tender import Tender

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "TenderXNepal-Bot/1.0 (+https://tenderxnepal.com; info@tenderxnepal.com)",
}

TENDER_KEYWORDS = [
    "tender", "notice", "bid", "rfp", "quotation", "procurement",
    "बोलपत्र", "सूचना", "खरिद", "दरभाउपत्र",
]

NEWSPAPERS: list[dict] = [
    {
        "name": "Gorkhapatra",
        "url_template": "https://gorkhapatraepaper.com/pdf/{year}/{month:02d}/{day:02d}/gorkhapatra.pdf",
    },
    # Add more newspapers here as their e-paper PDF URLs become known:
    # {"name": "Kantipur", "url_template": "..."},
]


def _today_url(template: str) -> str:
    today = date.today()
    return template.format(year=today.year, month=today.month, day=today.day)


def _extract_tender_blocks(pdf_bytes: bytes) -> Iterator[str]:
    """Yield text blocks from PDF pages that contain tender keywords."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        text = page.get_text()
        low = text.lower()
        if any(kw in low for kw in TENDER_KEYWORDS):
            # Split into paragraphs and yield tender-looking ones
            for block in re.split(r"\n{2,}", text):
                block = block.strip()
                if len(block) > 40 and any(kw in block.lower() for kw in TENDER_KEYWORDS):
                    yield block
    doc.close()


def _guess_organization(text: str) -> str:
    """Very naive: take the first non-empty line as the org name."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 5:
            return line[:300]
    return ""


def scrape_newspapers(db: Session) -> int:
    """Download today's e-paper PDFs and extract tender notice text blocks."""
    inserted = 0

    for paper in NEWSPAPERS:
        url = _today_url(paper["url_template"])
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Could not fetch %s PDF: %s", paper["name"], e)
            continue

        pdf_bytes = resp.content
        logger.info("Fetched %s PDF (%d bytes)", paper["name"], len(pdf_bytes))

        for block in _extract_tender_blocks(pdf_bytes):
            # Deduplicate: skip if this exact block was already saved today
            existing = (
                db.query(Tender)
                .filter(
                    Tender.source == "newspaper",
                    Tender.newspaper_name == paper["name"],
                    Tender.description == block,
                )
                .first()
            )
            if existing:
                continue

            tender = Tender(
                title=block[:250],
                organization=_guess_organization(block),
                description=block,
                source="newspaper",
                newspaper_name=paper["name"],
                source_url=url,
                publication_date=datetime.utcnow(),
                is_verified=False,  # admin must review before it appears as verified
            )
            db.add(tender)
            inserted += 1

        db.commit()
        logger.info("Newspaper '%s': inserted %d blocks", paper["name"], inserted)

    return inserted
