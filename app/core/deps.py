from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error
    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


def get_verified_active_user(user: User = Depends(get_current_user)) -> User:
    """Gate for anything that touches real bid data: email must be verified
    and the trial must not have expired. Admins bypass both checks."""
    if user.is_admin:
        return user
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="Please verify your email address to continue.")
    if user.trial_expired:
        raise HTTPException(status_code=403, detail="Your trial period has ended. Contact support to continue.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
