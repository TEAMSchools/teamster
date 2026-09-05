"""Extract the build specs out of a finished .twbx into portable data.

Reads build/20-goalstrip-full.twbx and emits specs.py, in which every reference
is a CAPTION rather than an internal [Calculation_...] id. That is what makes
the specs re-appliable to a fresh server baseline whose ids differ.

Run:  uv run python .claude/scratch/gen/extract_specs.py
"""

from __future__ import annotations

import pprint
import re
import zipfile
from pathlib import Path

from defusedxml import ElementTree

D = Path("/workspaces/teamster/.claude/scratch/gpa-goal-progress")
SRC = D / "build" / "20-goalstrip-full.twbx"
OUT = Path("/workspaces/teamster/.claude/scratch/gen/specs.py")
DS = "federated.0n798br073i5kb170j6l90uiv50a"
DS_CAP = "rpt_tableau__gpa_goal_progress (kipptaf_tableau)"

z = zipfile.ZipFile(SRC)
twb = next(n for n in z.namelist() if n.endswith(".twb"))
t = z.read(twb).decode("utf-8")
root = ElementTree.fromstring(t)

dsx = next(d for d in root.iter("datasource") if d.get("name") == DS)
params_ds = next(d for d in root.iter("datasource") if d.get("name") == "Parameters")

# ---- name -> caption, for both the datasource and the parameters ----
name2cap: dict[str, str] = {}
for c in dsx.findall("column"):
    if c.get("name") and c.get("caption"):
        name2cap[c.get("name") or ""] = c.get("caption") or ""
param_cap: dict[str, str] = {}
for c in params_ds.findall("column"):
    if c.get("name") and c.get("caption"):
        param_cap[c.get("name") or ""] = c.get("caption") or ""

# extract columns have no declared <column>; derive their caption the way
# Tableau does, from the snake_case local-name
for mr in dsx.iter("metadata-record"):
    if mr.get("class") != "column":
        continue
    loc = mr.find("local-name")
    if loc is None or not loc.text:
        continue
    ln = loc.text.strip("[]")
    name2cap.setdefault(f"[{ln}]", " ".join(w.capitalize() for w in ln.split("_")))


def to_captions(formula: str) -> str:
    """Rewrite internal ids back to captions so the formula is portable."""

    def param(m):
        return f"[{param_cap[f'[{m.group(1)}]']}]"

    s = re.sub(r"\[Parameters\]\.\[(Parameter \d+)\]", param, formula)

    def col(m):
        tok = m.group(0)
        return f"[{name2cap[tok]}]" if tok in name2cap else tok

    return re.sub(r"\[[^\[\]]+\]", col, s)


# ---------------- calculated fields ----------------
calcs = []
for c in dsx.findall("column"):
    calc = c.find("calculation")
    if calc is None or not calc.get("formula"):
        continue
    calcs.append(
        {
            "caption": c.get("caption"),
            "datatype": c.get("datatype"),
            "role": c.get("role"),
            "type": c.get("type"),
            "aggregation": c.get("aggregation"),
            "default_format": c.get("default-format"),
            "formula": to_captions(calc.get("formula") or ""),
        }
    )

# ---------------- parameters ----------------
params = []
for c in params_ds.findall("column"):
    members = [
        {"value": m.get("value"), "alias": m.get("alias")} for m in c.iter("member")
    ]
    params.append(
        {
            "caption": c.get("caption"),
            "datatype": c.get("datatype"),
            "type": c.get("type"),
            "value": c.get("value"),
            "alias": c.get("alias"),
            "members": members,
        }
    )


# ---------------- worksheets ----------------
def inst_caption(ws, inst_name):
    for ci in ws.iter("column-instance"):
        if ci.get("name") == inst_name:
            col = ci.get("column")
            return name2cap.get(col, col), ci.get("derivation")
    return inst_name, None


sheets = []
for ws in root.iter("worksheet"):
    nm = ws.get("name")
    if not nm or not nm.startswith("GPA - "):
        continue
    tb = ws.find("table")
    pane = tb.find(".//pane") if tb is not None else None
    if tb is None or pane is None:
        continue
    mark = pane.find("mark")
    entry = {
        "name": nm,
        "mark": mark.get("class") if mark is not None else None,
        "shelves": {},
        "filters": [],
        "formats": [],
        "label": None,
        "align": None,
        "stroke": False,
    }
    for shelf in ("rows", "cols"):
        el = tb.find(shelf)
        txt = (el.text or "").strip() if el is not None else ""
        pills = []
        for i in re.findall(r"\[(?:none|usr|avg|min|sum|attr|pcto)[^\]]*\]", txt):
            cap, deriv = inst_caption(ws, i)
            pcto = i.startswith("[pcto:")
            pills.append({"field": cap, "deriv": deriv, "pct_of_total": pcto})
        if ":Measure Names" in txt:
            pills.append(
                {"field": ":Measure Names", "deriv": None, "pct_of_total": False}
            )
        entry["shelves"][shelf] = pills
    for enc in ("color", "text", "tooltip", "lod"):
        out = []
        for el in ws.iter(enc):
            ref = (el.get("column") or "").split("].", 1)[-1]
            if ref == "[Multiple Values]":
                out.append({"field": ":Measure Values", "deriv": None})
                continue
            cap, deriv = inst_caption(ws, ref)
            out.append({"field": cap, "deriv": deriv})
        if out:
            entry["shelves"][enc] = out
    for f in ws.iter("filter"):
        ref = (f.get("column") or "").split("].", 1)[-1]
        cap, _ = inst_caption(ws, ref)
        gf = f.find("groupfilter")
        if gf is None:
            continue
        fn = gf.get("function")
        if fn == "member":
            entry["filters"].append(
                {"field": cap, "kind": "member", "value": gf.get("member")}
            )
        elif fn == "union":
            entry["filters"].append(
                {
                    "field": cap,
                    "kind": "members",
                    "values": [x.get("member") for x in gf],
                }
            )
        elif fn == "except":
            entry["filters"].append({"field": cap, "kind": "exclude_null"})
    for fm in ws.iter("format"):
        if fm.get("attr") == "text-format":
            ref = (fm.get("field") or "").split("].", 1)[-1]
            cap, _ = inst_caption(ws, ref)
            entry["formats"].append({"field": cap, "format": fm.get("value")})
        elif fm.get("attr") == "text-align":
            entry["align"] = fm.get("value")
        elif fm.get("attr") == "has-stroke":
            entry["stroke"] = True
    cl = ws.find(".//customized-label")
    if cl is not None:
        runs = [
            {
                "text": r.text,
                "size": r.get("fontsize"),
                "bold": r.get("bold"),
                "color": r.get("fontcolor"),
            }
            for r in cl.iter("run")
        ]
        entry["label"] = runs
    sheets.append(entry)

# ---------------- dashboard layout ----------------
dash = next(
    d for d in root.iter("dashboard") if d.get("name") == "Cumulative GPA Monitor"
)
sz = dash.find("size")
if sz is None:
    raise SystemExit("dashboard has no <size> element")


def zone_tree(z_el):
    out = {
        "friendly": z_el.get("friendly-name"),
        "type": z_el.get("type-v2"),
        "param": z_el.get("param"),
        "sheet": z_el.get("name"),
        "fixed_size": z_el.get("fixed-size"),
        "w": z_el.get("w"),
        "h": z_el.get("h"),
        "x": z_el.get("x"),
        "y": z_el.get("y"),
    }
    bg = [
        f.get("value")
        for f in z_el.iter("format")
        if f.get("attr") == "background-color"
    ]
    if bg:
        out["background"] = bg[0]
    kids = [zone_tree(k) for k in z_el if k.tag == "zone"]
    if kids:
        out["children"] = kids
    return out


layout = {
    "name": dash.get("name"),
    "size": {
        k: sz.get(k)
        for k in ("minwidth", "maxwidth", "minheight", "maxheight", "sizing-mode")
    },
    "zones": [zone_tree(z) for zs in dash.iter("zones") for z in zs],
}

# ---------------- colours ----------------
colours = []
for enc in dsx.iter("encoding"):
    if enc.get("attr") != "color":
        continue
    inst = enc.get("field") or ""
    m = re.match(r"\[(\w+):(.+):(\w+)\]", inst)
    if m is None:
        continue
    deriv, bare = m.group(1), m.group(2)
    colours.append(
        {
            "field": name2cap.get(f"[{bare}]", bare),
            "derivation": {"none": "None", "usr": "User"}.get(deriv, deriv),
            "map": [
                {"value": b.text, "hex": mp.get("to")}
                for mp in enc.iter("map")
                for b in mp.iter("bucket")
            ],
        }
    )

spec = {
    "datasource": {"name": DS, "caption": DS_CAP},
    "parameters": params,
    "calculated_fields": calcs,
    "worksheets": sheets,
    "dashboard": layout,
    "colours": colours,
}

# a Python literal, not JSON -- JSON's null/true/false are not Python, and the
# data legitimately contains the STRING "true" (boolean filter members)
body = pprint.pformat(spec, indent=1, width=88, sort_dicts=False)
OUT.write_text(
    '"""Cumulative GPA Monitor build specs.\n\n'
    "Extracted from build/20-goalstrip-full.twbx. Every field reference is a\n"
    "CAPTION, never an internal id, so these re-apply to any baseline.\n"
    'Regenerate with extract_specs.py.\n"""\n\n'
    "SPEC = " + body + "\n",
    encoding="utf-8",
)

print(f"parameters        : {len(params)}")
print(f"calculated fields : {len(calcs)}")
print(f"worksheets        : {len(sheets)}")
print(f"colour rules      : {len(colours)}")
print(f"dashboard zones   : {len(re.findall(chr(39) + 'type' + chr(39), body))}")
print(f"\nwrote {OUT} ({OUT.stat().st_size / 1024:.0f}KB)")

# ---- fidelity check: every formula reference resolved to a caption ----
bad = []
for c in calcs:
    for tok in re.findall(r"\[[^\[\]]+\]", c["formula"]):
        inner = tok.strip("[]")
        known = (
            {x["caption"] for x in calcs}
            | set(name2cap.values())
            | {p["caption"] for p in params}
        )
        if inner not in known:
            bad.append((c["caption"], tok))
print(f"\nunresolved references in formulas: {len(bad)}")
for c, tok in bad[:10]:
    print(f"   {c}: {tok}")
