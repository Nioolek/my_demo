"""Parse SKILL.md files and convert to LangGraph tools.

Reuses QwenPaw's SKILL.md format: YAML frontmatter + Markdown body.
"""

import re
from typing import Any

import yaml
from langchain_core.tools import StructuredTool, BaseTool

from src.models.skill import SkillResponse


def parse_skill_content(content: str) -> tuple[str, str, str]:
    """Parse SKILL.md content into (name, description, body).

    Args:
        content: Full SKILL.md file content with YAML frontmatter.

    Returns:
        Tuple of (name, description, markdown_body).

    Raises:
        ValueError: If frontmatter is missing or invalid.
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md must contain YAML frontmatter between --- markers")

    frontmatter_str = match.group(1)
    body = match.group(2).strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML frontmatter: {e}")

    if not isinstance(frontmatter, dict):
        raise ValueError("Frontmatter must be a YAML mapping")

    name = frontmatter.get("name")
    if not name:
        raise ValueError("SKILL.md frontmatter must include 'name' field")

    description = frontmatter.get("description", "")

    return name, description, body


def skill_to_tool(skill: SkillResponse) -> BaseTool:
    """Convert a SkillResponse to a LangChain/LangGraph tool."""
    name, description, body = parse_skill_content(skill.content)

    def execute_skill(query: str) -> str:
        """Execute the skill with the given user query."""
        return (
            f"## Skill: {name}\n\n"
            f"### Instructions\n{body}\n\n"
            f"### User Query\n{query}\n\n"
            f"Please follow the skill instructions above to answer the user's query."
        )

    return StructuredTool.from_function(
        func=execute_skill,
        name=name,
        description=description or f"Skill: {name}",
    )
