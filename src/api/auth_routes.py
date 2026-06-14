"""Authentication API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.auth import create_token
from src.db.client import fetch_one

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    user_id: str
    channel_source: str = "console"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """Login and receive a JWT token."""
    user = await fetch_one(
        "SELECT id, tenant_id::text, name, role FROM users "
        "WHERE id = %s AND channel_source = %s",
        body.user_id,
        body.channel_source,
    )
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token = create_token(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
    )
    return LoginResponse(
        access_token=token,
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
    )
