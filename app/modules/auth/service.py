from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.core.models import User, Hospital
from app.modules.auth.schemas import LoginRequest, UserResponse, UserUpdateRequest, TokenResponse
from app.core.security import verify_password, create_access_token

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _build_user_response(self, user: User, hospital: Hospital | None = None) -> UserResponse:
        h_name = hospital.name if hospital else None
        h_plugins = hospital.active_plugins if hospital else []
        role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
        is_doc = True if role_str.lower() == "doctor" else bool(user.is_doctor)
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=role_str,
            is_doctor=is_doc,
            departments=user.departments or [],
            specialization=user.specialization,
            avatar_url=user.avatar_url,
            phone=user.phone,
            tenant_id=user.tenant_id,
            hospital_name=h_name,
            active_plugins=h_plugins,
        )

    async def login(self, request: LoginRequest) -> TokenResponse:
        result = await self.db.execute(
            select(User).options(selectinload(User.hospital)).where(User.email == request.email)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise ValueError("Invalid email or password")

        if not verify_password(request.password, user.password_hash):
            raise ValueError("Invalid email or password")

        hospital = user.hospital or await self.db.get(Hospital, user.tenant_id)
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        
        token = create_access_token({
            "sub": str(user.id),
            "role": role_val,
            "tenant_id": str(user.tenant_id),
            "email": user.email,
        })

        return TokenResponse(
            access_token=token,
            user=self._build_user_response(user, hospital),
        )

    async def get_profile(self, user_id: UUID) -> UserResponse:
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        hospital = await self.db.get(Hospital, user.tenant_id) if user.tenant_id else None
        return self._build_user_response(user, hospital)

    async def list_users(self, tenant_id: UUID = None) -> list[UserResponse]:
        query = select(User).options(selectinload(User.hospital)).where(User.is_active == True)
        if tenant_id:
            query = query.where(User.tenant_id == tenant_id)

        result = await self.db.execute(query)
        users = result.scalars().all()
        return [self._build_user_response(u, u.hospital) for u in users]

    async def update_user(self, user_id: UUID, update_data: UserUpdateRequest, current_user: User) -> UserResponse:
        user = await self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        if update_data.is_doctor is not None:
            if current_user.role != "admin" and getattr(current_user.role, "value", str(current_user.role)) != "admin":
                raise PermissionError("Only administrators can configure doctor privileges")
            user.is_doctor = update_data.is_doctor

        if update_data.specialization is not None:
            user.specialization = update_data.specialization
        if update_data.phone is not None:
            user.phone = update_data.phone
        if update_data.departments is not None:
            user.departments = update_data.departments

        await self.db.flush()
        await self.db.refresh(user)
        hospital = await self.db.get(Hospital, user.tenant_id) if user.tenant_id else None
        return self._build_user_response(user, hospital)
