"""Integration tests for the REST API.

These hit the FastAPI app via TestClient but mock the `repo` singleton so they
run without a live database. They verify status codes, the response envelope,
validation errors, and soft-delete behavior.

Run:
    pytest tests/test_api.py -v
"""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())

VALID_PATIENT = {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "1985-04-12",
    "sex": "Female",
    "phone_number": "5551234567",
    "address_line_1": "123 Maple Street",
    "city": "Springfield",
    "state": "IL",
    "zip_code": "62704",
}


def _mock_patient(**overrides):
    """Build a mock Patient ORM object with all required attributes."""
    base = {
        "patient_id": "123e4567-e89b-12d3-a456-426614174000",
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1985-04-12",
        "sex": "Female",
        "phone_number": "5551234567",
        "email": None,
        "address_line_1": "123 Maple Street",
        "address_line_2": None,
        "city": "Springfield",
        "state": "IL",
        "zip_code": "62704",
        "insurance_provider": None,
        "insurance_member_id": None,
        "preferred_language": "English",
        "emergency_contact_name": None,
        "emergency_contact_phone": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    base.update(overrides)
    m = MagicMock()
    for k, v in base.items():
        setattr(m, k, v)
    return m


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_patient_success():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient_by_phone.return_value = None
        mock_repo.create_patient.return_value = _mock_patient()
        r = client.post("/patients", json=VALID_PATIENT)
    assert r.status_code == 201
    body = r.json()
    assert body["error"] is None
    assert body["data"]["first_name"] == "Jane"


def test_create_patient_duplicate_409():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient_by_phone.return_value = _mock_patient()
        r = client.post("/patients", json=VALID_PATIENT)
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]["error"]


def test_create_patient_validation_422():
    bad = {**VALID_PATIENT, "phone_number": "123"}
    r = client.post("/patients", json=bad)
    assert r.status_code == 422


def test_get_patient_not_found():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient.return_value = None
        r = client.get("/patients/does-not-exist")
    assert r.status_code == 404


def test_get_patient_success():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient.return_value = _mock_patient()
        r = client.get("/patients/123e4567-e89b-12d3-a456-426614174000")
    assert r.status_code == 200
    assert r.json()["data"]["patient_id"] == "123e4567-e89b-12d3-a456-426614174000"


def test_list_patients():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.list_patients.return_value = [_mock_patient()]
        r = client.get("/patients")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


def test_list_patients_filter():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.list_patients.return_value = [_mock_patient()]
        r = client.get("/patients?last_name=doe")
    assert r.status_code == 200
    mock_repo.list_patients.assert_called_once()
    args, kwargs = mock_repo.list_patients.call_args
    assert kwargs["last_name"] == "doe"


def test_update_patient_partial():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient.return_value = _mock_patient()
        mock_repo.update_patient.return_value = _mock_patient(first_name="Janet")
        r = client.put(
            "/patients/123e4567-e89b-12d3-a456-426614174000",
            json={"first_name": "Janet"},
        )
    assert r.status_code == 200
    assert r.json()["data"]["first_name"] == "Janet"


def test_update_patient_not_found():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient.return_value = None
        r = client.put("/patients/nope", json={"first_name": "Janet"})
    assert r.status_code == 404


def test_delete_patient_soft():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient.return_value = _mock_patient()
        mock_repo.soft_delete_patient.return_value = True
        r = client.delete("/patients/123e4567-e89b-12d3-a456-426614174000")
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True


def test_delete_patient_not_found():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.get_patient.return_value = None
        r = client.delete("/patients/nope")
    assert r.status_code == 404


def test_envelope_shape():
    with patch("app.api.patients.repo") as mock_repo:
        mock_repo.list_patients.return_value = []
        r = client.get("/patients")
    body = r.json()
    assert "data" in body
    assert "error" in body
