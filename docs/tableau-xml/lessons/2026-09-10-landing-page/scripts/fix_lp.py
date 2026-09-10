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


# ------------------------------------------------- layout round: zone surgery
#
# Three changes asked for after the first render review:
#   L1  drop the five header nav buttons -- the tab cards below already
#       navigate, so the header row was a second copy of the same thing
#   L2  move the GPA Roster links into the header, where the other four views
#       in this workbook put them
#   L3  put "What the terms mean" and "Where each tab has data" side by side
#
# Geometry. The canvas is fixed 1366x1500 and zone units are 1/100000 of it,
# so 100000 vertical units = 1500 px (66.667 u/px) and the 98828-unit content
# column = 1349 px (73.25 u/px). A zone whose `zone-style` carries
# `margin 4` measures `fixed-size` as CONTENT, and its cached w/h add the two
# 4 px margins: 586 units horizontally, 533 vertically. Flow CONTAINERS carry
# no margin, so for them cached size is exactly fixed-size x scale. Verified
# against every existing zone in this dashboard: logo 167 px -> 12811,
# param 130 -> 10103, button 120 -> 9371, header 80 px -> 5333, tiles 220 ->
# 14667.

UX = 73.25  # horizontal units per pixel, inside the 98828-unit column
UY = 100000 / 1500  # vertical units per pixel
MARGIN_X = 586  # a `margin 4` zone's two horizontal margins, in units
CONTENT_W = 98828

ZONE_RX = re.compile(r"<zone(?=[ >])[^>]*?(/?)>|</zone>")


def zone_block(text: str, marker: str) -> str:
    """The complete `<zone>` element containing `marker`, brace-matched.

    `<zone-style>` must not count as a zone open, hence the `(?=[ >])`
    lookahead; without it the depth never returns to zero.
    """
    i = text.index(marker)
    start = text.rindex("<zone ", 0, i)
    depth, pos = 0, start
    while True:
        m = ZONE_RX.search(text, pos)
        if m is None:
            raise RuntimeError(f"unbalanced zones around {marker!r}")
        if m.group(0).startswith("</zone"):
            depth -= 1
        elif m.group(1) != "/":
            depth += 1
        pos = m.end()
        if depth == 0:
            return text[start:pos]


def set_zone_attrs(block: str, zone_id: str, **attrs: str) -> str:
    """Rewrite named attributes on the `<zone>` opening tag with this id.

    Raw string swaps are not safe here: a flow container and its first child
    legitimately share identical `w`/`x`/`y` text, so an anchor that looks
    unique matches twice. Addressing the tag by id and editing attributes in
    place is the only form that stays unambiguous.
    """
    m = re.search(r"<zone (?=[^>]*\bid='" + re.escape(zone_id) + r"')[^>]*>", block)
    if m is None:
        raise RuntimeError(f"no zone with id={zone_id!r}")
    tag = m.group(0)
    new = tag
    for k, v in attrs.items():
        k = k.replace("_", "-")
        pat = r"\b" + re.escape(k) + r"='[^']*'"
        if not re.search(pat, new):
            raise RuntimeError(f"zone {zone_id} has no attribute {k!r}")
        new = re.sub(pat, f"{k}='{v}'", new, count=1)
    if new == tag:
        raise RuntimeError(f"zone {zone_id}: attribute rewrite was a no-op")
    return block[: m.start()] + new + block[m.end() :]


def reindent(block: str, delta: int) -> str:
    """Shift every line of a CRLF block by `delta` spaces (first line bare)."""
    lines = block.split("\r\n")
    out = [lines[0]]
    for ln in lines[1:]:
        if not ln.strip():
            out.append(ln)
        elif delta >= 0:
            out.append(" " * delta + ln)
        else:
            out.append(ln[-delta:] if ln.startswith(" " * -delta) else ln)
    return "\r\n".join(out)


def dashboard(text: str) -> str:
    m = re.search(r"<dashboard[^>]*name='Landing Page'.*?</dashboard>", text, re.S)
    if not m:
        raise RuntimeError("Landing Page dashboard not found")
    return m.group(0)


def edit_dashboard(text: str, fn) -> str:
    before = dashboard(text)
    after = fn(before)
    if after == before:
        raise RuntimeError("dashboard edit was a no-op")
    return sub_once(text, before, after)


def drop_header_buttons_and_add_roster(text: str) -> str:
    """L1 + L2, plus the width they free.

    The five nav buttons are 9371 units each (46855 total). 14934 of that goes
    to a `Roster links` container copied from `Academic Health Home` -- the
    same 240 px vertical container, label over three link sheets, that the
    other four views use -- and the remaining 31921 goes to the title zone,
    the only flexible child in the header row.

    Widening the title is also the real fix for the truncation that the first
    round patched by dropping the font to 12 pt: 29059 units (~397 px) could
    not hold the string at 16 pt, 60980 (~832 px) holds it comfortably. So the
    title goes back to its design size and `fix_header_title` is gone.
    """

    def fn(d: str) -> str:
        # --- the five buttons
        pat = (
            r"[ \t]*<zone fixed-size='120'[^>]*type-v2='dashboard-object'[^>]*>"
            r".*?</zone>\r\n"
        )
        d, n = re.subn(pat, "", d, flags=re.S)
        if n != 5:
            raise RuntimeError(f"removed {n} header buttons, expected 5")

        # --- the roster container, taken verbatim from Academic Health Home
        #     and re-indented from its 14-space nest to this header's 12
        src = zone_block(
            dashboard_of(BASE_TEXT, "Academic Health Home"),
            "friendly-name='Roster links'",
        )
        roster = reindent(src, -2)
        # ids: the Landing Page dashboard tops out at 46
        for old, new in (
            ("id='710'", "id='50'"),
            ("id='711'", "id='51'"),
            ("id='712'", "id='52'"),
            ("id='713'", "id='53'"),
            ("id='714'", "id='54'"),
            ("id='715'", "id='55'"),
        ):
            roster = sub_once(roster, old, new)
        # geometry, in this dashboard's scale rather than Academic Health
        # Home's: that header is 6667 units tall, this one is 5333. The label
        # keeps its 22 px fixed-size, which with its two 4 px margins is
        # 22*66.667 + 533 = 2000 units, leaving 3333 for the link row.
        # Academic Health Home's container is 240 px against three 4978-unit
        # links that need only 14934, so it ships with 2646 units of trailing
        # slack inside the flow. Copying that would put a gap in a container
        # this build created, so the width is cut to exactly the three links:
        # 14934 units, 204 px. The 2646 goes to the title with the rest.
        roster = set_zone_attrs(
            roster, "50", fixed_size="204", h="5333", w="14934", x="84480", y="533"
        )
        roster = set_zone_attrs(roster, "51", h="2000", w="14934", x="84480", y="533")
        roster = set_zone_attrs(roster, "52", h="3333", w="14934", x="84480", y="2533")
        for zid, x in (("53", "84480"), ("54", "89458"), ("55", "94436")):
            roster = set_zone_attrs(roster, zid, h="3333", w="4978", x=x, y="2533")

        # --- widen the title, shift the year control, append the container
        d = sub_once(
            d,
            "<zone h='5333' id='2' name='LP - Title' show-caption='true' show-title='false' w='29059' x='13397' y='533'>",
            "<zone h='5333' id='2' name='LP - Title' show-caption='true' show-title='false' w='60980' x='13397' y='533'>",
        )
        d = sub_once(d, "w='10103' x='42456' y='533'>", "w='10103' x='74377' y='533'>")
        anchor = "            <zone-style>\r\n              <format attr='border-color' value='#000000' />\r\n              <format attr='border-style' value='none' />\r\n              <format attr='border-width' value='0' />\r\n              <format attr='background-color' value='#001e62' />\r\n            </zone-style>\r\n"
        return sub_once(d, anchor, "            " + roster + "\r\n" + anchor)

    return edit_dashboard(text, fn)


def side_by_side_reference(text: str) -> str:
    """L3: put the definitions and coverage blocks side by side, and delete
    the Links row now that the roster links live in the header.

    A dashboard text zone CENTRES its content vertically. Verified on the
    first attempt at this layout: both blocks were dropped down their zone by
    exactly half the leftover -- the definitions text measured 338 px of
    content in a 696 px zone and started 179 px down, the coverage grid 157 px
    of content and started 269 px down -- so the two blocks did not line up
    with each other and both floated well below the cards above them. Nothing
    in the XML says so and nothing errors.

    So each block gets its own vertical column: a text zone sized close to its
    own content, then an empty spacer for the rest of the height. Sized so
    the residual centring offset is the same 21 px in both columns, which is
    what actually makes the two headings line up.

    The vertical budget is unchanged from the stacked version: the container
    still spans y=47066..93466, so the trailing empty zone and the outer flow
    zone need no edit. The slack that removing the Links row freed sits
    inside the two columns as page whitespace.
    """

    def fn(d: str) -> str:
        defs = zone_block(d, "id='37'")
        cov = zone_block(d, "id='38'")
        links = zone_block(d, "friendly-name='Links'")

        # both text zones drop two indent levels deeper: container > column
        new_defs = reindent(defs, 4)
        new_defs = sub_once(
            new_defs,
            "<zone fixed-size='400' forceUpdate='true' h='27200' id='37'"
            " is-fixed='true' type-v2='text' w='98828' x='586' y='47066'>",
            "<zone fixed-size='380' forceUpdate='true' h='25867' id='37'"
            " is-fixed='true' type-v2='text' w='57721' x='586' y='47066'>",
        )
        new_cov = reindent(cov, 4)
        new_cov = sub_once(
            new_cov,
            "<zone fixed-size='220' forceUpdate='true' h='15200' id='38'"
            " is-fixed='true' type-v2='text' w='98828' x='586' y='74266'>",
            "<zone fixed-size='199' forceUpdate='true' h='13800' id='38'"
            " is-fixed='true' type-v2='text' w='41107' x='58307' y='47066'>",
        )

        def spacer(zid: str, h: int, w: int, x: int, y: int) -> str:
            return (
                f"              <zone h='{h}' id='{zid}' type-v2='empty'"
                f" w='{w}' x='{x}' y='{y}'>\r\n"
                "                <zone-style>\r\n"
                "                  <format attr='border-color' value='#000000' />\r\n"
                "                  <format attr='border-style' value='none' />\r\n"
                "                  <format attr='border-width' value='0' />\r\n"
                "                  <format attr='margin' value='4' />\r\n"
                "                </zone-style>\r\n"
                "              </zone>"
            )

        container = (
            "          <zone fixed-size='696' friendly-name='Reference' h='46400'"
            " id='60' is-fixed='true' param='horz' type-v2='layout-flow'"
            " w='98828' x='586' y='47066'>\r\n"
            "            <zone fixed-size='780' h='46400' id='61' is-fixed='true'"
            " param='vert' type-v2='layout-flow' w='57721' x='586' y='47066'>\r\n"
            "              "
            + new_defs
            + "\r\n"
            + spacer("62", 20533, 57721, 586, 72933)
            + "\r\n"
            "            </zone>\r\n"
            "            <zone h='46400' id='63' param='vert' type-v2='layout-flow'"
            " w='41107' x='58307' y='47066'>\r\n"
            "              "
            + new_cov
            + "\r\n"
            + spacer("64", 32600, 41107, 58307, 60866)
            + "\r\n"
            "            </zone>\r\n"
            "          </zone>"
        )
        d = sub_once(d, "          " + defs + "\r\n          " + cov, container)
        return sub_once(d, "          " + links + "\r\n", "")

    return edit_dashboard(text, fn)


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
    ("drop_header_buttons_and_add_roster", drop_header_buttons_and_add_roster),
    ("side_by_side_reference", side_by_side_reference),
    ("set_default_view", set_default_view),
)


def dashboard_of(text: str, name: str) -> str:
    m = re.search(
        r"<dashboard[^>]*name='" + re.escape(name) + r"'.*?</dashboard>", text, re.S
    )
    if not m:
        raise RuntimeError(f"dashboard not found: {name!r}")
    return m.group(0)


#: Set by main() so the roster-links donor can be read from the untouched base.
BASE_TEXT = ""


def main() -> None:
    global BASE_TEXT
    text = BASE.read_text(encoding="utf-8", newline="")
    BASE_TEXT = text
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
