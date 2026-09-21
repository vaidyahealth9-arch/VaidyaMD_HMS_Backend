from pydantic import BaseModel
from typing import Optional, List
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
    departments: list[str] = []
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    reg_number: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    hospital_name: Optional[str] = None
    hospital_logo_url: Optional[str] = None
    active_plugins: Optional[list[str]] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class UserCreateRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "doctor"
    is_doctor: bool = False
    departments: List[str] = []
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    reg_number: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[UUID] = None

class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_doctor: Optional[bool] = None
    departments: Optional[List[str]] = None
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    reg_number: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[UUID] = None
    is_active: Optional[bool] = None

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
