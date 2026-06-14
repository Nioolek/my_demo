"""Multi-tenant authentication for LangGraph Server."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from langgraph_sdk import Auth

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))

auth = Auth()


def create_token(user_id: str, tenant_id: str) -> str:
    """Create a JWT token for a user."""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


@auth.authenticate
async def authenticate(headers: dict) -> str:
    """Extract user identity from JWT in Authorization header."""
    auth_header = headers.get(b"authorization", b"")
    if isinstance(auth_header, bytes):
        auth_header = auth_header.decode("utf-8")

    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Missing authorization token")

    try:
        payload = verify_token(token)
    except jwt.ExpiredSignatureError:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload["sub"]
