"""
VaidyaMD HMS — Cosmetic Gynecology Models (Compatibility Re-export)
The canonical domain models now live in `app.plugins.cosgyn.models`.
"""

from app.plugins.cosgyn.models import (
    FrequencyType, SessionStatus,
    CosgynTreatment, CosgynPatientPlan, CosgynSession
)

__all__ = [
    "FrequencyType", "SessionStatus",
    "CosgynTreatment", "CosgynPatientPlan", "CosgynSession"
]
