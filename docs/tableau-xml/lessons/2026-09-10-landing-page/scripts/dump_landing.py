"""Dump dashboard zone trees (text, sheets, nav) from downloaded .twb files."""

import sys

# trunk-ignore(bandit/B405): parse-only read of a workbook we downloaded ourselves
import xml.etree.ElementTree as ET
from pathlib import Path

SRC = Path("/workspaces/teamster/.claude/scratch/tableau/landing")


def text_of(zone: ET.Element) -> str:
    runs = [r.text or "" for r in zone.iter("run")]
    return "".join(runs).replace("Æ", "").strip()


def walk(zone: ET.Element, depth: int, out: list[str]) -> None:
    kind = zone.get("type-v2") or zone.get("type") or "container"
    name = zone.get("name") or ""
    param = zone.get("param") or ""
    txt = text_of(zone)
    label = f"{'  ' * depth}- [{kind}]"
    if name:
        label += f" sheet={name!r}"
    if param:
        label += f" param={param!r}"
    if txt:
        label += f" text={txt[:400]!r}"
    if kind != "container" or name or txt:
        out.append(label)
    for child in zone.findall("zone"):
        walk(child, depth + 1, out)


def dump(slug: str, dashboards: set[str]) -> None:
    # trunk-ignore(bandit/B314): parse-only read of a workbook we downloaded ourselves
    root = ET.parse(SRC / f"{slug}.twb").getroot()
    ws_titles = {}
    for ws in root.iter("worksheet"):
        title = ws.find("./layout-options/title")
        ws_titles[ws.get("name")] = text_of(title) if title is not None else ""
    for db in root.iter("dashboard"):
        if db.get("name") not in dashboards:
            continue
        print(f"\n===== {slug} :: {db.get('name')} =====")
        size = db.find("size")
        if size is not None:
            print(f"size: {size.attrib}")
        out: list[str] = []
        zones = db.find("zones")
        if zones is not None:
            for z in zones.findall("zone"):
                walk(z, 0, out)
        print("\n".join(out))
        print("-- worksheets used and their titles:")
        for z in db.iter("zone"):
            n = z.get("name")
            if n and n in ws_titles:
                print(f"  {n!r}: {ws_titles[n]!r}")
    print(f"\n-- {slug} actions:")
    for act in root.iter("action"):
        cap = act.get("caption")
        src = act.find("source")
        cmd = act.find("command")
        cmd_s = cmd.get("command") if cmd is not None else ""
        print(f"  {cap!r} src={src.attrib if src is not None else {}} cmd={cmd_s}")
    print(f"\n-- {slug} dashboards:")
    for db in root.iter("dashboard"):
        print(f"  {db.get('name')!r}")


if __name__ == "__main__":
    dump(sys.argv[1], set(sys.argv[2:]))
