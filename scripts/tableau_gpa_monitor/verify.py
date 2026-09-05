"""Compare a regenerated workbook against the hand-built reference on every
styling dimension. Proves the specs + module reproduce the real work.

  uv run python .claude/scratch/gen/verify.py <regen.twbx> <reference.twbx>
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

from defusedxml import ElementTree

DS = "federated.0n798br073i5kb170j6l90uiv50a"


def facts(path):
    z = zipfile.ZipFile(path)
    t = z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode()
    r = ElementTree.fromstring(t)
    ds = next(d for d in r.iter("datasource") if d.get("name") == DS)
    cap = {c.get("name"): c.get("caption") for c in ds.findall("column")}

    colours = {}
    for e in ds.iter("encoding"):
        if e.get("attr") != "color":
            continue
        inst = e.get("field") or ""
        bare = inst.strip("[]").split(":")[1]
        colours[cap.get(f"[{bare}]", bare)] = tuple(
            sorted(
                (b.text, m.get("to")) for m in e.iter("map") for b in m.iter("bucket")
            )
        )

    defaults = {
        c.get("caption"): c.get("default-format")
        for c in ds.findall("column")
        if c.get("default-format")
    }

    sheets = {}
    for w in r.iter("worksheet"):
        nm = w.get("name")
        if not nm or not nm.startswith("GPA - "):
            continue
        wcap = {c.get("name"): c.get("caption") for c in w.iter("column")}
        inst2cap = {}
        for ci in w.iter("column-instance"):
            inst2cap[ci.get("name")] = wcap.get(ci.get("column"), ci.get("column"))
        fmts, align, stroke, label = {}, None, False, None
        for f in w.iter("format"):
            a = f.get("attr")
            if a == "text-format":
                ref = (f.get("field") or "").split("].", 1)[-1]
                fmts[inst2cap.get(ref, ref)] = f.get("value")
            elif a == "text-align":
                align = f.get("value")
            elif a == "has-stroke":
                stroke = True
        cl = w.find(".//customized-label")
        if cl is not None:
            label = tuple(
                (rn.text, rn.get("fontsize"))
                for rn in cl.iter("run")
                if rn.text and not rn.text.startswith("<[")
            )
        sheets[nm] = {
            "formats": tuple(sorted(fmts.items())),
            "align": align,
            "stroke": stroke,
            "label": label,
        }
    return {"colours": colours, "defaults": defaults, "sheets": sheets}


a, b = facts(sys.argv[1]), facts(sys.argv[2])
new, ref = Path(sys.argv[1]).name, Path(sys.argv[2]).name
print(f"{new}  vs  {ref}\n")

ok = fail = 0
for dim in ("colours", "defaults"):
    keys = sorted(set(a[dim]) | set(b[dim]))
    for k in keys:
        same = a[dim].get(k) == b[dim].get(k)
        ok, fail = (ok + 1, fail) if same else (ok, fail + 1)
        if not same:
            print(
                f"  DIFF {dim}/{k}:\n     regen={a[dim].get(k)}"
                f"\n     ref  ={b[dim].get(k)}"
            )
print(f"colours + default-formats: {ok} match, {fail} differ")

sok = sfail = 0
gaps = {}
for nm in sorted(set(a["sheets"]) | set(b["sheets"])):
    xa, xb = a["sheets"].get(nm, {}), b["sheets"].get(nm, {})
    for field in ("formats", "align", "stroke", "label"):
        same = xa.get(field) == xb.get(field)
        sok, sfail = (sok + 1, sfail) if same else (sok, sfail + 1)
        if not same:
            gaps.setdefault(field, []).append(nm)
print(f"per-sheet styling:         {sok} match, {sfail} differ")
for field, names in sorted(gaps.items()):
    print(
        f"  {field}: {len(names)} sheets differ -> {names[:4]}"
        f"{'...' if len(names) > 4 else ''}"
    )
