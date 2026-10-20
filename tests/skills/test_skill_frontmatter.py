"""Every skill's frontmatter parses, so its description reaches the skill list."""

from pathlib import Path

import pytest
import yaml

SKILLS = sorted((Path(__file__).parents[2] / ".claude" / "skills").glob("*/SKILL.md"))


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_frontmatter_parses_with_a_description(path):
    # a ": " inside an unquoted description is invalid YAML; the skill then
    # lists with its bare name. Use a `>-` block.
    frontmatter = path.read_text().split("---")[1]
    data = yaml.safe_load(frontmatter)
    assert data["name"] == path.parent.name
    assert isinstance(data["description"], str) and data["description"].strip()
