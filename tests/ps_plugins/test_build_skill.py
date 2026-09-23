"""The end-user skill zip: layout, completeness, and link integrity."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "ps-plugins" / "skills" / "gradebook-expectations-upload"

_spec = importlib.util.spec_from_file_location(
    "build_skill", REPO / "ps-plugins" / "scripts" / "build_skill.py"
)
assert _spec is not None and _spec.loader is not None
build_skill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_skill)


def test_version_is_read_from_the_frontmatter():
    assert build_skill.skill_version(SKILL) == "1.0.0"


def test_zip_puts_files_at_the_root(tmp_path):
    out = build_skill.build(SKILL, tmp_path)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    assert "SKILL.md" in names, "SKILL.md must be at the zip root, not nested"
    assert not any(n.startswith("gradebook-expectations-upload/") for n in names)


def test_zip_carries_all_nine_files(tmp_path):
    out = build_skill.build(SKILL, tmp_path)
    with zipfile.ZipFile(out) as z:
        assert len([n for n in z.namelist() if not n.endswith("/")]) == 9


def test_every_relative_link_in_the_skill_resolves(tmp_path):
    """A dead pointer in the zip is silent for the user who hits it."""
    out = build_skill.build(SKILL, tmp_path)
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
    missing = build_skill.unresolved_links(SKILL)
    assert missing == [], f"broken relative links: {missing}"
    assert "references/sheets.md" in names
