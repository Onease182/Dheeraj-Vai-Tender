import fitz
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.core.constants import ATTACHMENT_CATEGORIES, PARTNER_ROLES, role_of_prefixed_key
from app.core.db import get_db
from app.core.deps import get_verified_active_user
from app.models.draft import Draft, DraftImage, DraftSessionDoc
from app.models.generated_document import GeneratedDocument
from app.models.user import User
from app.schemas.draft import DraftCreate, DraftOut, DraftSummary, DraftUpdate
from app.services import storage
from app.services.permissions import check_field_data_permission, check_role_permission, check_signature_upload_permission

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _get_owned_draft(db: Session, draft_id: str, user: User) -> Draft:
    draft = (
        db.query(Draft)
        .options(selectinload(Draft.images), selectinload(Draft.session_docs))
        .filter(Draft.id == draft_id, Draft.user_id == user.id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("", response_model=list[DraftSummary])
def list_drafts(db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    return db.query(Draft).filter(Draft.user_id == user.id).order_by(Draft.updated_at.desc()).all()


@router.post("", response_model=DraftOut, status_code=201)
def create_draft(payload: DraftCreate, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    check_field_data_permission(user, payload.field_data)
    draft = Draft(user_id=user.id, **payload.model_dump())
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/{draft_id}", response_model=DraftOut)
def get_draft(draft_id: str, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    return _get_owned_draft(db, draft_id, user)


@router.put("/{draft_id}", response_model=DraftOut)
def update_draft(
    draft_id: str, payload: DraftUpdate, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)
):
    draft = _get_owned_draft(db, draft_id, user)
    data = payload.model_dump(exclude_unset=True)
    if "field_data" in data:
        check_field_data_permission(user, data["field_data"])
    for key, value in data.items():
        setattr(draft, key, value)
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/{draft_id}", status_code=204)
def delete_draft(draft_id: str, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    draft = _get_owned_draft(db, draft_id, user)
    storage.delete_dir(f"drafts/{draft.id}")
    db.query(GeneratedDocument).filter(GeneratedDocument.draft_id == draft_id).delete()
    db.delete(draft)
    db.commit()


@router.put("/{draft_id}/images/{img_key}", response_model=DraftOut)
def upload_draft_image(
    draft_id: str,
    img_key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_active_user),
):
    check_signature_upload_permission(user)
    role = role_of_prefixed_key(img_key)
    if role:
        check_role_permission(user, role)

    draft = _get_owned_draft(db, draft_id, user)
    relative_path, _ = storage.save_upload(file, subdir=f"drafts/{draft.id}/images", stem=img_key)

    existing = next((img for img in draft.images if img.img_key == img_key), None)
    if existing:
        storage.delete(existing.storage_path)
        existing.storage_path = relative_path
    else:
        db.add(DraftImage(draft_id=draft.id, img_key=img_key, storage_path=relative_path))

    db.commit()
    db.refresh(draft)
    return draft


@router.post("/{draft_id}/session-docs", response_model=DraftOut, status_code=201)
def upload_draft_session_doc(
    draft_id: str,
    role: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_active_user),
):
    if role not in PARTNER_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {PARTNER_ROLES}")
    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {ATTACHMENT_CATEGORIES}")
    check_role_permission(user, role)

    draft = _get_owned_draft(db, draft_id, user)
    relative_path, _ = storage.save_upload(file, subdir=f"drafts/{draft.id}/session-docs/{role}/{category}")

    db.add(
        DraftSessionDoc(
            draft_id=draft.id,
            role=role,
            category=category,
            original_filename=file.filename or "document",
            storage_path=relative_path,
        )
    )
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/{draft_id}/session-docs/{doc_id}", response_model=DraftOut)
def delete_draft_session_doc(
    draft_id: str, doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)
):
    draft = _get_owned_draft(db, draft_id, user)
    doc = next((d for d in draft.session_docs if d.id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Session document not found")
    storage.delete(doc.storage_path)
    db.delete(doc)
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/{draft_id}/employer-pdf", response_model=DraftOut)
def upload_employer_pdf(
    draft_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)
):
    draft = _get_owned_draft(db, draft_id, user)
    if draft.employer_pdf_path:
        storage.delete(draft.employer_pdf_path)
    relative_path, _ = storage.save_upload(file, subdir=f"drafts/{draft.id}", stem="employer_tender")
    draft.employer_pdf_path = relative_path
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/{draft_id}/employer-pdf")
def download_employer_pdf(draft_id: str, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    draft = _get_owned_draft(db, draft_id, user)
    if not draft.employer_pdf_path:
        raise HTTPException(status_code=404, detail="No employer PDF uploaded for this draft")
    path = storage.absolute_path(draft.employer_pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Employer PDF file is missing from storage")
    return FileResponse(path, media_type="application/pdf", filename="employer_tender.pdf")


@router.get("/{draft_id}/employer-pdf/text")
def extract_employer_pdf_text(
    draft_id: str, page: int = 0, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)
):
    draft = _get_owned_draft(db, draft_id, user)
    if not draft.employer_pdf_path:
        raise HTTPException(status_code=404, detail="No employer PDF uploaded for this draft")
    path = storage.absolute_path(draft.employer_pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Employer PDF file is missing from storage")

    with fitz.open(str(path)) as doc:
        if page < 0 or page >= len(doc):
            raise HTTPException(status_code=400, detail=f"page must be between 0 and {len(doc) - 1}")
        text = doc[page].get_text()
        page_count = len(doc)

    return {"page": page, "page_count": page_count, "text": text}
