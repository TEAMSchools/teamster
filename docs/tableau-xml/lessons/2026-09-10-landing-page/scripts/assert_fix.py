"""assert_fix.py: assert the four render defects are fixed in out.twb, and
that nothing the rulings protect was lost.

    ~/.local/bin/uv run python /workspaces/teamster/.claude/scratch/tableau/lp/assert_fix.py

Written to FAIL against base.twb (production revision 26) and pass against
out.twb, so pass it a path:

    ... assert_fix.py base.twb   -> expected to fail
    ... assert_fix.py            -> checks out.twb
"""

import re
import sys
from pathlib import Path

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
NAVY = "#001e62"

TILES = (
    "LP - Tile Y1 GPA",
    "LP - Tile Course Failures",
    "LP - Tile Cumulative GPA",
    "LP - Tile Gradebook Health",
)
STRIPS = (
    "LP - Strip Y1 GPA",
    "LP - Strip Course Failures",
    "LP - Strip Cumulative GPA",
    "LP - Strip Gradebook Health",
)
GRADEBOOK = ("LP - Tile Gradebook Health", "LP - Strip Gradebook Health")


ZONE_RX = re.compile(r"<zone(?=[ >])[^>]*?(/?)>|</zone>")


def zone_block(text: str, marker: str) -> str:
    i = text.index(marker)
    start = text.rindex("<zone ", 0, i)
    depth, pos = 0, start
    while True:
        m = ZONE_RX.search(text, pos)
        if m is None:
            raise AssertionError(f"unbalanced zones around {marker!r}")
        if m.group(0).startswith("</zone"):
            depth -= 1
        elif m.group(1) != "/":
            depth += 1
        pos = m.end()
        if depth == 0:
            return text[start:pos]


def zone_open(text: str, zone_id: str) -> str:
    m = re.search(r"<zone (?=[^>]*\bid='" + re.escape(zone_id) + r"')[^>]*>", text)
    return m.group(0) if m else ""


def flow_gaps(d: str) -> dict:
    """For every layout-flow zone, parent size minus the sum of its children,
    along the flow axis.

    A flow container whose children do not sum to it is the shape that puts
    two zones on top of each other, and it is invisible in the XML until
    something renders over something else. The base already carries a 3-unit
    rounding gap on the Directory row from Desktop's own re-solve, so the
    test is "unchanged", not "zero".
    """
    out = {}
    for m in re.finditer(r"<zone (?=[^>]*type-v2='layout-flow')[^>]*>", d):
        tag = m.group(0)
        zid = re.search(r"id='([^']*)'", tag).group(1)
        horz = "param='horz'" in tag
        pw = int(re.search(r"\bw='(\d+)'", tag).group(1))
        ph = int(re.search(r"\bh='(\d+)'", tag).group(1))
        block = zone_block(d, f"id='{zid}'")
        inner = block[len(tag) :]
        cw = ch = 0
        depth = 0
        for mm in ZONE_RX.finditer(inner):
            if mm.group(0).startswith("</zone"):
                depth -= 1
                continue
            if depth == 0:
                ctag = mm.group(0)
                cw += int(re.search(r"\bw='(\d+)'", ctag).group(1))
                ch += int(re.search(r"\bh='(\d+)'", ctag).group(1))
            if mm.group(1) != "/":
                depth += 1
        out[zid] = (pw - cw) if horz else (ph - ch)
    return out


def ws(text: str, name: str) -> str:
    m = re.search(
        r"<worksheet name='" + re.escape(name) + r"'>.*?</worksheet>", text, re.S
    )
    if not m:
        raise AssertionError(f"worksheet missing: {name!r}")
    return m.group(0)


def label(block: str) -> str:
    m = re.search(r"<customized-label>.*?</customized-label>", block, re.S)
    return m.group(0) if m else ""


def value_runs(lab: str) -> list[str]:
    """The label's content runs, i.e. everything but the break runs."""
    runs = re.findall(r"<run[^>]*>.*?</run>", lab, re.S)
    return [r for r in runs if "Æ&#10;" not in r]


def check(text: str) -> list[str]:
    fails: list[str] = []

    def bad(msg: str) -> None:
        fails.append(msg)

    # ---- D1: label stacks small enough to fit their marks
    for name in ("LP - Tile Y1 GPA", "LP - Tile Course Failures"):
        lab = label(ws(text, name))
        n = len(value_runs(lab))
        if n != 4:
            bad(f"D1 {name}: {n} label runs, expected 4")
        if "vs. 2 wks" in lab or "vs. prev Q" in lab:
            bad(f"D1 {name}: trend tail still present")
        # ruling 1: the denominator line must survive AND resolve. A label run
        # renders a field only if that field is on the Text shelf; on Tooltip
        # alone it prints an empty gap.
        if "students" not in lab:
            bad(f"D1/R1 {name}: denominator line lost")
        block = ws(text, name)
        m = re.search(r"<encodings>.*?</encodings>", block, re.S)
        enc = m.group(0) if m else ""
        for inst in re.findall(r"\[usr:(Calculation_\d+):[a-z]+\]", lab):
            if "<text column='[federated." not in enc:
                bad(f"D1 {name}: no text encodings at all")
            on_text = any(
                inst in line for line in enc.splitlines() if "<text column=" in line
            )
            if not on_text:
                bad(f"D1 {name}: label field {inst} is not on the Text shelf")
    for name, cap in (
        ("LP - Tile Cumulative GPA", 22),
        ("LP - Tile Gradebook Health", 24),
    ):
        lab = label(ws(text, name))
        sizes = [int(s) for s in re.findall(r"fontsize='(\d+)'", lab)]
        if max(sizes) > cap:
            bad(f"D1 {name}: largest label run {max(sizes)}pt, expected <= {cap}")
    # All four strips: value plus its detail on ONE line. The stack is what
    # printed ####; side by side it fits, so the detail comes back rather
    # than staying dropped.
    for name in STRIPS:
        lab = label(ws(text, name))
        runs = value_runs(lab)
        if len(runs) != 2:
            bad(f"D1 {name}: {len(runs)} label runs, expected 2 (value + detail)")
        if "\u00c6&#10;" in lab:
            bad(f"D1 {name}: detail run is still on its own line")
        if runs and "fontsize='12'" not in runs[0]:
            bad(f"D1 {name}: value run is not 12pt")
        if len(runs) > 1 and "fontsize='8'" not in runs[1]:
            bad(f"D1 {name}: detail run is not 8pt")
        if len(runs) > 1 and "CDATA[  " not in runs[1]:
            bad(f"D1 {name}: detail run has no separator before it")
    if "still needed (region goal)" not in label(ws(text, "LP - Strip Cumulative GPA")):
        bad("D1 LP - Strip Cumulative GPA: detail text lost")
    # no sheet may still cull its labels (a culled label blanks, not clips)
    for name in TILES + STRIPS:
        if "mark-labels-cull' value='true'" in ws(text, name):
            bad(f"D1 {name}: mark-labels-cull still true")

    # ---- D2: no navy on the gradebook pair, no white text left behind
    for name in GRADEBOOK:
        b = ws(text, name)
        if f"<format attr='background-color' value='{NAVY}' />" in b:
            bad(f"D2 {name}: navy table background still present")
        if "#ffffff" in b:
            bad(f"D2 {name}: white text still present")
    if "element='header'" in ws(text, "LP - Strip Gradebook Health"):
        bad("D2 LP - Strip Gradebook Health: white header rule not removed")
    # the value must be readable, i.e. on the navy-on-white palette
    for name in GRADEBOOK:
        if f"fontcolor='{NAVY}'" not in label(ws(text, name)):
            bad(f"D2 {name}: value run is not navy-on-white")

    # ---- D3: no doubled Grade, parameter token preserved (rulings 8, 11)
    if "Grade <[Parameters].[Parameter 10]>" in text:
        bad("D3: literal 'Grade ' still precedes the grade parameter token")
    for name in ("LP - Tile Cumulative GPA", "LP - Strip Cumulative GPA"):
        m = re.search(r"<title>.*?</title>", ws(text, name), re.S)
        title = m.group(0) if m else ""
        if "[Parameters].[Parameter 10]" not in title:
            bad(f"D3/R8 {name}: grade parameter token lost from the title")

    # ---- D4 + layout: the header
    dash = re.search(r"<dashboard[^>]*name='Landing Page'.*?</dashboard>", text, re.S)
    d = dash.group(0) if dash else ""
    if not d:
        bad("Landing Page dashboard missing")
    hdr = zone_block(d, "friendly-name='Header'") if d else ""

    # D4 is fixed by width now, not by font size: the five buttons freed
    # 46855 units, the title took 29275 of them and went back to 16 pt.
    lab = label(ws(text, "LP - Title"))
    sizes = {int(s) for s in re.findall(r"fontsize='(\d+)'", lab)}
    if sizes != {16}:
        bad(f"D4 LP - Title: label sizes {sorted(sizes)}, expected exactly {{16}}")
    if "id='2'" in hdr and "w='60980'" not in zone_open(hdr, "2"):
        bad(f"D4 title zone not widened: {zone_open(hdr, '2')[:120]}")

    # ---- header height and the shortened canvas
    if "fixed-size='60'" not in zone_open(d, "9"):
        bad(f"header is not 60px: {zone_open(d, '9')[:120]}")
    size = re.search(r"<size[^>]*sizing-mode='fixed'[^>]*/>", d)
    ch = int(re.search(r"maxheight='(\d+)'", size.group(0)).group(1)) if size else 0
    if not size:
        bad("no fixed <size> on the dashboard")
    elif ch >= 1500:
        bad(f"canvas still {ch}px; the layout changes should have shortened it")
    # every vertical unit must be consistent with whatever canvas is declared
    if ch:
        uy = 100000 / ch
        for zid, px in (
            ("9", 60),
            ("14", 220),
            ("19", 150),
            ("36", 220),
            ("60", 420),
        ):
            m = re.search(r"\bh='(\d+)'", zone_open(d, zid))
            if m is None:
                bad(f"zone {zid} missing, cannot check its height")
                continue
            want = round(px * uy)
            if int(m.group(1)) != want:
                bad(f"zone {zid}: h={m.group(1)} but {px}px on a {ch} canvas is {want}")

    # ---- L1: no nav buttons anywhere on the dashboard
    nbuttons = len(re.findall(r"type-v2='dashboard-object'", d))
    if nbuttons:
        bad(f"L1 {nbuttons} header button zones remain, expected 0")
    if "tabdoc:goto-sheet" in d:
        bad("L1 a tabdoc:goto-sheet button survives on the dashboard")

    # ---- L2: roster links in the header, not in a body Links row
    if "friendly-name='Roster links'" not in hdr:
        bad("L2 no 'Roster links' container in the header")
    else:
        rost = zone_block(hdr, "friendly-name='Roster links'")
        for region in ("Newark", "Camden", "Paterson"):
            if f"name='Links - GPA Roster - {region}'" not in rost:
                bad(f"L2 roster container missing {region}")
    if "friendly-name='Links'" in d:
        bad("L2 the body Links row is still present")

    # ---- L3: the two reference blocks share one horizontal container
    if "friendly-name='Reference'" not in d:
        bad("L3 no 'Reference' container")
    else:
        ref = zone_block(d, "friendly-name='Reference'")
        if "param='horz'" not in zone_open(ref, "60"):
            bad("L3 Reference container is not horizontal")
        for zid in ("37", "38"):
            if f"id='{zid}'" not in ref:
                bad(f"L3 zone {zid} is not inside the Reference container")
        for dead in ("61", "62"):
            if f"id='{dead}'" in ref:
                bad(f"L3 stale wrapper zone {dead} survives")

    # ---- flow-container gaps: unchanged for zones the base already had,
    # zero for the containers this build created. A gap that grows is the
    # shape that slides one zone under another, and it raises no error.
    base_d = ""
    if (LP / "base.twb").exists():
        bt = (LP / "base.twb").read_text(encoding="utf-8", newline="")
        bm = re.search(r"<dashboard[^>]*name='Landing Page'.*?</dashboard>", bt, re.S)
        base_d = bm.group(0) if bm else ""
    base_gaps = flow_gaps(base_d) if base_d else {}
    for zid, gap in flow_gaps(d).items():
        want = base_gaps.get(zid, 0)
        if gap != want:
            bad(f"geometry zone {zid}: flow gap {gap}, expected {want}")

    # ---- default view opens on the page under review
    marks = re.findall(r"<window [^>]*maximized='true'[^>]*>", text)
    if len(marks) != 1 or "name='Landing Page'" not in marks[0]:
        bad(f"default view: {len(marks)} maximized windows, {marks[:1]}")

    return fails


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else LP / "out.twb"
    if not path.is_absolute():
        path = LP / path
    text = path.read_text(encoding="utf-8", newline="")
    fails = check(text)
    print(f"=== assert_fix on {path.name} ===")
    for f in fails:
        print(f"  FAIL {f}")
    print("PASS: all four defects fixed" if not fails else f"{len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
