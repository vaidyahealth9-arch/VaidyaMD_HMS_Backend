import hashlib
import secrets
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.core.models import User, Hospital, RefreshToken
from app.modules.auth.schemas import LoginRequest, UserResponse, UserUpdateRequest, TokenResponse
from app.core.security import verify_password, create_access_token

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _hash_token(self, token_str: str) -> str:
        return hashlib.sha256(token_str.strip().encode("utf-8")).hexdigest()

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
        
        access_token = create_access_token({
            "sub": str(user.id),
            "role": role_val,
            "tenant_id": str(user.tenant_id),
            "email": user.email,
        })

        raw_refresh = secrets.token_urlsafe(48)
        refresh_hash = self._hash_token(raw_refresh)
        expires_at = datetime.utcnow() + timedelta(days=14)

        refresh_entry = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
        )
        self.db.add(refresh_entry)
        await self.db.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            user=self._build_user_response(user, hospital),
        )

    async def refresh_tokens(self, raw_refresh_token: str) -> TokenResponse:
        if not raw_refresh_token:
            raise ValueError("Refresh token is required")

        token_hash = self._hash_token(raw_refresh_token)
        now = datetime.utcnow()

        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > now,
            )
        )
        token_record = result.scalar_one_or_none()
        if not token_record:
            raise ValueError("Invalid or expired refresh token")

        # Invalidate current refresh token (rotation)
        token_record.is_revoked = True
        token_record.last_used_at = now

        # Retrieve user
        user_res = await self.db.execute(
            select(User).options(selectinload(User.hospital)).where(User.id == token_record.user_id)
        )
        user = user_res.scalar_one_or_none()
        if not user or not user.is_active:
            raise ValueError("User inactive or no longer exists")

        hospital = user.hospital or await self.db.get(Hospital, user.tenant_id)
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)

        new_access_token = create_access_token({
            "sub": str(user.id),
            "role": role_val,
            "tenant_id": str(user.tenant_id),
            "email": user.email,
        })

        # Issue rotated refresh token
        new_raw_refresh = secrets.token_urlsafe(48)
        new_token_hash = self._hash_token(new_raw_refresh)
        new_expires_at = now + timedelta(days=14)

        new_refresh_entry = RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
        )
        self.db.add(new_refresh_entry)
        await self.db.flush()

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_raw_refresh,
            user=self._build_user_response(user, hospital),
        )

    async def revoke_token(self, raw_refresh_token: str) -> bool:
        if not raw_refresh_token:
            return False
        token_hash = self._hash_token(raw_refresh_token)
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        record = result.scalar_one_or_none()
        if record:
            record.is_revoked = True
            await self.db.flush()
            return True
        return False

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
