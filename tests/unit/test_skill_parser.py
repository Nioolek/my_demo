import pytest
from src.agent.skills import parse_skill_content, skill_to_tool

pytestmark = pytest.mark.unit


SAMPLE_SKILL_MD = """---
name: inventory_check
description: "Use this skill when the user asks about inventory levels or stock checks."
metadata:
  emoji: "📦"
---

# Inventory Check Skill

When the user asks about inventory, follow these steps:

1. Ask which product they want to check
2. Query the inventory system
3. Report current stock levels
"""


def test_parse_skill_content():
    name, description, body = parse_skill_content(SAMPLE_SKILL_MD)
    assert name == "inventory_check"
    assert "inventory" in description.lower()
    assert "# Inventory Check Skill" in body


def test_parse_skill_content_no_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill_content("No frontmatter here")


def test_parse_skill_content_missing_name():
    bad = "---\ndescription: test\n---\nbody"
    with pytest.raises(ValueError, match="name"):
        parse_skill_content(bad)


def test_skill_to_tool():
    from src.models.skill import SkillResponse, SkillStatus, SkillScope
    from uuid import uuid4

    skill = SkillResponse(
        id=uuid4(),
        tenant_id=uuid4(),
        name="test-skill",
        scope=SkillScope.TENANT,
        status=SkillStatus.APPROVED,
        content=SAMPLE_SKILL_MD,
        config={},
        channels=["all"],
        version=1,
    )
    tool = skill_to_tool(skill)
    assert tool.name == "inventory_check"
    assert "inventory" in tool.description.lower()
