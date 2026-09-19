import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from uuid import UUID
from decimal import Decimal
from typing import Optional

from app.core.models import Hospital, User, PatientWallet, WalletTransaction, WalletTxType
from app.modules.patients.model import Patient
from app.modules.billing.model import Invoice, TreatmentPackage, InvoiceStatus
from app.modules.billing.schemas import InvoiceCreate, InvoiceResponse, PaymentRequest, TreatmentPackageSchema
from app.modules.billing.exceptions import InvoiceNotFoundError, InsufficientWalletBalanceError

_SERVICE_CATALOG = [
    {"name": "Antenatal OP", "type": "OP", "cost": 600},
    {"name": "CARDIOLOGIST CONSULTATION", "type": "OP", "cost": 600},
    {"name": "Cervical Biopsy", "type": "OP", "cost": 2000},
    {"name": "IUI DONOR (IUI-D)", "type": "OP", "cost": 8000},
    {"name": "IUI HUSBAND (IUI-H)", "type": "OP", "cost": 6000},
    {"name": "2D ECHO", "type": "OP", "cost": 1500},
    {"name": "2020 IVF + MEDICINES", "type": "Package", "cost": 99000},
    {"name": "Triple Cycle ICSI", "type": "Package", "cost": 220000},
    {"name": "DIAGNOSTIC LAPAROSCOPY", "type": "Gyn-Theatre", "cost": 35000},
    {"name": "OPU (Ovum Pick Up)", "type": "Gyn-Theatre", "cost": 45000},
    {"name": "CASA SEMEN ANALYSIS", "type": "Andrology/Embryology", "cost": 1200},
    {"name": "EMBRYO TRANSFER", "type": "Andrology/Embryology", "cost": 25000},
    {"name": "AMH (Anti-Mullerian Hormone)", "type": "LAB", "cost": 2200},
    {"name": "BASELINE SCAN (TVS)", "type": "Scan", "cost": 1500},
    {"name": "IVF THEATRE CHARGE", "type": "IVF-Theatre", "cost": 15000},
    {"name": "INJECTION ADMINISTRATION CHARGE", "type": "Nurse", "cost": 200},
    {"name": "Yoga", "type": "Yoga", "cost": 0},
    {"name": "FERTILITY COUNSELLING", "type": "Counselling", "cost": 1500},
]

class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def get_service_catalog(self, service_type: str = None, q: str = None):
        catalog = _SERVICE_CATALOG
        if service_type:
            catalog = [s for s in catalog if s["type"].lower() == service_type.lower()]
        if q:
            q_lower = q.lower()
            catalog = [s for s in catalog if q_lower in s["name"].lower()]
        return catalog

    async def generate_invoice_number(self, branch_code: Optional[str] = None) -> str:
        code_prefix = f"INV-{branch_code.upper()}" if branch_code else "VMD-INV"
        result = await self.db.execute(select(func.count(Invoice.id)))
        count = result.scalar() or 0
        base_num = count + 1
        for attempt in range(100):
            inv_num = f"{code_prefix}-{(base_num + attempt):05d}"
            existing = await self.db.execute(select(Invoice.id).where(Invoice.invoice_number == inv_num))
            if not existing.scalar_one_or_none():
                return inv_num
        return f"{code_prefix}-{base_num:05d}-{random.randint(100, 999)}"

    def _build_invoice_response(self, invoice: Invoice, patient: Optional[Patient] = None) -> InvoiceResponse:
        total = invoice.total_amount
        paid = invoice.paid_amount
        pending = total - paid
        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            patient_id=invoice.patient_id,
            patient_name=patient.name if patient else None,
            patient_vid=patient.vid if patient else None,
            appointment_source=invoice.appointment_source or "OP",
            reason_for_attendance=invoice.reason_for_attendance,
            items=invoice.items,
            subtotal=invoice.subtotal,
            discount=invoice.discount,
            tax=invoice.tax,
            total_amount=invoice.total_amount,
            paid_amount=invoice.paid_amount,
            wallet_amount_used=invoice.wallet_amount_used or Decimal("0"),
            pending_due=pending if pending > Decimal("0") else Decimal("0"),
            status=invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
            payment_method=invoice.payment_method,
            upi_pay_mode=invoice.upi_pay_mode,
            notes=invoice.notes,
            tenant_id=invoice.tenant_id,
            branch_id=invoice.branch_id,
            created_at=invoice.created_at,
        )

    async def create_invoice(self, data: InvoiceCreate, tenant_id: UUID) -> InvoiceResponse:
        patient = await self.db.get(Patient, data.patient_id)
        if not patient:
            raise ValueError("Patient not found")

        branch_id = getattr(data, "branch_id", None) or getattr(patient, "branch_id", None)
        branch_code = None
        if branch_id:
            from app.core.models.branch import Branch
            b = await self.db.get(Branch, branch_id)
            if b and b.code:
                branch_code = b.code

        subtotal = sum(item.total for item in data.items)
        total = subtotal - data.discount + data.tax

        initial_paid = Decimal(str(data.paid_amount or 0))
        wallet_used = Decimal(str(data.wallet_amount_used or 0))

        if wallet_used > Decimal("0"):
            wallet_res = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == patient.id))
            wallet = wallet_res.scalar_one_or_none()
            if not wallet or wallet.balance < wallet_used:
                raise InsufficientWalletBalanceError("Insufficient patient advance wallet balance")
            wallet.balance -= wallet_used
            initial_paid += wallet_used

        status = InvoiceStatus.PENDING
        if initial_paid >= total and total > Decimal("0"):
            status = InvoiceStatus.PAID
        elif initial_paid > Decimal("0"):
            status = InvoiceStatus.PARTIALLY_PAID

        user_creator = data.created_by

        serializable_items = [
            {
                "description": str(item.description),
                "quantity": int(item.quantity),
                "unit_price": float(item.unit_price),
                "total": float(item.total),
            }
            for item in data.items
        ]

        inv_num = await self.generate_invoice_number(branch_code=branch_code)

        invoice = Invoice(
            invoice_number=inv_num,
            patient_id=data.patient_id,
            appointment_source=data.appointment_source or "OP",
            reason_for_attendance=data.reason_for_attendance,
            items=serializable_items,
            subtotal=subtotal,
            discount=data.discount,
            tax=data.tax,
            total_amount=total,
            paid_amount=initial_paid,
            wallet_amount_used=wallet_used,
            status=status,
            payment_method=data.payment_method or "cash",
            upi_pay_mode=data.upi_pay_mode,
            notes=data.notes,
            created_by=user_creator,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
        self.db.add(invoice)
        await self.db.flush()

        if wallet_used > Decimal("0"):
            w_tx = WalletTransaction(
                wallet_id=wallet.id,
                transaction_type=WalletTxType.DEBIT,
                amount=wallet_used,
                balance_after=wallet.balance,
                reference_invoice_id=invoice.id,
                notes=f"Deducted for Invoice #{invoice.invoice_number}",
                created_by=user_creator,
            )
            self.db.add(w_tx)
            await self.db.flush()

        await self.db.refresh(invoice)
        return self._build_invoice_response(invoice, patient)

    async def list_invoices(self, filters: dict, tenant_id: UUID = None) -> list[InvoiceResponse]:
        query = select(Invoice).options(selectinload(Invoice.patient)).order_by(desc(Invoice.created_at))
        if tenant_id:
            query = query.where(Invoice.tenant_id == tenant_id)
        if filters.get("status"):
            query = query.where(Invoice.status == filters["status"])
        if filters.get("patient_id"):
            query = query.where(Invoice.patient_id == filters["patient_id"])
        if filters.get("appointment_source"):
            query = query.where(Invoice.appointment_source == filters["appointment_source"])

        result = await self.db.execute(query)
        invoices = result.scalars().all()
        return [self._build_invoice_response(inv, inv.patient) for inv in invoices]

    async def get_invoice(self, invoice_id: UUID) -> InvoiceResponse:
        invoice = await self.db.get(Invoice, invoice_id)
        if not invoice:
            raise InvoiceNotFoundError("Invoice not found")
        patient = await self.db.get(Patient, invoice.patient_id)
        return self._build_invoice_response(invoice, patient)

    async def record_payment(self, invoice_id: UUID, payload: PaymentRequest) -> InvoiceResponse:
        invoice = await self.db.get(Invoice, invoice_id)
        if not invoice:
            raise InvoiceNotFoundError("Invoice not found")

        invoice.paid_amount += payload.amount
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        elif invoice.paid_amount > Decimal("0"):
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        if payload.payment_method:
            invoice.payment_method = payload.payment_method
        if payload.upi_pay_mode:
            invoice.upi_pay_mode = payload.upi_pay_mode

        await self.db.flush()
        await self.db.refresh(invoice)
        patient = await self.db.get(Patient, invoice.patient_id)
        return self._build_invoice_response(invoice, patient)

    async def list_packages(self, plugin_id: str = None, tenant_id: UUID = None) -> list[TreatmentPackage]:
        query = select(TreatmentPackage).where(TreatmentPackage.is_active == True)
        if tenant_id:
            query = query.where(TreatmentPackage.tenant_id == tenant_id)
        if plugin_id:
            query = query.where(TreatmentPackage.plugin_id == plugin_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_package(self, data: TreatmentPackageSchema, tenant_id: UUID) -> TreatmentPackage:
        package = TreatmentPackage(
            name=data.name,
            description=data.description,
            plugin_id=data.plugin_id or "fertility",
            items=data.items,
            base_price=data.base_price,
            is_active=data.is_active,
            tenant_id=tenant_id,
        )
        self.db.add(package)
        await self.db.flush()
        await self.db.refresh(package)
        return package
