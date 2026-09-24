from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.wallet.schemas import DepositRequest, DeductRequest, TopUpPayload, PayInvoicePayload
from app.modules.wallet.service import WalletService

router = APIRouter(prefix="/wallet", tags=["Wallet (Clean Architecture)"])

def get_wallet_service(db: AsyncSession = Depends(get_db)) -> WalletService:
    return WalletService(db)

@router.get("/{patient_id}")
async def get_patient_wallet(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        return await service.get_patient_wallet(patient_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/deposit", status_code=201)
async def deposit_to_wallet(
    payload: DepositRequest,
    current_user: User = Depends(get_current_user),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        if not payload.created_by:
            payload.created_by = current_user.id
        return await service.deposit(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{patient_id}/topup", status_code=201)
async def topup_patient_wallet(
    patient_id: UUID,
    payload: TopUpPayload,
    current_user: User = Depends(get_current_user),
    service: WalletService = Depends(get_wallet_service),
):
    dep = DepositRequest(
        patient_id=patient_id,
        amount=payload.amount,
        payment_mode=payload.payment_method,
        notes=payload.notes,
        created_by=current_user.id,
    )
    try:
        return await service.deposit(dep)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/deduct")
async def deduct_from_wallet(
    payload: DeductRequest,
    current_user: User = Depends(get_current_user),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        if not payload.created_by:
            payload.created_by = current_user.id
        return await service.deduct(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{patient_id}/pay-invoice")
async def pay_invoice_from_wallet(
    patient_id: UUID,
    payload: PayInvoicePayload,
    current_user: User = Depends(get_current_user),
    service: WalletService = Depends(get_wallet_service),
):
    deduct = DeductRequest(
        patient_id=patient_id,
        amount=payload.amount,
        reference_invoice_id=payload.invoice_id,
        discount=payload.discount or 0.0,
        notes=f"Paid against invoice {payload.invoice_id}",
        created_by=current_user.id,
    )
    try:
        return await service.deduct(deduct)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
