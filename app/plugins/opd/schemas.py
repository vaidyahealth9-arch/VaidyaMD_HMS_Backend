"""
VaidyaMD HMS — General OPD Plugin Schemas
"""

OPD_CONSULTATION_SCHEMA = {
    "plugin_id": "opd",
    "record_type": "opd_consultation",
    "schema_version": "1.0",
    "title": "General OPD Consultation",
    "description": "Standard outpatient consultation form.",
    "sections": [
        {
            "id": "vitals",
            "title": "Vitals",
            "fields": [
                {"id": "weight", "label": "Weight (kg)", "type": "number", "placeholder": "65", "step": "0.1", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "height", "label": "Height (cm)", "type": "number", "placeholder": "165", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "bmi", "label": "BMI (auto-calculated)", "type": "number", "placeholder": "23.8", "readOnly": True, "role_access": ["doctor", "nurse", "admin"]},
                {"id": "blood_pressure_systolic", "label": "BP Systolic (mmHg)", "type": "number", "placeholder": "120", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "blood_pressure_diastolic", "label": "BP Diastolic (mmHg)", "type": "number", "placeholder": "80", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "heart_rate", "label": "Heart Rate (bpm)", "type": "number", "placeholder": "72", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "respiratory_rate", "label": "Respiratory Rate (breaths/min)", "type": "number", "placeholder": "16", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "temperature", "label": "Temperature (°F)", "type": "number", "placeholder": "98.6", "step": "0.1", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "spo2", "label": "SpO2 (%)", "type": "number", "placeholder": "98", "min": 0, "max": 100, "role_access": ["doctor", "nurse", "admin"]},
            ],
        },
        {
            "id": "clinical",
            "title": "Clinical Notes",
            "fields": [
                {"id": "chief_complaints", "label": "Chief Complaints", "type": "textarea", "rows": 3, "placeholder": "Patient presents with...", "required": True, "role_access": ["doctor", "nurse", "admin"]},
                {"id": "previous_history", "label": "Previous History", "type": "textarea", "rows": 3, "placeholder": "Past medical/surgical history...", "required": False, "role_access": ["doctor", "admin"]},
                {"id": "present_history", "label": "Present History", "type": "textarea", "rows": 4, "placeholder": "Detailed history of present illness...", "required": False, "role_access": ["doctor", "admin"]},
                {
                    "id": "examination",
                    "label": "Examination Findings",
                    "type": "textarea",
                    "rows": 3,
                    "placeholder": "Vitals stable, CVS normal...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                    "role_badge": "Doctor Only",
                },
            ],
        },
        {
            "id": "assessment",
            "title": "Assessment & Plan",
            "fields": [
                {
                    "id": "previous_investigations",
                    "label": "Previous Investigations",
                    "type": "textarea",
                    "rows": 2,
                    "placeholder": "Past reports...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
                {
                    "id": "investigations_to_be_advised",
                    "label": "Investigations To Be Advised",
                    "type": "textarea",
                    "rows": 2,
                    "placeholder": "CBC, LFT, USG Abdomen...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                    "role_badge": "Doctor Only",
                },
                {
                    "id": "medications",
                    "label": "Treatment (Medications)",
                    "type": "array",
                    "role_access": ["doctor", "admin"],
                    "role_badge": "Doctor Only",
                    "items": {
                        "type": "object",
                        "fields": [
                            {"id": "drug_name", "label": "Drug Name", "type": "text"},
                            {"id": "dose", "label": "Dose", "type": "text"},
                            {"id": "frequency", "label": "Frequency", "type": "text"},
                            {"id": "instructions", "label": "Instructions", "type": "text"}
                        ]
                    }
                },
                {
                    "id": "treatment_notes",
                    "label": "Treatment Notes",
                    "type": "textarea",
                    "rows": 3,
                    "placeholder": "Dietary/lifestyle instructions...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                    "role_badge": "Doctor Only",
                },
                {
                    "id": "follow_up",
                    "label": "Follow Up",
                    "type": "select",
                    "options": [
                        {"value": "1_week", "label": "1 Week"},
                        {"value": "2_weeks", "label": "2 Weeks"},
                        {"value": "1_month", "label": "1 Month"},
                        {"value": "3_months", "label": "3 Months"},
                        {"value": "sos", "label": "SOS"},
                        {"value": "no_followup", "label": "No Follow Up"},
                    ],
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
            ],
        },
    ],
}
