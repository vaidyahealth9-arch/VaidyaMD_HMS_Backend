from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
from decimal import Decimal

from app.core.models import Patient, Invoice, InvoiceStatus
from app.modules.wallet.model import PatientWallet, WalletTransaction, WalletTxType
from app.modules.wallet.schemas import DepositRequest, DeductRequest

class WalletService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_patient_wallet(self, patient_id: UUID):
        result = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == patient_id))
        wallet = result.scalar_one_or_none()
        if not wallet:
            patient = await self.db.get(Patient, patient_id)
            if not patient:
                raise ValueError("Patient not found")
            wallet = PatientWallet(
                patient_id=patient_id,
                balance=Decimal("0.00"),
                tenant_id=patient.tenant_id,
            )
            self.db.add(wallet)
            await self.db.flush()
            await self.db.refresh(wallet)

        tx_res = await self.db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.wallet_id == wallet.id)
            .order_by(desc(WalletTransaction.created_at))
        )
        transactions = tx_res.scalars().all()

        total_deposited = sum(
            float(t.amount)
            for t in transactions
            if t.transaction_type in (WalletTxType.DEPOSIT, "deposit", "DEPOSIT")
        )
        total_utilized = sum(
            float(t.amount)
            for t in transactions
            if t.transaction_type in (
                WalletTxType.INVOICE_DEBIT,
                WalletTxType.DEBIT,
                "invoice_debit",
                "debit",
                "INVOICE_DEBIT",
            )
        )

        return {
            "wallet_id": wallet.id,
            "patient_id": wallet.patient_id,
            "balance": float(wallet.balance),
            "total_deposited": total_deposited,
            "total_utilized": total_utilized,
            "transactions": [
                {
                    "id": t.id,
                    "type": t.transaction_type.value if hasattr(t.transaction_type, "value") else str(t.transaction_type),
                    "amount": float(t.amount),
                    "payment_mode": t.payment_mode,
                    "reference_invoice_id": str(t.reference_invoice_id) if t.reference_invoice_id else None,
                    "notes": t.notes,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in transactions
            ]
        }

    async def deposit(self, payload: DepositRequest):
        if payload.amount <= 0:
            raise ValueError("Deposit amount must be greater than 0")

        result = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == payload.patient_id))
        wallet = result.scalar_one_or_none()
        if not wallet:
            patient = await self.db.get(Patient, payload.patient_id)
            if not patient:
                raise ValueError("Patient not found")
            wallet = PatientWallet(
                patient_id=payload.patient_id,
                balance=Decimal("0.00"),
                tenant_id=patient.tenant_id,
            )
            self.db.add(wallet)
            await self.db.flush()

        wallet.balance += Decimal(str(payload.amount))

        tx = WalletTransaction(
            wallet_id=wallet.id,
            tenant_id=wallet.tenant_id,
            branch_id=wallet.branch_id,
            transaction_type=WalletTxType.DEPOSIT,
            amount=Decimal(str(payload.amount)),
            payment_mode=payload.payment_mode,
            notes=payload.notes,
            created_by=payload.created_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(wallet)

        return {"message": f"Successfully credited ₹{payload.amount} to wallet", "balance": float(wallet.balance)}

    async def deduct(self, payload: DeductRequest):
        result = await self.db.execute(select(PatientWallet).where(PatientWallet.patient_id == payload.patient_id))
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise ValueError("Patient wallet not found")

        amt = Decimal(str(payload.amount))
        if wallet.balance < amt:
            raise ValueError(f"Insufficient wallet balance (Available: ₹{wallet.balance})")

        invoice = None
        if payload.reference_invoice_id:
            invoice = await self.db.get(Invoice, payload.reference_invoice_id)
            if not invoice:
                raise ValueError("Referenced invoice not found")

            disc = Decimal(str(payload.discount or 0))
            if disc > Decimal("0"):
                invoice.discount = (invoice.discount or Decimal("0")) + disc
                invoice.total_amount = max(Decimal("0"), invoice.total_amount - disc)

            invoice.paid_amount = (invoice.paid_amount or Decimal("0")) + amt
            invoice.wallet_amount_used = (invoice.wallet_amount_used or Decimal("0")) + amt

            if invoice.paid_amount >= invoice.total_amount:
                invoice.status = InvoiceStatus.PAID
            elif invoice.paid_amount > Decimal("0"):
                invoice.status = InvoiceStatus.PARTIALLY_PAID

            if not invoice.payment_method or invoice.payment_method.lower() in ("pending", "cash"):
                invoice.payment_method = "wallet"

            note_entry = f"Paid ₹{amt} from advance wallet"
            if disc > Decimal("0"):
                note_entry += f" (Concession: ₹{disc})"
            invoice.notes = f"{invoice.notes} | {note_entry}" if invoice.notes else note_entry

        wallet.balance -= amt

        tx = WalletTransaction(
            wallet_id=wallet.id,
            tenant_id=wallet.tenant_id,
            branch_id=wallet.branch_id or (invoice.branch_id if invoice else None),
            transaction_type=WalletTxType.INVOICE_DEBIT,
            amount=amt,
            payment_mode="wallet",
            reference_invoice_id=payload.reference_invoice_id,
            notes=payload.notes or (f"Paid against invoice #{invoice.invoice_number}" if invoice else None),
            created_by=payload.created_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(wallet)
        if invoice:
            await self.db.refresh(invoice)

        return {"message": f"Debited ₹{payload.amount} from wallet", "balance": float(wallet.balance)}
