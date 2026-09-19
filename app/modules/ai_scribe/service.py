"""
VaidyaMD HMS — AI Scribe Clinical Service
Awaiting third-party speech-to-text / LLM pipeline integration.
"""

from typing import Dict, Any


class AIScribeService:
    @staticmethod
    def parse_clinical_transcript(transcript: str) -> dict[str, Any]:
        """
        Processes ambient audio/text transcript into structured clinical schema.
        Currently awaiting external LLM/ASR integration (e.g. MedLM, Whisper).
        Returns clean, empty clinical schema without synthetic/mock data.
        """
        return {
            "vitals": {
                "blood_pressure_systolic": "",
                "blood_pressure_diastolic": "",
                "heart_rate": "",
                "temperature": "",
                "spo2": "",
                "weight": "",
            },
            "clinical": {
                "chief_complaints": "",
                "history_of_illness": "",
                "past_medical_history": "",
            },
            "assessment": {
                "provisional_diagnosis": "",
                "investigations_ordered": "",
                "plan": "",
            },
        }
