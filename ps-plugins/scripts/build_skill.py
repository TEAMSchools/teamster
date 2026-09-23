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

VERSION = re.compile(r'^version:\s*"([^"]+)"', re.MULTILINE)
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def skill_version(skill_dir: Path) -> str:
    match = VERSION.search((skill_dir / "SKILL.md").read_text())
    if match is None:
        raise ValueError("SKILL.md frontmatter has no version: field")
    return match.group(1)


def unresolved_links(skill_dir: Path) -> list[str]:
    """Relative markdown links that do not resolve inside the skill folder."""
    missing: list[str] = []
    for md in sorted(skill_dir.rglob("*.md")):
        for target in MD_LINK.findall(md.read_text()):
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
            if f.is_file():
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
