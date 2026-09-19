"""
VaidyaMD HMS — Patient Model with Extended Fertility Demographics, VID Generation & Partner Linking
"""

import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, Integer, Enum, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class RegistrationType(str, enum.Enum):
    PATIENT = "patient"
    DONOR_BANK = "donor_bank"
    DONOR_HOSPITAL = "donor_hospital"


class Patient(Base):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vid = Column(String(20), unique=True, nullable=False, comment="VaidyaMD ID: VH-{HOSP_CODE}-XXXXX")
    registration_type = Column(Enum(RegistrationType), default=RegistrationType.PATIENT, nullable=False)

    title = Column(String(20), nullable=True, comment="Mr, Mrs, Ms, Dr")
    name = Column(String(255), nullable=False)
    surname = Column(String(255), nullable=True)
    surname_at_birth = Column(String(255), nullable=True)

    age = Column(Integer)
    dob = Column(Date)
    gender = Column(Enum(Gender), nullable=False)
    marital_status = Column(String(50), nullable=True, comment="single, married, divorced, widowed, cohabiting")

    phone = Column(String(20), nullable=False)
    alternate_phone = Column(String(20), nullable=True)
    email = Column(String(255))
    alternate_email = Column(String(255), nullable=True)
    address = Column(Text)

    husband_alternate_phone = Column(String(20), nullable=True)
    husband_alternate_address = Column(Text, nullable=True)

    education_qualification = Column(String(255), nullable=True)
    occupation = Column(String(255))
    nationality = Column(String(100), default="Indian")
    mother_tongue = Column(String(100), nullable=True)
    country_of_birth = Column(String(100), default="India")

    blood_group = Column(String(10), comment="E.g. O+ve, A-ve, B+ve")
    photo_url = Column(String(500))

    # Identity & Regulatory Docs
    identity_type = Column(String(50), nullable=True, comment="aadhaar, pan, passport, voter_id")
    aadhaar_encrypted = Column(String(500), comment="AES-256 encrypted identity number")
    identity_issued_country = Column(String(100), default="India")
    abha_number = Column(String(50), nullable=True, comment="Ayushman Bharat Health Account Number")

    # Referral & Marketing Source Tracking
    referred_by_type = Column(String(50), nullable=True, comment="doctor, marketing_person, walk_in, online, other")
    referred_by_name = Column(String(255), nullable=True, comment="Name of referring doctor or entity")
    referring_doctor = Column(String(255), nullable=True, comment="Referring doctor or clinic name")
    marketing_person_name = Column(String(255), nullable=True, comment="Marketing coordinator or person name")
    area = Column(String(255), nullable=True, comment="Geographical area/city for lead ROI analytics")
    treating_doctor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    marketing_person_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    financial_type = Column(String(50), default="self_pay", comment="self_pay, insurance, corporate")
    is_surrogate = Column(Boolean, default=False)

    # Partner Linking (Self-referential FK)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=True,
                        comment="Linked partner for fertility couple tracking")

    # Tenant & Branch FK
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True)

    # Clinical Metadata & Fast Flags
    tags = Column(JSONB, default=list, comment="Searchable tags like 'IVF', 'High Risk', 'Donor'")
    alert_notes = Column(JSONB, default=list, comment="Array of high-priority free-text alert strings")
    clinical_notes = Column(JSONB, default=list, comment="Array of bulleted structured notes (e.g. MALE ISSUES, FEMALE ISSUES)")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hospital = relationship("Hospital", back_populates="patients")
    branch = relationship("Branch", back_populates="patients")
    partner = relationship("Patient", remote_side=[id], uselist=False)
    treating_doctor = relationship("User", foreign_keys=[treating_doctor_id])
    marketing_person = relationship("User", foreign_keys=[marketing_person_id])

    clinical_records = relationship("ClinicalRecord", back_populates="patient", lazy="selectin")
    appointments = relationship("Appointment", back_populates="patient", lazy="selectin")
    documents = relationship("Document", back_populates="patient", lazy="selectin")
    invoices = relationship("Invoice", back_populates="patient", lazy="selectin")
    treatment_cycles = relationship("TreatmentCycle", foreign_keys="[TreatmentCycle.patient_id]", back_populates="patient", lazy="selectin")
    cryo_samples = relationship("CryoSample", foreign_keys="[CryoSample.patient_id]", back_populates="patient", lazy="selectin")
    wallet = relationship("PatientWallet", back_populates="patient", uselist=False, lazy="selectin")
