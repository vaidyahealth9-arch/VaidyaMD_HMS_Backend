from pydantic import BaseModel, field_validator
from typing import Optional, Any
from uuid import UUID
from datetime import date, datetime


class PatientCreate(BaseModel):
    name: str
    registration_type: Optional[str] = "patient"
    title: Optional[str] = None
    surname: Optional[str] = None
    surname_at_birth: Optional[str] = None
    age: Optional[int] = None
    dob: Optional[date] = None
    gender: str
    marital_status: Optional[str] = None

    phone: str
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    alternate_email: Optional[str] = None
    address: Optional[str] = None
    husband_alternate_phone: Optional[str] = None
    husband_alternate_address: Optional[str] = None

    education_qualification: Optional[str] = None
    occupation: Optional[str] = None
    nationality: Optional[str] = "Indian"
    mother_tongue: Optional[str] = None
    country_of_birth: Optional[str] = "India"
    blood_group: Optional[str] = None
    photo_url: Optional[str] = None

    identity_type: Optional[str] = None
    aadhaar_number: Optional[str] = None
    identity_issued_country: Optional[str] = "India"
    abha_number: Optional[str] = None

    referred_by_type: Optional[str] = None
    referred_by_name: Optional[str] = None
    referring_doctor: Optional[str] = None
    marketing_person_name: Optional[str] = None
    area: Optional[str] = None
    treating_doctor_id: Optional[UUID] = None
    marketing_person_id: Optional[UUID] = None

    financial_type: Optional[str] = "self_pay"
    is_surrogate: Optional[bool] = False
    partner_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    tags: Optional[list[str]] = []
    alert_notes: Optional[list[str]] = []
    clinical_notes: Optional[list[str]] = []

    @field_validator("treating_doctor_id", "marketing_person_id", "partner_id", "branch_id", mode="before")
    @classmethod
    def empty_str_to_none_uuid(cls, v: Any) -> Any:
        if v == "" or v is None or v == "undefined":
            return None
        return v

    @field_validator("dob", mode="before")
    @classmethod
    def empty_str_to_none_dob(cls, v: Any) -> Any:
        if v == "" or v is None or v == "undefined":
            return None
        return v

    @field_validator("age", mode="before")
    @classmethod
    def empty_str_to_none_age(cls, v: Any) -> Any:
        if v == "" or v is None or v == "undefined":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("gender", mode="before")
    @classmethod
    def normalize_gender(cls, v: Any) -> str:
        if not v:
            return "female"
        return str(v).lower()


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    registration_type: Optional[str] = None
    title: Optional[str] = None
    surname: Optional[str] = None
    age: Optional[int] = None
    dob: Optional[date] = None
    marital_status: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    education_qualification: Optional[str] = None
    occupation: Optional[str] = None
    nationality: Optional[str] = None
    mother_tongue: Optional[str] = None
    blood_group: Optional[str] = None
    photo_url: Optional[str] = None
    abha_number: Optional[str] = None
    referred_by_type: Optional[str] = None
    referred_by_name: Optional[str] = None
    referring_doctor: Optional[str] = None
    marketing_person_name: Optional[str] = None
    area: Optional[str] = None
    treating_doctor_id: Optional[UUID] = None
    financial_type: Optional[str] = None
    partner_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    tags: Optional[list[str]] = None
    alert_notes: Optional[list[str]] = None
    clinical_notes: Optional[list[str]] = None


class PatientResponse(BaseModel):
    id: UUID
    vid: str
    registration_type: Optional[str] = "patient"
    title: Optional[str] = None
    name: str
    surname: Optional[str] = None
    age: Optional[int] = None
    dob: Optional[date] = None
    gender: str
    marital_status: Optional[str] = None
    phone: str
    alternate_phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    husband_alternate_phone: Optional[str] = None
    education_qualification: Optional[str] = None
    occupation: Optional[str] = None
    nationality: Optional[str] = "Indian"
    mother_tongue: Optional[str] = None
    blood_group: Optional[str] = None
    photo_url: Optional[str] = None
    identity_type: Optional[str] = None
    aadhaar_masked: Optional[str] = None
    abha_number: Optional[str] = None
    referred_by_type: Optional[str] = None
    referred_by_name: Optional[str] = None
    referring_doctor: Optional[str] = None
    marketing_person_name: Optional[str] = None
    area: Optional[str] = None
    financial_type: Optional[str] = "self_pay"
    is_surrogate: Optional[bool] = False

    partner_id: Optional[UUID] = None
    partner_name: Optional[str] = None
    partner_vid: Optional[str] = None
    partner_age: Optional[int] = None
    partner_phone: Optional[str] = None
    partner_blood_group: Optional[str] = None

    tags: Optional[list[str]] = []
    alert_notes: Optional[list[str]] = []
    clinical_notes: Optional[list[str]] = []
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PatientListResponse(BaseModel):
    patients: list[PatientResponse]
    total: int
    page: int
    per_page: int


class LinkPartnerRequest(BaseModel):
    partner_id: UUID


class AlertNotesUpdate(BaseModel):
    alert_notes: list[str]


class ClinicalNotesUpdate(BaseModel):
    clinical_notes: list[str]

class ConsentCreate(BaseModel):
    title: str 
    signature: str 
