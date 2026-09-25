"""Split an oversized skill file into references, verbatim, by `## ` heading.

Usage: split_skill.py SOURCE MAPPING_JSON OUTDIR

MAPPING_JSON maps each `## ` heading text to a destination path relative to
OUTDIR, plus an optional "_default" key for lines before the first heading
(default: SKILL.md). Every source line lands in exactly one destination.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FENCE = re.compile(r"^(`{3,}|~{3,})")


def _closes(line: str, marker: str, fence: str) -> bool:
    return (
        marker[0] == fence[0]
        and len(marker) >= len(fence)
        and not line[len(marker) :].strip()
    )


def split_sections(
    text: str, mapping: dict[str, str], default: str
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    dest = default
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif _closes(line, marker, fence):
                fence = None
        elif fence is None and line.startswith("## "):
            heading = line[3:].strip()
            if heading not in mapping:
                raise KeyError(f"unmapped heading: {heading}")
            dest = mapping[heading]
        out.setdefault(dest, []).append(line)
    return out


def main(argv: list[str]) -> int:
    source, mapping_path, outdir = Path(argv[1]), Path(argv[2]), Path(argv[3])
    mapping = json.loads(mapping_path.read_text())
    default = mapping.pop("_default", "SKILL.md")
    text = source.read_text()
    out = split_sections(text, mapping, default)
    for dest, lines in out.items():
        path = outdir / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(lines))
    lines_in = len(text.splitlines(keepends=True))
    lines_out = sum(len(v) for v in out.values())
    print(f"lines in: {lines_in}, lines out: {lines_out}")
    return 0 if lines_in == lines_out else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
