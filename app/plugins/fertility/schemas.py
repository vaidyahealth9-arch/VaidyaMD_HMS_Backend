"""
VaidyaMD HMS — Fertility Plugin JSON Schema Definitions
CRITICAL: These schemas drive the DynamicForm renderer on the frontend.
          Clinical data is stored as JSONB — NOT as SQL columns.
"""

FEMALE_HISTORY_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "female_history",
    "schema_version": "1.0",
    "title": "Female Clinical History",
    "description": "Capture detailed reproductive and medical background.",
    "sections": [
        {
            "id": "complaints_menstrual",
            "title": "Chief Complaints & Menstrual History",
            "fields": [
                {
                    "id": "chief_complaints",
                    "label": "Chief Complaints (c/o)",
                    "type": "textarea",
                    "rows": 3,
                    "placeholder": "Primary infertility for 3 years. Irregular cycles (35-45 days).",
                    "required": True,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "menstrual_history",
                    "label": "Menstrual History",
                    "type": "select",
                    "options": [
                        {"value": "regular", "label": "Regular"},
                        {"value": "irregular_oligo_amenorrhea", "label": "Irregular (Oligo/Amenorrhea)"},
                        {"value": "menorrhagia", "label": "Menorrhagia"},
                        {"value": "dysmenorrhea", "label": "Dysmenorrhea"},
                        {"value": "oligomenorrhea", "label": "Oligomenorrhea"},
                    ],
                    "required": True,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "lmp",
                    "label": "Last Menstrual Period (LMP)",
                    "type": "date",
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "cycle_length",
                    "label": "Cycle Length (days)",
                    "type": "number",
                    "placeholder": "28",
                    "min": 15,
                    "max": 90,
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "obs_history",
                    "label": "Obstetric History (G P L A)",
                    "type": "text",
                    "placeholder": "G0 P0 L0 A0",
                    "pattern": r"G\d+ P\d+ L\d+ A\d+",
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "duration_infertility",
                    "label": "Duration of Infertility (years)",
                    "type": "number",
                    "placeholder": "3",
                    "min": 0,
                    "max": 30,
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
            ],
        },
        {
            "id": "past_medical_surgical",
            "title": "Past Medical / Surgical History",
            "fields": [
                {
                    "id": "past_medical_history",
                    "label": "Past Medical & Surgical History",
                    "type": "checkbox_group",
                    "options": [
                        {"value": "thyroid", "label": "Thyroid"},
                        {"value": "pcos", "label": "PCOS"},
                        {"value": "endometriosis", "label": "Endometriosis"},
                        {"value": "laparoscopy", "label": "Laparoscopy"},
                        {"value": "hysteroscopy", "label": "Hysteroscopy"},
                        {"value": "hysterectomy", "label": "Hysterectomy"},
                        {"value": "tb_female", "label": "Tuberculosis"},
                        {"value": "diabetes", "label": "Diabetes"},
                        {"value": "hypertension", "label": "Hypertension"},
                        {"value": "fibroid", "label": "Uterine Fibroid"},
                        {"value": "ovarian_cyst", "label": "Ovarian Cyst"},
                        {"value": "autoimmune", "label": "Autoimmune Disorder"},
                    ],
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
            ],
        },
        {
            "id": "systemic_examination",
            "title": "Systemic Examination",
            "role_access": ["doctor", "admin"],
            "role_badge": "Doctor Only",
            "fields": [
                {
                    "id": "per_abdomen",
                    "label": "Per Abdomen (PA)",
                    "type": "textarea",
                    "rows": 3,
                    "placeholder": "Findings for Per Abdomen examination...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
                {
                    "id": "per_vaginal",
                    "label": "Per Vaginal (PV)",
                    "type": "textarea",
                    "rows": 3,
                    "placeholder": "Findings for Per Vaginal examination...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
                {
                    "id": "per_speculum",
                    "label": "Per Speculum (PS)",
                    "type": "textarea",
                    "rows": 3,
                    "placeholder": "Findings for Per Speculum examination...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
                {
                    "id": "provisional_diagnosis",
                    "label": "Provisional Diagnosis",
                    "type": "textarea",
                    "rows": 2,
                    "placeholder": "Provisional diagnosis based on history and examination...",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
            ],
        },
    ],
}

MALE_HISTORY_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "male_history",
    "schema_version": "1.0",
    "title": "Male History & Andrology",
    "description": "Partner evaluation and andrological assessment.",
    "sections": [
        {
            "id": "previous_investigations",
            "title": "Previous Investigations",
            "fields": [
                {
                    "id": "previous_semen_analysis",
                    "label": "Previous Semen Analysis Findings",
                    "type": "textarea",
                    "rows": 3,
                    "placeholder": "Normozoospermia Count 45M/ml, Motility 60%.",
                    "required": False,
                    "role_access": ["doctor", "embryologist", "andrologist", "admin"],
                },
                {
                    "id": "previous_hormonal_profile",
                    "label": "Previous Hormonal Profile",
                    "type": "textarea",
                    "rows": 2,
                    "placeholder": "FSH, LH, Testosterone values...",
                    "required": False,
                    "role_access": ["doctor", "embryologist", "andrologist", "admin"],
                },
            ],
        },
        {
            "id": "specific_history",
            "title": "Past Medical & Personal History",
            "fields": [
                {
                    "id": "past_history",
                    "label": "Past Medical History",
                    "type": "checkbox_group",
                    "options": [
                        {"value": "mumps", "label": "H/O Mumps"},
                        {"value": "diabetes", "label": "Diabetes"},
                        {"value": "smoking_alcohol", "label": "Smoking / Alcohol"},
                        {"value": "varicocele", "label": "Varicocele"},
                        {"value": "undescended_testis", "label": "Undescended Testis"},
                        {"value": "orchitis", "label": "Orchitis"},
                        {"value": "hypertension", "label": "Hypertension"},
                        {"value": "inguinal_hernia_repair", "label": "Inguinal Hernia Repair"},
                        {"value": "sti", "label": "H/O STI"},
                    ],
                    "required": False,
                    "role_access": ["doctor", "embryologist", "andrologist", "admin"],
                },
                {
                    "id": "occupation",
                    "label": "Occupation",
                    "type": "text",
                    "placeholder": "Software Engineer / Business / etc.",
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "additional_notes",
                    "label": "Additional Notes",
                    "type": "textarea",
                    "rows": 2,
                    "placeholder": "Any other relevant history...",
                    "required": False,
                    "role_access": ["doctor", "embryologist", "andrologist", "admin"],
                },
            ],
        },
    ],
}

FOLLICULAR_SCAN_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "follicular_scan",
    "schema_version": "1.0",
    "title": "Follicular Scan",
    "description": "Ultrasound follicle monitoring data.",
    "sections": [
        {
            "id": "scan_details",
            "title": "Scan Details",
            "fields": [
                {
                    "id": "scan_date",
                    "label": "Scan Date",
                    "type": "date",
                    "required": True,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "cycle_day",
                    "label": "Cycle Day",
                    "type": "number",
                    "placeholder": "10",
                    "min": 1,
                    "max": 40,
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "uterine_lining",
                    "label": "Uterine Lining (mm)",
                    "type": "number",
                    "placeholder": "9.5",
                    "step": "0.1",
                    "required": False,
                    "role_access": ["doctor", "nurse", "admin"],
                },
                {
                    "id": "afc_left",
                    "label": "Antral Follicle Count — Left (AFC Left)",
                    "type": "number",
                    "placeholder": "6",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
                {
                    "id": "afc_right",
                    "label": "Antral Follicle Count — Right (AFC Right)",
                    "type": "number",
                    "placeholder": "7",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
                {
                    "id": "follicles_left",
                    "label": "Follicle Sizes — Left Ovary (mm, comma separated)",
                    "type": "text",
                    "placeholder": "18, 16, 14, 12",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
                {
                    "id": "follicles_right",
                    "label": "Follicle Sizes — Right Ovary (mm, comma separated)",
                    "type": "text",
                    "placeholder": "20, 17, 15",
                    "required": False,
                    "role_access": ["doctor", "admin"],
                },
            ],
        },
    ],
}

# --- NEW SCHEMAS FROM DOCX TEMPLATES ---

GYNAECOLOGY_HISTORY_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "gynaecology_history",
    "schema_version": "1.0",
    "title": "General Gynaecology History",
    "description": "Comprehensive gynaecological history intake and examinations.",
    "sections": [
        {
            "id": "complaints",
            "title": "Chief Complaints",
            "fields": [
                {"id": "presenting_complaints", "label": "Presenting Complaint(s)", "type": "textarea", "required": True, "role_access": ["doctor", "nurse", "admin"]},
                {"id": "duration_complaints", "label": "Duration", "type": "text", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "associated_symptoms", "label": "Associated Symptoms", "type": "textarea", "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "menstrual_history",
            "title": "Menstrual History",
            "fields": [
                {"id": "menarche_age", "label": "Age at Menarche", "type": "number", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "cycle_length_regularity", "label": "Cycle Length & Regularity", "type": "text", "placeholder": "28 days, regular", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "flow_duration", "label": "Duration of Flow (days)", "type": "number", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "flow_amount", "label": "Amount of Flow (pads/day)", "type": "text", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "dysmenorrhea_type", "label": "Dysmenorrhea Detail", "type": "text", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "lmp_gyn", "label": "LMP (Last Menstrual Period)", "type": "date", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "pmp_gyn", "label": "PMP (Previous Menstrual Period)", "type": "date", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "intermenstrual_bleeding", "label": "Intermenstrual Bleeding", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}], "role_access": ["doctor", "nurse", "admin"]},
                {"id": "postcoital_bleeding", "label": "Postcoital Bleeding", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}], "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "obstetric_gyn",
            "title": "Obstetric History",
            "fields": [
                {"id": "gpla", "label": "Gravida / Para / Living / Abortions", "type": "text", "placeholder": "G0 P0 L0 A0", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "delivery_modes", "label": "Modes of Delivery", "type": "textarea", "placeholder": "1. Normal vaginal delivery (2020), 2. CS (2023)...", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "obstetric_complications", "label": "Complications", "type": "textarea", "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "past_history_gyn",
            "title": "Past Medical & Surgical History",
            "fields": [
                {"id": "medical_conditions_gyn", "label": "Medical Conditions", "type": "checkbox_group", "options": [{"value": "diabetes", "label": "Diabetes"}, {"value": "hypertension", "label": "Hypertension"}, {"value": "thyroid", "label": "Thyroid"}, {"value": "tb", "label": "Tuberculosis"}, {"value": "cardiac", "label": "Cardiac Disease"}, {"value": "bleeding_disorders", "label": "Bleeding Disorders"}], "role_access": ["doctor", "nurse", "admin"]},
                {"id": "surgical_gyn", "label": "Surgical History", "type": "checkbox_group", "options": [{"value": "cs", "label": "CS"}, {"value": "tubal_ligation", "label": "Tubal Ligation"}, {"value": "hysterectomy", "label": "Hysterectomy"}, {"value": "laparotomy", "label": "Laparotomy/Laparoscopy"}], "role_access": ["doctor", "nurse", "admin"]},
                {"id": "allergies_gyn", "label": "Allergies", "type": "text", "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "screening",
            "title": "Screening History",
            "fields": [
                {"id": "last_pap_smear", "label": "Last Pap Smear (Date & Result)", "type": "text", "role_access": ["doctor", "admin"]},
                {"id": "last_mammogram", "label": "Last Mammogram (Date & Result)", "type": "text", "role_access": ["doctor", "admin"]},
                {"id": "hpv_vaccine", "label": "HPV Vaccination Status", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}, {"value": "partial", "label": "Partially Vaccinated"}], "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "exams_gyn",
            "title": "Systemic Examination",
            "role_access": ["doctor", "admin"],
            "role_badge": "Doctor Only",
            "fields": [
                {"id": "pa_exam", "label": "Per Abdomen (P/A) Inspection & Palpation", "type": "textarea", "role_access": ["doctor", "admin"]},
                {"id": "ps_exam", "label": "Per Speculum (P/S) Examination (Cervix/Vagina)", "type": "textarea", "role_access": ["doctor", "admin"]},
                {"id": "pv_exam", "label": "Per Vaginal (P/V) Examination (Uterus position/Adnexa)", "type": "textarea", "role_access": ["doctor", "admin"]},
                {"id": "gyn_provisional_diagnosis", "label": "Provisional Diagnosis", "type": "textarea", "required": True, "role_access": ["doctor", "admin"]},
                {"id": "investigations_advised", "label": "Investigations Advised", "type": "textarea", "role_access": ["doctor", "admin"]},
                {"id": "gyn_treatment_plan", "label": "Treatment Plan", "type": "textarea", "role_access": ["doctor", "admin"]},
            ]
        }
    ]
}

INFERTILITY_HISTORY_COMBINED_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "infertility_history_combined",
    "schema_version": "1.0",
    "title": "Combined Infertility Proforma",
    "description": "Comprehensive history intake for both male and female partners.",
    "sections": [
        {
            "id": "presenting_complaint_couple",
            "title": "Presenting Complaint (Both Partners)",
            "fields": [
                {"id": "infertility_duration", "label": "Duration of Infertility (years)", "type": "number", "required": True, "role_access": ["doctor", "nurse", "admin"]},
                {"id": "infertility_type", "label": "Infertility Type", "type": "select", "options": [{"value": "primary", "label": "Primary Infertility"}, {"value": "secondary", "label": "Secondary Infertility"}], "required": True, "role_access": ["doctor", "nurse", "admin"]},
                {"id": "marriage_duration", "label": "Duration of Marriage (years)", "type": "number", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "unprotected_duration", "label": "Duration of Unprotected Intercourse (years)", "type": "number", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "intercourse_frequency", "label": "Frequency/Timing of Intercourse", "type": "text", "placeholder": "2-3 times per week, mid-cycle focus", "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "female_hx_combined",
            "title": "Female Partner Clinical Profile",
            "fields": [
                {"id": "female_menstrual_hx", "label": "Female Menstrual History & Regularity", "type": "textarea", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "female_obstetric_hx", "label": "Female Obstetric History (G P L A)", "type": "text", "placeholder": "G0 P0 L0 A0", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "female_past_medical", "label": "Female Medical Conditions", "type": "checkbox_group", "options": [{"value": "pcos", "label": "PCOS"}, {"value": "endometriosis", "label": "Endometriosis"}, {"value": "thyroid", "label": "Thyroid"}, {"value": "tubal_block", "label": "Tubal Blockage"}, {"value": "genital_tb", "label": "Genital TB"}, {"value": "diabetes", "label": "Diabetes"}], "role_access": ["doctor", "nurse", "admin"]},
                {"id": "female_past_surgeries", "label": "Female Pelvic Surgeries", "type": "textarea", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "female_prev_fertility_tx", "label": "Previous Infertility Treatments (IUI, IVF, OI)", "type": "textarea", "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "male_hx_combined",
            "title": "Male Partner Clinical Profile",
            "fields": [
                {"id": "male_semen_hx", "label": "Previous Semen Findings (if any)", "type": "textarea", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "male_sexual_erectile", "label": "Sexual & Erectile History", "type": "text", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "male_past_medical", "label": "Male Medical Conditions", "type": "checkbox_group", "options": [{"value": "mumps", "label": "H/O Mumps/Orchitis"}, {"value": "varicocele", "label": "Varicocele"}, {"value": "cryptorchidism", "label": "Undescended Testes"}, {"value": "trauma", "label": "Testicular Trauma"}, {"value": "diabetes", "label": "Diabetes"}], "role_access": ["doctor", "nurse", "admin"]},
                {"id": "male_occupation_heat", "label": "Occupation & Heat/Toxin Exposure", "type": "text", "placeholder": "Laptop use, hot environment", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "male_lifestyle_habits", "label": "Male Lifestyle Habits", "type": "checkbox_group", "options": [{"value": "smoking", "label": "Smoking"}, {"value": "alcohol", "label": "Alcohol"}, {"value": "anabolic_steroids", "label": "Anabolic Steroids"}], "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "clinical_diagnoses_couple",
            "title": "Couples Examinations & Diagnoses",
            "role_access": ["doctor", "admin"],
            "role_badge": "Doctor Only",
            "fields": [
                {"id": "female_pv_exam_combined", "label": "Female Per Vaginal & Speculum Examination", "type": "textarea", "role_access": ["doctor", "admin"]},
                {"id": "male_genital_exam_combined", "label": "Male Genital Examination (Testes, Epididymis, Vas)", "type": "textarea", "role_access": ["doctor", "admin"]},
                {"id": "couple_diagnosis", "label": "Combined Provisional Diagnosis & Advice", "type": "textarea", "required": True, "role_access": ["doctor", "admin"]},
            ]
        }
    ]
}

CASA_SEMEN_ANALYSIS_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "semen_analysis_casa",
    "schema_version": "1.0",
    "title": "CASA Semen Analysis",
    "description": "Computer-Assisted Sperm Analysis Lab Report.",
    "sections": [
        {
            "id": "collection_details",
            "title": "Sample Collection Parameters",
            "fields": [
                {"id": "collection_date", "label": "Date of Collection", "type": "date", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "analysis_date", "label": "Date of Analysis", "type": "date", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "abstinence_period", "label": "Abstinence Period (days)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "time_to_analysis", "label": "Time to Analysis (min)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "collection_method", "label": "Collection Method", "type": "select", "options": [{"value": "masturbation_clinic", "label": "Masturbation at Clinic"}, {"value": "masturbation_home", "label": "Masturbation at Home"}, {"value": "coitus_sac", "label": "Coitus Sac"}], "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
            ]
        },
        {
            "id": "macroscopic",
            "title": "Macroscopic Evaluation",
            "fields": [
                {"id": "semen_volume", "label": "Volume (mL)", "type": "number", "step": "0.1", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "liquefaction_time", "label": "Liquefaction Time (min)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "semen_appearance", "label": "Appearance", "type": "text", "placeholder": "Grey-white / Yellowish", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "semen_ph", "label": "pH", "type": "number", "step": "0.1", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "semen_viscosity", "label": "Viscosity", "type": "select", "options": [{"value": "normal", "label": "Normal"}, {"value": "high", "label": "High"}, {"value": "very_high", "label": "Very High"}], "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
            ]
        },
        {
            "id": "casa_motility",
            "title": "CASA Motility Parameters",
            "fields": [
                {"id": "total_motility", "label": "Total Motility (%)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "progressive_motility", "label": "Progressive Motility (PR) (%)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "non_progressive_motility", "label": "Non-Progressive Motility (NP) (%)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "immotile", "label": "Immotile (%)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "velocity_vcl", "label": "Curvilinear Velocity (VCL) (µm/s)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "velocity_vsl", "label": "Straight-Line Velocity (VSL) (µm/s)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "velocity_vap", "label": "Average Path Velocity (VAP) (µm/s)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "linearity_lin", "label": "Linearity (LIN) (%)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "straightness_str", "label": "Straightness (STR) (%)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
            ]
        },
        {
            "id": "concentration_morphology",
            "title": "Concentration & Morphology",
            "fields": [
                {"id": "sperm_concentration", "label": "Sperm Concentration (million/mL)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "total_sperm_number", "label": "Total Sperm Number (million/ejaculate)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "normal_forms", "label": "Normal Morphology Forms (%)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "head_defects", "label": "Head Defects (%)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "tail_defects", "label": "Tail Defects (%)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "vitality_live", "label": "Vitality (Live Sperm) (%)", "type": "number", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
            ]
        },
        {
            "id": "interpretation",
            "title": "Lab Interpretation & Signature",
            "fields": [
                {"id": "additional_findings", "label": "Additional Findings (Agglutination, Debris, Round Cells, etc.)", "type": "textarea", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "lab_comments", "label": "Interpretation / Comments", "type": "textarea", "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
                {"id": "analyst_name", "label": "Analyzed By (Name / Signature)", "type": "text", "required": True, "role_access": ["doctor", "embryologist", "andrologist", "admin"]},
            ]
        }
    ]
}

OPU_PROCEDURE_NOTES_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "opu_procedure_notes",
    "schema_version": "1.0",
    "title": "OPU Clinical Procedure Notes",
    "description": "Surgical and recovery notes for oocyte retrieval.",
    "sections": [
        {
            "id": "team",
            "title": "Surgical Team",
            "fields": [
                {"id": "opu_surgeon", "label": "Surgeon / Doctor", "type": "text", "required": True, "role_access": ["doctor", "admin"]},
                {"id": "opu_anaesthetist", "label": "Anaesthetist", "type": "text", "role_access": ["doctor", "admin"]},
                {"id": "opu_assistant", "label": "Staff in Attendance", "type": "text", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "pre_op_ab", "label": "Pre-Op Antibiotic (e.g. Monocef 1g IV)", "type": "text", "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "procedure",
            "title": "Procedure Notes",
            "fields": [
                {"id": "positioning_drapes", "label": "Patient Positioning & Precautions", "type": "textarea", "placeholder": "Patient positioned in lithotomy after IV anaesthesia. Vaginal lavage with normal saline, ETO sterile disposable drapes.", "role_access": ["doctor", "admin"]},
                {"id": "oocyte_needle", "label": "Retrieval Needle Used", "type": "select", "options": [{"value": "17G_single", "label": "17G Single Lumen"}, {"value": "17G_double", "label": "17G Double Lumen"}, {"value": "18G_single", "label": "18G Single Lumen"}], "role_access": ["doctor", "admin"]},
                {"id": "opu_approach", "label": "Access Approach", "type": "select", "options": [{"value": "vaginal_fornices", "label": "Transvaginal via vaginal fornices"}, {"value": "transuterine", "label": "Transuterine"}, {"value": "transcervical", "label": "Transcervical"}], "role_access": ["doctor", "admin"]},
                {"id": "cervix_condition", "label": "P/S Cervix & Vagina Condition", "type": "select", "options": [{"value": "healthy", "label": "Vulva, Vagina, Cervix appear healthy"}, {"value": "ectropion", "label": "Ectropion noted"}, {"value": "hyperemic", "label": "Hyperemic / Inflammation"}], "role_access": ["doctor", "admin"]},
                {"id": "procedure_difficulty", "label": "Procedure Difficulty", "type": "select", "options": [{"value": "easy", "label": "Easy"}, {"value": "difficult", "label": "Difficult"}], "role_access": ["doctor", "admin"]},
                {"id": "ovary_mobility", "label": "Ovary Mobility", "type": "select", "options": [{"value": "mobile", "label": "Mobile"}, {"value": "fixed", "label": "Fixed / Adhered"}], "role_access": ["doctor", "admin"]},
                {"id": "oocytes_retrieved_count", "label": "Number of Oocytes Obtained", "type": "number", "required": True, "role_access": ["doctor", "admin"]},
                {"id": "free_fluid_check", "label": "Free Fluid", "type": "text", "role_access": ["doctor", "admin"]},
            ]
        },
        {
            "id": "management_advise",
            "title": "Post-Op Management Advice",
            "fields": [
                {"id": "advisory_basis", "label": "Management Basis", "type": "select", "options": [{"value": "op", "label": "OP basis management"}, {"value": "ip", "label": "IP basis management (Admission)"}], "required": True, "role_access": ["doctor", "admin"]},
                {"id": "ohss_prevention", "label": "OHSS Prophylactic Measures", "type": "checkbox_group", "options": [{"value": "no_fresh_et", "label": "No fresh ET (Freeze All)"}, {"value": "calcium_gluconate", "label": "IV Calcium Gluconate (10% 1 Amp in 100ml NS)"}, {"value": "cabergoline", "label": "Cabergoline 0.25mg BD x 8 days"}, {"value": "letrozole", "label": "Letrozole 2.5mg BD x 5 days"}, {"value": "clexane", "label": "Inj Clexane 40mg SC Daily x 2 days"}, {"value": "cetrotide", "label": "Inj Cetrotide 0.25mg SC x 3 days"}], "role_access": ["doctor", "admin"]},
                {"id": "post_op_meds", "label": "Post-Op Medications List", "type": "textarea", "placeholder": "Tab Pan 40 OD x 8 days, Syp Totalax 3 spoons BD x 7 days, Tab Meprate 10mg BD x 15 days.", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "dietary_instructions", "label": "Dietary & Fluid Advice", "type": "textarea", "placeholder": "Oral fluids 4 litres/day. Egg whites 4/day. Biscuits 4/day.", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "investigations_advised", "label": "Daily / Today Investigations", "type": "checkbox_group", "options": [{"value": "haemogram", "label": "Haemogram"}, {"value": "urea", "label": "Blood Urea"}, {"value": "creatinine", "label": "Serum Creatinine"}, {"value": "lft", "label": "LFT"}, {"value": "electrolytes", "label": "Serum Electrolytes"}], "role_access": ["doctor", "nurse", "admin"]},
                {"id": "follow_up_notes", "label": "Next Appointment / Follow-up", "type": "text", "placeholder": "Follow-up on (Day 2-3) of period. Embryology report on Day 8.", "role_access": ["doctor", "nurse", "admin"]},
            ]
        }
    ]
}

OPU_PROFORMA_RECORD_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "opu_proforma_record",
    "schema_version": "1.0",
    "title": "OPU Retrieval Record (ART Act 2021)",
    "description": "Stimulation summary, retrieval parameters, oocyte yield, and donor details.",
    "sections": [
        {
            "id": "ident_consent",
            "title": "Cycle Ident & Pre-procedure Consent",
            "fields": [
                {"id": "oocyte_source", "label": "Oocyte Source", "type": "select", "options": [{"value": "self", "label": "Self"}, {"value": "donor", "label": "Donor"}], "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "sperm_source", "label": "Sperm Source", "type": "select", "options": [{"value": "partner", "label": "Partner"}, {"value": "donor", "label": "Donor"}], "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "consent_form_21", "label": "Oocyte Retrieval Consent (Form 21)", "type": "select", "options": [{"value": "obtained", "label": "Obtained & Verified"}, {"value": "pending", "label": "Pending"}], "required": True, "role_access": ["doctor", "nurse", "admin"]},
                {"id": "pre_treatment_counseling", "label": "Pre-treatment Counselling", "type": "select", "options": [{"value": "done", "label": "Done"}, {"value": "not_done", "label": "Not Done"}], "role_access": ["doctor", "nurse", "admin"]},
                {"id": "wristband_check", "label": "ID/Wristband Check", "type": "select", "options": [{"value": "verified", "label": "Verified"}, {"value": "unverified", "label": "Unverified"}], "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "stimulation_summary",
            "title": "Clinical Stimulation Summary",
            "fields": [
                {"id": "protocol_type", "label": "Stimulation Protocol", "type": "select", "options": [{"value": "antagonist", "label": "Antagonist Protocol"}, {"value": "long_agonist", "label": "Long Agonist Protocol"}, {"value": "short_agonist", "label": "Short Agonist Protocol"}], "role_access": ["doctor", "admin"]},
                {"id": "stim_start_date", "label": "Stimulation Start Date", "type": "date", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "stim_days", "label": "Stimulation Days", "type": "number", "role_access": ["doctor", "nurse", "admin"]},
                {"id": "gonadotropin_type", "label": "Gonadotropin Type", "type": "text", "placeholder": "rFSH, hMG", "role_access": ["doctor", "admin"]},
                {"id": "gonadotropin_dose", "label": "Total Gonadotropin Dose (IU)", "type": "number", "role_access": ["doctor", "admin"]},
                {"id": "trigger_type", "label": "Trigger Type", "type": "select", "options": [{"value": "hcg", "label": "hCG"}, {"value": "agonist", "label": "Agonist"}, {"value": "dual", "label": "Dual Trigger"}], "role_access": ["doctor", "admin"]},
                {"id": "trigger_datetime", "label": "Trigger Date & Time", "type": "text", "placeholder": "dd-mm-yyyy hh:mm", "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "oocyte_donor_sec",
            "title": "Donor Details (ART Act 2021 Compliance)",
            "fields": [
                {"id": "donor_id", "label": "Donor ID / Reference Number", "type": "text", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "donor_age", "label": "Donor Age (Limit: 23-35 years)", "type": "number", "min": 23, "max": 35, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "donor_consent_form_23", "label": "Donor Consent (Form 23)", "type": "select", "options": [{"value": "on_file", "label": "On File & Signed"}, {"value": "pending", "label": "Pending"}], "role_access": ["doctor", "admin"]},
                {"id": "registered_art_bank", "label": "Sourced via Registered ART Bank", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}], "role_access": ["doctor", "admin"]},
                {"id": "donor_insurance_validity", "label": "Donor 12-Month Insurance Policy (IRDAI compliant)", "type": "select", "options": [{"value": "active", "label": "Active Policy on File"}, {"value": "no", "label": "Not Active"}], "role_access": ["doctor", "admin"]},
                {"id": "insurance_policy_number", "label": "Policy Number & Validity Date", "type": "text", "role_access": ["doctor", "admin"]},
            ]
        },
        {
            "id": "witnessing_sign",
            "title": "Retrieval Sign-off & Witnessing",
            "fields": [
                {"id": "double_witnessing", "label": "Double Witnessing Done at Labelling", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}], "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "witness_name", "label": "Witness Name / Signature", "type": "text", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "adverse_events", "label": "Adverse Events Recorded", "type": "textarea", "placeholder": "None / specify if bleeding, injury, etc.", "role_access": ["doctor", "embryologist", "admin"]},
            ]
        }
    ]
}

CRYO_PROFORMA_RECORD_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "cryo_proforma_record",
    "schema_version": "1.0",
    "title": "Cryopreservation & Storage Record",
    "description": "Vitrification freezes, tank inventory log, and thawing survival parameters.",
    "sections": [
        {
            "id": "freeze_event",
            "title": "Freezing Event Parameters",
            "fields": [
                {"id": "cryo_target", "label": "What is Frozen", "type": "select", "options": [{"value": "embryos", "label": "Embryos"}, {"value": "oocytes", "label": "Oocytes"}, {"value": "sperm", "label": "Sperm"}], "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "freeze_date", "label": "Freeze Date", "type": "date", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "freezing_method", "label": "Method", "type": "select", "options": [{"value": "vitrification", "label": "Vitrification (Fast)"}, {"value": "slow", "label": "Slow Freezing"}], "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "freeze_kit_lot", "label": "Kit / Media Lot Number", "type": "text", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "straws_used_count", "label": "Straws / Devices Used", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "freeze_consent_form", "label": "Freezing Consent F15/F16", "type": "select", "options": [{"value": "obtained", "label": "Obtained"}, {"value": "pending", "label": "Pending"}], "required": True, "role_access": ["doctor", "nurse", "admin"]},
            ]
        },
        {
            "id": "storage_monitoring",
            "title": "Cryo Can Storage Location & LN2 Safety",
            "fields": [
                {"id": "tank_dewar_id", "label": "Tank / Dewar ID", "type": "text", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "tank_type", "label": "Tank Type", "type": "select", "options": [{"value": "vapour", "label": "Vapour Phase"}, {"value": "liquid", "label": "Liquid Phase"}], "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "current_ln2_level", "label": "Current LN2 Level (mm/cm)", "type": "text", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "last_topup_date", "label": "Last LN2 Top-Up Date", "type": "date", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "next_topup_due", "label": "Next Top-Up Due Date", "type": "date", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "local_alarm_fitted", "label": "Local Alarm Fitted (ART Rules 2022)", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}], "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "autodialer_alarm", "label": "Autodialer / Remote Alarm Operational", "type": "select", "options": [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}], "role_access": ["doctor", "embryologist", "admin"]},
            ]
        },
        {
            "id": "consent_disposition",
            "title": "Consent Validity & Expiry Disposition",
            "fields": [
                {"id": "storage_start_date", "label": "Storage Start Date", "type": "date", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "consent_valid_until", "label": "Consent Valid Till Date", "type": "date", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "annual_review_date", "label": "Next Annual Review Date", "type": "date", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "action_on_expiry", "label": "Action Approved on Expiry/Withdrawal", "type": "select", "options": [{"value": "discard", "label": "Discard Straws"}, {"value": "donate", "label": "Donate to Research"}, {"value": "transfer", "label": "Transfer Out"}], "role_access": ["doctor", "admin"]},
                {"id": "double_witness_cryo", "label": "Double Witness Verified", "type": "text", "placeholder": "Witness clinician / Embryologist name", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
            ]
        }
    ]
}

EMBRYOLOGY_PROFORMA_RECORD_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "embryology_proforma_record",
    "schema_version": "1.0",
    "title": "Embryology Record",
    "description": "Denudation, insemination methods, Day-1 fertilization, embryo development charts, and ET logs.",
    "sections": [
        {
            "id": "retrieve_summary",
            "title": "Stimulation & Retrieval Summary",
            "fields": [
                {"id": "amh_level", "label": "AMH (ng/mL)", "type": "number", "step": "0.01", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "afc_count", "label": "Antral Follicle Count (AFC)", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "opu_datetime_emb", "label": "OPU Date & Time", "type": "text", "placeholder": "dd-mm-yyyy hh:mm", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "denudation_time", "label": "Denudation Time (ICSI)", "type": "text", "placeholder": "hh:mm", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "coc_retrieved_emb", "label": "Total COC Retrieved", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
            ]
        },
        {
            "id": "oocyte_assessment",
            "title": "Day 0 Oocyte Maturity Assessment",
            "fields": [
                {"id": "m_ii_mature", "label": "M II (Mature) Count", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "m_i_count", "label": "M I Count", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "gv_germinal_vesicle", "label": "GV (Germinal Vesicle) Count", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "atretic_count", "label": "Atretic Count", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "degenerate_count", "label": "Degenerate Count", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "oocyte_quality_desc", "label": "General Oocyte Quality & Remarks", "type": "text", "placeholder": "Good / Fair / Cytoplasmic granularity...", "role_access": ["doctor", "embryologist", "admin"]},
            ]
        },
        {
            "id": "andrology_sperm_prep",
            "title": "Andrology Semen Prep Summary",
            "fields": [
                {"id": "sample_type_prep", "label": "Sample Type", "type": "select", "options": [{"value": "fresh", "label": "Fresh Ejaculate"}, {"value": "frozen", "label": "Frozen-Thaw"}, {"value": "surgical", "label": "Surgical (TESA/TESE)"}, {"value": "donor", "label": "Donor"}], "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "prep_method", "label": "Preparation Method", "type": "select", "options": [{"value": "gradient", "label": "Density Gradient"}, {"value": "swim_up", "label": "Swim-Up"}, {"value": "wash", "label": "Simple Wash"}, {"value": "microfluidics", "label": "Microfluidic Chip selection"}], "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "pre_wash_conc", "label": "Pre-Wash Concentration (million/mL)", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "pre_wash_motility", "label": "Pre-Wash Motility (%)", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "post_prep_conc", "label": "Post-Prep Concentration (million/mL)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "post_prep_motility", "label": "Post-Prep Motility (%)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
            ]
        },
        {
            "id": "insemination_check",
            "title": "Insemination Parameters & Day-1 Fert Check",
            "fields": [
                {"id": "insemination_method", "label": "Insemination Method", "type": "select", "options": [{"value": "conventional_ivf", "label": "Conventional IVF"}, {"value": "icsi", "label": "ICSI"}, {"value": "split", "label": "Split (IVF + ICSI)"}], "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "insemination_datetime", "label": "Insemination Date & Time", "type": "text", "placeholder": "dd-mm-yyyy hh:mm", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "oocytes_inseminated_count", "label": "No. of Oocytes Inseminated/Injected", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "fert_check_datetime", "label": "Day-1 Fert Check Date & Time", "type": "text", "placeholder": "dd-mm-yyyy hh:mm", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "fert_2pn_normal", "label": "Normal Fertilisation (2PN)", "type": "number", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "fert_1pn", "label": "Abnormal (1PN)", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "fert_3pn", "label": "Abnormal (3PN+)", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "fert_degenerate", "label": "Degenerate post-ICSI", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
            ]
        },
        {
            "id": "embryo_transfer_log",
            "title": "Embryo Transfer (ET) Clinic Notes",
            "fields": [
                {"id": "et_date", "label": "Embryo Transfer Date", "type": "date", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "et_day", "label": "Transfer Day", "type": "select", "options": [{"value": "day_2", "label": "Day 2"}, {"value": "day_3", "label": "Day 3 (Cleavage)"}, {"value": "day_5", "label": "Day 5 (Blastocyst)"}, {"value": "day_6", "label": "Day 6"}], "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "et_transferred_count", "label": "Number of Embryos Transferred", "type": "number", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "et_endometrium_thickness", "label": "Endometrium Thickness (mm)", "type": "number", "step": "0.1", "role_access": ["doctor", "admin"]},
                {"id": "et_transferred_grades", "label": "Embryos Transferred (IDs & Grades)", "type": "text", "placeholder": "Embryo 1 (4AA), Embryo 3 (3BB)", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "et_catheter", "label": "Transfer Catheter Used", "type": "text", "role_access": ["doctor", "embryologist", "admin"]},
                {"id": "et_difficulty", "label": "Transfer Difficulty", "type": "select", "options": [{"value": "easy", "label": "Easy"}, {"value": "moderate", "label": "Moderate"}, {"value": "difficult", "label": "Difficult"}], "role_access": ["doctor", "admin"]},
                {"id": "et_clinician", "label": "Transfer Clinician / Doctor", "type": "text", "role_access": ["doctor", "admin"]},
                {"id": "et_witness", "label": "Double Witness Verified By", "type": "text", "required": True, "role_access": ["doctor", "embryologist", "admin"]},
            ]
        }
    ]
}


# Treatment Cycle Workflow State Machine Configuration
CYCLE_WORKFLOW_CONFIGS = {
    "icsi": {
        "label": "ICSI (Antagonist Protocol)",
        "steps": [
            {"id": "stimulation", "label": "Stimulation", "icon": "syringe"},
            {"id": "trigger", "label": "Trigger", "icon": "bolt"},
            {"id": "opu", "label": "OPU", "icon": "egg"},
            {"id": "embryology", "label": "Embryology", "icon": "flask"},
            {"id": "transfer", "label": "Transfer / Freeze", "icon": "heart-pulse"},
            {"id": "beta_hcg", "label": "Beta HCG", "icon": "vial"},
        ],
    },
    "oi": {
        "label": "OI (Ovulation Induction)",
        "steps": [
            {"id": "stimulation", "label": "Stimulation", "icon": "syringe"},
            {"id": "trigger", "label": "Trigger", "icon": "bolt"},
            {"id": "timed_intercourse", "label": "Timed Intercourse", "icon": "calendar"},
            {"id": "luteal_support", "label": "Luteal Support", "icon": "pills"},
            {"id": "pregnancy_test", "label": "Pregnancy Test", "icon": "vial"},
        ],
    },
    "iui": {
        "label": "IUI / IUI-D",
        "steps": [
            {"id": "stimulation", "label": "Stimulation", "icon": "syringe"},
            {"id": "trigger", "label": "Trigger", "icon": "bolt"},
            {"id": "semen_prep", "label": "Semen Prep", "icon": "microscope"},
            {"id": "iui_procedure", "label": "IUI Procedure", "icon": "medical"},
            {"id": "luteal_support", "label": "Luteal Support", "icon": "pills"},
            {"id": "pregnancy_test", "label": "Pregnancy Test", "icon": "vial"},
        ],
    },
    "fet": {
        "label": "FET (Frozen Embryo Transfer)",
        "steps": [
            {"id": "preparation", "label": "Preparation", "icon": "snowflake"},
            {"id": "lining_check", "label": "Lining Check", "icon": "scan"},
            {"id": "transfer", "label": "Transfer", "icon": "heart-pulse"},
            {"id": "luteal_support", "label": "Luteal Support", "icon": "pills"},
            {"id": "beta_hcg", "label": "Beta HCG", "icon": "vial"},
        ],
    },
}

# Checklist templates per procedure
CHECKLIST_TEMPLATES = {
    "opu_prep": {
        "label": "OPU Pre-op Checklist",
        "items": [
            {"id": "pac_clearance", "label": "PAC Clearance Documented", "description": "Cleared by Anesthesiologist"},
            {"id": "art_consents", "label": "ART Consents Signed", "description": "Both H & W signatures verified"},
            {"id": "partner_sample", "label": "Partner Semen Sample Backup", "description": "Ensure frozen sample is available in Lab"},
            {"id": "nbm", "label": "Fasting Confirmed (NBM)", "description": "Patient must be NBM for 6-8 hours prior"},
            {"id": "iv_access", "label": "IV Access Established", "description": "18G cannula in situ"},
            {"id": "prophylactic_ab", "label": "Prophylactic Antibiotics Given", "description": "As per protocol"},
        ],
    },
    "embryo_transfer": {
        "label": "Embryo Transfer Checklist",
        "items": [
            {"id": "embryo_confirmed", "label": "Embryo Grade Confirmed", "description": "Embryologist sign-off"},
            {"id": "uterine_check", "label": "Uterine Lining ≥ 8mm", "description": "Confirmed by scan"},
            {"id": "consents_signed", "label": "Transfer Consent Signed", "description": "Both partners"},
            {"id": "bladder_full", "label": "Bladder Comfortably Full", "description": "For abdominal scan guidance"},
            {"id": "catheter_ready", "label": "Transfer Catheter Ready", "description": "Wallace / Labotect loaded"},
        ],
    },
    "hysteroscopy": {
        "label": "Hysteroscopy Pre-op Checklist",
        "items": [
            {"id": "fasting", "label": "Fasting for 6+ Hours", "description": "NBM confirmed"},
            {"id": "consent", "label": "Procedure Consent Signed", "description": "Risks explained"},
            {"id": "pre_op_labs", "label": "Pre-op Labs Done", "description": "CBC, Coagulation profile"},
            {"id": "distension_media", "label": "Distension Media Ready", "description": "Normal saline checked"},
        ],
    },
    "laparoscopy": {
        "label": "Laparoscopy Pre-op Checklist",
        "items": [
            {"id": "fasting", "label": "Fasting for 8+ Hours", "description": "NBM confirmed"},
            {"id": "consent", "label": "Operative Consent Signed", "description": "Procedure risks explained"},
            {"id": "pre_op_labs", "label": "Pre-op Labs & ECG Done", "description": "CBC, LFT, KFT, ECG"},
            {"id": "dvt_prophylaxis", "label": "DVT Prophylaxis", "description": "Compression stockings in place"},
        ],
    },
}

DIAGNOSTICS_SCAN_TAGS = [
    {"value": "pelvic_3d_ns", "label": "Pelvic Scan 3D NS", "category": "pelvic"},
    {"value": "pelvic_2d_tvs", "label": "Pelvic Scan 2D TVS", "category": "pelvic"},
    {"value": "pelvic_2d_tas", "label": "Pelvic Scan 2D TAS", "category": "pelvic"},
    {"value": "follicular_scan", "label": "Follicular Scan", "category": "follicular"},
    {"value": "sono_salpingogram", "label": "Sono-salpingogram (SSG)", "category": "procedure"},
    {"value": "pregnancy_early", "label": "Pregnancy Scan — Early", "category": "pregnancy"},
    {"value": "pregnancy_2nd_trimester", "label": "Pregnancy Scan — 2nd Trimester", "category": "pregnancy"},
    {"value": "pregnancy_3rd_trimester", "label": "Pregnancy Scan — 3rd Trimester", "category": "pregnancy"},
    {"value": "semen_analysis", "label": "Semen Analysis Report", "category": "andrology"},
    {"value": "hormonal_profile", "label": "Hormonal Profile", "category": "lab"},
    {"value": "genetic_report", "label": "Genetic / Karyotype Report", "category": "lab"},
    {"value": "consent_art", "label": "ART Consent Form", "category": "consent"},
    {"value": "previous_rx", "label": "Previous Prescription", "category": "rx"},
]


# -------------------------------------------------------------
# ADDITIONAL USG, DIAGNOSTIC & ANDROLOGY TEMPLATES
# -------------------------------------------------------------

PELVIC_ORGAN_USG_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "pelvic_organ_usg",
    "schema_version": "1.0",
    "title": "Pelvic Organ Ultrasound Scan",
    "description": "Comprehensive transvaginal / transabdominal pelvic examination.",
    "sections": [
        {
            "id": "uterus_assessment",
            "title": "Uterine Assessment",
            "fields": [
                {"id": "scan_approach", "label": "Scan Approach", "type": "select", "options": [{"value": "tvs", "label": "Transvaginal (TVS)"}, {"value": "tas", "label": "Transabdominal (TAS)"}, {"value": "both", "label": "Both TVS & TAS"}], "required": True},
                {"id": "uterus_position", "label": "Uterine Position", "type": "select", "options": [{"value": "anteverted", "label": "Anteverted"}, {"value": "retroverted", "label": "Retroverted"}, {"value": "axial", "label": "Axial"}], "required": True},
                {"id": "uterus_length_mm", "label": "Length (mm)", "type": "number", "placeholder": "75"},
                {"id": "uterus_width_mm", "label": "Width (mm)", "type": "number", "placeholder": "45"},
                {"id": "uterus_ap_mm", "label": "AP Diameter (mm)", "type": "number", "placeholder": "40"},
                {"id": "myometrium", "label": "Myometrium Echotexture", "type": "select", "options": [{"value": "homogeneous", "label": "Homogeneous / Normal"}, {"value": "heterogeneous", "label": "Heterogeneous / Adenomyosis signs"}, {"value": "fibroid", "label": "Fibroid(s) Present"}]},
                {"id": "fibroid_details", "label": "Fibroid Details / FIGO Classification", "type": "textarea", "placeholder": "Single intramural fibroid 2.5cm in posterior wall (FIGO 4)..."},
            ]
        },
        {
            "id": "endometrium_adnexa",
            "title": "Endometrium & Adnexa",
            "fields": [
                {"id": "endometrial_thickness_mm", "label": "Endometrial Thickness (mm)", "type": "number", "placeholder": "8.5", "required": True},
                {"id": "endometrial_pattern", "label": "Endometrial Pattern", "type": "select", "options": [{"value": "trilaminar", "label": "Trilaminar (Triple Line)"}, {"value": "homogeneous_hyperechoic", "label": "Homogeneous / Secretory"}, {"value": "irregular", "label": "Irregular / Cystic"}]},
                {"id": "right_ovary_dimensions", "label": "Right Ovary (L x W x AP mm)", "type": "text", "placeholder": "32 x 20 x 18 mm"},
                {"id": "right_ovary_afc", "label": "Right Ovary AFC", "type": "number", "placeholder": "8"},
                {"id": "left_ovary_dimensions", "label": "Left Ovary (L x W x AP mm)", "type": "text", "placeholder": "30 x 19 x 16 mm"},
                {"id": "left_ovary_afc", "label": "Left Ovary AFC", "type": "number", "placeholder": "7"},
                {"id": "pod_free_fluid", "label": "Pouch of Douglas (POD) Free Fluid", "type": "select", "options": [{"value": "none", "label": "None"}, {"value": "minimal", "label": "Minimal / Physiological"}, {"value": "moderate_excess", "label": "Moderate / Pathological"}]},
                {"id": "sonographer_impression", "label": "Overall Impression", "type": "textarea", "placeholder": "Normal pelvic scan with good bilateral ovarian reserve...", "required": True}
            ]
        }
    ]
}

SONOHYSTEROGRAM_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "sonohysterogram",
    "schema_version": "1.0",
    "title": "Saline Infusion Sonohysterography (SIS)",
    "description": "Endometrial cavity and tubal patency evaluation using sterile saline infusion.",
    "sections": [
        {
            "id": "procedure_cavity",
            "title": "Cavity & Tubal Assessment",
            "fields": [
                {"id": "catheter_used", "label": "Catheter Type", "type": "text", "placeholder": "Insemination / Balloon Catheter 5F"},
                {"id": "saline_volume_ml", "label": "Saline Volume Infused (mL)", "type": "number", "placeholder": "10"},
                {"id": "cavity_distension", "label": "Cavity Distension", "type": "select", "options": [{"value": "adequate", "label": "Adequate Distension"}, {"value": "poor", "label": "Poor / Incomplete Distension"}]},
                {"id": "cavity_contour", "label": "Cavity Contour", "type": "select", "options": [{"value": "regular_normal", "label": "Smooth & Regular (Normal)"}, {"value": "polyp", "label": "Endometrial Polyp(s)"}, {"value": "submucosal_fibroid", "label": "Submucosal Fibroid"}, {"value": "synechiae", "label": "Intrauterine Adhesions / Synechiae"}, {"value": "septum", "label": "Uterine Septum"}]},
                {"id": "lesion_dimensions", "label": "Lesion Dimensions / Location", "type": "text", "placeholder": "e.g. 8x5mm pedunculated polyp at fundus"},
                {"id": "right_tube_patency", "label": "Right Tubal Spill", "type": "select", "options": [{"value": "patent", "label": "Patent (Immediate Spill Seen)"}, {"value": "blocked", "label": "Blocked / No Spill"}, {"value": "indeterminate", "label": "Indeterminate"}]},
                {"id": "left_tube_patency", "label": "Left Tubal Spill", "type": "select", "options": [{"value": "patent", "label": "Patent (Immediate Spill Seen)"}, {"value": "blocked", "label": "Blocked / No Spill"}, {"value": "indeterminate", "label": "Indeterminate"}]},
                {"id": "patient_tolerance", "label": "Patient Tolerance / Pain Score", "type": "select", "options": [{"value": "mild", "label": "Mild Discomfort (VAS 1-3)"}, {"value": "moderate", "label": "Moderate Cramping (VAS 4-6)"}, {"value": "severe", "label": "Severe Pain (VAS 7-10)"}]},
                {"id": "sis_impression", "label": "Impression & Plan", "type": "textarea", "required": True}
            ]
        }
    ]
}

ENDOMETRIAL_ASSESSMENT_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "endometrial_assessment",
    "schema_version": "1.0",
    "title": "Endometrial Receptivity Assessment Scan",
    "description": "Serial Doppler & morphological assessment for FET / IUI cycle monitoring.",
    "sections": [
        {
            "id": "lining_parameters",
            "title": "Endometrial Receptivity Parameters",
            "fields": [
                {"id": "cycle_day", "label": "Day of Cycle / Progesterone Day", "type": "text", "placeholder": "Day 14 or P+0"},
                {"id": "lining_thickness_mm", "label": "Thickness (mm)", "type": "number", "placeholder": "9.2", "required": True},
                {"id": "triple_line_pattern", "label": "Triple Line (Multilayered)", "type": "select", "options": [{"value": "type_a_distinct", "label": "Type A — Distinct Triple Line (Optimal)"}, {"value": "type_b_isoechoic", "label": "Type B — Isoechoic / Moderate"}, {"value": "type_c_hyperechoic", "label": "Type C — Hyperechoic / Secretory"}]},
                {"id": "subendometrial_vascularity", "label": "Sub-endometrial Blood Flow", "type": "select", "options": [{"value": "zone_3_intra", "label": "Zone 3/4 — Intra-endometrial flow (Optimal)"}, {"value": "zone_2_sub", "label": "Zone 2 — Sub-endometrial border flow"}, {"value": "zone_1_outer", "label": "Zone 1 — Outer myometrial junction only"}, {"value": "zone_0_absent", "label": "Zone 0 — Absent vascularity"}]},
                {"id": "uterine_artery_ri", "label": "Uterine Artery Resistance Index (RI)", "type": "number", "placeholder": "0.72"},
                {"id": "uterine_artery_pi", "label": "Uterine Artery Pulsatility Index (PI)", "type": "number", "placeholder": "1.85"},
                {"id": "endometrial_readiness", "label": "Receptivity Decision", "type": "select", "options": [{"value": "ready", "label": "Ready for Trigger / Progesterone Start"}, {"value": "continue_estrogen", "label": "Extend Estrogen Prime 3-5 Days"}, {"value": "cancel_cycle", "label": "Sub-optimal Lining — Cancel / Postpone"}]},
                {"id": "remarks", "label": "Remarks & Instructions", "type": "textarea"}
            ]
        }
    ]
}

EARLY_PREGNANCY_SCAN_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "early_pregnancy_scan",
    "schema_version": "1.0",
    "title": "Early Pregnancy Ultrasound Scan Report",
    "description": "Viability and gestational assessment post-ART conception.",
    "sections": [
        {
            "id": "gestation_details",
            "title": "Gestational Sac & Embryo Viability",
            "fields": [
                {"id": "scan_date", "label": "Date of Scan", "type": "date", "required": True},
                {"id": "gestational_age_weeks", "label": "Calculated GA by ET/LMP (Wks + Days)", "type": "text", "placeholder": "6w 4d", "required": True},
                {"id": "sac_location", "label": "Sac Location", "type": "select", "options": [{"value": "intrauterine", "label": "Intrauterine (Normal)"}, {"value": "ectopic_tubal", "label": "Ectopic — Tubal"}, {"value": "ectopic_cornual", "label": "Ectopic — Cornual / Interstitial"}, {"value": "cervical_scar", "label": "Caesarean Scar Pregnancy"}]},
                {"id": "number_of_sacs", "label": "Number of Gestational Sacs", "type": "number", "placeholder": "1", "required": True},
                {"id": "mean_sac_diameter_mm", "label": "Mean Sac Diameter (MSD mm)", "type": "number", "placeholder": "18.5"},
                {"id": "yolk_sac", "label": "Yolk Sac", "type": "select", "options": [{"value": "present_normal", "label": "Present & Normal (3-5mm)"}, {"value": "enlarged", "label": "Enlarged (>6mm)"}, {"value": "absent", "label": "Absent"}]},
                {"id": "fetal_pole", "label": "Fetal Pole", "type": "select", "options": [{"value": "present", "label": "Present"}, {"value": "not_yet_seen", "label": "Not Yet Visualized"}]},
                {"id": "crl_mm", "label": "Crown-Rump Length (CRL mm)", "type": "number", "placeholder": "7.2"},
                {"id": "cardiac_activity", "label": "Fetal Cardiac Activity", "type": "select", "options": [{"value": "present_regular", "label": "Present & Regular"}, {"value": "absent", "label": "Absent"}, {"value": "bradycardia", "label": "Bradycardia (<100 bpm)"}]},
                {"id": "fhr_bpm", "label": "Fetal Heart Rate (bpm)", "type": "number", "placeholder": "128"},
                {"id": "subchorionic_hematoma", "label": "Subchorionic Bleed / Hematoma", "type": "select", "options": [{"value": "none", "label": "None"}, {"value": "small", "label": "Small (<20% of sac)"}, {"value": "moderate_large", "label": "Moderate / Large (>20% of sac)"}]},
                {"id": "adnexa_corpus_luteum", "label": "Corpus Luteum / Ovaries", "type": "text", "placeholder": "Normal right corpus luteum 22mm, no free fluid"},
                {"id": "impression", "label": "Impression", "type": "textarea", "placeholder": "Single live intrauterine gestation corresponding to 6 weeks 4 days...", "required": True}
            ]
        }
    ]
}

SPERM_DFI_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "sperm_dfi",
    "schema_version": "1.0",
    "title": "Sperm DNA Fragmentation Index (DFI) Report",
    "description": "Chromatin dispersion / Halosperm assay for male fertility evaluation.",
    "sections": [
        {
            "id": "dfi_metrics",
            "title": "DNA Fragmentation Classification",
            "fields": [
                {"id": "test_date", "label": "Test Date", "type": "date", "required": True},
                {"id": "method_used", "label": "Assay Method", "type": "select", "options": [{"value": "scd_halosperm", "label": "Sperm Chromatin Dispersion (SCD / Halosperm)"}, {"value": "tunel", "label": "TUNEL Assay"}, {"value": "spsa", "label": "SCSA (Flow Cytometry)"}]},
                {"id": "big_halo_pct", "label": "Big Halo (Intact DNA) %", "type": "number", "placeholder": "55"},
                {"id": "medium_halo_pct", "label": "Medium Halo (Intact DNA) %", "type": "number", "placeholder": "25"},
                {"id": "small_halo_pct", "label": "Small Halo (Fragmented) %", "type": "number", "placeholder": "12"},
                {"id": "without_halo_pct", "label": "Without Halo (Fragmented) %", "type": "number", "placeholder": "6"},
                {"id": "degraded_pct", "label": "Degraded Sperm %", "type": "number", "placeholder": "2"},
                {"id": "total_dfi_pct", "label": "Total DFI (% Fragmented)", "type": "number", "placeholder": "20", "required": True},
                {"id": "dfi_interpretation", "label": "DFI Category", "type": "select", "options": [{"value": "excellent", "label": "< 15% — Excellent DNA Integrity"}, {"value": "good", "label": "15-25% — Good / Acceptable Fertility Potential"}, {"value": "high_risk", "label": "> 25-30% — High DNA Damage (ICSI / Antioxidant therapy recommended)"}, {"value": "severe", "label": "> 30% — Severe DNA Fragmentation (MACS / Microfluidic selection indicated)"}], "required": True},
                {"id": "lab_comments", "label": "Analyst Comments & Clinical Recommendations", "type": "textarea"}
            ]
        }
    ]
}

SPERM_PREPARATION_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "sperm_preparation",
    "schema_version": "1.0",
    "title": "Sperm Preparation & Recovery Record",
    "description": "Pre-processing vs Post-processing semen analysis for IUI / IVF / ICSI.",
    "sections": [
        {
            "id": "pre_process",
            "title": "Pre-Processing Semen Parameters",
            "fields": [
                {"id": "collection_time", "label": "Collection Time", "type": "text", "placeholder": "09:15 AM"},
                {"id": "abstinence_days", "label": "Abstinence (Days)", "type": "number", "placeholder": "3"},
                {"id": "volume_ml", "label": "Ejaculate Volume (mL)", "type": "number", "placeholder": "3.0"},
                {"id": "liquefaction_mins", "label": "Liquefaction Time (min)", "type": "number", "placeholder": "20"},
                {"id": "pre_conc_million_ml", "label": "Pre-wash Concentration (M/mL)", "type": "number", "placeholder": "45"},
                {"id": "pre_total_motility_pct", "label": "Pre-wash Total Motility (%)", "type": "number", "placeholder": "55"},
                {"id": "pre_rapid_progressive_pct", "label": "Pre-wash Grade A / Rapid PR (%)", "type": "number", "placeholder": "35"},
                {"id": "pre_morphology_normal_pct", "label": "Pre-wash Normal Forms (%)", "type": "number", "placeholder": "4"},
            ]
        },
        {
            "id": "post_process",
            "title": "Processing Method & Post-Wash Yield",
            "fields": [
                {"id": "prep_method", "label": "Preparation Method", "type": "select", "options": [{"value": "density_gradient", "label": "Double Density Gradient (40/80% Sil-Select)"}, {"value": "swim_up", "label": "Direct Swim-Up"}, {"value": "microfluidic_chip", "label": "Microfluidic Sperm Separation (Zymōt)"}, {"value": "simple_wash", "label": "Centrifugal Pellet Wash"}], "required": True},
                {"id": "media_used", "label": "Washing Media & Lot #", "type": "text", "placeholder": "SpermRinse / FertiCult Lot #4421"},
                {"id": "post_volume_ml", "label": "Final Insemination Volume (mL)", "type": "number", "placeholder": "0.5"},
                {"id": "post_conc_million_ml", "label": "Post-wash Concentration (M/mL)", "type": "number", "placeholder": "38", "required": True},
                {"id": "post_progressive_motility_pct", "label": "Post-wash Progressive Motility (%)", "type": "number", "placeholder": "90", "required": True},
                {"id": "total_motile_inseminated_million", "label": "Total Motile Sperm Inseminated (TMC M)", "type": "number", "placeholder": "19.0", "required": True},
                {"id": "intended_use", "label": "Intended Procedure", "type": "select", "options": [{"value": "iui_h", "label": "IUI-H (Husband)"}, {"value": "iui_d", "label": "IUI-D (Donor)"}, {"value": "ivf", "label": "Conventional IVF"}, {"value": "icsi", "label": "ICSI"}]},
                {"id": "analyst_name", "label": "Processed By (Embryologist / Andrologist)", "type": "text", "required": True},
                {"id": "impression", "label": "Final Impression", "type": "textarea", "placeholder": "Optimal post-wash yield suitable for intrauterine insemination."}
            ]
        }
    ]
}

SEMEN_FREEZING_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "semen_freezing",
    "schema_version": "1.0",
    "title": "Semen Cryopreservation Record",
    "description": "Autologous / donor semen cryopreservation with test-thaw verification.",
    "sections": [
        {
            "id": "freezing_details",
            "title": "Cryopreservation Log & Tank Coordinates",
            "fields": [
                {"id": "freeze_date", "label": "Freezing Date", "type": "date", "required": True},
                {"id": "indication", "label": "Indication for Freezing", "type": "select", "options": [{"value": "pre_chemo", "label": "Onco-fertility / Pre-Chemotherapy"}, {"value": "ivf_backup", "label": "IVF/ICSI Backup Sample"}, {"value": "donor_quarantine", "label": "Donor Sperm Quarantine (ART Act 2021)"}, {"value": "severe_oligo", "label": "Severe Oligozoospermia Pooling"}, {"value": "post_surgical", "label": "Post-TESA / PESA Cryopreservation"}]},
                {"id": "pre_freeze_volume_ml", "label": "Volume (mL)", "type": "number", "placeholder": "2.5"},
                {"id": "pre_freeze_conc_m_ml", "label": "Pre-freeze Conc (M/mL)", "type": "number", "placeholder": "35"},
                {"id": "pre_freeze_motility_pct", "label": "Pre-freeze Motility (%)", "type": "number", "placeholder": "60"},
                {"id": "cryoprotectant", "label": "Freezing Media / Cryoprotectant", "type": "text", "placeholder": "SpermFreeze / Glycerol-Egg-Yolk"},
                {"id": "straws_vials_frozen", "label": "Number of Vials / Straws Frozen", "type": "number", "placeholder": "3", "required": True},
                {"id": "tank_no", "label": "Tank #", "type": "text", "placeholder": "Tank-1", "required": True},
                {"id": "canister_no", "label": "Canister #", "type": "text", "placeholder": "Canister-3", "required": True},
                {"id": "goblet_colour", "label": "Goblet Colour", "type": "text", "placeholder": "Yellow"},
                {"id": "test_thaw_survival_pct", "label": "Test-Thaw Survival Rate (%)", "type": "number", "placeholder": "50"},
                {"id": "consent_form_signed", "label": "Consent Form 16 (ART Act 2021) Signed", "type": "select", "options": [{"value": "yes", "label": "Yes — On File"}, {"value": "pending", "label": "Pending"}], "required": True},
                {"id": "expiry_date", "label": "Consent Expiry Date", "type": "date", "required": True},
                {"id": "embryologist_sign", "label": "Embryologist / Witness", "type": "text", "required": True}
            ]
        }
    ]
}

SURGICAL_SPERM_RETRIEVAL_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "surgical_sperm_retrieval",
    "schema_version": "1.0",
    "title": "Surgical Sperm Retrieval (TESA / PESA / TESE) Record",
    "description": "Intra-operative testicular & epididymal sperm aspiration procedure notes.",
    "sections": [
        {
            "id": "procedure_notes",
            "title": "Surgical Retrieval & Lab Assessment",
            "fields": [
                {"id": "procedure_date", "label": "Date of Procedure", "type": "date", "required": True},
                {"id": "procedure_type", "label": "Procedure", "type": "select", "options": [{"value": "pesa_right", "label": "PESA — Right Epididymis"}, {"value": "pesa_left", "label": "PESA — Left Epididymis"}, {"value": "tesa_bilateral", "label": "TESA — Bilateral Testes"}, {"value": "micro_tese", "label": "Micro-TESE (Open Microdissection)"}, {"value": "open_tese", "label": "Conventional Open TESE"}], "required": True},
                {"id": "surgeon_name", "label": "Operating Andrologist / Urologist", "type": "text", "required": True},
                {"id": "anaesthesia_type", "label": "Anaesthesia", "type": "select", "options": [{"value": "local_cord_block", "label": "Local Cord Block + Sedation"}, {"value": "ga", "label": "General Anaesthesia"}, {"value": "spinal", "label": "Spinal Anaesthesia"}]},
                {"id": "tissue_aspirate_appearance", "label": "Tissue / Aspirate Nature", "type": "text", "placeholder": "Testicular tubules teased in buffered sperm medium"},
                {"id": "sperm_presence", "label": "Sperm Identification in Lab", "type": "select", "options": [{"value": "motile_sperm_present", "label": "Motile Sperm Present (Suitable for ICSI)"}, {"value": "twitching_non_progressive", "label": "Immotile / Twitching Sperm Present (PENTOX / Laser viable)"}, {"value": "sperm_absent_sertoli", "label": "No Sperm Identified / Sertoli Cells only"}], "required": True},
                {"id": "motility_grade", "label": "Motility & Yield Quality", "type": "text", "placeholder": "Occasional progressive sperm found per high power field"},
                {"id": "disposition_sample", "label": "Sample Disposition", "type": "select", "options": [{"value": "fresh_icsi_today", "label": "Used for Fresh ICSI Today"}, {"value": "cryopreserved_tubules", "label": "Cryopreserved (Vitrified in Straws)"}, {"value": "both_fresh_and_frozen", "label": "Part Fresh Injected + Remaining Frozen"}, {"value": "discarded", "label": "Discarded (No Sperm)"}]},
                {"id": "post_op_recovery", "label": "Post-operative Recovery & Hemostasis", "type": "textarea", "placeholder": "Procedure uneventful, scrotum dressing intact, patient discharged stable."}
            ]
        }
    ]
}

IUI_PROCEDURE_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "iui_procedure",
    "schema_version": "1.0",
    "title": "Intrauterine Insemination (IUI) Procedure Record",
    "description": "IUI-H / IUI-D insemination documentation and timing.",
    "sections": [
        {
            "id": "iui_details",
            "title": "Insemination Details",
            "fields": [
                {"id": "insemination_datetime", "label": "Insemination Date & Time", "type": "datetime-local", "required": True},
                {"id": "iui_type", "label": "IUI Type", "type": "select", "options": [{"value": "iui_husband", "label": "IUI-H (Husband Semen)"}, {"value": "iui_donor", "label": "IUI-D (Donor Semen — ART Bank)"}], "required": True},
                {"id": "trigger_to_iui_interval_hours", "label": "Timing Post-Trigger (Hours)", "type": "number", "placeholder": "36"},
                {"id": "ovulation_confirmed_scan", "label": "Pre-IUI Scan Ovulation Status", "type": "select", "options": [{"value": "ruptured", "label": "Follicle Ruptured / Collapsed (Post-ovulatory)"}, {"value": "impending_rupture", "label": "Intact Mature Follicle (>18mm, Impending Rupture)"}, {"value": "luteinized_unruptured", "label": "LUF Suspected"}]},
                {"id": "catheter_type", "label": "Insemination Catheter", "type": "text", "placeholder": "Wallace IUI Catheter / Labotect"},
                {"id": "ease_of_procedure", "label": "Ease of Insemination", "type": "select", "options": [{"value": "easy_smooth", "label": "Easy & Smooth (No tenaculum)"}, {"value": "moderate", "label": "Moderate (Mild resistance / Tenaculum used)"}, {"value": "difficult", "label": "Difficult (Cervical stenosis / Sounding required)"}]},
                {"id": "cervical_mucus_bleeding", "label": "Cervical Trauma / Bleeding", "type": "select", "options": [{"value": "clean", "label": "Clean / No bleeding"}, {"value": "minimal_spotting", "label": "Minimal spotting on catheter tip"}]},
                {"id": "performing_doctor", "label": "Doctor / Clinician Name", "type": "text", "required": True},
                {"id": "witness_embryologist", "label": "Embryologist Sample Handover Witness", "type": "text", "required": True},
                {"id": "luteal_support_prescribed", "label": "Luteal Phase Support Prescribed", "type": "textarea", "placeholder": "Tab. Dydrogesterone (Duphaston) 10mg BD x 14 days, Tab. Folic Acid 5mg OD"}
            ]
        }
    ]
}

RX_GROUP_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "rx_group",
    "schema_version": "1.0",
    "title": "Prescription Group Template",
    "description": "Reusable medication sets for rapid prescription writing.",
    "sections": [
        {
            "id": "rx_group_info",
            "title": "Prescription Bundle Information",
            "fields": [
                {"id": "group_name", "label": "Group / Bundle Name", "type": "text", "placeholder": "e.g. Antagonist Stimulation Standard", "required": True},
                {"id": "target_gender", "label": "Target Patient", "type": "select", "options": [{"value": "female", "label": "Female"}, {"value": "male", "label": "Male"}, {"value": "both", "label": "Both Partners"}]},
                {"id": "medications_list", "label": "Medications JSON Array", "type": "textarea", "placeholder": "[{'drug': '...', 'dose': '...', 'freq': '...', 'duration': '...'}]", "required": True}
            ]
        }
    ]
}

FERTILITY_CONSULTATION_SCHEMA = {
    "plugin_id": "fertility",
    "record_type": "fertility_consultation",
    "schema_version": "1.0",
    "title": "Fertility OPD Consultation",
    "description": "Standard fertility outpatient consultation form.",
    "sections": [
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
                    "placeholder": "AMH, Pelvic TVS, Semen Analysis...",
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
