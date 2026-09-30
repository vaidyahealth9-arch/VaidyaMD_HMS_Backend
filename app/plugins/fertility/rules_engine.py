"""
VaidyaMD HMS — Medication Calendar & Stimulation Protocol Rules Engine
Pure Python rules engine that computes a day-by-day drug timetable given sentinel dates and drug rules.
Supports Ovarian Stimulation protocols and HRT Frozen Embryo Transfer (FET Day 3 / Day 5) protocols.
"""

from datetime import datetime, date, timedelta
from typing import Any, Optional


def parse_date(d: Any) -> Optional[date]:
    if not d:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def generate_hrt_fet_calendar(
    sentinel_dates: dict[str, Any],
    total_days: int = 23,
) -> dict[str, Any]:
    """
    Generates a clinical HRT Frozen Embryo Transfer (Day 3 / Day 5) schedule
    strictly aligned with Requirements-fertility/new references/HRT_FET_Editable_Day3_Day5.xlsx.
    """
    bleed_date = parse_date(sentinel_dates.get("lmp_day1") or sentinel_dates.get("bleed_date") or date.today())
    estrogen_days_count = int(sentinel_dates.get("planned_estrogen_days", 13))
    embryo_stage = str(sentinel_dates.get("embryo_stage", "Day 5")).strip()
    is_day3 = "3" in embryo_stage
    
    p0_date = parse_date(sentinel_dates.get("p0_date"))
    if not p0_date:
        p0_date = bleed_date + timedelta(days=estrogen_days_count)
        
    p0_time = str(sentinel_dates.get("p0_time", "08:00 AM")).strip()
    e2_drug = str(sentinel_dates.get("e2_drug", "Estradiol Valerate (Progynova)")).strip()
    e2_dose = str(sentinel_dates.get("e2_dose", "2 mg")).strip()
    e2_route = str(sentinel_dates.get("e2_route", "Oral")).strip()
    e2_freq = str(sentinel_dates.get("e2_frequency", "TDS")).strip()
    
    p4_drug = str(sentinel_dates.get("p4_drug", "Micronized Progesterone + Inj. Gestone")).strip()
    p4_dose = str(sentinel_dates.get("p4_dose", "400 mg PV BD + 100 mg IM OD")).strip()
    p4_route = str(sentinel_dates.get("p4_route", "Vaginal / IM")).strip()
    p4_freq = str(sentinel_dates.get("p4_frequency", "BD / OD")).strip()

    days: list[dict[str, Any]] = []
    
    for cycle_day in range(1, total_days + 1):
        cur_date = bleed_date + timedelta(days=cycle_day - 1)
        p_offset = (cur_date - p0_date).days
        
        is_p0_or_after = p_offset >= 0
        estrogen_day_val = cycle_day if not is_p0_or_after or p_offset == 0 else None
        
        if cycle_day == 1:
            phase = "HRT start"
            med_name = "Estradiol"
            med_dose = e2_dose
            med_route = e2_route
            med_freq = e2_freq
            timing = "08:00 / 14:00 / 20:00"
            monitoring = "Baseline TVS ± E2/P4"
            embryo_tag = ""
            notes = "Baseline scan: lining < 4mm, ovaries quiescent"
        elif not is_p0_or_after:
            if cycle_day == 12:
                phase = "Endometrial assessment"
                monitoring = "TVS ± E2/P4; assess lining"
                notes = "12 days shown as a common template, not a universal requirement."
            elif cycle_day == 13:
                phase = "Assessment / optimization"
                monitoring = "Repeat TVS/labs if required"
                notes = "Confirm triple-line pattern ≥ 7-8mm and serum P4 < 1.0 ng/mL"
            else:
                phase = "Endometrial preparation"
                monitoring = ""
                notes = ""
            med_name = "Estradiol"
            med_dose = e2_dose
            med_route = e2_route
            med_freq = e2_freq
            timing = "As prescribed"
            embryo_tag = ""
        else:
            med_name = "Estradiol + Progesterone"
            med_dose = f"{e2_dose} + {p4_dose}"
            med_route = f"{e2_route} + {p4_route}"
            med_freq = f"{e2_freq} / {p4_freq}"
            
            if p_offset == 0:
                phase = "P0 — Progesterone start"
                timing = f"P0 Start at {p0_time}"
                monitoring = "Endometrium acceptable / clinic criteria met"
                embryo_tag = ""
                notes = f"P0 exact date/time ({p0_time}) is the key timing anchor for programmed HRT-FET."
            elif p_offset == 1:
                phase = "P+1"
                timing = "As prescribed"
                monitoring = ""
                embryo_tag = ""
                notes = ""
            elif p_offset == 2:
                phase = "P+2"
                timing = "As prescribed"
                monitoring = ""
                embryo_tag = ""
                notes = ""
            elif p_offset == 3:
                phase = "P+3"
                timing = "Transfer window" if is_day3 else "As prescribed"
                monitoring = "Embryo Transfer procedure" if is_day3 else ""
                embryo_tag = "Day-3"
                notes = "Use your clinic's validated progesterone-exposure schedule (~72 hours)."
            elif p_offset == 4:
                phase = "P+4"
                timing = "As prescribed"
                monitoring = ""
                embryo_tag = ""
                notes = ""
            elif p_offset == 5:
                phase = "P+5"
                timing = "Transfer window" if not is_day3 else "As prescribed"
                monitoring = "Embryo Transfer procedure" if not is_day3 else ""
                embryo_tag = "Day-5 blastocyst"
                notes = "Use your clinic's validated progesterone-exposure schedule (~120 hours)."
            elif cycle_day == total_days:
                phase = "Pregnancy testing"
                timing = "Morning serum test"
                monitoring = "Serum β-hCG on clinic-defined date"
                embryo_tag = ""
                notes = "Confirm gestational viability and continue luteal support"
            else:
                phase = "Post-transfer"
                timing = "As prescribed"
                monitoring = ""
                embryo_tag = ""
                notes = "Maintain luteal phase estradiol and progesterone support"

        # Determine milestone tag for FET calendar
        fet_milestone = ""
        if cycle_day == 1:
            fet_milestone = "Day 1 (HRT Start)"
        elif cycle_day == 12:
            fet_milestone = "D12 Endometrial Scan"
        elif cycle_day == 13:
            fet_milestone = "Endometrium Assessment"
        elif p_offset == 0:
            fet_milestone = "P0 (Progesterone Start)"
        elif p_offset == 3 and is_day3:
            fet_milestone = "Day-3 Embryo Transfer 👶"
        elif p_offset == 5 and not is_day3:
            fet_milestone = "Day-5 Blastocyst Transfer 👶"
        elif cycle_day == total_days:
            fet_milestone = "Beta-hCG Pregnancy Test 🩸"
        else:
            fet_milestone = phase if "Transfer" in phase or "P0" in phase else ""

        days.append({
            "cycle_day": cycle_day,
            "day_number": cycle_day,
            "date": cur_date.isoformat(),
            "display_date": cur_date.strftime("%d %b %Y"),
            "day_of_week": cur_date.strftime("%A"),
            "estrogen_day": estrogen_day_val,
            "phase": phase,
            "milestone": fet_milestone,
            "stim_day_label": f"HRT Day {cycle_day}" if not is_p0_or_after else (f"P0" if p_offset == 0 else f"P+{p_offset}"),
            "medication": med_name,
            "dose": med_dose,
            "unit": "mg",
            "route": med_route,
            "frequency": med_freq,
            "timing": timing,
            "monitoring_criteria": monitoring,
            "result_value": "",
            "embryo_stage": embryo_tag,
            "notes": notes,
            "medications": [
                {
                    "drug_name": med_name,
                    "dose": med_dose,
                    "route": med_route,
                    "frequency": med_freq,
                    "instructions": timing,
                }
            ],
        })

    transfer_date = p0_date + timedelta(days=3 if is_day3 else 5)
    beta_hcg_date = bleed_date + timedelta(days=total_days - 1)

    return {
        "protocol_name": "HRT FET Protocol (Day 3 / Day 5)",
        "protocol_category": "fet",
        "bleed_date": bleed_date.isoformat(),
        "p0_date": p0_date.isoformat(),
        "p0_time": p0_time,
        "embryo_stage": "Day 3" if is_day3 else "Day 5",
        "transfer_date": transfer_date.isoformat(),
        "beta_hcg_date": beta_hcg_date.isoformat(),
        "start_date": bleed_date.isoformat(),
        "end_date": beta_hcg_date.isoformat(),
        "total_days": len(days),
        "days": days,
    }


def generate_medication_calendar(
    rules: list[dict[str, Any]],
    sentinel_dates: dict[str, Any],
    total_days: int = 21,
    treatment_type: Optional[str] = None,
    timeline_events: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """
    Generate a calendar grid where each item represents a calendar day.
    Checks if FET protocol is indicated, delegating to generate_hrt_fet_calendar.
    Supports multi-track timeline events (scans, investigations, procedures)
    and prior-cycle downregulation offsets (e.g. Day 21 prior cycle = Day -7).
    """
    is_fet = (
        sentinel_dates.get("protocol_category") == "fet" or
        sentinel_dates.get("p0_date") or
        sentinel_dates.get("is_hrt_fet") or
        "FET" in str(treatment_type or "").upper()
    )
    if is_fet and not rules:
        return generate_hrt_fet_calendar(sentinel_dates, total_days=max(23, total_days))

    lmp = parse_date(sentinel_dates.get("lmp_day1"))
    stim_start = parse_date(sentinel_dates.get("stim_start"))
    trigger = parse_date(sentinel_dates.get("trigger"))
    opu = parse_date(sentinel_dates.get("opu"))
    et = parse_date(sentinel_dates.get("et"))
    baseline = parse_date(sentinel_dates.get("baseline_scan"))
    d12_scan = parse_date(sentinel_dates.get("d12_scan"))
    p0_date = parse_date(sentinel_dates.get("p0_date"))
    beta_hcg = parse_date(sentinel_dates.get("beta_hcg_date"))
    insemination = parse_date(sentinel_dates.get("insemination"))

    anchor_base = stim_start or lmp or baseline or date.today()

    # Determine timeline span considering possible negative offsets (e.g. Long Agonist D21 of prior cycle = -7)
    rule_starts = [int(r.get("day_start_offset", 1)) for r in rules] if rules else [1]
    event_starts = [int(e.get("day_offset", 1)) for e in (timeline_events or [])] if timeline_events else [1]
    min_offset = min(rule_starts + event_starts + [1])
    
    rule_ends = [int(r.get("day_end_offset", total_days)) for r in rules] if rules else [total_days]
    event_ends = [int(e.get("day_offset", total_days)) for e in (timeline_events or [])] if timeline_events else [total_days]
    max_offset = max(rule_ends + event_ends + [total_days, 14])

    # Date boundaries
    cycle_start_date = anchor_base + timedelta(days=min_offset - 1 if min_offset <= 0 else 0)
    cycle_end_date = anchor_base + timedelta(days=max_offset - 1)

    if et and et > cycle_end_date:
        cycle_end_date = et + timedelta(days=2)
    if beta_hcg and beta_hcg > cycle_end_date:
        cycle_end_date = beta_hcg + timedelta(days=1)

    calendar_days: list[dict[str, Any]] = []
    is_iui = "IUI" in str(treatment_type or "").upper() or "OI" in str(treatment_type or "").upper()

    milestone_map = {}
    if lmp:
        milestone_map[lmp] = "Day 1 (LMP)"
    if baseline:
        milestone_map[baseline] = "Baseline Scan"
    if stim_start:
        milestone_map[stim_start] = "Stimulation Start"
    if d12_scan:
        milestone_map[d12_scan] = "D12 Endometrial Scan"
    if p0_date:
        milestone_map[p0_date] = "P0 (Progesterone Start)"
    if trigger:
        milestone_map[trigger] = "Trigger Day ⚡"
    if is_iui:
        if insemination:
            milestone_map[insemination] = "IUI Insemination 💉"
        elif opu:
            milestone_map[opu] = "IUI Insemination 💉"
    else:
        if opu:
            milestone_map[opu] = "OPU / Retrieval 🧫"
        if et:
            milestone_map[et] = "Embryo Transfer 👶"
    if beta_hcg:
        milestone_map[beta_hcg] = "Beta-hCG Pregnancy Test 🩸"

    # Map timeline events by day offset
    events_by_offset: dict[int, list[dict[str, Any]]] = {}
    for ev in (timeline_events or []):
        off = int(ev.get("day_offset", 1))
        events_by_offset.setdefault(off, []).append(ev)

    current_date = cycle_start_date
    day_counter = 1

    while current_date <= cycle_end_date:
        # Calculate offset relative to anchor_base
        offset_from_anchor = (current_date - anchor_base).days + 1
        
        # Scans, investigations, and procedures for this day
        day_events = events_by_offset.get(offset_from_anchor, [])
        scans = [e.get("title") for e in day_events if e.get("type") == "scan"]
        investigations = [e.get("title") for e in day_events if e.get("type") == "investigation"]
        procedures = [e.get("title") for e in day_events if e.get("type") == "procedure"]

        # Milestone precedence
        milestone = milestone_map.get(current_date, "")
        if not milestone:
            if procedures:
                milestone = f"{procedures[0]} 🧫"
            elif scans:
                milestone = f"{scans[0]} 🔍"
            elif investigations and "Beta" in investigations[0]:
                milestone = f"{investigations[0]} 🩸"

        # Day Labeling
        if offset_from_anchor <= 0:
            prior_cycle_day = 28 + offset_from_anchor
            stim_day_label = f"Prior Cycle D{prior_cycle_day}"
        elif is_iui:
            stim_day_label = f"Cycle Day {offset_from_anchor}"
        elif stim_start and current_date >= stim_start:
            s_day = (current_date - stim_start).days + 1
            stim_day_label = f"Stim Day {s_day}"
        elif lmp and current_date >= lmp:
            c_day = (current_date - lmp).days + 1
            stim_day_label = f"Cycle Day {c_day}"
        else:
            stim_day_label = f"Day {offset_from_anchor}"

        # Match active drugs
        day_meds = []
        for rule in rules:
            anchor_key = rule.get("sentinel_anchor", "stim_start")
            anchor_date = parse_date(sentinel_dates.get(anchor_key)) or anchor_base
            
            start_offset = int(rule.get("day_start_offset", 1))
            end_offset = int(rule.get("day_end_offset", 10))

            rule_start_date = anchor_date + timedelta(days=start_offset - 1 if start_offset > 0 else start_offset)
            rule_end_date = anchor_date + timedelta(days=end_offset - 1 if end_offset > 0 else end_offset)

            if rule_start_date <= current_date <= rule_end_date:
                day_meds.append({
                    "drug_name": rule.get("drug_name"),
                    "dose": rule.get("dose"),
                    "route": rule.get("route", "SC"),
                    "frequency": rule.get("frequency", "OD"),
                    "instructions": rule.get("instructions", ""),
                })

        # Smart fallback if no rules
        if not day_meds and not rules:
            if is_iui:
                if 1 <= offset_from_anchor <= 5:
                    day_meds.append({"drug_name": "Tab Letrozole (Femara 2.5mg)", "dose": "2.5 mg", "route": "PO", "frequency": "OD", "instructions": "Take at bedtime"})
                if trigger and current_date == trigger:
                    day_meds.append({"drug_name": "Inj hCG (Ovitrelle 250mcg)", "dose": "250 mcg", "route": "SC", "frequency": "Stat", "instructions": "Subcutaneous trigger"})
            else:
                if stim_start and current_date >= stim_start:
                    s_day = (current_date - stim_start).days + 1
                    if 1 <= s_day <= 10:
                        day_meds.append({"drug_name": "Rec-FSH (Gonal-F / Puregon)", "dose": "225 IU", "route": "SC", "frequency": "OD Evening", "instructions": "Inject subcutaneously"})
                    if 6 <= s_day <= 10:
                        day_meds.append({"drug_name": "GnRH Antagonist (Cetrotide 0.25mg)", "dose": "0.25 mg", "route": "SC", "frequency": "OD Morning", "instructions": "Inject subcutaneously"})

        calendar_days.append({
            "date": current_date.isoformat(),
            "day_number": day_counter,
            "cycle_day_offset": offset_from_anchor,
            "day_of_week": current_date.strftime("%A"),
            "display_date": current_date.strftime("%d %b %Y"),
            "milestone": milestone,
            "stim_day_label": stim_day_label,
            "medications": day_meds,
            "scans": scans,
            "investigations": investigations,
            "procedures": procedures,
        })

        current_date += timedelta(days=1)
        day_counter += 1

    return {
        "start_date": cycle_start_date.isoformat(),
        "end_date": cycle_end_date.isoformat(),
        "total_days": len(calendar_days),
        "days": calendar_days,
    }
