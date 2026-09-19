from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class LoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    is_doctor: bool = False
    departments: list[str]
    specialization: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    tenant_id: UUID
    hospital_name: Optional[str] = None
    active_plugins: Optional[list[str]] = None

    class Config:
        from_attributes = True

class UserUpdateRequest(BaseModel):
    is_doctor: Optional[bool] = None
    specialization: Optional[str] = None
    phone: Optional[str] = None
    departments: Optional[list[str]] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserResponse

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class SwitchRoleRequest(BaseModel):
    role: str
    department: Optional[str] = None

