"""
PPMO e-GP scraper — pulls public tender notices from the Government of Nepal
procurement portal (ppmo.gov.np / bolpatra.gov.np).

Rate-limited to respect server capacity (Nepal Electronic Transactions Act 2063).
Uses httpx + BeautifulSoup (no headless browser needed for the public listing).
"""
import logging
import time
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models.tender import Tender

logger = logging.getLogger(__name__)

PPMO_BASE = "https://bolpatra.gov.np/egp/searchOpportunity"
HEADERS = {
    "User-Agent": "TenderXNepal-Bot/1.0 (+https://tenderxnepal.com; info@tenderxnepal.com)",
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_DELAY = 3  # seconds between requests — stay polite


def _parse_date(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def scrape_ppmo(db: Session, max_pages: int = 5) -> int:
    """
    Scrape up to `max_pages` pages from the PPMO e-GP public listing.
    Returns the count of new tenders inserted.
    """
    inserted = 0

    try:
        for page in range(1, max_pages + 1):
            params = {"page": page, "size": 20}
            try:
                resp = httpx.get(PPMO_BASE, params=params, headers=HEADERS, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("PPMO request failed on page %d: %s", page, e)
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table tbody tr")

            if not rows:
                logger.info("PPMO: no rows on page %d, stopping", page)
                break

            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 5:
                    continue

                source_url = None
                link_tag = row.find("a", href=True)
                if link_tag:
                    href = link_tag["href"]
                    source_url = href if href.startswith("http") else f"https://bolpatra.gov.np{href}"

                # Skip if already in DB
                if source_url and db.query(Tender).filter(Tender.source_url == source_url).first():
                    continue

                title = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                organization = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                pub_date = _parse_date(cells[3].get_text(strip=True)) if len(cells) > 3 else None
                deadline = _parse_date(cells[4].get_text(strip=True)) if len(cells) > 4 else None

                tender = Tender(
                    title=title or "Untitled",
                    organization=organization,
                    source="ppmo",
                    source_url=source_url,
                    publication_date=pub_date,
                    submission_deadline=deadline,
                )
                db.add(tender)
                inserted += 1

            db.commit()
            logger.info("PPMO page %d: inserted %d so far", page, inserted)
            time.sleep(REQUEST_DELAY)

    except Exception as e:
        db.rollback()
        logger.exception("PPMO scraper crashed: %s", e)

    logger.info("PPMO scrape complete — %d new tenders", inserted)
    return inserted
