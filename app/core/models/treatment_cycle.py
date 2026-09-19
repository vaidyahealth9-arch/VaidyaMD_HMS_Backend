"""
VaidyaMD HMS — Treatment Cycle Model (Compatibility Re-export)
The canonical domain model now lives in `app.plugins.fertility.models`.
"""

from app.plugins.fertility.models import TreatmentCycle, TreatmentCycleStatus

__all__ = ["TreatmentCycle", "TreatmentCycleStatus"]
