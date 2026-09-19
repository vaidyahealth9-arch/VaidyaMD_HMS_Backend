"""
VaidyaMD HMS — Embryology Models (Compatibility Re-export)
The canonical domain models now live in `app.plugins.fertility.models`.
"""

from app.plugins.fertility.models import OocyteRecord, EmbryologyWitness

__all__ = ["OocyteRecord", "EmbryologyWitness"]
