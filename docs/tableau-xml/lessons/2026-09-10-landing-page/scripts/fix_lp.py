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


def inline_detail_run(block: str, fontcolor: str | None = None) -> str:
    """Move a strip's second label line onto the same row as its value.

    The `####` fix cut these strips to a single value run because a 12 pt
    value stacked over an 8 pt detail line does not fit a ~43 px row band.
    Side by side on one line it does: the constraint was always vertical, and
    a three-region column is 337 px wide against about 130 px of text.

    Drops the break run and gives the detail run a two-space separator, so
    the row reads `58%  (-4.0pp vs. 1 wk)`. Every field these runs reference
    is already a `<text>` encoding on its pane -- checked for all four
    strips -- so they resolve rather than printing an empty gap.
    """
    color = f"fontcolor='{fontcolor}' " if fontcolor else ""
    pat = (
        r"\r\n\s*<run>\u00c6&#10;</run>"
        r"\r\n(\s*)<run " + re.escape(color) + r"fontname='Tableau Light' fontsize='8'>"
        r"<!\[CDATA\[(.*?)\]\]></run>"
    )
    m = re.search(pat, block, flags=re.S)
    if m is None:
        raise RuntimeError(f"no stacked detail run to inline (color={fontcolor!r})")
    replacement = (
        "\r\n"
        + m.group(1)
        + "<run "
        + color
        + "fontname='Tableau Light' fontsize='8'><![CDATA[  "
        + m.group(2)
        + "]]></run>"
    )
    new, n = re.subn(pat, lambda _: replacement, block, flags=re.S)
    if n != 1:
        raise RuntimeError(f"detail-run pattern matched {n} times, expected 1")
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
        text, "LP - Strip Y1 GPA", lambda b: no_cull(inline_detail_run(b))
    )


def fix_strip_failures(text: str) -> str:
    return edit_worksheet(
        text, "LP - Strip Course Failures", lambda b: no_cull(inline_detail_run(b))
    )


def fix_strip_cumulative(text: str) -> str:
    """The one strip that never showed `####`, because it has two region rows
    rather than three. Inlined anyway so all four columns read alike."""
    return edit_worksheet(
        text,
        "LP - Strip Cumulative GPA",
        lambda b: no_cull(inline_detail_run(b, fontcolor=GREY)),
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
        # The detail run reads `of <N> teachers`, but that field already
        # returns "52 of 363" -- on the tile the same field is written
        # without the leading `of`. Stacked and then dropped it never showed;
        # inline it rendered `3% of 3 of 95 teachers`. Match the tile.
        b = sub_once(b, "CDATA[of <[federated.", "CDATA[<[federated.")
        # its detail run is still white at this point; recolour, then inline
        b = sub_once(
            b,
            "<run fontcolor='#ffffff' fontname='Tableau Light' fontsize='8'>",
            f"<run fontcolor='{GREY}' fontname='Tableau Light' fontsize='8'>",
        )
        return no_cull(inline_detail_run(b, fontcolor=GREY))

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

    A dashboard text zone CENTRES its content vertically. Verified by
    measurement: with both blocks in one 696 px container the definitions'
    338 px of content started 179 px down and the coverage grid's 157 px
    started 269 px down, exactly half the leftover in each case, so the two
    headings did not line up and both floated below the cards.

    So the container is sized to the taller block and the shorter one gets
    its own column with a spacer beneath it, chosen so BOTH end up with the
    same residual centring offset. That equal offset is what actually aligns
    the two headings; equal zone heights would not.

    Geometry here is written for the 1500 px canvas; `relayout_vertical`
    rewrites every vertical number afterwards for the final canvas height.
    """

    def fn(d: str) -> str:
        defs = zone_block(d, "id='37'")
        cov = zone_block(d, "id='38'")
        links = zone_block(d, "friendly-name='Links'")

        new_defs = reindent(defs, 2)
        new_defs = sub_once(
            new_defs,
            "<zone fixed-size='400' forceUpdate='true' h='27200' id='37'"
            " is-fixed='true' type-v2='text' w='98828' x='586' y='47066'>",
            "<zone fixed-size='780' forceUpdate='true' h='24800' id='37'"
            " is-fixed='true' type-v2='text' w='57721' x='586' y='47066'>",
        )
        new_cov = reindent(cov, 4)
        new_cov = sub_once(
            new_cov,
            "<zone fixed-size='220' forceUpdate='true' h='15200' id='38'"
            " is-fixed='true' type-v2='text' w='98828' x='586' y='74266'>",
            "<zone fixed-size='183' forceUpdate='true' h='12733' id='38'"
            " is-fixed='true' type-v2='text' w='41107' x='58307' y='47066'>",
        )
        container = (
            "          <zone fixed-size='372' friendly-name='Reference' h='24800'"
            " id='60' is-fixed='true' param='horz' type-v2='layout-flow'"
            " w='98828' x='586' y='47066'>\r\n"
            "            " + new_defs + "\r\n"
            "            <zone h='24800' id='63' param='vert' type-v2='layout-flow'"
            " w='41107' x='58307' y='47066'>\r\n"
            "              " + new_cov + "\r\n"
            "              <zone h='12067' id='64' type-v2='empty' w='41107'"
            " x='58307' y='59799'>\r\n"
            "                <zone-style>\r\n"
            "                  <format attr='border-color' value='#000000' />\r\n"
            "                  <format attr='border-style' value='none' />\r\n"
            "                  <format attr='border-width' value='0' />\r\n"
            "                  <format attr='margin' value='4' />\r\n"
            "                </zone-style>\r\n"
            "              </zone>\r\n"
            "            </zone>\r\n"
            "          </zone>"
        )
        d = sub_once(d, "          " + defs + "\r\n          " + cov, container)
        return sub_once(d, "          " + links + "\r\n", "")

    return edit_dashboard(text, fn)


#: The dashboard's vertical layout, in PIXELS, after every change in this
#: script. The canvas shrinks to fit it: the Links row is gone, the two
#: reference blocks share a row instead of stacking, and the header drops to
#: 60 px. `relayout_vertical` turns this into units and rewrites every y/h.
#:
#:   id -> (height px, [child ids])   height None = fills its parent
CANVAS_W = 1366
CANVAS_H = 1130  # was 1500
OUTER_MARGIN = 8  # the outer flow zone's top and bottom inset
MARGIN_V = 8  # a `margin 4` zone's two vertical margins

#: Outer vertical flow, in order, with each row's total height in pixels.
ROWS = (
    ("9", 60),  # Header  (was 80)
    ("14", 220),  # Tiles
    ("19", 150),  # Regions
    ("20", 28),  # Miami footnote: fixed-size 20 + margins
    ("36", 220),  # Directory
    ("60", 420),  # Reference: 21 lines of definitions plus centring slack
    ("45", 16),  # trailing spacer
)

#: Zones that simply fill their parent's height (every horizontal row's
#: children, and the columns of a horizontal container).
FILL = {
    "9": ["1", "2", "3", "50"],
    "14": ["10", "11", "12", "13"],
    "19": ["15", "16", "17", "18"],
    "36": ["23", "26", "29", "32", "35"],
    "60": ["37", "63"],
}

#: Vertical sub-stacks: parent -> [(child id, height px or None to fill)].
STACKS = {
    "50": [("51", 30), ("52", None)],  # roster label over the three links
    "23": [("21", None), ("22", 32)],  # card over guide slot
    "26": [("24", None), ("25", 32)],
    "29": [("27", None), ("28", 32)],
    "32": [("30", None), ("31", 32)],
    "35": [("33", None), ("34", 32)],
    "63": [("38", 211), ("64", None)],  # coverage grid over its spacer
}

#: Children of a vertical sub-stack row that fill it (the three roster links).
STACK_FILL = {"52": ["53", "54", "55"]}

#: Rows whose own `fixed-size` this script rewrites (the ones whose height it
#: changes). The rest keep the pixel height they already had, so their
#: `fixed-size` is already right and must not be touched.
VFIXED_ROWS = {"9", "60"}

#: Same, for zones inside a vertical sub-stack.
VFIXED_STACK = {"38"}


def relayout_vertical(text: str) -> str:
    """Rewrite every vertical measurement for a shorter canvas.

    Zone units are always 1/100000 of the canvas, so shortening the canvas
    does NOT change any unit value on its own -- it changes what a unit is
    worth in pixels, which silently breaks every `fixed-size` in the file.
    Every vertical `y` and `h` therefore has to be recomputed from the
    intended pixel heights, which is what ROWS/FILL/STACKS declare. Widths
    are untouched: the canvas is still 1366 px wide.
    """
    uy = 100000 / CANVAS_H

    def u(px: float) -> int:
        return round(px * uy)

    def fn(d: str) -> str:
        d = sub_once(
            d,
            "<size maxheight='1500' maxwidth='1366' minheight='1500' minwidth='1366'"
            " sizing-mode='fixed' />",
            f"<size maxheight='{CANVAS_H}' maxwidth='{CANVAS_W}'"
            f" minheight='{CANVAS_H}' minwidth='{CANVAS_W}' sizing-mode='fixed' />",
        )
        top = u(OUTER_MARGIN)
        total = 100000 - 2 * top
        d = set_zone_attrs(d, "46", h=str(total), y=str(top))

        # Each row is rounded to whole units independently, so the last one
        # takes the remainder rather than its own rounding -- otherwise the
        # column is off by a unit or two and the flow no longer closes.
        heights = [u(px) for _, px in ROWS[:-1]]
        heights.append(total - sum(heights))
        want_last = u(ROWS[-1][1])
        if abs(heights[-1] - want_last) > len(ROWS):
            raise RuntimeError(
                f"trailing row absorbed {heights[-1]} units, wanted about {want_last}"
            )

        y = top
        for (zid, px), h in zip(ROWS, heights, strict=True):
            d = set_zone_attrs(d, zid, h=str(h), y=str(y))
            if zid in VFIXED_ROWS:
                d = set_zone_attrs(d, zid, fixed_size=str(px))
            for kid in FILL.get(zid, []):
                d = set_zone_attrs(d, kid, h=str(h), y=str(y))
            for parent in (zid, *FILL.get(zid, [])):
                if parent not in STACKS:
                    continue
                ky = y
                fixed = sum(p for _, p in STACKS[parent] if p is not None)
                for kid, kpx in STACKS[parent]:
                    kh = u(kpx) if kpx is not None else h - u(fixed)
                    d = set_zone_attrs(d, kid, h=str(kh), y=str(ky))
                    if kid in VFIXED_STACK and kpx is not None:
                        # a `margin 4` zone measures fixed-size as content,
                        # so its two 8 px of margin come off first
                        d = set_zone_attrs(d, kid, fixed_size=str(kpx - MARGIN_V))
                    for gk in STACK_FILL.get(kid, []):
                        d = set_zone_attrs(d, gk, h=str(kh), y=str(ky))
                    ky += kh
                if ky != y + h:
                    raise RuntimeError(f"stack {parent} sums to {ky - y}, not {h}")
            y += h
        if y != top + total:
            raise RuntimeError(f"rows end at {y}, expected {top + total}")
        return d

    return edit_dashboard(text, fn)


STEPS = (
    ("fix_tile_y1", fix_tile_y1),
    ("fix_tile_failures", fix_tile_failures),
    ("fix_tile_cumulative", fix_tile_cumulative),
    ("fix_tile_gradebook", fix_tile_gradebook),
    ("fix_strip_y1", fix_strip_y1),
    ("fix_strip_failures", fix_strip_failures),
    ("fix_strip_cumulative", fix_strip_cumulative),
    ("fix_strip_gradebook", fix_strip_gradebook),
    ("fix_grade_grade", fix_grade_grade),
    ("drop_header_buttons_and_add_roster", drop_header_buttons_and_add_roster),
    ("side_by_side_reference", side_by_side_reference),
    ("relayout_vertical", relayout_vertical),
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
