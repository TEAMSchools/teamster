"""Print a dashboard's zone tree: depth, id, type, name/param, geometry."""

import re
import sys

# trunk-ignore(bandit/B405)
import xml.etree.ElementTree as ET
from pathlib import Path

t = Path(sys.argv[1]).read_text(encoding="utf-8", newline="")
name = sys.argv[2]
m = re.search(r"<dashboard[^>]*name='" + re.escape(name) + r"'.*?</dashboard>", t, re.S)
if not m:
    raise SystemExit(f"no dashboard {name!r}")
root = ET.fromstring(m.group(0))  # trunk-ignore(bandit/B314)
zones = root.find("zones")


def walk(el, depth=0):
    for z in el.findall("zone"):
        a = z.attrib
        who = a.get("name") or a.get("param") or a.get("type-v2") or ""
        fixed = f" fixed={a['fixed-size']}" if "fixed-size" in a else ""
        fn = f" [{a['friendly-name']}]" if "friendly-name" in a else ""
        btn = z.find("button")
        cap = ""
        if btn is not None:
            c = btn.find(".//caption")
            cap = f" BUTTON caption={c.text!r}" if c is not None else " BUTTON"
        print(
            f"{'  ' * depth}id={a.get('id', '-'):>3} {a.get('type-v2', 'sheet'):<14}"
            f" x={a.get('x'):>6} y={a.get('y'):>6} w={a.get('w'):>6} h={a.get('h'):>6}"
            f"{fixed}{fn} {who}{cap}"
        )
        walk(z, depth + 1)


walk(zones)
