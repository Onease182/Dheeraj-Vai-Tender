from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_verified_active_user
from app.models.draft import Draft
from app.models.generated_document import GeneratedDocument
from app.models.user import User
from app.schemas.generate import GenerateRequest, GenerateResponse, GenerationHistoryResponse
from app.services import storage
from app.services.bid_compute import resolve_authorized_signature_key, with_derived_fields
from app.services.doc_generator import BidDocumentGenerator
from app.services.validation import determine_partner_count, validate_bid

router = APIRouter(prefix="/generate", tags=["generate"])

settings = get_settings()
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BACKEND_ROOT / "templates"


def _generated_dir(user_id: str) -> Path:
    return Path(settings.storage_root) / "generated" / user_id


@router.post("", response_model=GenerateResponse)
def generate_bid(payload: GenerateRequest, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    draft = (
        db.query(Draft)
        .options(selectinload(Draft.images))
        .filter(Draft.id == payload.draft_id, Draft.user_id == user.id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    field_data = with_derived_fields(payload.field_data)

    image_mapping: dict[str, str] = {}
    for img in draft.images:
        image_mapping[img.img_key] = str(storage.absolute_path(img.storage_path))

    authorized_key = resolve_authorized_signature_key(field_data)
    has_authorized_signature = bool(authorized_key and authorized_key in image_mapping)
    if authorized_key and authorized_key in image_mapping:
        image_mapping["AUTHORISED_SIG"] = image_mapping[authorized_key]

    errors = validate_bid(field_data, authorized_signature_present=has_authorized_signature)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    generator = BidDocumentGenerator(templates_dir=TEMPLATES_DIR, output_dir=_generated_dir(user.id))
    try:
        output_path = generator.generate(field_data, image_mapping)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc_id = output_path.stem

    db.add(
        GeneratedDocument(
            user_id=user.id,
            draft_id=draft.id,
            doc_id=doc_id,
            filename=output_path.name,
            jv_name=field_data.get("JV_NAME", ""),
            partner_count=determine_partner_count(field_data),
        )
    )
    db.commit()

    return GenerateResponse(id=doc_id, filename=output_path.name, download_url=f"/generate/{doc_id}/download")


@router.get("/history", response_model=GenerationHistoryResponse)
def generation_history(db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    query = db.query(GeneratedDocument).filter(GeneratedDocument.user_id == user.id)
    total = query.count()
    rows = query.order_by(GeneratedDocument.created_at.desc()).limit(20).all()
    items = [
        {
            "id": row.id,
            "doc_id": row.doc_id,
            "filename": row.filename,
            "jv_name": row.jv_name,
            "partner_count": row.partner_count,
            "created_at": row.created_at,
            "download_url": f"/generate/{row.doc_id}/download",
        }
        for row in rows
    ]
    return GenerationHistoryResponse(total=total, items=items)


@router.get("/{doc_id}/download")
def download_generated_bid(doc_id: str, user: User = Depends(get_verified_active_user)):
    directory = _generated_dir(user.id)
    matches = list(directory.glob(f"{doc_id}.docx"))
    if not matches:
        raise HTTPException(status_code=404, detail="Generated document not found")
    return FileResponse(
        matches[0],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=matches[0].name,
    )
