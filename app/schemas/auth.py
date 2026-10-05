from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangeEmailRequest(BaseModel):
    email: EmailStr
    password: str  # confirm identity


class VerifyEmailChangeRequest(BaseModel):
    token: str


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    preferred_locale: str
    is_admin: bool
    email_verified: bool
    trial_ends_at: datetime
    trial_expired: bool
    can_use_first_partner: bool
    can_use_second_partner: bool
    can_upload_signature_stamp: bool

    class Config:
        from_attributes = True
