from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.app_settings import AppSettings
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.billing import CurrentInvoiceResponse, InvoiceOut
from app.services import storage
from app.services.billing import get_or_create_current_invoice

router = APIRouter(prefix="/billing", tags=["billing"])


def _get_settings_row(db: Session) -> AppSettings:
    row = db.get(AppSettings, "global")
    if not row:
        row = AppSettings(id="global")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/me", response_model=CurrentInvoiceResponse)
def current_invoice(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.trial_expired:
        return CurrentInvoiceResponse(locked=False)

    invoice = get_or_create_current_invoice(db, user)
    settings_row = _get_settings_row(db)
    qr_available = bool(settings_row.qr_code_path)

    if not invoice:
        return CurrentInvoiceResponse(
            locked=True,
            qr_code_available=qr_available,
            message="Your access has expired. Please contact support to set up your subscription.",
        )

    return CurrentInvoiceResponse(locked=True, invoice=invoice, qr_code_available=qr_available)


@router.get("/qr-code")
def get_qr_code(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    settings_row = _get_settings_row(db)
    if not settings_row.qr_code_path:
        raise HTTPException(status_code=404, detail="No payment QR code has been uploaded yet.")
    path = storage.absolute_path(settings_row.qr_code_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="QR code file is missing from storage.")
    return FileResponse(path)


@router.post("/invoices/{invoice_id}/submit-proof", response_model=InvoiceOut)
def submit_proof(
    invoice_id: str,
    proof_reference: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id == user.id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status not in ("pending", "rejected"):
        raise HTTPException(status_code=400, detail="This invoice is not awaiting payment proof.")

    if file is not None:
        relative_path, _ = storage.save_upload(file, subdir=f"invoices/{invoice.id}")
        invoice.proof_image_path = relative_path
    if proof_reference:
        invoice.proof_reference = proof_reference

    invoice.status = "submitted"
    invoice.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(invoice)
    return invoice
