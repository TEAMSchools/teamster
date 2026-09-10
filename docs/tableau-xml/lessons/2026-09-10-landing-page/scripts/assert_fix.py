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
    for name in (
        "LP - Strip Y1 GPA",
        "LP - Strip Course Failures",
        "LP - Strip Gradebook Health",
    ):
        lab = label(ws(text, name))
        n = len(value_runs(lab))
        if n != 1:
            bad(f"D1 {name}: {n} label runs, expected 1 (single value line)")
    # the cumulative strip already rendered correctly: it must NOT be touched
    cum = label(ws(text, "LP - Strip Cumulative GPA"))
    if len(value_runs(cum)) != 2:
        bad("D1 LP - Strip Cumulative GPA: the working strip was modified")
    if "still needed (region goal)" not in cum:
        bad("D1 LP - Strip Cumulative GPA: second line lost")
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

    # ---- D4: header title one step down
    lab = label(ws(text, "LP - Title"))
    sizes = {int(s) for s in re.findall(r"fontsize='(\d+)'", lab)}
    if sizes != {12}:
        bad(f"D4 LP - Title: label sizes {sorted(sizes)}, expected exactly {{12}}")

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
