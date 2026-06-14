import pytest
from src.models.tenant import TenantCreate, TenantResponse, UserCreate, UserResponse
from src.models.agent import AgentCreate, AgentResponse
from src.models.skill import SkillCreate, SkillResponse, SkillStatus, SkillScope

pytestmark = pytest.mark.unit


def test_tenant_create():
    t = TenantCreate(name="Test Store")
    assert t.name == "Test Store"
    assert t.config == {}


def test_tenant_response():
    import uuid
    tid = uuid.uuid4()
    t = TenantResponse(id=tid, name="Store A")
    assert t.id == tid


def test_user_create():
    u = UserCreate(id="user1", name="Alice", role="manager", tenant_id=__import__("uuid").uuid4())
    assert u.role == "manager"


def test_skill_status_values():
    assert SkillStatus.DRAFT == "draft"
    assert SkillStatus.PENDING == "pending"
    assert SkillStatus.APPROVED == "approved"
    assert SkillStatus.REJECTED == "rejected"
    assert SkillStatus.DISABLED == "disabled"


def test_skill_scope_values():
    assert SkillScope.SYSTEM == "system"
    assert SkillScope.TENANT == "tenant"


def test_skill_create_defaults():
    s = SkillCreate(name="test-skill", content="# Test")
    assert s.scope == SkillScope.TENANT
    assert s.status == SkillStatus.DRAFT


def test_agent_create():
    import uuid
    a = AgentCreate(tenant_id=uuid.uuid4(), name="my-agent", model="gpt-4o")
    assert a.temperature == 0.7
