import random
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from uuid import UUID
from decimal import Decimal
from typing import Optional

from app.core.models import Hospital, User, PatientWallet, WalletTransaction, WalletTxType
from app.modules.patients.model import Patient
from app.modules.billing.model import Invoice, TreatmentPackage, PatientPackage, ServiceItem, InvoiceStatus
from app.modules.billing.schemas import (
    InvoiceCreate,
    InvoiceResponse,
    PaymentRequest,
    TreatmentPackageSchema,
    TreatmentPackageUpdate,
    ServiceItemCreate,
    ServiceItemUpdate,
    PatientPackageAssignRequest,
    PatientPackageConsumeRequest,
    PatientPackageResponse,
)
from app.modules.billing.exceptions import InvoiceNotFoundError, InsufficientWalletBalanceError

class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_service_catalog(
        self,
        tenant_id: Optional[UUID] = None,
        branch_id: Optional[UUID] = None,
        service_type: Optional[str] = None,
        q: Optional[str] = None,
    ):
        query = select(ServiceItem).where(ServiceItem.is_active == True)
        if tenant_id:
            query = query.where(ServiceItem.tenant_id == tenant_id)
        if branch_id:
            query = query.where(or_(ServiceItem.branch_id == branch_id, ServiceItem.branch_id.is_(None)))
        if service_type:
            query = query.where(func.lower(ServiceItem.category) == service_type.lower())
        if q:
            query = query.where(ServiceItem.name.ilike(f"%{q}%"))
        
        query = query.order_by(ServiceItem.category, ServiceItem.name)
        result = await self.db.execute(query)
        items = result.scalars().all()
        return [
            {
                "id": str(it.id),
                "code": it.code,
                "name": it.name,
                "type": it.category,
                "category": it.category,
                "cost": float(it.base_price),
                "base_price": float(it.base_price),
                "hsn_sac": it.hsn_sac,
                "gst_rate": float(it.gst_rate) if it.gst_rate is not None else 0.0,
            }
            for it in items
        ]


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

        # Automatic Package Allocation if package_id was billed
        if getattr(data, "package_id", None):
            pkg = await self.db.get(TreatmentPackage, data.package_id)
            if pkg and pkg.tenant_id == tenant_id:
                items_allocated = []
                for idx, it in enumerate(pkg.items or [], 1):
                    qty = int(it.get("quantity") or it.get("qty") or 1)
                    price = float(it.get("price") or it.get("cost") or 0.0)
                    items_allocated.append({
                        "id": f"pkg_it_{idx}_{uuid.uuid4().hex[:6]}",
                        "name": it.get("name") or it.get("description") or f"Service {idx}",
                        "service_code": it.get("code") or it.get("service_code") or "",
                        "total_qty": qty,
                        "consumed_qty": 0,
                        "remaining_qty": qty,
                        "unit_price": price,
                        "history": [],
                    })
                patient_pkg = PatientPackage(
                    tenant_id=tenant_id,
                    patient_id=data.patient_id,
                    package_id=pkg.id,
                    invoice_id=invoice.id,
                    package_name=pkg.name,
                    total_price=pkg.base_price,
                    status="active",
                    items=items_allocated,
                )
                self.db.add(patient_pkg)
                await self.db.flush()

        # Quota deductions for services billed under an active package
        for item in data.items:
            if getattr(item, "patient_package_id", None) and getattr(item, "package_item_id", None):
                pt_pkg = await self.db.get(PatientPackage, item.patient_package_id)
                if pt_pkg and pt_pkg.tenant_id == tenant_id:
                    items_list = list(pt_pkg.items or [])
                    for p_it in items_list:
                        if p_it.get("id") == str(item.package_item_id) or p_it.get("name", "").lower() == item.description.lower():
                            p_it["consumed_qty"] = p_it.get("consumed_qty", 0) + item.quantity
                            p_it["remaining_qty"] = max(0, p_it.get("total_qty", 0) - p_it["consumed_qty"])
                            if "history" not in p_it:
                                p_it["history"] = []
                            p_it["history"].append({
                                "timestamp": datetime.utcnow().isoformat(),
                                "consumed_qty": item.quantity,
                                "invoice_id": str(invoice.id),
                                "notes": f"Redeemed via Invoice #{invoice.invoice_number}",
                            })
                    if all(p_it.get("remaining_qty", 0) <= 0 for p_it in items_list):
                        pt_pkg.status = "completed"
                    pt_pkg.items = items_list
                    flag_modified(pt_pkg, "items")
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

        await self.db.commit()
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

    async def update_package(self, package_id: UUID, data: TreatmentPackageUpdate, tenant_id: UUID) -> TreatmentPackage:
        package = await self.db.get(TreatmentPackage, package_id)
        if not package or package.tenant_id != tenant_id:
            raise ValueError("Treatment package not found in current hospital")
        if data.name is not None:
            package.name = data.name.strip()
        if data.description is not None:
            package.description = data.description
        if data.plugin_id is not None:
            package.plugin_id = data.plugin_id
        if data.items is not None:
            package.items = data.items
        if data.base_price is not None:
            package.base_price = data.base_price
        if data.is_active is not None:
            package.is_active = data.is_active
        await self.db.commit()
        await self.db.refresh(package)
        return package

    async def delete_package(self, package_id: UUID, tenant_id: UUID) -> bool:
        package = await self.db.get(TreatmentPackage, package_id)
        if not package or package.tenant_id != tenant_id:
            return False
        package.is_active = False
        await self.db.commit()
        return True

    async def create_service_item(self, data: ServiceItemCreate, tenant_id: UUID) -> ServiceItem:
        item = ServiceItem(
            tenant_id=tenant_id,
            branch_id=data.branch_id,
            code=data.code.strip(),
            name=data.name.strip(),
            category=data.category.strip(),
            base_price=data.base_price,
            hsn_sac=data.hsn_sac.strip() if data.hsn_sac else None,
            gst_rate=data.gst_rate,
            is_active=True,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update_service_item(self, item_id: UUID, data: ServiceItemUpdate, tenant_id: UUID) -> ServiceItem:
        item = await self.db.get(ServiceItem, item_id)
        if not item or item.tenant_id != tenant_id:
            raise ValueError("Service item not found in current hospital")
        if data.code is not None:
            item.code = data.code.strip()
        if data.name is not None:
            item.name = data.name.strip()
        if data.category is not None:
            item.category = data.category.strip()
        if data.base_price is not None:
            item.base_price = data.base_price
        if data.hsn_sac is not None:
            item.hsn_sac = data.hsn_sac.strip() if data.hsn_sac else None
        if data.gst_rate is not None:
            item.gst_rate = data.gst_rate
        if data.is_active is not None:
            item.is_active = data.is_active
        if data.branch_id is not None:
            item.branch_id = data.branch_id
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def delete_service_item(self, item_id: UUID, tenant_id: UUID) -> bool:
        item = await self.db.get(ServiceItem, item_id)
        if not item or item.tenant_id != tenant_id:
            return False
        item.is_active = False
        await self.db.commit()
        return True

    async def assign_patient_package(
        self, data: PatientPackageAssignRequest, tenant_id: UUID
    ) -> PatientPackageResponse:
        patient = await self.db.get(Patient, data.patient_id)
        if not patient or patient.tenant_id != tenant_id:
            raise ValueError("Patient not found in current hospital")

        pkg = await self.db.get(TreatmentPackage, data.package_id)
        if not pkg or pkg.tenant_id != tenant_id:
            raise ValueError("Treatment package not found")

        source_items = data.custom_items if data.custom_items else pkg.items
        items_allocated = []
        for idx, it in enumerate(source_items or [], 1):
            qty = int(it.get("quantity") or it.get("qty") or 1)
            price = float(it.get("price") or it.get("cost") or 0.0)
            items_allocated.append({
                "id": f"pkg_it_{idx}_{uuid.uuid4().hex[:6]}",
                "name": it.get("name") or it.get("description") or f"Service {idx}",
                "service_code": it.get("code") or it.get("service_code") or "",
                "total_qty": qty,
                "consumed_qty": 0,
                "remaining_qty": qty,
                "unit_price": price,
                "history": [],
            })

        patient_pkg = PatientPackage(
            tenant_id=tenant_id,
            patient_id=data.patient_id,
            package_id=pkg.id,
            invoice_id=data.invoice_id,
            package_name=pkg.name,
            total_price=pkg.base_price,
            status="active",
            items=items_allocated,
        )
        self.db.add(patient_pkg)
        await self.db.commit()
        await self.db.refresh(patient_pkg)

        return PatientPackageResponse(
            id=patient_pkg.id,
            tenant_id=patient_pkg.tenant_id,
            patient_id=patient_pkg.patient_id,
            patient_name=patient.name,
            package_id=patient_pkg.package_id,
            invoice_id=patient_pkg.invoice_id,
            package_name=patient_pkg.package_name,
            total_price=patient_pkg.total_price,
            status=patient_pkg.status,
            items=patient_pkg.items or [],
            created_at=patient_pkg.created_at,
            updated_at=patient_pkg.updated_at,
        )

    async def get_patient_packages(
        self, patient_id: UUID, tenant_id: UUID
    ) -> list[PatientPackageResponse]:
        query = (
            select(PatientPackage)
            .options(selectinload(PatientPackage.patient))
            .where(
                PatientPackage.patient_id == patient_id,
                PatientPackage.tenant_id == tenant_id,
            )
            .order_by(desc(PatientPackage.created_at))
        )
        result = await self.db.execute(query)
        pkgs = result.scalars().all()
        return [
            PatientPackageResponse(
                id=p.id,
                tenant_id=p.tenant_id,
                patient_id=p.patient_id,
                patient_name=p.patient.name if p.patient else None,
                package_id=p.package_id,
                invoice_id=p.invoice_id,
                package_name=p.package_name,
                total_price=p.total_price,
                status=p.status,
                items=p.items or [],
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in pkgs
        ]

    async def consume_package_service(
        self,
        patient_package_id: UUID,
        data: PatientPackageConsumeRequest,
        tenant_id: UUID,
    ) -> PatientPackageResponse:
        query = (
            select(PatientPackage)
            .options(selectinload(PatientPackage.patient))
            .where(
                PatientPackage.id == patient_package_id,
                PatientPackage.tenant_id == tenant_id,
            )
        )
        result = await self.db.execute(query)
        pkg = result.scalar_one_or_none()
        if not pkg:
            raise ValueError("Patient package allocation not found")

        matched = False
        items = list(pkg.items or [])
        for it in items:
            if it.get("id") == data.item_id or it.get("name", "").lower() == data.item_id.lower():
                rem = it.get("remaining_qty", 0)
                if rem < data.quantity:
                    raise ValueError(f"Insufficient quota: {rem} remaining, requested {data.quantity}")
                it["consumed_qty"] = it.get("consumed_qty", 0) + data.quantity
                it["remaining_qty"] = max(0, it.get("total_qty", 0) - it["consumed_qty"])
                if "history" not in it:
                    it["history"] = []
                it["history"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "consumed_qty": data.quantity,
                    "doctor_id": str(data.doctor_id) if data.doctor_id else None,
                    "notes": data.notes or "Service consumed via clinic workbench",
                })
                matched = True
                break

        if not matched:
            raise ValueError(f"Service item '{data.item_id}' not found in package allocation")

        if all(it.get("remaining_qty", 0) <= 0 for it in items):
            pkg.status = "completed"

        pkg.items = items
        flag_modified(pkg, "items")
        await self.db.commit()
        await self.db.refresh(pkg)

        return PatientPackageResponse(
            id=pkg.id,
            tenant_id=pkg.tenant_id,
            patient_id=pkg.patient_id,
            patient_name=pkg.patient.name if pkg.patient else None,
            package_id=pkg.package_id,
            invoice_id=pkg.invoice_id,
            package_name=pkg.package_name,
            total_price=pkg.total_price,
            status=pkg.status,
            items=pkg.items or [],
            created_at=pkg.created_at,
            updated_at=pkg.updated_at,
        )

