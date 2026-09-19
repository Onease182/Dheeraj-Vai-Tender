from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import Base, engine
from app import models  # noqa: F401 — ensures every model is registered on Base.metadata before create_all()
from app.routers import admin, auth, bid, billing, drafts, generate, meta, pdf, profiles

settings = get_settings()

app = FastAPI(title="TenderX Nepal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(meta.router)
app.include_router(profiles.router)
app.include_router(drafts.router)
app.include_router(bid.router)
app.include_router(generate.router)
app.include_router(pdf.router)
app.include_router(admin.router)
app.include_router(billing.router)


@app.on_event("startup")
def on_startup():
    # Dev convenience: create tables directly. Use Alembic migrations in production.
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok"}
