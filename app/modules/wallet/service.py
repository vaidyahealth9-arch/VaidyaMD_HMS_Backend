from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID
from decimal import Decimal

from app.core.models import Patient
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

        return {
            "wallet_id": wallet.id,
            "patient_id": wallet.patient_id,
            "balance": float(wallet.balance),
            "transactions": [
                {
                    "id": t.id,
                    "type": t.transaction_type.value if hasattr(t.transaction_type, "value") else str(t.transaction_type),
                    "amount": float(t.amount),
                    "payment_mode": t.payment_mode,
                    "reference_invoice_id": t.reference_invoice_id,
                    "notes": t.notes,
                    "created_at": t.created_at,
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

        wallet.balance -= amt

        tx = WalletTransaction(
            wallet_id=wallet.id,
            transaction_type=WalletTxType.DEBIT,
            amount=amt,
            reference_invoice_id=payload.reference_invoice_id,
            notes=payload.notes,
            created_by=payload.created_by,
        )
        self.db.add(tx)
        await self.db.flush()
        await self.db.refresh(wallet)

        return {"message": f"Debited ₹{payload.amount} from wallet", "balance": float(wallet.balance)}
