from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.core.models import User
from app.core.dependencies import get_current_user
from app.modules.auth.schemas import (
    LoginRequest, UserResponse, UserUpdateRequest, TokenResponse, RefreshTokenRequest
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication (Clean Architecture)"])

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)

@router.post("/login", response_model=TokenResponse)
@router.post("/login/", response_model=TokenResponse, include_in_schema=False)
async def login(
    request: LoginRequest, 
    service: AuthService = Depends(get_auth_service)
):
    try:
        return await service.login(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

@router.post("/refresh", response_model=TokenResponse)
@router.post("/refresh/", response_model=TokenResponse, include_in_schema=False)
async def refresh_token(
    request: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
):
    try:
        return await service.refresh_tokens(request.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

@router.post("/logout")
@router.post("/logout/", include_in_schema=False)
async def logout(
    request: RefreshTokenRequest,
    service: AuthService = Depends(get_auth_service),
):
    await service.revoke_token(request.refresh_token)
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    try:
        return await service.get_profile(current_user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")

@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    return await service.list_users(current_user.tenant_id)

@router.get("/doctors", response_model=list[UserResponse])
async def list_doctors(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    users = await service.list_users(current_user.tenant_id)
    return [u for u in users if u.is_doctor or u.role in ["doctor", "admin"]]
 
@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    try:
        return await service.update_user(user_id, update_data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
