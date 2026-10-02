from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_admin
from app.models.tender import Tender
from app.schemas.tender import TenderList, TenderOut
from app.services.scraper_ppmo import scrape_ppmo
from app.services.scraper_newspaper import scrape_newspapers

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("", response_model=TenderList)
def list_tenders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str | None = Query(None),
    category: str | None = Query(None),
    district: str | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Tender)

    if source:
        query = query.filter(Tender.source == source)
    if category:
        query = query.filter(Tender.category == category)
    if district:
        query = query.filter(Tender.district == district)
    if q:
        query = query.filter(
            or_(
                Tender.title.ilike(f"%{q}%"),
                Tender.organization.ilike(f"%{q}%"),
                Tender.description.ilike(f"%{q}%"),
            )
        )

    query = query.order_by(Tender.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    pages = max(1, -(-total // page_size))

    return TenderList(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender


@router.post("/admin/scrape", dependencies=[Depends(require_admin)])
def trigger_scrape(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(scrape_ppmo, db)
    background_tasks.add_task(scrape_newspapers, db)
    return {"message": "Scraping started in background"}
