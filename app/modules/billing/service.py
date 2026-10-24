import random
import uuid
from datetime import datetime, date
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


    async def generate_invoice_number(self, branch_code: Optional[str] = None, source_module: Optional[str] = None) -> str:
        dept_tag = "MAIN"
        if source_module:
            mod_lower = source_module.lower().strip()
            if "pharm" in mod_lower:
                dept_tag = "PHARMA"
            elif "lab" in mod_lower or "lims" in mod_lower:
                dept_tag = "LAB"
            elif "ipd" in mod_lower:
                dept_tag = "IPD"
            elif "art" in mod_lower or "ivf" in mod_lower or "fertil" in mod_lower:
                dept_tag = "ART"
            elif "cos" in mod_lower:
                dept_tag = "COSGYN"
            elif "counsel" in mod_lower:
                dept_tag = "COUNSEL"
            elif branch_code and branch_code.upper() != "MAIN":
                dept_tag = branch_code.upper()
            else:
                dept_tag = "MAIN"
        elif branch_code:
            dept_tag = branch_code.upper()

        code_prefix = f"INV-{dept_tag}"
        result = await self.db.execute(select(func.count(Invoice.id)).where(Invoice.invoice_number.like(f"{code_prefix}-%")))
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

        patient_age = None
        patient_gender = None
        patient_address = None
        patient_phone = None
        patient_mrn = None

        if patient:
            patient_age = getattr(patient, "age", None)
            if patient_age is None and getattr(patient, "dob", None):
                try:
                    today = date.today()
                    patient_age = today.year - patient.dob.year - ((today.month, today.day) < (patient.dob.month, patient.dob.day))
                except Exception:
                    patient_age = None

            raw_gender = getattr(patient, "gender", None)
            if raw_gender:
                patient_gender = raw_gender.value if hasattr(raw_gender, "value") else str(raw_gender)

            patient_address = getattr(patient, "address", None)
            patient_phone = getattr(patient, "phone", None)
            patient_mrn = getattr(patient, "mrn", None) or getattr(patient, "vid", None)

        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            patient_id=invoice.patient_id,
            patient_name=patient.name if patient else None,
            patient_vid=patient.vid if patient else None,
            patient_mrn=patient_mrn,
            patient_age=patient_age,
            patient_gender=patient_gender,
            patient_address=patient_address,
            patient_phone=patient_phone,
            appointment_source=invoice.appointment_source or "OP",
            source_module=getattr(invoice, "source_module", None) or (invoice.appointment_source or "opd").lower(),
            source_reference_id=getattr(invoice, "source_reference_id", None),
            reason_for_attendance=invoice.reason_for_attendance,
            items=invoice.items,
            subtotal=invoice.subtotal,
            discount=invoice.discount,
            tax=invoice.tax,
            round_off=getattr(invoice, "round_off", None) or Decimal("0"),
            total_amount=invoice.total_amount,
            paid_amount=invoice.paid_amount,
            wallet_amount_used=invoice.wallet_amount_used or Decimal("0"),
            pending_due=pending if pending > Decimal("0") else Decimal("0"),
            status=invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
            payment_method=invoice.payment_method,
            upi_pay_mode=invoice.upi_pay_mode,
            notes=invoice.notes,
            payment_transactions=getattr(invoice, "payment_transactions", None) or [],
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
        discount = data.discount
        if not discount and getattr(data, "discount_value", None):
            discount = Decimal(str(data.discount_value))
        if not discount:
            discount = Decimal("0")

        tax = data.tax if data.tax else Decimal("0")
        raw_net = max(Decimal("0"), subtotal - discount + tax)
        rounded_total = Decimal(str(round(float(raw_net))))
        round_off = data.round_off if data.round_off is not None else (rounded_total - raw_net)
        total = rounded_total

        wallet_used = Decimal(str(round(float(data.wallet_amount_used or data.wallet_deduction or 0))))
        payment_method = data.payment_method or "cash"
        upi_pay_mode = data.upi_pay_mode

        split_summary = []
        tx_list = []
        initial_paid = Decimal("0")

        if getattr(data, "split_payments", None) and len(data.split_payments) > 0:
            payment_method = "split"
            wallet_used = Decimal("0")
            for sp in data.split_payments:
                sp_amt = Decimal(str(sp.amount or 0))
                if sp_amt <= Decimal("0"):
                    continue
                initial_paid += sp_amt
                m_str = sp.payment_method
                if sp.upi_pay_mode:
                    m_str += f" ({sp.upi_pay_mode})"
                if sp.reference:
                    m_str += f" [Ref: {sp.reference}]"
                split_summary.append(f"{m_str}: ₹{sp_amt}")
                if "wallet" in sp.payment_method.lower():
                    wallet_used += sp_amt
                tx_list.append({
                    "id": str(uuid.uuid4()),
                    "type": "payment",
                    "amount": float(sp_amt),
                    "payment_method": sp.payment_method,
                    "upi_pay_mode": sp.upi_pay_mode,
                    "reference": sp.reference,
                    "notes": sp.notes or "Split tender payment",
                    "timestamp": datetime.utcnow().isoformat(),
                })
        else:
            is_full_paid = getattr(data, "payment_status", None) == "paid" or (
                data.paid_amount is not None and Decimal(str(data.paid_amount)) >= total and total > Decimal("0")
            )
            if is_full_paid:
                initial_paid = total
                if wallet_used > Decimal("0"):
                    tender_amt = max(Decimal("0"), total - wallet_used)
                    tx_list.append({
                        "id": str(uuid.uuid4()),
                        "type": "payment",
                        "amount": float(wallet_used),
                        "payment_method": "wallet",
                        "notes": "Patient advance wallet deduction",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    if tender_amt > Decimal("0"):
                        tx_list.append({
                            "id": str(uuid.uuid4()),
                            "type": "payment",
                            "amount": float(tender_amt),
                            "payment_method": payment_method,
                            "upi_pay_mode": upi_pay_mode,
                            "notes": "Direct settlement",
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                else:
                    if total > Decimal("0"):
                        tx_list.append({
                            "id": str(uuid.uuid4()),
                            "type": "payment",
                            "amount": float(total),
                            "payment_method": payment_method,
                            "upi_pay_mode": upi_pay_mode,
                            "notes": "Full payment settlement",
                            "timestamp": datetime.utcnow().isoformat(),
                        })
            else:
                direct_tender = Decimal(str(round(float(data.paid_amount or 0))))
                initial_paid = direct_tender + wallet_used
                if wallet_used > Decimal("0"):
                    tx_list.append({
                        "id": str(uuid.uuid4()),
                        "type": "payment",
                        "amount": float(wallet_used),
                        "payment_method": "wallet",
                        "notes": "Patient advance wallet deduction",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                if direct_tender > Decimal("0"):
                    tx_list.append({
                        "id": str(uuid.uuid4()),
                        "type": "payment",
                        "amount": float(direct_tender),
                        "payment_method": payment_method,
                        "upi_pay_mode": upi_pay_mode,
                        "notes": "Partial settlement",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

        wallet = None
        if wallet_used > Decimal("0"):
            wallet_res = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == patient.id))
            wallet = wallet_res.scalar_one_or_none()
            if not wallet or wallet.balance < wallet_used:
                avail = wallet.balance if wallet else Decimal("0")
                raise InsufficientWalletBalanceError(f"Insufficient patient advance wallet balance (Available: ₹{avail})")
            wallet.balance -= wallet_used

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
                "service_code": item.service_code,
                "category": item.category,
                "tax_rate": float(item.tax_rate) if item.tax_rate else 0.0,
            }
            for item in data.items
        ]

        src_mod = (data.source_module or data.appointment_source or "opd").lower()
        inv_num = await self.generate_invoice_number(branch_code=branch_code, source_module=src_mod)

        combined_notes = data.notes or ""
        if split_summary:
            split_txt = f"Split Tenders: {', '.join(split_summary)}"
            combined_notes = f"{combined_notes} | {split_txt}" if combined_notes else split_txt
        if getattr(data, "discount_reason", None):
            combined_notes = f"{combined_notes} | Discount Reason: {data.discount_reason}" if combined_notes else f"Discount Reason: {data.discount_reason}"

        invoice = Invoice(
            invoice_number=inv_num,
            patient_id=data.patient_id,
            appointment_source=data.appointment_source or src_mod.upper(),
            source_module=src_mod,
            source_reference_id=data.source_reference_id,
            reason_for_attendance=data.reason_for_attendance,
            items=serializable_items,
            subtotal=subtotal,
            discount=discount,
            tax=data.tax,
            round_off=round_off,
            total_amount=total,
            paid_amount=initial_paid,
            wallet_amount_used=wallet_used,
            status=status,
            payment_method=payment_method,
            upi_pay_mode=upi_pay_mode,
            notes=combined_notes or None,
            payment_transactions=tx_list,
            created_by=user_creator,
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
        self.db.add(invoice)
        await self.db.flush()

        # Bidirectional linkage if source_reference_id was provided
        if data.source_reference_id:
            try:
                if src_mod == "ipd":
                    from app.modules.ipd.model import IPDAdmission
                    adm = await self.db.get(IPDAdmission, data.source_reference_id)
                    if adm:
                        adm.invoice_id = invoice.id
                elif src_mod in ("opd", "appointments", "appointment"):
                    from app.modules.appointments.model import Appointment
                    app_obj = await self.db.get(Appointment, data.source_reference_id)
                    if app_obj:
                        app_obj.invoice_id = invoice.id
                        if not app_obj.metadata_:
                            app_obj.metadata_ = {}
                        app_obj.metadata_["invoice_id"] = str(invoice.id)
                        app_obj.metadata_["invoice_number"] = invoice.invoice_number
                        flag_modified(app_obj, "metadata_")
                elif src_mod == "lims":
                    from app.core.models.clinical_record import ClinicalRecord
                    rec = await self.db.get(ClinicalRecord, data.source_reference_id)
                    if rec:
                        rec.invoice_id = invoice.id
            except Exception:
                pass

        # Automatic Package Allocation if package_id was billed or package source
        target_pkg_id = getattr(data, "package_id", None)
        if not target_pkg_id and (src_mod == "package" or any("package" in (it.category or "").lower() for it in data.items)):
            for it in data.items:
                pkg_match = await self.db.execute(
                    select(TreatmentPackage).where(
                        TreatmentPackage.tenant_id == tenant_id,
                        func.lower(TreatmentPackage.name) == func.lower(it.description),
                    )
                )
                matched_pkg = pkg_match.scalar_one_or_none()
                if matched_pkg:
                    target_pkg_id = matched_pkg.id
                    break

        if target_pkg_id:
            pkg = await self.db.get(TreatmentPackage, target_pkg_id)
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

        if wallet_used > Decimal("0") and wallet:
            w_tx = WalletTransaction(
                wallet_id=wallet.id,
                tenant_id=tenant_id,
                branch_id=branch_id,
                transaction_type=WalletTxType.INVOICE_DEBIT,
                amount=wallet_used,
                payment_mode="wallet",
                reference_invoice_id=invoice.id,
                notes=f"Deducted for Invoice #{invoice.invoice_number}",
                created_by=user_creator or invoice.created_by,
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

        if payload.discount and payload.discount > Decimal("0"):
            disc_rounded = Decimal(str(round(float(payload.discount))))
            invoice.discount = (invoice.discount or Decimal("0")) + disc_rounded
            invoice.total_amount = Decimal(str(round(float(max(Decimal("0"), invoice.total_amount - disc_rounded)))))

        total_payment_added = Decimal("0")
        split_entries = []
        is_split = bool(getattr(payload, "split_payments", None) and len(payload.split_payments) > 0)

        if is_split:
            for sp in payload.split_payments:
                sp_amt = Decimal(str(round(float(sp.amount or 0))))
                if sp_amt <= Decimal("0"):
                    continue
                total_payment_added += sp_amt

                if "wallet" in sp.payment_method.lower():
                    wallet_res = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == invoice.patient_id))
                    wallet = wallet_res.scalar_one_or_none()
                    if not wallet or wallet.balance < sp_amt:
                        avail = wallet.balance if wallet else Decimal("0")
                        raise InsufficientWalletBalanceError(f"Insufficient patient advance wallet balance (Available: ₹{avail})")
                    wallet.balance -= sp_amt
                    invoice.wallet_amount_used = (invoice.wallet_amount_used or Decimal("0")) + sp_amt
                    w_tx = WalletTransaction(
                        wallet_id=wallet.id,
                        tenant_id=invoice.tenant_id,
                        branch_id=invoice.branch_id,
                        transaction_type=WalletTxType.INVOICE_DEBIT,
                        amount=sp_amt,
                        payment_mode="wallet",
                        reference_invoice_id=invoice.id,
                        notes=f"Deducted for Invoice #{invoice.invoice_number}" + (f" | {payload.notes}" if payload.notes else ""),
                        created_by=invoice.created_by,
                    )
                    self.db.add(w_tx)
                    await self.db.flush()
                    await self.db.refresh(wallet)

                m_str = sp.payment_method
                if sp.upi_pay_mode:
                    m_str += f" ({sp.upi_pay_mode})"
                if sp.reference:
                    m_str += f" [Ref: {sp.reference}]"
                split_entries.append(f"{m_str}: ₹{sp_amt}")

            invoice.payment_method = "split"
        else:
            total_payment_added = Decimal(str(round(float(payload.amount))))
            is_wallet = payload.payment_method and "wallet" in payload.payment_method.lower()
            if is_wallet and payload.amount > Decimal("0"):
                wallet_res = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == invoice.patient_id))
                wallet = wallet_res.scalar_one_or_none()
                if not wallet or wallet.balance < payload.amount:
                    avail = wallet.balance if wallet else Decimal("0")
                    raise InsufficientWalletBalanceError(f"Insufficient patient advance wallet balance (Available: ₹{avail})")

                wallet.balance -= payload.amount
                invoice.wallet_amount_used = (invoice.wallet_amount_used or Decimal("0")) + payload.amount

                w_tx = WalletTransaction(
                    wallet_id=wallet.id,
                    tenant_id=invoice.tenant_id,
                    branch_id=invoice.branch_id,
                    transaction_type=WalletTxType.INVOICE_DEBIT,
                    amount=payload.amount,
                    payment_mode="wallet",
                    reference_invoice_id=invoice.id,
                    notes=f"Deducted for Invoice #{invoice.invoice_number}" + (f" | {payload.notes}" if payload.notes else ""),
                    created_by=invoice.created_by,
                )
                self.db.add(w_tx)
                await self.db.flush()
                await self.db.refresh(wallet)

            if payload.payment_method:
                invoice.payment_method = payload.payment_method
            if payload.upi_pay_mode:
                invoice.upi_pay_mode = payload.upi_pay_mode

        invoice.paid_amount += total_payment_added
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        elif invoice.paid_amount > Decimal("0"):
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        audit_note = payload.notes or ""
        if split_entries:
            split_txt = f"Payment Tenders: {', '.join(split_entries)}"
            audit_note = f"{audit_note} | {split_txt}" if audit_note else split_txt

        if audit_note:
            existing_notes = f"{invoice.notes} | " if invoice.notes else ""
            invoice.notes = f"{existing_notes}{audit_note}"

        tx_entries = list(invoice.payment_transactions or [])
        if is_split:
            for sp in payload.split_payments:
                sp_amt = Decimal(str(sp.amount or 0))
                if sp_amt > Decimal("0"):
                    tx_entries.append({
                        "id": str(uuid.uuid4()),
                        "type": "payment",
                        "amount": float(sp_amt),
                        "payment_method": sp.payment_method,
                        "upi_pay_mode": sp.upi_pay_mode,
                        "reference": sp.reference,
                        "notes": sp.notes or (payload.notes or "Subsequent payment"),
                        "timestamp": datetime.utcnow().isoformat(),
                    })
        elif total_payment_added > Decimal("0"):
            tx_entries.append({
                "id": str(uuid.uuid4()),
                "type": "payment",
                "amount": float(total_payment_added),
                "payment_method": payload.payment_method or "cash",
                "upi_pay_mode": payload.upi_pay_mode,
                "notes": payload.notes or "Subsequent payment",
                "timestamp": datetime.utcnow().isoformat(),
            })
        invoice.payment_transactions = tx_entries
        flag_modified(invoice, "payment_transactions")

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(invoice)
        patient = await self.db.get(Patient, invoice.patient_id)
        return self._build_invoice_response(invoice, patient)

    async def cancel_invoice(self, invoice_id: UUID, reason: str, cancelled_by: Optional[UUID] = None) -> InvoiceResponse:
        invoice = await self.db.get(Invoice, invoice_id)
        if not invoice:
            raise InvoiceNotFoundError("Invoice not found")
        if invoice.status == InvoiceStatus.CANCELLED:
            raise ValueError("Invoice is already cancelled")

        invoice.status = InvoiceStatus.CANCELLED
        cancel_note = f"CANCELLED: {reason}"
        invoice.notes = f"{invoice.notes} | {cancel_note}" if invoice.notes else cancel_note

        txs = list(invoice.payment_transactions or [])
        txs.append({
            "id": str(uuid.uuid4()),
            "type": "cancellation",
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "cancelled_by": str(cancelled_by) if cancelled_by else None,
        })
        invoice.payment_transactions = txs
        flag_modified(invoice, "payment_transactions")

        await self.db.commit()
        await self.db.refresh(invoice)
        patient = await self.db.get(Patient, invoice.patient_id)
        return self._build_invoice_response(invoice, patient)

    async def refund_invoice(
        self,
        invoice_id: UUID,
        amount: Decimal,
        reason: str,
        refund_to_wallet: bool = True,
        payment_method: str = "wallet",
        notes: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
    ) -> InvoiceResponse:
        invoice = await self.db.get(Invoice, invoice_id)
        if not invoice:
            raise InvoiceNotFoundError("Invoice not found")
        if amount <= Decimal("0"):
            raise ValueError("Refund amount must be greater than zero")
        if amount > invoice.paid_amount:
            raise ValueError(f"Refund amount (₹{amount}) cannot exceed amount paid (₹{invoice.paid_amount})")

        invoice.paid_amount -= amount
        if invoice.paid_amount <= Decimal("0"):
            invoice.status = InvoiceStatus.REFUNDED
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        if refund_to_wallet:
            wallet_res = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == invoice.patient_id))
            wallet = wallet_res.scalar_one_or_none()
            if not wallet:
                wallet = PatientWallet(
                    patient_id=invoice.patient_id,
                    tenant_id=invoice.tenant_id,
                    branch_id=invoice.branch_id,
                    balance=Decimal("0.00"),
                )
                self.db.add(wallet)
                await self.db.flush()

            wallet.balance += amount
            w_tx = WalletTransaction(
                wallet_id=wallet.id,
                tenant_id=invoice.tenant_id,
                branch_id=invoice.branch_id,
                transaction_type=WalletTxType.CREDIT,
                amount=amount,
                payment_mode=payment_method or "wallet_refund",
                reference_invoice_id=invoice.id,
                notes=f"Refund from Invoice #{invoice.invoice_number}: {reason}",
                created_by=invoice.created_by,
            )
            self.db.add(w_tx)
            await self.db.flush()

        txs = list(invoice.payment_transactions or [])
        txs.append({
            "id": str(uuid.uuid4()),
            "type": "refund",
            "amount": float(amount),
            "refund_to_wallet": refund_to_wallet,
            "payment_method": payment_method,
            "reason": reason,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat(),
        })
        invoice.payment_transactions = txs
        flag_modified(invoice, "payment_transactions")

        refund_note = f"Refunded ₹{amount} ({'Credited to Wallet' if refund_to_wallet else payment_method}): {reason}"
        invoice.notes = f"{invoice.notes} | {refund_note}" if invoice.notes else refund_note

        await self.db.commit()
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
        patient_ids = [patient_id]
        patient = await self.db.get(Patient, patient_id)
        if patient and patient.partner_id:
            patient_ids.append(patient.partner_id)

        query = (
            select(PatientPackage)
            .options(selectinload(PatientPackage.patient))
            .where(
                PatientPackage.patient_id.in_(patient_ids),
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

