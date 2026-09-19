import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from app.core.deps import get_verified_active_user
from app.models.user import User
from app.routers.generate import _generated_dir
from app.services.doc_generator import BidDocumentGenerator
from app.services.pdf_export import split_and_compress

router = APIRouter(prefix="/generate", tags=["pdf"])

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BACKEND_ROOT / "templates"


@router.post("/{doc_id}/pdf")
def generate_section_pdfs(
    doc_id: str, partner_count: int = Query(..., ge=1, le=3), user: User = Depends(get_verified_active_user)
):
    directory = _generated_dir(user.id)
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


@router.get("/{doc_id}/pdf/preview")
def preview_generated_pdf(doc_id: str, user: User = Depends(get_verified_active_user)):
    directory = _generated_dir(user.id)
    matches = list(directory.glob(f"{doc_id}.pdf"))
    if not matches:
        raise HTTPException(status_code=404, detail="PDF not found. Generate it first.")
    return FileResponse(matches[0], media_type="application/pdf", filename=matches[0].name)
