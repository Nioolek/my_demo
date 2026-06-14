import os
import pytest
import jwt

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.unit


def test_create_token():
    from src.auth import create_token
    token = create_token(user_id="user1", tenant_id="tenant1")
    payload = jwt.decode(token, "test-secret", algorithms=["HS256"])
    assert payload["sub"] == "user1"
    assert payload["tenant_id"] == "tenant1"


def test_verify_token_valid():
    from src.auth import create_token, verify_token
    token = create_token(user_id="user1", tenant_id="tenant1")
    payload = verify_token(token)
    assert payload["sub"] == "user1"


def test_verify_token_invalid():
    from src.auth import verify_token
    with pytest.raises(Exception):
        verify_token("invalid-token")


def test_verify_token_expired():
    from src.auth import verify_token
    import jwt as pyjwt
    token = pyjwt.encode(
        {"sub": "user1", "exp": 0},
        "test-secret",
        algorithm="HS256",
    )
    with pytest.raises(Exception):
        verify_token(token)
