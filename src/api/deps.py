"""FastAPI dependency functions for request context."""

from starlette.requests import Request

from src.auth import verify_token


async def get_current_user(request: Request) -> dict:
    """Extract current user from JWT token."""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        from starlette.exceptions import HTTPException
        raise HTTPException(status_code=401, detail="Missing authorization")
    return verify_token(token)


async def get_tenant_id(request: Request) -> str:
    """Extract tenant_id from the current user's token."""
    user = await get_current_user(request)
    return user["tenant_id"]
