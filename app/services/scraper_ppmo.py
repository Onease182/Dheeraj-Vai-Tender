"""
PPMO e-GP scraper — pulls public tender notices from the Government of Nepal
procurement portal (bolpatra.gov.np).

Uses Playwright headless browser to bypass bot detection.
Rate-limited to respect server capacity (Nepal Electronic Transactions Act 2063).
"""
import logging
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.tender import Tender

logger = logging.getLogger(__name__)

PPMO_URL = "https://bolpatra.gov.np/egp/searchOpportunity"


def _parse_date(raw: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def scrape_ppmo(db: Session, max_pages: int = 5) -> int:
    """
    Scrape up to `max_pages` pages from the PPMO e-GP public listing using Playwright.
    Returns the count of new tenders inserted.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed — run: pip install playwright && playwright install chromium")
        return 0

    inserted = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for page_num in range(1, max_pages + 1):
                url = f"{PPMO_URL}?page={page_num}"
                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_timeout(3000)  # let JS render
                except Exception as e:
                    logger.error("PPMO navigation failed on page %d: %s", page_num, e)
                    break

                title_text = page.title()
                if "maintenance" in title_text.lower():
                    logger.warning("PPMO is under maintenance, stopping scrape")
                    break

                # Try table rows
                rows = page.query_selector_all("table tbody tr")
                if not rows:
                    logger.info("PPMO: no rows on page %d, stopping", page_num)
                    break

                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) < 3:
                        continue

                    source_url = None
                    link = row.query_selector("a[href]")
                    if link:
                        href = link.get_attribute("href") or ""
                        source_url = href if href.startswith("http") else f"https://bolpatra.gov.np{href}"

                    # Skip duplicates
                    if source_url and db.query(Tender).filter(Tender.source_url == source_url).first():
                        continue

                    title = cells[1].inner_text().strip() if len(cells) > 1 else ""
                    organization = cells[2].inner_text().strip() if len(cells) > 2 else ""
                    pub_date = _parse_date(cells[3].inner_text()) if len(cells) > 3 else None
                    deadline = _parse_date(cells[4].inner_text()) if len(cells) > 4 else None

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
                logger.info("PPMO page %d: %d tenders inserted so far", page_num, inserted)
                time.sleep(3)

            browser.close()

    except Exception as e:
        db.rollback()
        logger.exception("PPMO scraper crashed: %s", e)

    logger.info("PPMO scrape complete — %d new tenders", inserted)
    return inserted
