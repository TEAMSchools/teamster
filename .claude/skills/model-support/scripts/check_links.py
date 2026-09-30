"""Report relative markdown links whose targets do not exist.

Usage: check_links.py PATH...   (files or directories; scans *.md)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

# [text](<target>), [text](target), or either followed by a "title".
LINK = re.compile(r"\]\((?:<([^>]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"(`+).+?\1")
LIST_ITEM = re.compile(r"^\s*([-*+]|\d+[.)])\s")
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
        in_list = prev_blank = indented_code = False
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
            blank = not line.strip()
            indented = line.startswith(("    ", "\t"))
            if LIST_ITEM.match(line):
                in_list = True
            elif not blank and not indented:
                in_list = False
            # An indented code block opens after a blank line, outside a list.
            indented_code = indented and not in_list and (prev_blank or indented_code)
            prev_blank = blank
            if indented_code:
                continue
            for angle, bare in LINK.findall(INLINE_CODE.sub("", line)):
                target = angle or bare
                if target.startswith(SKIP):
                    continue
                if not (md.parent / unquote(target.split("#", 1)[0])).exists():
                    broken.append((md, number, target))
    return broken


def main(argv: list[str]) -> int:
    broken = find_broken_links([Path(p) for p in argv[1:]])
    for md, number, target in broken:
        print(f"{md}:{number}: {target}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
