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


def test_version_accepts_single_quotes(tmp_path):
    """The regex shouldn't care which quote style the next edit uses."""
    (tmp_path / "SKILL.md").write_text("---\nname: x\nversion: '2.3.4'\n---\n")
    assert build_skill.skill_version(tmp_path) == "2.3.4"


def test_unresolved_links_ignores_a_title_after_the_path(tmp_path):
    """[text](path "title") must check `path`, not `path "title"`."""
    (tmp_path / "target.md").write_text("hi\n")
    (tmp_path / "SKILL.md").write_text('[text](target.md "a title")\n')
    assert build_skill.unresolved_links(tmp_path) == []


def test_is_excluded_catches_os_and_editor_leftovers():
    """These would otherwise ship inside the zip sent to Teaching & Learning."""
    for name in (".DS_Store", "SKILL.md.swp", "notes.md~", "stale.md.orig"):
        assert build_skill.is_excluded(Path(name)), name
    assert build_skill.is_excluded(Path("__pycache__/helper.pyc"))


def test_is_excluded_keeps_every_real_skill_file():
    """An over-broad rule would silently drop content instead of junk."""
    for name in (
        "SKILL.md",
        "INSTALL.md",
        "references/sheets.md",
        "references/csv-format.md",
        "playbooks/rollover.md",
    ):
        assert not build_skill.is_excluded(Path(name)), name


def test_is_excluded_ignores_directories_above_the_skill():
    """It takes a RELATIVE path on purpose.

    Passing an absolute path would test the checkout's own parents, so a
    clone living under a directory named __pycache__ would match every file
    and build an empty zip.
    """
    assert not build_skill.is_excluded(Path("references/sheets.md"))
    assert build_skill.is_excluded(Path("__pycache__") / "references" / "sheets.md")


def test_build_survives_a_checkout_under_an_excluded_directory_name(tmp_path):
    """The regression itself: the bug lived in the caller, not is_excluded.

    is_excluded's body never changed. build() used to hand it an ABSOLUTE
    path, so every ancestor segment was tested too and a checkout under a
    directory named __pycache__ excluded every file -- producing an empty
    zip with no error. Driving build() from such a layout is the only test
    here that fails against that bug.
    """
    skill = tmp_path / "__pycache__" / "repo" / "skill"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: x\nversion: 1.0.0\n---\n")
    (skill / "references" / "sheets.md").write_text("header\n")

    out = build_skill.build(skill, tmp_path / "dist")

    with zipfile.ZipFile(out) as z:
        names = {n for n in z.namelist() if not n.endswith("/")}
    assert names == {"SKILL.md", "references/sheets.md"}
