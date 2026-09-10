"""Dump worksheet titles, captions, mark-label text, and column captions per datasource."""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SRC = Path("/workspaces/teamster/.claude/scratch/tableau/landing")


def text_of(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(r.text or "" for r in el.iter("run")).replace("Æ", "").strip()


def main(slug: str, pattern: str) -> None:
    root = ET.parse(SRC / f"{slug}.twb").getroot()
    rx = re.compile(pattern)
    for ws in root.iter("worksheet"):
        name = ws.get("name", "")
        if not rx.search(name):
            continue
        title = text_of(ws.find("./layout-options/title"))
        caption = text_of(ws.find("./layout-options/caption"))
        labels = [text_of(cl) for cl in ws.iter("customized-label")]
        tips = [text_of(ct) for ct in ws.iter("customized-tooltip")]
        # calculated columns local to the sheet with formulas that are string literals
        lits = []
        for col in ws.iter("column"):
            calc = col.find("calculation")
            if calc is not None and calc.get("formula", "").startswith('"'):
                lits.append(calc.get("formula")[:300])
        rows = [c.get("column") for c in ws.iter("rows")]
        print(f"\n## {name}")
        if title:
            print(f"title: {title!r}")
        if caption:
            print(f"caption: {caption!r}")
        for lab in labels:
            if lab:
                print(f"label: {lab[:600]!r}")
        for t in tips:
            if t:
                print(f"tooltip: {t[:300]!r}")
        for lit in lits:
            print(f"literal: {lit!r}")
        shelf_rows = ws.find("./table/rows")
        shelf_cols = ws.find("./table/cols")
        if shelf_rows is not None and shelf_rows.text:
            print(f"rows: {shelf_rows.text[:200]}")
        if shelf_cols is not None and shelf_cols.text:
            print(f"cols: {shelf_cols.text[:200]}")
        enc = ws.find("./table/panes")
        if enc is not None:
            for e in enc.iter("encoding"):
                print(f"enc: {e.attrib}")
            for t in enc.iter("text"):
                print(f"textshelf: {t.attrib}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
