"""Run once to create the admin user: python seed_admin.py"""
import sys
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User

ADMIN_EMAIL = "dheeraj.uparkoti.17@gmail.com"
ADMIN_PASSWORD = "dheeraj123"

db = SessionLocal()
try:
    existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if existing:
        existing.hashed_password = hash_password(ADMIN_PASSWORD)
        existing.is_admin = True
        existing.email_verified = True
        db.commit()
        print(f"Updated existing user: {ADMIN_EMAIL}")
    else:
        user = User(
            email=ADMIN_EMAIL,
            hashed_password=hash_password(ADMIN_PASSWORD),
            full_name="Dheeraj Uparkoti",
            is_admin=True,
            email_verified=True,
            can_use_first_partner=True,
            can_use_second_partner=True,
            can_upload_signature_stamp=True,
        )
        db.add(user)
        db.commit()
        print(f"Created admin user: {ADMIN_EMAIL}")
finally:
    db.close()
