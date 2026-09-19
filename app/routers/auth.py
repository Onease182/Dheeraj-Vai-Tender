import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.email import send_password_reset_email, send_verification_email

PASSWORD_RESET_TOKEN_MINUTES = 60

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    token = secrets.token_urlsafe(32)
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        email_verification_token=token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user.email, token)

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/verify-email", response_model=UserResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email_verification_token == payload.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")
    user.email_verified = True
    user.email_verification_token = None
    db.commit()
    db.refresh(user)
    return user


@router.post("/resend-verification")
def resend_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.email_verified:
        return {"detail": "Already verified."}
    token = secrets.token_urlsafe(32)
    current_user.email_verification_token = token
    db.commit()
    send_verification_email(current_user.email, token)
    return {"detail": "Verification email sent."}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    # Always return the same generic response, whether or not the email
    # exists — don't let this endpoint be used to enumerate registered users.
    if user:
        token = secrets.token_urlsafe(32)
        user.password_reset_token = token
        user.password_reset_expires_at = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_MINUTES)
        db.commit()
        send_password_reset_email(user.email, token)
    return {"detail": "If that email is registered, a password reset link has been sent."}


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.password_reset_token == payload.token).first()
    if not user or not user.password_reset_expires_at or datetime.utcnow() > user.password_reset_expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset link.")

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.commit()

    return TokenResponse(access_token=create_access_token(user.id))
