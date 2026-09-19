"""
VaidyaMD HMS — Models Package (Universal Registry)
Aggregates core identities, domain-driven module models, and specialty plugin models.
"""

# Core System Entities (Horizontal Infrastructure)
from app.core.models.tenant import Hospital
from app.core.models.branch import Branch
from app.core.models.permission_profile import PermissionProfile
from app.core.models.user import User, UserRole
from app.core.models.clinical_record import ClinicalRecord
from app.core.models.document import Document

# Domain-Driven Core Modules
from app.modules.patients.model import Patient, Gender, RegistrationType
from app.modules.appointments.model import Appointment, AppointmentStatus
from app.modules.billing.model import Invoice, TreatmentPackage, InvoiceStatus
from app.modules.notifications.model import Notification, NotificationType
from app.modules.templates.model import ProtocolTemplate, ProtocolDrugRule, ClinicalTemplate
from app.modules.wallet.model import PatientWallet, WalletTransaction, WalletTxType
from app.modules.ipd.model import Ward, Bed, IPDAdmission, NursingTask
from app.modules.pharmacy.model import PharmacyIndent, PurchaseOrder, GoodsReceivedNote, InventoryBatch
from app.modules.counseling.models import CounselingNote
from app.modules.auth.models import RefreshToken

# Specialty Plugins (Plug-and-Play Verticals)
from app.plugins.fertility.models import (
    TreatmentCycle, TreatmentCycleStatus,
    TreatmentCycleType,
    OocyteRecord, EmbryologyWitness,
    CryoSample, CryoSampleStatus,
)
from app.plugins.cosgyn.models import (
    FrequencyType, SessionStatus,
    CosgynTreatment, CosgynPatientPlan, CosgynSession,
)

__all__ = [
    # Core
    "Hospital",
    "Branch",
    "PermissionProfile",
    "User", "UserRole",
    "ClinicalRecord",
    "Document",
    # Modules
    "Patient", "Gender", "RegistrationType",
    "ClinicalTemplate",
    "Appointment", "AppointmentStatus",
    "Invoice", "TreatmentPackage", "InvoiceStatus",
    "Notification", "NotificationType",
    "ProtocolTemplate", "ProtocolDrugRule",
    "PatientWallet", "WalletTransaction", "WalletTxType",
    "Ward", "Bed", "IPDAdmission", "NursingTask",
    "PharmacyIndent", "PurchaseOrder", "GoodsReceivedNote", "InventoryBatch",
    "CounselingNote",
    "RefreshToken",
    # Fertility Plugin
    "TreatmentCycle", "TreatmentCycleStatus",
    "TreatmentCycleType",
    "OocyteRecord", "EmbryologyWitness",
    "CryoSample", "CryoSampleStatus",
    # CosGyn Plugin
    "FrequencyType", "SessionStatus",
    "CosgynTreatment", "CosgynPatientPlan", "CosgynSession",
]
