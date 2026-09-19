from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.core.constants import ATTACHMENT_CATEGORIES, PARTNER_ROLES
from app.core.db import get_db
from app.core.deps import get_verified_active_user
from app.models.profile import PartnerProfile, ProfileAttachment, ProfileImage
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileOut, ProfileSummary, ProfileUpdate
from app.services import storage

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _get_owned_profile(db: Session, profile_id: str, user: User) -> PartnerProfile:
    profile = (
        db.query(PartnerProfile)
        .options(selectinload(PartnerProfile.images), selectinload(PartnerProfile.attachments))
        .filter(PartnerProfile.id == profile_id, PartnerProfile.user_id == user.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("", response_model=list[ProfileSummary])
def list_profiles(db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    return (
        db.query(PartnerProfile)
        .filter(PartnerProfile.user_id == user.id)
        .order_by(PartnerProfile.updated_at.desc())
        .all()
    )


@router.post("", response_model=ProfileOut, status_code=201)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    if payload.role not in PARTNER_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {PARTNER_ROLES}")
    profile = PartnerProfile(user_id=user.id, **payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: str, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    return _get_owned_profile(db, profile_id, user)


@router.put("/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: str, payload: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)
):
    profile = _get_owned_profile(db, profile_id, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: str, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)):
    profile = _get_owned_profile(db, profile_id, user)
    storage.delete_dir(f"profiles/{profile.id}")
    db.delete(profile)
    db.commit()


@router.put("/{profile_id}/images/{img_key}", response_model=ProfileOut)
def upload_profile_image(
    profile_id: str,
    img_key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_active_user),
):
    profile = _get_owned_profile(db, profile_id, user)
    relative_path, _ = storage.save_upload(file, subdir=f"profiles/{profile.id}/images", stem=img_key)

    existing = next((img for img in profile.images if img.img_key == img_key), None)
    if existing:
        storage.delete(existing.storage_path)
        existing.storage_path = relative_path
    else:
        db.add(ProfileImage(profile_id=profile.id, img_key=img_key, storage_path=relative_path))

    db.commit()
    db.refresh(profile)
    return profile


@router.post("/{profile_id}/attachments", response_model=ProfileOut, status_code=201)
def upload_profile_attachment(
    profile_id: str,
    category: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_active_user),
):
    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {ATTACHMENT_CATEGORIES}")
    profile = _get_owned_profile(db, profile_id, user)
    relative_path, size = storage.save_upload(file, subdir=f"profiles/{profile.id}/attachments/{category}")

    db.add(
        ProfileAttachment(
            profile_id=profile.id,
            category=category,
            original_filename=file.filename or "document",
            storage_path=relative_path,
            file_size=size,
            description=description,
        )
    )
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}/attachments/{attachment_id}", response_model=ProfileOut)
def delete_profile_attachment(
    profile_id: str, attachment_id: str, db: Session = Depends(get_db), user: User = Depends(get_verified_active_user)
):
    profile = _get_owned_profile(db, profile_id, user)
    attachment = next((a for a in profile.attachments if a.id == attachment_id), None)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    storage.delete(attachment.storage_path)
    db.delete(attachment)
    db.commit()
    db.refresh(profile)
    return profile
