import uuid

import pytest

from src.auth import create_token, verify_token
from src.db.client import execute

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_login_flow(_init_pool):
    """Test the full login flow: create tenant+user, then login."""
    tenant_id = str(uuid.uuid4())
    await execute(
        "INSERT INTO tenants (id, name) VALUES (%s, %s)",
        tenant_id, "Auth Test Store",
    )
    await execute(
        "INSERT INTO users (id, tenant_id, name, role, channel_source) "
        "VALUES (%s, %s, %s, %s, %s)",
        "auth-test-user", tenant_id, "Auth Tester", "manager", "console",
    )

    token = create_token("auth-test-user", tenant_id)
    payload = verify_token(token)
    assert payload["sub"] == "auth-test-user"
    assert payload["tenant_id"] == tenant_id

    await execute("DELETE FROM users WHERE id = %s", "auth-test-user")
    await execute("DELETE FROM tenants WHERE id = %s", tenant_id)
