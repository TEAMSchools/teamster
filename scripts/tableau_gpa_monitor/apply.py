"""Apply the spec's styling layer to a workbook that already has the sheets.

Covers what builds 09-20 did: field default colours, per-sheet number formats,
BAN captions, stacked-bar strokes, tile alignment. Idempotent-ish: it asserts
the target is unstyled rather than double-applying.

  uv run python .claude/scratch/gen/apply.py <in.twbx> <out.twbx>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from specs import SPEC  # noqa: E402
from twb import Workbook, esc  # noqa: E402

DS = SPEC["datasource"]["name"]
DS_CAP = SPEC["datasource"]["caption"]


def apply_all(src: Path, out: Path) -> Workbook:
    wb = Workbook(src)
    caps = wb.caption_map(DS)
    added = []

    # ---- 1. datasource column-instances for every coloured field ----------
    ds_s, ds_e = wb.ds_bounds(DS_CAP, DS)
    existing = set()
    for line in wb.t[ds_s:ds_e].split("\r\n"):
        if "<column-instance " in line and "name='" in line:
            existing.add(line.split("name='")[1].split("'")[0])
    ci_xml = ""
    for rule in SPEC["colours"]:
        col = caps[rule["field"]]
        inst = wb.instance(col, rule["derivation"], "nk")
        if inst in existing:
            continue
        ci_xml += (
            f"\r\n      <column-instance column='{col}' "
            f"derivation='{rule['derivation']}' name='{inst}' "
            f"pivot='key' type='nominal' />"
        )
    if ci_xml:
        wb.insert_before("\r\n      <extract ", ci_xml, ds_s)
        added.append(ci_xml)

    # ---- 2. the colour block ---------------------------------------------
    ds_s, ds_e = wb.ds_bounds(DS_CAP, DS)
    if "\r\n      <style>" in wb.t[ds_s:ds_e]:
        raise ValueError("datasource already carries a <style> block")
    body = ""
    for rule in SPEC["colours"]:
        inst = wb.instance(caps[rule["field"]], rule["derivation"], "nk")
        maps = ""
        for m in rule["map"]:
            v = m["value"]
            bucket = v if v == "%null%" else f"&quot;{v.strip(chr(34))}&quot;"
            maps += (
                f"\r\n            <map to='{m['hex']}'>"
                f"\r\n              <bucket>{bucket}</bucket>"
                f"\r\n            </map>"
            )
        body += (
            f"\r\n          <encoding attr='color' field='{inst}' "
            f"type='palette'>{maps}"
            f"\r\n          </encoding>"
        )
    style_xml = (
        f"\r\n      <style>"
        f"\r\n        <style-rule element='mark'>{body}"
        f"\r\n        </style-rule>"
        f"\r\n      </style>"
    )
    wb.insert_before("\r\n      <semantic-values>", style_xml, ds_s)
    added.append(style_xml)

    # ---- 3. default-format on the columns ---------------------------------
    nfmt = 0
    for c in SPEC["calculated_fields"]:
        if not c.get("default_format"):
            continue
        ds_s, ds_e = wb.ds_bounds(DS_CAP, DS)
        blk = wb.t[ds_s:ds_e]
        import re

        m = re.search(
            r"(\r\n      <column [^>]*?caption='"
            + re.escape(c["caption"])
            + r"' )(datatype=)",
            blk,
        )
        if not m:
            continue
        new = (
            blk[: m.start(2)]
            + f"default-format='{c['default_format']}' "
            + blk[m.start(2) :]
        )
        wb.t = wb.t[:ds_s] + new + wb.t[ds_e:]
        nfmt += 1

    # ---- 4. per-sheet styling --------------------------------------------
    nstyle = nlabel = nstroke = 0
    for sheet in SPEC["worksheets"]:
        nm = sheet["name"]
        marker = f"\r\n    <worksheet name='{nm}'>"
        if marker not in wb.t:
            continue
        s = wb.t.index(marker)
        e = wb.t.index("\r\n    </worksheet>", s)
        blk = wb.t[s:e]
        decl = set()
        for line in blk.split("\r\n"):
            if "<column-instance " in line and "name='" in line:
                decl.add(line.split("name='")[1].split("'")[0])

        # bind `decl` per iteration: a bare closure over the loop
        # variable would resolve against the LAST sheet (ruff B023)
        def find_inst(caption, decl=decl):
            col = caps.get(caption)
            if not col:
                return None
            bare = col.strip("[]")
            for i in decl:
                parts = i.strip("[]").split(":")
                if bare in parts:
                    return i
            return None

        # table-level: text-format rules + alignment
        rules = ""
        for f in sheet.get("formats", []):
            inst = find_inst(f["field"])
            if not inst:
                continue
            rules += (
                f"\r\n          <style-rule element='cell'>"
                f"\r\n            <format attr='text-format' "
                f"field='[{DS}].{inst}' value='{esc(f['format'])}' />"
                f"\r\n          </style-rule>"
            )
        if sheet.get("align"):
            rules += (
                f"\r\n          <style-rule element='cell'>"
                f"\r\n            <format attr='text-align' "
                f"value='{sheet['align']}' />"
                f"\r\n          </style-rule>"
            )
        if rules and "\r\n        <style />" in blk:
            blk = blk.replace(
                "\r\n        <style />",
                f"\r\n        <style>{rules}\r\n        </style>",
                1,
            )
            nstyle += 1

        # pane-level: mark labels on, and the stacked-bar white stroke
        pane_fmt = ""
        if sheet.get("stroke"):
            pane_fmt += (
                "\r\n                <format attr='has-stroke' "
                "value='true' />"
                "\r\n                <format attr='stroke-color' "
                "value='#ffffff' />"
            )
            nstroke += 1
        if pane_fmt and "mark-labels-show" in blk:
            i = blk.index("<format attr='mark-labels-show' value='true' />")
            j = blk.index("/>", i) + 2
            blk = blk[:j] + pane_fmt + blk[j:]

        # customized-label. The value run is a CDATA pill reference; rebuild
        # it against THIS workbook's instance rather than the spec's id.
        if sheet.get("label") and "<customized-label>" not in blk:
            import re as _re

            tm = _re.search(
                r"<text column='\[" + _re.escape(DS) + r"\]\.([^']+)' />", blk
            )
            if tm:
                pill = tm.group(1)
                runs = ""
                for r in sheet["label"]:
                    txt = r["text"] or ""
                    attrs = ""
                    if r.get("size"):
                        attrs += f" fontsize='{r['size']}'"
                    if r.get("bold"):
                        attrs += " bold='true'"
                    if r.get("color"):
                        attrs += f" fontcolor='{r['color']}'"
                    if txt.startswith("<["):
                        runs += (
                            f"\r\n                <run{attrs}>"
                            f"<![CDATA[<[{DS}].{pill}>]]></run>"
                        )
                    elif txt.strip("\r\n") == "Æ" or txt.startswith("Æ"):
                        runs += "\r\n                <run>Æ&#10;</run>"
                    else:
                        runs += f"\r\n                <run{attrs}>{esc(txt)}</run>"
                lbl = (
                    f"\r\n            <customized-label>"
                    f"\r\n              <formatted-text>{runs}"
                    f"\r\n              </formatted-text>"
                    f"\r\n            </customized-label>"
                )
                anchor = "\r\n            </encodings>"
                if anchor in blk:
                    k = blk.index(anchor) + len(anchor)
                    blk = blk[:k] + lbl + blk[k:]
                    nlabel += 1
        wb.t = wb.t[:s] + blk + wb.t[e:]

    print(f"  column-instances : {ci_xml.count('<column-instance')}")
    print(f"  colour rules     : {len(SPEC['colours'])}")
    print(f"  default-formats  : {nfmt}")
    print(f"  sheet styles     : {nstyle}")
    print(f"  strokes          : {nstroke}")
    print(f"  BAN labels       : {nlabel}")

    wb.check()
    bad = wb.audit_shelf_refs()
    if bad:
        raise ValueError(f"unresolved shelf refs: {bad}")
    unused = wb.audit_colour_rules(DS)
    if unused:
        raise ValueError(f"colour rules nothing uses: {unused}")
    print("  audits: shelf refs OK, colour rules OK")
    print("  (geometry audit skipped: only valid on freshly generated layout)")
    wb.save(out)
    return wb


if __name__ == "__main__":
    a, b = Path(sys.argv[1]), Path(sys.argv[2])
    print(f"applying spec styling: {a.name} -> {b.name}")
    apply_all(a, b)
    print(f"wrote {b}")
