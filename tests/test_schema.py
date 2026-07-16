"""Unit tests for the patient schema validation.

These don't touch the database — they validate the Pydantic models that both
the REST API and the voice-agent tool handlers rely on.

Run:
    pytest tests/test_schema.py -v
"""

from datetime import date
import pytest
from pydantic import ValidationError

from app.db.schema import PatientCreate, PatientUpdate, Sex


VALID = {
    "first_name": "Jane",
    "last_name": "O'Brien",
    "date_of_birth": "04/12/1985",
    "sex": "Female",
    "phone_number": "(555) 123-4567",
    "address_line_1": "123 Maple Street",
    "city": "Springfield",
    "state": "il",
    "zip_code": "62704",
}


def test_valid_patient_create():
    p = PatientCreate(**VALID)
    assert p.first_name == "Jane"
    assert p.last_name == "O'Brien"
    assert p.date_of_birth == date(1985, 4, 12)
    assert p.phone_number == "5551234567"  # normalized
    assert p.state == "IL"  # uppercased


def test_invalid_name_with_numbers():
    with pytest.raises(ValidationError):
        PatientCreate(**{**VALID, "first_name": "Jane123"})


def test_invalid_future_dob():
    with pytest.raises(ValidationError):
        PatientCreate(**{**VALID, "date_of_birth": "12/31/2099"})


def test_invalid_phone_short():
    with pytest.raises(ValidationError):
        PatientCreate(**{**VALID, "phone_number": "123"})


def test_invalid_state():
    with pytest.raises(ValidationError):
        PatientCreate(**{**VALID, "state": "XX"})


def test_invalid_zip():
    with pytest.raises(ValidationError):
        PatientCreate(**{**VALID, "zip_code": "123"})


def test_invalid_sex_enum():
    with pytest.raises(ValidationError):
        PatientCreate(**{**VALID, "sex": "Unknown"})


def test_optional_fields_default_none():
    p = PatientCreate(**VALID)
    assert p.email is None
    assert p.insurance_provider is None
    assert p.emergency_contact_phone is None


def test_valid_email():
    p = PatientCreate(**{**VALID, "email": "jane@example.com"})
    assert p.email is not None


def test_invalid_email():
    with pytest.raises(ValidationError):
        PatientCreate(**{**VALID, "email": "not-an-email"})


def test_partial_update_ignores_none():
    u = PatientUpdate(first_name="Janet")
    data = {k: v for k, v in u.model_dump(mode="json").items() if v is not None}
    assert data == {"first_name": "Janet"}


def test_update_validation_still_applies():
    with pytest.raises(ValidationError):
        PatientUpdate(phone_number="123")


def test_zip_plus4_accepted():
    p = PatientCreate(**{**VALID, "zip_code": "62704-1234"})
    assert p.zip_code == "62704-1234"


def test_emergency_contact_phone_normalized():
    p = PatientCreate(**{**VALID, "emergency_contact_phone": "555-987-6543"})
    assert p.emergency_contact_phone == "5559876543"
