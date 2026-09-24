#!/usr/bin/env python3
"""Package the end-user Claude skill into an installable zip.

The files go at the ZIP ROOT, not inside a folder. That is the layout that
installs correctly in Claude Desktop today; nesting them breaks the install with
no useful error.

Standard library only, like build_plugin.py.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "gradebook-expectations-upload"
DIST = REPO / "dist"  # ps-plugins/dist, beside the plugin zips

# This zip is sent to Teaching & Learning, so anything a local editor or the OS
# leaves behind would ship to them. build_plugin.py excludes the same shapes.
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep"}
EXCLUDE_SUFFIXES = (".pyc", ".swp", ".swo", ".bak", ".orig", ".rej", "~")
EXCLUDE_DIRS = {"__pycache__", ".ipynb_checkpoints"}


def is_excluded(path: Path) -> bool:
    """Editor and OS leftovers that must not reach an end user's install."""
    if path.name in EXCLUDE_NAMES or path.name.endswith(EXCLUDE_SUFFIXES):
        return True
    return any(part in EXCLUDE_DIRS for part in path.parts)


# Accepts "1.0.0", '1.0.0', and 1.0.0 -- whatever quote style the next editor
# of SKILL.md's frontmatter happens to use.
VERSION = re.compile(r"^version:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", re.MULTILINE)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# A markdown link may carry a title after the path: [text](path "title") or
# [text](path 'title'). Strips it so the title text isn't checked as part of
# the path.
LINK_TITLE = re.compile(r"^(\S+)\s+[\"'].*[\"']$")


def skill_version(skill_dir: Path) -> str:
    match = VERSION.search((skill_dir / "SKILL.md").read_text())
    if match is None:
        raise ValueError("SKILL.md frontmatter has no version: field")
    return match.group(1)


def unresolved_links(skill_dir: Path) -> list[str]:
    """Relative markdown links that do not resolve inside the skill folder.

    Only inline links (`[text](path)`, optionally with a trailing title) are
    checked. Reference-style links (`[text][ref]`) are not matched at all, so
    a broken one passes silently, and links inside fenced code blocks are
    checked as if they were real -- both are accepted limitations, not bugs to
    fix here, given the skill uses inline links throughout.
    """
    missing: list[str] = []
    for md in sorted(skill_dir.rglob("*.md")):
        for raw_target in MD_LINK.findall(md.read_text()):
            target = raw_target.strip()
            title_match = LINK_TITLE.match(target)
            if title_match:
                target = title_match.group(1)
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if not (md.parent / target.split("#")[0]).exists():
                missing.append(f"{md.relative_to(skill_dir)} -> {target}")
    return missing


def build(skill_dir: Path, dist: Path) -> Path:
    broken = unresolved_links(skill_dir)
    if broken:
        raise ValueError(f"broken relative links: {broken}")

    dist.mkdir(parents=True, exist_ok=True)
    out = dist / f"gradebook_expectations_upload_v{skill_version(skill_dir)}.zip"
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill_dir.rglob("*")):
            if f.is_file() and not is_excluded(f):
                z.write(f, f.relative_to(skill_dir))
    return out


def main() -> int:
    out = build(SKILL, DIST)
    with zipfile.ZipFile(out) as z:
        count = len([n for n in z.namelist() if not n.endswith("/")])
    print(f"wrote {out.name} ({count} files, {out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
