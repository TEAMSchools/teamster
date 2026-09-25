"""Report relative markdown links whose targets do not exist.

Usage: check_links.py PATH...   (files or directories; scans *.md)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK = re.compile(r"\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
SKIP = ("http:", "https:", "mailto:", "#")


def _md_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        files.extend(sorted(path.rglob("*.md")) if path.is_dir() else [path])
    return files


def find_broken_links(paths: list[Path]) -> list[tuple[Path, int, str]]:
    broken: list[tuple[Path, int, str]] = []
    for md in _md_files(paths):
        fence: str | None = None
        for number, line in enumerate(md.read_text().splitlines(), start=1):
            match = FENCE.match(line)
            if match:
                marker = match.group(1)
                if fence is None:
                    fence = marker
                elif (
                    marker[0] == fence[0]
                    and len(marker) >= len(fence)
                    and not line.strip()[len(marker) :].strip()
                ):
                    fence = None
                continue
            if fence is not None:
                continue
            for target in LINK.findall(line):
                if target.startswith(SKIP):
                    continue
                if not (md.parent / target.split("#", 1)[0]).exists():
                    broken.append((md, number, target))
    return broken


def main(argv: list[str]) -> int:
    broken = find_broken_links([Path(p) for p in argv[1:]])
    for md, number, target in broken:
        print(f"{md}:{number}: {target}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
