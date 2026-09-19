"""
VaidyaMD HMS — Cryopreservation Models (Compatibility Re-export)
The canonical domain models now live in `app.plugins.fertility.models`.
"""

from app.plugins.fertility.models import CryoSample, CryoSampleStatus

__all__ = ["CryoSample", "CryoSampleStatus"]
