"""Patient data model using SQLModel (Pydantic + SQLAlchemy in one).

SQLModel lets us define the ORM table and the API schemas in one place:
  - `Patient`         — the table model (maps to the `patients` table)
  - `PatientCreate`   — input schema for POST /patients
  - `PatientUpdate`   — input schema for PUT /patients/:id (partial)
  - `PatientRead`     — output schema for API responses

Validation rules from the assessment spec are enforced via field validators
and SQLAlchemy column constraints.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from dateutil import parser as date_parser
from pydantic import EmailStr, field_validator
from sqlmodel import Field, SQLModel

# --- Static reference data ---------------------------------------------------

# 50 US states + DC
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
    "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}

NAME_REGEX = re.compile(r"^[A-Za-z][A-Za-z'\-]{0,49}$")
ZIP_REGEX = re.compile(r"^\d{5}(-\d{4})?$")
MEMBER_ID_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\- ]{0,29}$")


class Sex(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE = "Decline to Answer"


# --- Helpers -----------------------------------------------------------------


def _normalize_phone(raw: str) -> str:
    """Strip a US phone down to 10 digits (no country code)."""
    digits = re.sub(r"\D", "", raw.strip())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Invalid US phone number — must be 10 digits")
    return digits


def _parse_dob(raw: str | date) -> date:
    """Parse a DOB from string or date; reject future dates."""
    if isinstance(raw, date):
        d = raw
    else:
        try:
            d = date_parser.parse(str(raw), fuzzy=False).date()
        except (ValueError, OverflowError) as exc:
            raise ValueError("Invalid date of birth — use MM/DD/YYYY") from exc
    if d >= date.today():
        raise ValueError("Date of birth cannot be today or in the future")
    return d


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# --- Table model -------------------------------------------------------------


class Patient(SQLModel, table=True):
    """The `patients` table — ORM model."""

    __tablename__ = "patients"

    patient_id: str = Field(default=None, primary_key=True)
    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    date_of_birth: date
    sex: str  # stored as text, validated to enum values
    phone_number: str = Field(max_length=10)
    email: Optional[str] = Field(default=None, max_length=255)
    address_line_1: str = Field(max_length=200)
    address_line_2: Optional[str] = Field(default=None, max_length=200)
    city: str = Field(max_length=100)
    state: str = Field(max_length=2)
    zip_code: str = Field(max_length=10)
    insurance_provider: Optional[str] = Field(default=None, max_length=100)
    insurance_member_id: Optional[str] = Field(default=None, max_length=30)
    preferred_language: str = Field(default="English", max_length=50)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=100)
    emergency_contact_phone: Optional[str] = Field(default=None, max_length=10)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    deleted_at: Optional[datetime] = Field(default=None)


# --- API schemas (no table=True) --------------------------------------------


class PatientCreate(SQLModel):
    """Input schema for POST /patients — all required fields enforced."""

    first_name: str = Field(max_length=50)
    last_name: str = Field(max_length=50)
    date_of_birth: date
    sex: Sex
    phone_number: str
    email: Optional[EmailStr] = None
    address_line_1: str = Field(max_length=200)
    address_line_2: Optional[str] = Field(default=None, max_length=200)
    city: str = Field(max_length=100)
    state: str
    zip_code: str
    insurance_provider: Optional[str] = Field(default=None, max_length=100)
    insurance_member_id: Optional[str] = Field(default=None, max_length=30)
    preferred_language: str = Field(default="English", max_length=50)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=100)
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not NAME_REGEX.match(v):
            raise ValueError("Name must be 1–50 alphabetic chars, hyphens, or apostrophes")
        return v

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _validate_dob(cls, v):
        return _parse_dob(v)

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        return _normalize_phone(v)

    @field_validator("state")
    @classmethod
    def _validate_state(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in US_STATES:
            raise ValueError(f"Invalid US state abbreviation: {v}")
        return v

    @field_validator("zip_code")
    @classmethod
    def _validate_zip(cls, v: str) -> str:
        if not ZIP_REGEX.match(v):
            raise ValueError("ZIP must be 5 digits or ZIP+4")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def _validate_ec_phone(cls, v):
        if v is None or v == "":
            return None
        return _normalize_phone(v)

    @field_validator("insurance_member_id")
    @classmethod
    def _validate_member_id(cls, v):
        if v is None or v == "":
            return None
        if not MEMBER_ID_REGEX.match(v):
            raise ValueError("Insurance member ID must be alphanumeric (max 30 chars)")
        return v


class PatientUpdate(SQLModel):
    """Input schema for PUT /patients/:id — every field optional (partial)."""

    first_name: Optional[str] = Field(default=None, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = Field(default=None, max_length=200)
    address_line_2: Optional[str] = Field(default=None, max_length=200)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = Field(default=None, max_length=100)
    insurance_member_id: Optional[str] = Field(default=None, max_length=30)
    preferred_language: Optional[str] = Field(default=None, max_length=50)
    emergency_contact_name: Optional[str] = Field(default=None, max_length=100)
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _validate_name(cls, v):
        if v is None:
            return None
        if not NAME_REGEX.match(v):
            raise ValueError("Name must be 1–50 alphabetic chars, hyphens, or apostrophes")
        return v

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _validate_dob(cls, v):
        if v is None:
            return None
        return _parse_dob(v)

    @field_validator("phone_number")
    @classmethod
    def _validate_phone(cls, v):
        if v is None or v == "":
            return None
        return _normalize_phone(v)

    @field_validator("state")
    @classmethod
    def _validate_state(cls, v):
        if v is None:
            return None
        v = v.upper().strip()
        if v not in US_STATES:
            raise ValueError(f"Invalid US state abbreviation: {v}")
        return v

    @field_validator("zip_code")
    @classmethod
    def _validate_zip(cls, v):
        if v is None:
            return None
        if not ZIP_REGEX.match(v):
            raise ValueError("ZIP must be 5 digits or ZIP+4")
        return v

    @field_validator("emergency_contact_phone")
    @classmethod
    def _validate_ec_phone(cls, v):
        if v is None or v == "":
            return None
        return _normalize_phone(v)

    @field_validator("insurance_member_id")
    @classmethod
    def _validate_member_id(cls, v):
        if v is None or v == "":
            return None
        if not MEMBER_ID_REGEX.match(v):
            raise ValueError("Insurance member ID must be alphanumeric (max 30 chars)")
        return v


class PatientRead(SQLModel):
    """Output schema for API responses — includes auto fields."""

    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[str] = None
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: str
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
