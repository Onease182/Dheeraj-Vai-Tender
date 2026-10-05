import io
import secrets
import zipfile
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.constants import ATTACHMENT_CATEGORIES, PARTNER_ROLES
from app.core.db import get_db
from app.core.deps import require_admin
from app.core.security import hash_password
from app.models.app_settings import AppSettings
from app.models.draft import Draft, DraftImage, DraftSessionDoc
from app.models.generated_document import GeneratedDocument
from app.models.invoice import INVOICE_STATUSES, Invoice
from app.models.profile import PartnerProfile
from app.models.user import User
from app.schemas.admin import (
    AdminDraftOut,
    AdminDraftSummary,
    AdminDraftUpdate,
    AdminGenerateRequest,
    AdminGenerateResponse,
    AdminGenerationHistoryResponse,
    AdminResetPasswordRequest,
    AdminResetPasswordResponse,
    AdminUserOut,
    AdminUserUpdate,
)
from app.schemas.billing import AdminInvoiceCreate, AdminInvoiceUpdate, InvoiceOut
from app.schemas.profile import ProfileSummary
from app.services import storage
from app.services.bid_compute import resolve_authorized_signature_key, with_derived_fields
from app.services.billing import verify_invoice
from app.services.doc_generator import BidDocumentGenerator
from app.services.email import send_email_change_notice_admin, send_password_reset_by_admin_email
from app.services.pdf_export import split_and_compress
from app.services.validation import determine_partner_count, validate_bid

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

settings = get_settings()
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BACKEND_ROOT / "templates"


def _generated_dir(user_id: str) -> Path:
    return Path(settings.storage_root) / "generated" / user_id


def _get_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _get_draft(db: Session, user_id: str, draft_id: str) -> Draft:
    draft = (
        db.query(Draft)
        .options(selectinload(Draft.images), selectinload(Draft.session_docs))
        .filter(Draft.id == draft_id, Draft.user_id == user_id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    counts = dict(
        db.query(GeneratedDocument.user_id, func.count(GeneratedDocument.id))
        .group_by(GeneratedDocument.user_id)
        .all()
    )
    results = []
    for user in users:
        out = AdminUserOut.model_validate(user)
        out.generation_count = counts.get(user.id, 0)
        results.append(out)
    return results


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: str, payload: AdminUserUpdate, db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    data = payload.model_dump(exclude_unset=True)

    extend_days = data.pop("extend_trial_days", None)
    for key, value in data.items():
        setattr(user, key, value)
    if extend_days:
        user.trial_ends_at = user.trial_ends_at + timedelta(days=extend_days)

    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", response_model=AdminResetPasswordResponse)
def reset_user_password(user_id: str, payload: AdminResetPasswordRequest, db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    new_password = payload.new_password or secrets.token_urlsafe(9)

    user.hashed_password = hash_password(new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.commit()

    send_password_reset_by_admin_email(user.email, new_password)

    return AdminResetPasswordResponse(new_password=new_password)


@router.put("/users/{user_id}/email", response_model=AdminUserOut)
def change_user_email(user_id: str, payload: dict, db: Session = Depends(get_db)):
    from pydantic import EmailStr, TypeAdapter
    new_email = payload.get("email", "").strip()
    try:
        TypeAdapter(EmailStr).validate_python(new_email)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid email address.")
    user = _get_user(db, user_id)
    existing = db.query(User).filter(User.email == new_email).first()
    if existing and existing.id != user_id:
        raise HTTPException(status_code=400, detail="Email already in use by another account.")
    old_email = user.email
    if old_email == new_email:
        return AdminUserOut.model_validate(user)
    user.email = new_email
    user.pending_email = None
    user.pending_email_token = None
    db.commit()
    db.refresh(user)
    send_email_change_notice_admin(old_email, new_email)
    out = AdminUserOut.model_validate(user)
    out.generation_count = 0
    return out


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete an admin account")
    # Cascade: generated docs, drafts, profiles, invoices
    db.query(GeneratedDocument).filter(GeneratedDocument.user_id == user_id).delete()
    db.query(Invoice).filter(Invoice.user_id == user_id).delete()
    for draft in db.query(Draft).filter(Draft.user_id == user_id).all():
        db.query(DraftImage).filter(DraftImage.draft_id == draft.id).delete()
        db.query(DraftSessionDoc).filter(DraftSessionDoc.draft_id == draft.id).delete()
        db.delete(draft)
    db.query(PartnerProfile).filter(PartnerProfile.user_id == user_id).delete()
    storage.delete_dir(f"drafts/{user_id}")
    storage.delete_dir(f"generated/{user_id}")
    db.delete(user)
    db.commit()


@router.get("/users/{user_id}/drafts", response_model=list[AdminDraftSummary])
def list_user_drafts(user_id: str, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    return db.query(Draft).filter(Draft.user_id == user_id).order_by(Draft.updated_at.desc()).all()


@router.get("/users/{user_id}/drafts/{draft_id}", response_model=AdminDraftOut)
def get_user_draft(user_id: str, draft_id: str, db: Session = Depends(get_db)):
    return _get_draft(db, user_id, draft_id)


@router.put("/users/{user_id}/drafts/{draft_id}", response_model=AdminDraftOut)
def update_user_draft(user_id: str, draft_id: str, payload: AdminDraftUpdate, db: Session = Depends(get_db)):
    draft = _get_draft(db, user_id, draft_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(draft, key, value)
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/users/{user_id}/drafts/{draft_id}/images/{img_key}", response_model=AdminDraftOut)
def upload_user_draft_image(
    user_id: str,
    draft_id: str,
    img_key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    draft = _get_draft(db, user_id, draft_id)
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


@router.post("/users/{user_id}/drafts/{draft_id}/session-docs", response_model=AdminDraftOut, status_code=201)
def upload_user_draft_session_doc(
    user_id: str,
    draft_id: str,
    role: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if role not in PARTNER_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {PARTNER_ROLES}")
    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {ATTACHMENT_CATEGORIES}")

    draft = _get_draft(db, user_id, draft_id)
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


@router.delete("/users/{user_id}/drafts/{draft_id}/session-docs/{doc_id}", response_model=AdminDraftOut)
def delete_user_draft_session_doc(user_id: str, draft_id: str, doc_id: str, db: Session = Depends(get_db)):
    draft = _get_draft(db, user_id, draft_id)
    doc = next((d for d in draft.session_docs if d.id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Session document not found")
    storage.delete(doc.storage_path)
    db.delete(doc)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/users/{user_id}/profiles", response_model=list[ProfileSummary])
def list_user_profiles(user_id: str, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    return (
        db.query(PartnerProfile)
        .filter(PartnerProfile.user_id == user_id)
        .order_by(PartnerProfile.updated_at.desc())
        .all()
    )


@router.get("/users/{user_id}/generation-history", response_model=AdminGenerationHistoryResponse)
def user_generation_history(user_id: str, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    query = db.query(GeneratedDocument).filter(GeneratedDocument.user_id == user_id)
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
            "download_url": f"/admin/users/{user_id}/generate/{row.doc_id}/download",
        }
        for row in rows
    ]
    return AdminGenerationHistoryResponse(total=total, items=items)


@router.post("/users/{user_id}/generate", response_model=AdminGenerateResponse)
def generate_for_user(user_id: str, payload: AdminGenerateRequest, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    draft = _get_draft(db, user_id, payload.draft_id)

    field_data = with_derived_fields(draft.field_data)

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

    generator = BidDocumentGenerator(templates_dir=TEMPLATES_DIR, output_dir=_generated_dir(user_id))
    try:
        output_path = generator.generate(field_data, image_mapping)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc_id = output_path.stem
    db.add(
        GeneratedDocument(
            user_id=user_id,
            draft_id=draft.id,
            doc_id=doc_id,
            filename=output_path.name,
            jv_name=field_data.get("JV_NAME", ""),
            partner_count=determine_partner_count(field_data),
        )
    )
    db.commit()

    return AdminGenerateResponse(
        id=doc_id, filename=output_path.name, download_url=f"/admin/users/{user_id}/generate/{doc_id}/download"
    )


@router.get("/users/{user_id}/generate/{doc_id}/download")
def download_for_user(user_id: str, doc_id: str, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    directory = _generated_dir(user_id)
    matches = list(directory.glob(f"{doc_id}.docx"))
    if not matches:
        raise HTTPException(status_code=404, detail="Generated document not found")
    return FileResponse(
        matches[0],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=matches[0].name,
    )


@router.post("/users/{user_id}/generate/{doc_id}/pdf")
def generate_section_pdfs_for_user(
    user_id: str, doc_id: str, partner_count: int = Query(..., ge=1, le=3), db: Session = Depends(get_db)
):
    _get_user(db, user_id)
    directory = _generated_dir(user_id)
    matches = list(directory.glob(f"{doc_id}.docx"))
    if not matches:
        raise HTTPException(status_code=404, detail="Generated document not found")
    docx_path = matches[0]

    generator = BidDocumentGenerator(templates_dir=TEMPLATES_DIR, output_dir=directory)
    try:
        pdf_path = generator.convert_to_pdf(docx_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    split_dir = directory / f"{doc_id}_sections"
    written, warnings = split_and_compress(pdf_path, partner_count, split_dir)
    if not written:
        raise HTTPException(status_code=422, detail="No sections were produced from the generated PDF.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in written:
            zf.write(path, arcname=path.name)
    buffer.seek(0)

    headers = {"Content-Disposition": f'attachment; filename="{doc_id}_sections.zip"'}
    if warnings:
        headers["X-Split-Warnings"] = " | ".join(warnings)
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


# ---------------------------------------------------------------------------
# Billing: QR settings + invoice CRUD / verification
# ---------------------------------------------------------------------------


def _get_settings_row(db: Session) -> AppSettings:
    row = db.get(AppSettings, "global")
    if not row:
        row = AppSettings(id="global")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/settings/qr-code")
def get_qr_code_info(db: Session = Depends(get_db)):
    row = _get_settings_row(db)
    return {"qr_code_configured": bool(row.qr_code_path), "updated_at": row.updated_at}


@router.get("/settings/qr-code/image")
def get_qr_code_image(db: Session = Depends(get_db)):
    row = _get_settings_row(db)
    if not row.qr_code_path:
        raise HTTPException(status_code=404, detail="QR code not configured")
    path = Path(settings.storage_root) / row.qr_code_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="QR code file not found")
    return FileResponse(str(path), media_type="image/png")


@router.put("/settings/qr-code")
def upload_qr_code(file: UploadFile = File(...), db: Session = Depends(get_db)):
    row = _get_settings_row(db)
    if row.qr_code_path:
        storage.delete(row.qr_code_path)
    relative_path, _ = storage.save_upload(file, subdir="settings", stem="payment_qr_code")
    row.qr_code_path = relative_path
    db.commit()
    return {"qr_code_configured": True}


@router.get("/invoices", response_model=list[InvoiceOut])
def list_all_invoices(status: str | None = Query(None), db: Session = Depends(get_db)):
    query = db.query(Invoice)
    if status:
        if status not in INVOICE_STATUSES:
            raise HTTPException(status_code=400, detail=f"status must be one of {INVOICE_STATUSES}")
        query = query.filter(Invoice.status == status)
    return query.order_by(Invoice.created_at.desc()).all()


@router.get("/invoices/{invoice_id}/proof-image")
def get_invoice_proof_image(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice or not invoice.proof_image_path:
        raise HTTPException(status_code=404, detail="No proof image for this invoice")
    path = storage.absolute_path(invoice.proof_image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Proof image is missing from storage")
    return FileResponse(path)


@router.get("/users/{user_id}/invoices", response_model=list[InvoiceOut])
def list_user_invoices(user_id: str, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    return db.query(Invoice).filter(Invoice.user_id == user_id).order_by(Invoice.created_at.desc()).all()


@router.post("/users/{user_id}/invoices", response_model=InvoiceOut, status_code=201)
def create_invoice_for_user(user_id: str, payload: AdminInvoiceCreate, db: Session = Depends(get_db)):
    _get_user(db, user_id)
    if payload.status not in INVOICE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {INVOICE_STATUSES}")
    invoice = Invoice(user_id=user_id, **payload.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.put("/invoices/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: str, payload: AdminInvoiceUpdate, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in INVOICE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {INVOICE_STATUSES}")
    for key, value in data.items():
        setattr(invoice, key, value)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.proof_image_path:
        storage.delete(invoice.proof_image_path)
    db.delete(invoice)
    db.commit()


@router.post("/invoices/{invoice_id}/verify", response_model=InvoiceOut)
def verify_invoice_payment(invoice_id: str, db: Session = Depends(get_db), admin_user: User = Depends(require_admin)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "verified":
        raise HTTPException(status_code=400, detail="Invoice is already verified")
    verify_invoice(db, invoice, verified_by_user_id=admin_user.id)
    db.refresh(invoice)
    return invoice


@router.post("/invoices/{invoice_id}/reject", response_model=InvoiceOut)
def reject_invoice_payment(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = "rejected"
    db.commit()
    db.refresh(invoice)
    return invoice
