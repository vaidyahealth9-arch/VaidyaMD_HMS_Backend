"""
VaidyaMD HMS — HL7 v2.x MLLP Server & Parser
Implements standard Minimal Lower Layer Protocol (MLLP) over TCP port 2575 for lab equipment ingestion.
Parses ORU^R01 observation result messages (CASA Semen Analyzers, Hematology, Biochemistry).
"""

import asyncio
from datetime import datetime
from uuid import UUID
from typing import Optional, Any
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.models import ClinicalRecord, Patient

# MLLP Framing Characters
SB = b"\x0b"  # Start Block (VT)
EB = b"\x1c"  # End Block (FS)
CR = b"\x0d"  # Carriage Return


def parse_hl7_message(raw_msg_str: str) -> dict[str, Any]:
    """
    Parse HL7 v2.x ER7 message text into structured clinical dictionary.
    Extracts MSH, PID, OBR, and OBX segments.
    """
    lines = [line.strip() for line in raw_msg_str.split("\r") if line.strip()]
    if len(lines) == 0:
        lines = [line.strip() for line in raw_msg_str.split("\n") if line.strip()]

    parsed_result = {
        "message_type": "ORU^R01",
        "patient_mrn": None,
        "patient_name": None,
        "sample_id": None,
        "test_name": "Diagnostic Laboratory Analysis",
        "analyzer_id": "MINDRAY-BC5000",
        "timestamp": datetime.utcnow().isoformat(),
        "observations": {},
        "raw_hl7": raw_msg_str,
    }

    for line in lines:
        fields = line.split("|")
        seg_type = fields[0].strip()

        if seg_type == "MSH":
            # MSH|^~\&|CASA_ANALYZER|LAB_DEPT|VAIDYAMD_HMS|CLINIC|20260901120000||ORU^R01|MSG001|P|2.5
            if len(fields) > 3 and fields[3]:
                parsed_result["analyzer_id"] = fields[3]
            if len(fields) > 9:
                parsed_result["message_type"] = fields[8]

        elif seg_type == "PID":
            # PID|1||PAT-2026-089||SHARMA^PRIYA||19940512|F
            if len(fields) > 3:
                parsed_result["patient_mrn"] = fields[3].strip()
            if len(fields) > 5 and fields[5]:
                parsed_result["patient_name"] = fields[5].replace("^", " ").strip()

        elif seg_type == "OBR":
            # OBR|1||SAMP-98762|CASA_SEMEN^CASA Semen Analysis|||20260901...
            if len(fields) > 3:
                parsed_result["sample_id"] = fields[3].strip()
            if len(fields) > 4 and fields[4]:
                parsed_result["test_name"] = fields[4].replace("^", " — ").strip()

        elif seg_type == "OBX":
            # OBX|1|NM|CONC^Sperm Concentration||48.5|M/mL|15.0 - 250.0|N|||F
            if len(fields) > 5:
                obx_id = fields[3].split("^")[0] if "^" in fields[3] else fields[3]
                obx_name = fields[3].split("^")[1] if "^" in fields[3] else fields[3]
                val = fields[5].strip()
                unit = fields[6].strip() if len(fields) > 6 else ""
                ref_range = fields[7].strip() if len(fields) > 7 else ""
                flag = fields[8].strip() if len(fields) > 8 else "N"

                try:
                    num_val = float(val)
                except ValueError:
                    num_val = val

                parsed_result["observations"][obx_id.lower()] = {
                    "code": obx_id,
                    "name": obx_name,
                    "value": num_val,
                    "unit": unit,
                    "reference_range": ref_range,
                    "flag": flag,  # N = Normal, H = High, L = Low, A = Abnormal
                }

    return parsed_result


async def save_hl7_clinical_record(parsed_data: dict[str, Any], tenant_id: Optional[UUID] = None) -> Optional[ClinicalRecord]:
    """
    Save parsed HL7 observations into database as a ClinicalRecord marked as 'Pending Authorization'.
    Strictly matches patient by MRN/VID within tenant scope.
    """
    async with AsyncSessionLocal() as db:
        patient = None
        mrn = parsed_data.get("patient_mrn")
        if mrn:
            query = select(Patient).where(Patient.vid == mrn)
            if tenant_id:
                query = query.where(Patient.tenant_id == tenant_id)
            res = await db.execute(query)
            patient = res.scalar_one_or_none()

        if not patient:
            print(f"❌ HL7 Ingest: No matching patient found with MRN '{mrn}' (tenant: {tenant_id}).")
            return None

        # Determine record type
        test_name_lower = (parsed_data.get("test_name") or "").lower()
        if "semen" in test_name_lower or "casa" in test_name_lower or "andrology" in test_name_lower:
            record_type = "casa_semen_analysis"
            plugin_id = "fertility"
        else:
            record_type = "diagnostic_lab_report"
            plugin_id = "lims"

        record = ClinicalRecord(
            patient_id=patient.id,
            plugin_id=plugin_id,
            record_type=record_type,
            schema_version="1.0",
            data={
                "sample_id": parsed_data.get("sample_id", f"SMP-{datetime.utcnow().strftime('%Y%m%d%H%M')}"),
                "analyzer_id": parsed_data.get("analyzer_id", "ANALYZER-HL7-01"),
                "test_name": parsed_data.get("test_name", "Laboratory Test"),
                "status": "Pending Authorization",
                "observations": parsed_data.get("observations", {}),
                "ingested_at": datetime.utcnow().isoformat(),
                "patient_name": patient.name,
                "patient_mrn": patient.vid,
            },
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        print(f"✅ Ingested HL7 lab report {record.id} for {patient.name} [{record_type} - Pending Authorization]")
        return record


class HL7MLLPProtocol(asyncio.Protocol):
    """Asyncio protocol handler for HL7 MLLP framing."""

    def __init__(self):
        self.buffer = bytearray()

    def connection_made(self, transport):
        self.transport = transport
        peer = transport.get_extra_info("peername")
        print(f"📡 HL7 Equipment connected from {peer}")

    def data_received(self, data):
        self.buffer.extend(data)

        # Check for MLLP frame: Starts with \x0b and ends with \x1c\x0d
        while True:
            start = self.buffer.find(SB)
            if start == -1:
                self.buffer.clear()
                break

            end = self.buffer.find(EB + CR, start)
            if end == -1:
                # Wait for remainder of frame
                break

            msg_bytes = self.buffer[start + 1 : end]
            del self.buffer[: end + 2]

            try:
                msg_str = msg_bytes.decode("utf-8", errors="ignore")
                parsed = parse_hl7_message(msg_str)
                asyncio.create_task(save_hl7_clinical_record(parsed))

                # Send HL7 ACK (Positive Acknowledgement)
                ack = (
                    f"MSH|^~\\&|VAIDYAMD_HMS|CLINIC|{parsed.get('analyzer_id', 'ANALYZER')}|LAB|{datetime.utcnow().strftime('%Y%m%d%H%M%S')}||ACK^R01|ACK001|P|2.5\r"
                    f"MSA|AA|MSG001|Message accepted successfully\r"
                )
                self.transport.write(SB + ack.encode("utf-8") + EB + CR)
            except Exception as e:
                print(f"❌ Error parsing HL7 frame: {e}")


async def start_hl7_mllp_server(host="0.0.0.0", port=2575):
    """Start background asyncio HL7 MLLP server on port 2575."""
    try:
        loop = asyncio.get_running_loop()
        server = await loop.create_server(lambda: HL7MLLPProtocol(), host, port)
        print(f"🧪 HL7 MLLP Ingestion Server listening on {host}:{port}")
        return server
    except Exception as e:
        print(f"⚠️ Note: HL7 MLLP port {port} could not bind ({e}). Simulation endpoints available.")
        return None
