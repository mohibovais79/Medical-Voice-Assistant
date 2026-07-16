"""REST API for patient records.

All responses use a consistent envelope:
    { "data": <payload | null>, "error": <string | null> }
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError

from app.core.logging import get_logger
from app.db import repo
from app.db.schema import PatientCreate, PatientRead, PatientUpdate

log = get_logger(__name__)
router = APIRouter(prefix="/patients", tags=["patients"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None}


def _err(error: Any) -> dict[str, Any]:
    return {"data": None, "error": error}


def _to_read(p) -> dict[str, Any]:
    """Convert a Patient ORM object to a dict for JSON response."""
    return PatientRead.model_validate(p).model_dump(mode="json")


@router.get("", response_model=None)
def list_patients(
    last_name: Optional[str] = Query(default=None),
    date_of_birth: Optional[str] = Query(default=None),
    phone_number: Optional[str] = Query(default=None),
):
    try:
        rows = repo.list_patients(last_name=last_name, date_of_birth=date_of_birth, phone_number=phone_number)
        return _ok([_to_read(r) for r in rows])
    except Exception as exc:
        log.exception("list_patients failed")
        raise HTTPException(status_code=500, detail=_err(str(exc)))


@router.get("/{patient_id}", response_model=None)
def get_patient(patient_id: str):
    row = repo.get_patient(patient_id)
    if not row:
        raise HTTPException(status_code=404, detail=_err("Patient not found"))
    return _ok(_to_read(row))


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
def create_patient(body: dict[str, Any]):
    try:
        payload = PatientCreate(**body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_err(str(exc)))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=_err(str(exc)))

    existing = repo.get_patient_by_phone(payload.phone_number)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=_err(
                f"A patient with phone {payload.phone_number} already exists "
                f"(patient_id={existing.patient_id}). Use PUT /patients/{existing.patient_id} to update."
            ),
        )

    try:
        data = payload.model_dump(mode="json")
        row = repo.create_patient(data)
        return _ok(_to_read(row))
    except Exception as exc:
        log.exception("create_patient failed")
        raise HTTPException(status_code=500, detail=_err(str(exc)))


@router.put("/{patient_id}", response_model=None)
def update_patient(patient_id: str, body: dict[str, Any]):
    if not body:
        raise HTTPException(status_code=400, detail=_err("Empty update body"))

    try:
        payload = PatientUpdate(**body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_err(str(exc)))

    update_data = {k: v for k, v in payload.model_dump(mode="json").items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail=_err("No valid fields to update"))

    existing = repo.get_patient(patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail=_err("Patient not found"))

    try:
        row = repo.update_patient(patient_id, update_data)
        return _ok(_to_read(row))
    except Exception as exc:
        log.exception("update_patient failed")
        raise HTTPException(status_code=500, detail=_err(str(exc)))


@router.delete("/{patient_id}", response_model=None)
def delete_patient(patient_id: str):
    existing = repo.get_patient(patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail=_err("Patient not found"))

    try:
        ok = repo.soft_delete_patient(patient_id)
        if not ok:
            raise HTTPException(status_code=404, detail=_err("Patient not found or already deleted"))
        return _ok({"patient_id": patient_id, "deleted": True})
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("delete_patient failed")
        raise HTTPException(status_code=500, detail=_err(str(exc)))
