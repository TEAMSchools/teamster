"""fix_lp.py: fix the four render defects on the Landing Page.

    ~/.local/bin/uv run python /workspaces/teamster/.claude/scratch/tableau/lp/fix_lp.py

Reads base.twb (production revision 26, which ALREADY CONTAINS the landing
page), writes out.twb. This is a patch script, not a build script: build_lp.py
added the page to a workbook that did not have one and cannot run against a
base that does.

The four defects, and why each fix is the fix:

D1  Every tile number and three of the four region-strip values render as
    `####`. `####` is Tableau's "the mark label does not fit this cell".
    The one strip that renders correctly (cumulative) is the only one with
    two region rows instead of three, i.e. the only one whose rows are tall
    enough for a two-line label -- so the constraint is vertical space per
    mark, not width, not number format, and not data. The skill's catalog
    says the same thing from the other side: removing one <run> line fixed
    it, growing the box did not. So the fix shortens label stacks rather
    than resizing zones, which also keeps dashboard geometry untouched.

D2  The healthy-gradebook tile and strip inherit a navy `element='table'`
    background from the Gradebook Rollup sheets they were cloned from, and
    their label runs are white to suit it. Drop the background, put the text
    back on the palette the other three tiles use.

D3  The cumulative tile and strip titles read `Grade Grade 11`: the title run
    opens with a literal `Grade ` and `[Parameter 10]`'s aliases are already
    `Grade 9` / `Grade 10` / `Grade 11`.

D4  The header title truncates to `Academic & Gradebook Health | Landi..`
    at 16 pt in a 29059-unit (~436 px) zone. 14 pt still clipped (`Landing
    P..`) on the round-1 render, so this goes to 12 pt; widening the zone
    would mean reflowing all eight header zones by hand.

Ruling check: no fix contradicts a ruling in the SDD ledger.
  - Ruling 1 (denominator line on the Y1 and failures tiles) is PRESERVED;
    the runs dropped are the two redundant trend lines, not the denominator.
  - Rulings 8 and 11 (the cumulative tile and strip titles must name the
    grade parameter) are PRESERVED; only the duplicated literal word goes,
    the `[Parameters].[Parameter 10]` token stays.
  - Ruling 9 (the `(projected)` qualifier) is untouched.
  - Ruling 12 has two halves. The 12/8 pt strip sizes stay for the value run.
    Its white `element='header'` rule is REMOVED, because the ruling's stated
    reason -- "region names would render in the default dark header colour on
    navy" -- is exactly what D2 deletes. Keeping it would put white header
    text on a white background, which is the same bug with the colours
    swapped.
"""

import re
import xml.etree.ElementTree as ET  # trunk-ignore(bandit/B405): parse-only well-formedness check on a file we wrote
from pathlib import Path

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
BASE = LP / "base.twb"
OUT = LP / "out.twb"

GRADES_DS = "federated.1ikycy21f3ow4k1eazzbx1iah2yl"
NAVY = "#001e62"
GREY = "#8c8c8c"

#: The dashboard whose window carries the default-view marker in the output.
TARGET_DASHBOARD = "Landing Page"
MARKER = " maximized='true'"


def sub_once(text: str, anchor: str, replacement: str) -> str:
    n = text.count(anchor)
    if n != 1:
        raise RuntimeError(f"anchor matched {n} times, expected 1: {anchor[:100]!r}")
    return text.replace(anchor, replacement)


def sub_n(text: str, anchor: str, replacement: str, n: int) -> str:
    got = text.count(anchor)
    if got != n:
        raise RuntimeError(
            f"anchor matched {got} times, expected {n}: {anchor[:100]!r}"
        )
    return text.replace(anchor, replacement)


def edit_worksheet(text: str, name: str, fn) -> str:
    """Extract one <worksheet>, run fn on it, assert it changed, put it back."""
    pat = r"<worksheet name='" + re.escape(name) + r"'>.*?</worksheet>"
    m = re.search(pat, text, re.S)
    if not m:
        raise RuntimeError(f"worksheet not found: {name!r}")
    before = m.group(0)
    after = fn(before)
    if after == before:
        raise RuntimeError(f"edit was a no-op on {name!r}")
    return sub_once(text, before, after)


# --------------------------------------------------------------- D1: ####


def drop_trend_tail(block: str) -> str:
    """Remove the trailing `vs. 2 wks` and `vs. prev Q` label lines, with the
    break run that precedes each. Leaves heading / value / denominator /
    `vs. 1 wk` -- four lines where there were six."""
    pat = (
        r"\r\n\s*<run>Æ&#10;</run>"
        r"\r\n\s*<run fontname='Tableau Light' fontsize='10'>"
        r"<!\[CDATA\[\(<[^>]*>\s*vs\. 2 wks\)\]\]></run>"
        r"\r\n\s*<run>Æ&#10;</run>"
        r"\r\n\s*<run fontname='Tableau Light' fontsize='10'>"
        r"<!\[CDATA\[\(<[^>]*>\s*vs\. prev Q\)\]\]></run>"
    )
    new, n = re.subn(pat, "", block)
    if n != 1:
        raise RuntimeError(f"trend-tail pattern matched {n} times, expected 1")
    return new


def promote_to_text(block: str, instance: str, after: str) -> str:
    """Add a `<text>` encoding for a column-instance that is currently only on
    the Tooltip shelf.

    Verified 2026-09-10 by render, four cases in one image: a `<customized-label>`
    run renders a field ONLY if that field is also on the Text shelf. The
    cumulative tile (2 text encodings) and the gradebook tile (3) print every
    number in their labels; the Y1 and failures tiles reference a count that
    sits on `<tooltip>` alone, and that run rendered as an empty gap -- `of
    students` with no number -- with no error anywhere. Same failure shape as
    the skill's parameter-token-in-a-label entry: blank, not loud.

    The instance stays on Tooltip as well; the customized-tooltip text
    references it too, and a field is allowed on both shelves.
    """
    anchor = f"              <text column='{after}' />\r\n"
    add = f"              <text column='{instance}' />\r\n"
    if add in block:
        raise RuntimeError(f"already a text encoding: {instance}")
    return sub_once(block, anchor, anchor + add)


def shrink_heading(block: str) -> str:
    """Tile heading run 13 pt -> 11 pt."""
    return sub_once(
        block,
        "<run fontname='Tableau Regular' fontsize='13'>",
        "<run fontname='Tableau Regular' fontsize='11'>",
    )


def strip_second_label_line(block: str) -> str:
    """Reduce a strip's mark label to its single value run.

    A three-region strip gives each mark about 43 px; a 12 pt value over an
    8 pt second line does not fit, and Tableau prints `####` for the whole
    cell rather than dropping the second line itself. The second line's
    content (the weekly delta, the teacher denominator) is on the tile above
    and in the tooltip, so nothing is lost that the page does not already say.
    """
    pat = (
        r"\r\n\s*<run>Æ&#10;</run>"
        r"\r\n\s*<run fontname='Tableau Light' fontsize='8'>"
        r"<!\[CDATA\[.*?\]\]></run>"
    )
    new, n = re.subn(pat, "", block, flags=re.S)
    if n != 1:
        raise RuntimeError(f"strip second-line pattern matched {n} times, expected 1")
    return new


def no_cull(block: str) -> str:
    """mark-labels-cull true -> false.

    A culled label renders blank rather than clipped, which reads as missing
    data. Not the cause of `####`, but it is the failure mode a too-tight
    cell falls into next, and the four sheets that carry it inherited it from
    their clone source rather than choosing it.
    """
    old = "<format attr='mark-labels-cull' value='true' />"
    new = "<format attr='mark-labels-cull' value='false' />"
    if old not in block:
        return block
    return block.replace(old, new)


#: (tile, denominator instance, the last existing <text> encoding to sit after)
DENOMINATORS = {
    "LP - Tile Y1 GPA": (
        f"[{GRADES_DS}].[usr:Calculation_1000000000000000021:qk]",
        f"[{GRADES_DS}].[usr:Calculation_1092052566973874180:qk]",
    ),
    "LP - Tile Course Failures": (
        f"[{GRADES_DS}].[usr:Calculation_1000000000000000024:qk]",
        f"[{GRADES_DS}].[usr:Calculation_1092052567237197834:qk]",
    ),
}


def fix_tile_y1(text: str) -> str:
    inst, after = DENOMINATORS["LP - Tile Y1 GPA"]
    return edit_worksheet(
        text,
        "LP - Tile Y1 GPA",
        lambda b: promote_to_text(
            no_cull(shrink_heading(drop_trend_tail(b))), inst, after
        ),
    )


def fix_tile_failures(text: str) -> str:
    inst, after = DENOMINATORS["LP - Tile Course Failures"]
    return edit_worksheet(
        text,
        "LP - Tile Course Failures",
        lambda b: promote_to_text(
            no_cull(shrink_heading(drop_trend_tail(b))), inst, after
        ),
    )


def fix_tile_cumulative(text: str) -> str:
    """30 pt value -> 22 pt, 13 pt heading -> 11 pt. Four lines, kept."""

    def fn(b: str) -> str:
        b = sub_once(
            b,
            "<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='30'>",
            "<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='22'>",
        )
        return no_cull(shrink_heading(b))

    return edit_worksheet(text, "LP - Tile Cumulative GPA", fn)


def fix_strip_y1(text: str) -> str:
    return edit_worksheet(
        text, "LP - Strip Y1 GPA", lambda b: no_cull(strip_second_label_line(b))
    )


def fix_strip_failures(text: str) -> str:
    return edit_worksheet(
        text,
        "LP - Strip Course Failures",
        lambda b: no_cull(strip_second_label_line(b)),
    )


# ------------------------------------------- D1 + D2 on the gradebook pair


def fix_tile_gradebook(text: str) -> str:
    """Drop the navy table background, recolour every white run, shrink the
    42 pt value to 24 pt."""

    def fn(b: str) -> str:
        b = sub_once(
            b,
            "        <style>\r\n"
            "          <style-rule element='table'>\r\n"
            f"            <format attr='background-color' value='{NAVY}' />\r\n"
            "          </style-rule>\r\n"
            "        </style>\r\n",
            "",
        )
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontname='Tableau Medium' fontsize='13'>",
            "<run fontname='Tableau Regular' fontsize='11'>",
        )
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontsize='16'> | </run>",
            f"<run fontcolor='{GREY}' fontsize='11'> | </run>",
        )
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontname='Tableau Light' fontsize='12'>",
            f"<run fontcolor='{GREY}' fontname='Tableau Light' fontsize='10'>",
        )
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontname='Tableau Semibold' fontsize='42'>",
            f"<run fontcolor='{NAVY}' fontname='Tableau Semibold' fontsize='24'>",
        )
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontname='Tableau Regular' fontsize='12'>healthy</run>",
            f"<run fontcolor='{GREY}' fontname='Tableau Regular' fontsize='10'>healthy</run>",
        )
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontsize='14'>",
            f"<run fontcolor='{GREY}' fontsize='10'>",
        )
        return no_cull(b)

    return edit_worksheet(text, "LP - Tile Gradebook Health", fn)


def fix_strip_gradebook(text: str) -> str:
    """Drop the navy table background AND the white header rule that only
    existed to survive it (ruling 12's second half), recolour the value run,
    and drop the second label line like the other two strips."""

    def fn(b: str) -> str:
        b = sub_once(
            b,
            "        <style>\r\n"
            "          <style-rule element='header'>\r\n"
            "            <format attr='color' value='#ffffff' />\r\n"
            "          </style-rule>\r\n"
            "          <style-rule element='table'>\r\n"
            f"            <format attr='background-color' value='{NAVY}' />\r\n"
            "          </style-rule>\r\n"
            "        </style>\r\n",
            "",
        )
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontname='Tableau Semibold' fontsize='12'>",
            f"<run fontcolor='{NAVY}' fontname='Tableau Semibold' fontsize='12'>",
        )
        # this strip's second line is `of <N> teachers`, not the `vs. 1 wk`
        # shape the other two carry, so it needs its own pattern
        pat = (
            r"\r\n\s*<run>Æ&#10;</run>"
            r"\r\n\s*<run fontcolor='#ffffff' fontname='Tableau Light' fontsize='8'>"
            r"<!\[CDATA\[.*?\]\]></run>"
        )
        b2, n = re.subn(pat, "", b, flags=re.S)
        if n != 1:
            raise RuntimeError(f"gradebook strip second line matched {n}, expected 1")
        return no_cull(b2)

    return edit_worksheet(text, "LP - Strip Gradebook Health", fn)


# ------------------------------------------------------- D3: "Grade Grade"


def fix_grade_grade(text: str) -> str:
    """Drop the literal `Grade ` that precedes the parameter token in the two
    cumulative titles. `[Parameter 10]`'s aliases are `Grade 9`/`Grade 10`/
    `Grade 11`, so the token already carries the word."""
    return sub_n(
        text,
        "<![CDATA[Grade <[Parameters].[Parameter 10]> · ",
        "<![CDATA[<[Parameters].[Parameter 10]> · ",
        2,
    )


# --------------------------------------------------- D4: header truncation


def fix_header_title(text: str) -> str:
    """`LP - Title`'s two 16 pt mark-label runs -> 12 pt.

    14 pt still clipped to `Academic & Gradebook Health | Landing P..` on the
    round-1 render, so this takes the second step down rather than reflowing
    all eight header zones to widen the title.
    """

    def fn(b: str) -> str:
        b = sub_once(
            b,
            "<run bold='true' fontalignment='0' fontsize='16'>",
            "<run bold='true' fontalignment='0' fontsize='12'>",
        )
        return sub_once(
            b,
            "<run fontalignment='0' fontsize='16'>",
            "<run fontalignment='0' fontsize='12'>",
        )

    return edit_worksheet(text, "LP - Title", fn)


# ------------------------------------------------------ default-view marker


def set_default_view(text: str) -> str:
    """Move the single `maximized='true'` marker onto the Landing Page window.

    Production revision 26 carries it on `Gradebook Teacher View`; the review
    copy has to open on the page under review. Generic: strips the one
    existing marker wherever it sits, then sets it on the target.
    """
    n = text.count(MARKER)
    if n != 1:
        raise RuntimeError(f"expected exactly 1 maximized marker in base, found {n}")
    text = text.replace(MARKER, "")
    m = re.search(
        r"<window class='dashboard'[^>]*name='" + re.escape(TARGET_DASHBOARD) + r"'",
        text,
    )
    if not m:
        raise RuntimeError(f"no dashboard window named {TARGET_DASHBOARD!r}")
    old = m.group(0)
    new = old.replace(
        "<window class='dashboard'", "<window class='dashboard'" + MARKER, 1
    )
    text = sub_once(text, old, new)
    if text.count(MARKER) != 1:
        raise RuntimeError("default-view marker not left exactly once")
    return text


STEPS = (
    ("fix_tile_y1", fix_tile_y1),
    ("fix_tile_failures", fix_tile_failures),
    ("fix_tile_cumulative", fix_tile_cumulative),
    ("fix_tile_gradebook", fix_tile_gradebook),
    ("fix_strip_y1", fix_strip_y1),
    ("fix_strip_failures", fix_strip_failures),
    ("fix_strip_gradebook", fix_strip_gradebook),
    ("fix_grade_grade", fix_grade_grade),
    ("fix_header_title", fix_header_title),
    ("set_default_view", set_default_view),
)


def main() -> None:
    text = BASE.read_text(encoding="utf-8", newline="")
    start = len(text)
    for name, fn in STEPS:
        before = len(text)
        text = fn(text)
        print(f"{name}: {len(text) - before:+d} bytes")
    ET.fromstring(text)  # trunk-ignore(bandit/B314): well-formedness check only
    if "\n" in text.replace("\r\n", ""):
        raise RuntimeError("bare LF introduced")
    OUT.write_text(text, encoding="utf-8", newline="")
    print(f"wrote {OUT} ({len(text)} chars, {len(text) - start:+d} from base)")


if __name__ == "__main__":
    main()
