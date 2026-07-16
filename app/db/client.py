"""Database engine + session management (SQLModel / SQLAlchemy).

Connects directly to Supabase Postgres via the connection string. Provides:
  - `engine`  — the SQLAlchemy engine (connection pool)
  - `get_session()` — context manager for a DB session
  - `PatientRepo` — repository class with all patient CRUD operations
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.schema import Patient

from typing import Any, Optional

log = get_logger(__name__)


# --- Engine (lazy init) ------------------------------------------------------

_engine = None
_SessionLocal = None


def _ensure_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL must be set in the environment")
    url = settings.database_url
    # psycopg2 needs the postgresql+psycopg2 dialect prefix
    if url.startswith("postgresql://") and "+" not in url.split("://")[0]:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    _engine = create_engine(url, pool_pre_ping=True, echo=False)
    _SessionLocal = sessionmaker(bind=_engine, class_=Session, expire_on_commit=False)
    log.info("Database engine created")


def get_session() -> Session:
    """Return a new DB session. Caller is responsible for closing it."""
    _ensure_engine()
    return _SessionLocal()


# --- Repository --------------------------------------------------------------


class PatientRepo:
    """All patient CRUD operations go through here — single source of truth."""

    @staticmethod
    def list_patients(
        last_name: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        phone_number: Optional[str] = None,
        include_deleted: bool = False,
    ) -> list[Patient]:
        with get_session() as session:
            stmt = select(Patient)
            if not include_deleted:
                stmt = stmt.where(Patient.deleted_at.is_(None))
            if last_name:
                stmt = stmt.where(Patient.last_name.ilike(last_name))
            if date_of_birth:
                stmt = stmt.where(Patient.date_of_birth == date_of_birth)
            if phone_number:
                digits = "".join(c for c in phone_number if c.isdigit())[-10:]
                stmt = stmt.where(Patient.phone_number == digits)
            stmt = stmt.order_by(Patient.created_at.desc())
            return list(session.exec(stmt).all())

    @staticmethod
    def get_patient(patient_id: str) -> Optional[Patient]:
        with get_session() as session:
            stmt = (
                select(Patient)
                .where(Patient.patient_id == patient_id)
                .where(Patient.deleted_at.is_(None))
            )
            return session.exec(stmt).first()

    @staticmethod
    def get_patient_by_phone(phone_number: str) -> Optional[Patient]:
        digits = "".join(c for c in phone_number if c.isdigit())[-10:]
        with get_session() as session:
            stmt = (
                select(Patient)
                .where(Patient.phone_number == digits)
                .where(Patient.deleted_at.is_(None))
            )
            return session.exec(stmt).first()

    @staticmethod
    def create_patient(data: dict[str, Any]) -> Patient:
        if "patient_id" not in data or not data["patient_id"]:
            data["patient_id"] = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)
        patient = Patient(**data)
        with get_session() as session:
            session.add(patient)
            session.commit()
            session.refresh(patient)
            log.info("Created patient %s (%s %s)", patient.patient_id, patient.first_name, patient.last_name)
            return patient

    @staticmethod
    def update_patient(patient_id: str, data: dict[str, Any]) -> Optional[Patient]:
        data["updated_at"] = datetime.now(timezone.utc)
        with get_session() as session:
            stmt = (
                select(Patient)
                .where(Patient.patient_id == patient_id)
                .where(Patient.deleted_at.is_(None))
            )
            patient = session.exec(stmt).first()
            if not patient:
                return None
            for key, value in data.items():
                if hasattr(patient, key):
                    setattr(patient, key, value)
            session.add(patient)
            session.commit()
            session.refresh(patient)
            log.info("Updated patient %s", patient_id)
            return patient

    @staticmethod
    def soft_delete_patient(patient_id: str) -> bool:
        with get_session() as session:
            stmt = (
                select(Patient)
                .where(Patient.patient_id == patient_id)
                .where(Patient.deleted_at.is_(None))
            )
            patient = session.exec(stmt).first()
            if not patient:
                return False
            patient.deleted_at = datetime.now(timezone.utc)
            session.add(patient)
            session.commit()
            log.info("Soft-deleted patient %s", patient_id)
            return True


# Singleton used throughout the app
repo = PatientRepo()
