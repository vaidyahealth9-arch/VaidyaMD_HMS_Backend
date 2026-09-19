import re
from typing import Dict, Any, Tuple

class AIScribeService:
    @staticmethod
    def parse_clinical_transcript(transcript: str) -> dict[str, Any]:
        bp_sys, bp_dia = "", ""
        heart_rate = ""
        temp = ""
        spo2 = ""
        weight = ""
        chief_complaint = ""
        history_of_illness = ""
        past_medical_history = ""
        diagnosis = ""
        investigations = ""
        plan = ""

        if transcript:
            # Extract BP
            bp_match = re.search(r"\b(\d{2,3})[/](\d{2,3})\b", transcript)
            if bp_match:
                bp_sys, bp_dia = int(bp_match.group(1)), int(bp_match.group(2))

            # Extract Pulse / HR
            hr_match = re.search(r"\b(?:pulse|hr|heart rate)[:\s]*(\d{2,3})\b", transcript, re.I)
            if hr_match:
                heart_rate = int(hr_match.group(1))

            # Extract Temperature
            temp_match = re.search(r"\b(?:temp|temperature)[:\s]*(\d{2,3}(?:\.\d+)?)\b", transcript, re.I)
            if temp_match:
                temp = float(temp_match.group(1))

            # Extract SpO2
            spo2_match = re.search(r"\b(?:spo2|o2|saturation)[:\s]*(\d{2,3})\b", transcript, re.I)
            if spo2_match:
                spo2 = int(spo2_match.group(1))

            # Extract Weight
            wt_match = re.search(r"\b(?:weight|wt)[:\s]*(\d{2,3}(?:\.\d+)?)\s*(?:kg)?\b", transcript, re.I)
            if wt_match:
                weight = float(wt_match.group(1))

            t_lower = transcript.lower()

            # Extract Past History
            past_match = re.search(r"(?:past (?:medical|surgical)? history|known case of|past history of|k/c/o)[:\s]*([^\.\n;]+)", transcript, re.I)
            if past_match:
                past_medical_history = past_match.group(1).strip()
            elif "diabetes" in t_lower or "hypertension" in t_lower or "thyroid" in t_lower or "pcos" in t_lower:
                conditions = []
                if "diabetes" in t_lower or "t2dm" in t_lower: conditions.append("Type 2 Diabetes Mellitus")
                if "hypertension" in t_lower or "htn" in t_lower: conditions.append("Hypertension")
                if "hypothyroid" in t_lower or "thyroid" in t_lower: conditions.append("Hypothyroidism")
                if "pcos" in t_lower or "pcod" in t_lower: conditions.append("PCOS")
                if conditions:
                    past_medical_history = "Known case of " + ", ".join(conditions)

            # Extract HOPI (History of Present Illness)
            hopi_match = re.search(r"(?:history of (?:present )?illness|hopi)[:\s]*([^\.\n]+(?:\.[^\.\n]+)?)", transcript, re.I)
            if hopi_match:
                history_of_illness = hopi_match.group(1).strip()

            # Dynamic complaints / diagnosis matching
            if "infertility" in t_lower or "conceive" in t_lower or "pregnancy" in t_lower or "follicular" in t_lower or "ivf" in t_lower:
                chief_complaint = "Inability to conceive / Subfertility workup. " + transcript[:140]
                if not history_of_illness:
                    history_of_illness = "Couple presenting for evaluation of fertility. Prior cycles and menstrual regularity reviewed."
                diagnosis = "Primary / Secondary Subfertility (Workup in progress)"
                investigations = "Pelvic TVS Follicular Scan, AMH, Day 2/3 FSH/LH, Semen Analysis (WHO 6th Edition)"
                plan = "1. Tab Folic Acid 5mg OD\n2. Schedule baseline Day 2 transvaginal ultrasound scan\n3. Male partner semen analysis after 3 days abstinence\n4. Review in OPD with reports"
            elif "fever" in t_lower or "chills" in t_lower:
                chief_complaint = f"Patient presents with acute fever and chills. Note: '{transcript[:120]}'"
                if not history_of_illness:
                    history_of_illness = "Acute onset of high-grade fever associated with chills and body ache."
                diagnosis = "Acute Febrile Illness (Fever) / Possible Viral Infection"
                investigations = "Complete Blood Count (CBC) with ESR, Dengue NS1 & IgM/IgG, Widal Test, Urine Routine"
                plan = "1. Tab Paracetamol 650mg TDS SOS\n2. Adequate oral fluid intake (2-3L/day)\n3. Review with CBC report tomorrow"
            elif "hypertension" in t_lower or "high bp" in t_lower:
                chief_complaint = f"Elevated blood pressure check. Context: '{transcript[:120]}'"
                if not history_of_illness:
                    history_of_illness = "Patient detected with elevated blood pressure on routine screening."
                diagnosis = "Essential Hypertension (Stage 1 / Stage 2)"
                investigations = "12-Lead ECG, Serum Creatinine, Electrolytes, Lipid Profile, Urine Microalbumin"
                plan = "1. Tab Telmisartan 40mg OD morning\n2. Low sodium diet (<5g/day)\n3. Home BP charting"
            elif len(transcript) > 20:
                chief_complaint = transcript[:200]
                diagnosis = "Clinical Consultation Evaluation & Symptom Management"
                plan = "1. Prescribed supportive medical therapy\n2. Follow-up after review of investigation results"

        return {
            "vitals": {
                "blood_pressure_systolic": bp_sys,
                "blood_pressure_diastolic": bp_dia,
                "heart_rate": heart_rate,
                "temperature": temp,
                "spo2": spo2,
                "weight": weight,
            },
            "clinical": {
                "chief_complaints": chief_complaint,
                "history_of_illness": history_of_illness,
                "past_medical_history": past_medical_history,
            },
            "assessment": {
                "provisional_diagnosis": diagnosis,
                "investigations_ordered": investigations,
                "plan": plan,
            }
        }
