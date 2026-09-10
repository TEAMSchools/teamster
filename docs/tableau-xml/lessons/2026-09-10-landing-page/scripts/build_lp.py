"""build_lp.py: additive edit of the suite workbook. Run from the main checkout:
    ~/.local/bin/uv run python /workspaces/teamster/.claude/scratch/tableau/lp/build_lp.py
Reads base.twb, writes out.twb. Every step asserts its anchors."""

import re
import uuid
import xml.etree.ElementTree as ET  # trunk-ignore(bandit/B405): parse-only well-formedness check on a file we wrote
from pathlib import Path

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
BASE = LP / "base.twb"
OUT = LP / "out.twb"

GOAL_DS = "federated.0n798br073i5kb170j6l90uiv50a"  # rpt_tableau__gpa_goal_progress
GRADES_DS = (
    "federated.1ikycy21f3ow4k1eazzbx1iah2yl"  # rpt_tableau__student_course_grades+
)
GB_DS = "federated.16ubt9s0rwp4cw14hwm3e1xmc56p"  # rpt_tableau__gradebook_audit


def crlf(block: str) -> str:
    """Triple-quoted Python block -> CRLF text, leading newline dropped."""
    return block.lstrip("\n").replace("\r\n", "\n").replace("\n", "\r\n")


def new_uuid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def sub_once(text: str, anchor: str, replacement: str) -> str:
    n = text.count(anchor)
    if n != 1:
        raise RuntimeError(f"anchor matched {n} times, expected 1: {anchor[:80]!r}")
    return text.replace(anchor, replacement)


def insert_before(text: str, anchor: str, block: str) -> str:
    return sub_once(text, anchor, block + anchor)


def insert_after(text: str, anchor: str, block: str) -> str:
    return sub_once(text, anchor, anchor + block)


def element(text: str, open_pat: str, close_tag: str) -> str:
    """Return the first element whose opening tag matches open_pat (regex)."""
    m = re.search(open_pat, text)
    if not m:
        raise RuntimeError(f"no element for {open_pat!r}")
    end = text.index(close_tag, m.start()) + len(close_tag)
    return text[m.start() : end]


# ---------------------------------------------------------------- task 3
#: The datasource-level calcs this build adds to the goals source, in the order
#: they are written. Each is one of the workbook's own goal calcs with the
#: `p_Region` branch resolved: the 001/002 pair to the region goal (so a region
#: row compares against its own goal) and 003 to the org goal (Controller
#: Ruling 10: a network tile must not follow a parameter another tab controls).
#: Formulas are stored XML-escaped, exactly as they land in the file.
LP_CALCS: tuple[tuple[str, str, str], ...] = (
    (
        "Calculation_7700000000000000001",
        "LP Students still needed (region)",
        "// LP copy of [Students still needed] with the p_Region branch removed&#10;"
        "IF [Calculation_9485136151529756033] / [Calculation_4693780698737655073]&#10;"
        "   &gt;= AVG([gpa_goal_proportion_region])&#10;"
        "THEN 0&#10;"
        "ELSE ROUND(AVG([gpa_goal_proportion_region]) * [Calculation_4693780698737655073])&#10;"
        "     - [Calculation_9485136151529756033]&#10;"
        "END",
    ),
    (
        "Calculation_7700000000000000002",
        "LP Gap to goal (region)",
        "// LP copy of [Gap to goal (pts)] with the p_Region branch removed&#10;"
        "([Calculation_9485136151529756033] / [Calculation_4693780698737655073]&#10;"
        " - AVG([gpa_goal_proportion_region])) * 100",
    ),
    (
        "Calculation_7700000000000000003",
        "LP Students still needed (org)",
        "// LP copy of [Students still needed] with the p_Region branch removed&#10;"
        "IF [Calculation_9485136151529756033] / [Calculation_4693780698737655073]&#10;"
        "   &gt;= AVG([gpa_goal_proportion_org])&#10;"
        "THEN 0&#10;"
        "ELSE ROUND(AVG([gpa_goal_proportion_org]) * [Calculation_4693780698737655073])&#10;"
        "     - [Calculation_9485136151529756033]&#10;"
        "END",
    ),
)
LP_CALC_BY_NAME = {name: (cap, formula) for name, cap, formula in LP_CALCS}
#: the region-goal shortfall (strip sheets) and the org-goal one (network tile)
LP_NEEDED_REGION = "Calculation_7700000000000000001"
LP_NEEDED_ORG = "Calculation_7700000000000000003"


def lp_calc_column(name: str, indent: int) -> str:
    """One LP calc as a `<column>` element at the requested indentation.

    The same calc is written twice at different depths: once at the
    datasource level (6 spaces) and once inside the worksheet that uses it
    (12 spaces), which is how every other calc in base.twb is carried."""
    caption, formula = LP_CALC_BY_NAME[name]
    pad = " " * indent
    return (
        f"{pad}<column caption='{caption}' datatype='real' name='[{name}]' "
        f"role='measure' type='quantitative'>\r\n"
        f"{pad}  <calculation class='tableau' formula='{formula}' />\r\n"
        f"{pad}</column>\r\n"
    )


def add_goal_calcs(t: str) -> str:
    """The LP_CALCS variants of the existing goal pair, on the goals source.
    The originals read the org or region goal by p_Region; these resolve that
    branch at build time.

    The datasource-level column carries 6-space indentation; the worksheet-level
    copies carry 12-space indentation. A plain-substring anchor on just the
    6-space form still matches all 4 occurrences, because the trailing 6 of the
    12 leading spaces plus '<column...' is itself a substring of the deeper
    indent. Prefixing the anchor with the preceding CRLF forces line-start
    alignment and disambiguates (confirmed: count == 1 for the CRLF-prefixed
    form vs. 4 for the bare form)."""
    anchor_line = (
        "      <column caption='Gap to goal (pts)' datatype='real' "
        "name='[Calculation_3466859908724272046]' role='measure' type='quantitative'>"
    )
    anchor = "\r\n" + anchor_line
    block = "".join(lp_calc_column(name, 6) for name, _cap, _f in LP_CALCS)
    return sub_once(t, anchor, "\r\n" + block + anchor_line)


# ---------------------------------------------------------------- helpers, task 4
DROP = "__DROP_FILTER__"


def worksheet_block(t: str, name: str) -> str:
    r"""The whole <worksheet> element, indentation through trailing CRLF.

    The opening-tag pattern is prefixed with \r\n so it is line-anchored (a
    six-space-indented anchor is a substring of a twelve-space one); the two
    leading characters are dropped again so the returned block starts at the
    worksheet's own indentation and inserting a copy after it adds no blank
    line."""
    blk = element(
        t, rf"\r\n    <worksheet name='{re.escape(name)}'>", "    </worksheet>\r\n"
    )
    return blk[2:]


def cut_once(block: str, pattern: str, what: str, required: bool = True) -> str:
    """Delete the first regex match, asserting it matched exactly once."""
    block, n = re.subn(pattern, "", block, count=1, flags=re.S)
    if n != 1 and (required or n != 0):
        raise RuntimeError(f"cut {what}: matched {n}, wanted 1")
    return block


def apply_drop_filters(block: str, drops: list[tuple[str, str]], name: str) -> str:
    r"""Remove one categorical filter and every trace of it from a clone.

    Four places carry a filtered column-instance: the <filter> element, the
    <slices> line, the worksheet's <column-instance> dependency line, and --
    when the instance wraps a calculated field -- that calc's <column>
    definition. The assertion requires the identifier to be gone from the whole
    worksheet, not just from <filter>/<slices>, so all four go. Every pattern
    is \r\n-anchored and consumes no trailing newline, so the surrounding lines
    close up exactly.

    The filter element's form varies (filter-group attribute or not, one-line
    groupfilter or a nested union), so it is matched by regex, not a literal.
    The opening tag ends `(?<!/)>` because base.twb also holds 6 SELF-CLOSING
    categorical filters: a plain `[^>]*>` matches through their `/>` and the
    following `.*?</filter>` then runs on to the NEXT filter's close, silently
    deleting an unrelated filter. `[^>]*[^/>]>` is not equivalent here -- a
    filter with no attribute after `column='...'` has `>` immediately after the
    quote and would stop matching. selftest_drop_filters() proves both halves.
    """
    for ds, inst in drops:
        block = cut_once(
            block,
            rf"\r\n          <filter class='categorical' column='\[{re.escape(ds)}\]\.\[{re.escape(inst)}\]'[^>]*(?<!/)>.*?</filter>",
            f"[{name}] filter {inst}",
        )
        slice_line = f"\r\n            <column>[{ds}].[{inst}]</column>"
        if block.count(slice_line) != 1:
            raise RuntimeError(
                f"[{name}] slice {inst}: matched {block.count(slice_line)}, wanted 1"
            )
        block = block.replace(slice_line, "")
        block = cut_once(
            block,
            rf"\r\n            <column-instance column='\[[^']*\]' derivation='[^']*' name='\[{re.escape(inst)}\]'[^>]*/>",
            f"[{name}] column-instance {inst}",
        )
        calc = re.fullmatch(r"none:(Calculation_\d+):nk", inst)
        if calc:
            block = cut_once(
                block,
                rf"\r\n            <column [^>]*name='\[{calc.group(1)}\]'[^>]*[^/>]>.*?</column>",
                f"[{name}] calc column {calc.group(1)}",
            )
            if calc.group(1) in block:
                raise RuntimeError(
                    f"[{name}] {calc.group(1)} still referenced after the drop"
                )
    return block


def selftest_drop_filters() -> None:
    """A self-closing filter next to a paired one: neither is eaten by mistake.

    Regression proof for the `(?<!/)>` guard. Without it the SELF-CLOSING
    filter's opening tag matches (`[^>]*>` runs through its `/>`), the
    following `.*?</filter>` runs on to the NEXT filter's close, and one
    substitution silently deletes two filters. With the guard the self-closing
    filter simply does not match, so cut_once raises instead of corrupting.
    base.twb holds 6 self-closing categorical filters.
    """
    block = crlf("""
          <filter class='categorical' column='[DS].[none:keep:nk]' filter-group='3' />
          <filter class='categorical' column='[DS].[none:go:nk]' filter-group='4'>
            <groupfilter function='level-members' level='[none:go:nk]' />
          </filter>
          <slices>
            <column>[DS].[none:go:nk]</column>
          </slices>
            <column-instance column='[go]' derivation='None' name='[none:go:nk]' pivot='key' type='nominal' />
""")
    keep = (
        "<filter class='categorical' column='[DS].[none:keep:nk]' filter-group='3' />"
    )
    out = apply_drop_filters(block, [("DS", "none:go:nk")], "selftest")
    if "[none:go:nk]" in out:
        raise RuntimeError("selftest: the paired filter was not removed")
    if out.count(keep) != 1:
        raise RuntimeError("selftest: the self-closing filter was destroyed")
    try:
        apply_drop_filters(block, [("DS", "none:keep:nk")], "selftest")
    except RuntimeError:
        pass
    else:
        raise RuntimeError("selftest: a self-closing filter was matched and cut")
    print(
        "selftest_drop_filters: paired filter removed, self-closing filter "
        "intact, self-closing target refused"
    )


def clone_worksheet(
    t: str, src_name: str, new_name: str, edits: list[tuple[str, str]]
) -> str:
    src = worksheet_block(t, src_name)
    new = sub_once(
        src, f"<worksheet name='{src_name}'>", f"<worksheet name='{new_name}'>"
    )
    # drop repository-location so <layout-options> is legal as the first child
    new, n = re.subn(r"\r\n      <repository-location [^>]*/>", "", new, count=1)
    if n not in (0, 1) or "<repository-location" in new:
        raise RuntimeError(f"[{new_name}] repository-location not removed")
    # fresh simple-id
    sid = re.search(r"<simple-id uuid='[^']*' />", new)
    if not sid:
        raise RuntimeError(f"[{new_name}] no simple-id to replace")
    new = sub_once(new, sid.group(0), f"<simple-id uuid='{new_uuid()}' />")
    drops: list[tuple[str, str]] = []
    for anchor, value in edits:
        if anchor == DROP:
            ds, _, inst = value.partition("|")
            drops.append((ds, inst))
    new = apply_drop_filters(new, drops, new_name)
    for anchor, repl in edits:
        if anchor == DROP:
            continue
        n = new.count(anchor)
        if n != 1:
            raise RuntimeError(f"[{new_name}] edit anchor matched {n}: {anchor[:80]!r}")
        new = new.replace(anchor, repl)
    # insert right after the source worksheet, so <worksheets> stays grouped
    return insert_after(t, src, new)


def add_window(t: str, sheet_name: str) -> str:
    block = crlf(
        f"""
    <window class='worksheet' hidden='true' name='{sheet_name}'>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
      </cards>
      <simple-id uuid='{new_uuid()}' />
    </window>
"""
    )
    return insert_before(t, "  </windows>\r\n", block)


def drop_filter(ws_edits: list, ds: str, inst: str) -> None:
    """Queue removal of one categorical filter and its slice for a clone."""
    ws_edits.append((DROP, f"{ds}|{inst}"))


# ---------------------------------------------------------------- task 4: title
def add_title(t: str) -> str:
    t = clone_worksheet(
        t,
        "Y1 Landing - Title",
        "LP - Title",
        [
            (
                "<run bold='true' fontalignment='0' fontsize='16'>Academic Health</run>",
                "<run bold='true' fontalignment='0' fontsize='16'>Academic &amp; Gradebook Health</run>",
            ),
            (
                "<run fontalignment='0' fontsize='16'> | Home</run>",
                "<run fontalignment='0' fontsize='16'> | Landing Page</run>",
            ),
            (
                "<![CDATA[This tab shows the change of Y1 GPA throughout each of the terms . Y1 values are weighted. This tab last updated on <Data Update Time> PST.]]>",
                "Middle and high schools in Camden, Newark and Paterson. One place to see the headline numbers and find the right tab.",
            ),
        ],
    )
    return add_window(t, "LP - Title")


# ---------------------------------------------------------------- task 4: tiles
TITLE_STYLE = "fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'"
BRK = "\r\n                <run>Æ&#10;</run>\r\n                "


def layout_options(title_runs: str, caption: str) -> str:
    return crlf(
        f"""
      <layout-options>
        <title>
          <formatted-text>
{title_runs}
          </formatted-text>
        </title>
        <caption>
          <formatted-text>
            <run fontcolor='#8c8c8c' fontsize='8' italic='true'><![CDATA[{caption} Updated <Data Update Time>.]]></run>
          </formatted-text>
        </caption>
      </layout-options>
"""
    )


def add_tile_y1(t: str) -> str:
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Weighted Y1 GPA · marking period <[Parameters].[Parameter 4]> · middle and high schools]]></run>",
        "Students with a Y1 GPA this marking period.",
    )
    value = "<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='16'><![CDATA[<[federated.1ikycy21f3ow4k1eazzbx1iah2yl].[usr:Calculation_4005670422403850240:qk]>]]></run>"
    # Controller Ruling 1: the denominator line, in the source's small-text
    # style, off the count column-instance the sheet already carries on Tooltip.
    denom = "<run fontname='Tableau Light' fontsize='10'><![CDATA[of <[federated.1ikycy21f3ow4k1eazzbx1iah2yl].[usr:Calculation_1000000000000000021:qk]> students]]></run>"
    edits = [
        (
            "<worksheet name='LP - Tile Y1 GPA'>\r\n      <table>",
            "<worksheet name='LP - Tile Y1 GPA'>\r\n" + lo + "      <table>",
        ),
        (
            "<run fontname='Tableau Regular' fontsize='10'>% At/Above 3.0</run>",
            "<run fontname='Tableau Regular' fontsize='13'>% at or above 3.0 weighted Y1 GPA</run>",
        ),
        (value, value + BRK + denom),
    ]
    drop_filter(
        edits, GRADES_DS, "none:Calculation_4005670422414364681:nk"
    )  # Region Filter
    drop_filter(edits, GRADES_DS, "none:hos:nk")
    drop_filter(edits, GRADES_DS, "none:school_level:nk")
    t = clone_worksheet(t, "Y1 Landing - BAN Network ≥3.0", "LP - Tile Y1 GPA", edits)
    return add_window(t, "LP - Tile Y1 GPA")


def add_tile_failures(t: str) -> str:
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Y1 grades · marking period <[Parameters].[Parameter 4]> · middle and high schools]]></run>",
        "Students with a Y1 failing-course count.",
    )
    value = "<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='16'><![CDATA[<[federated.1ikycy21f3ow4k1eazzbx1iah2yl].[usr:Calculation_4005670422403997698:qk]>]]></run>"
    denom = "<run fontname='Tableau Light' fontsize='10'><![CDATA[of <[federated.1ikycy21f3ow4k1eazzbx1iah2yl].[usr:Calculation_1000000000000000024:qk]> students]]></run>"
    edits = [
        (
            "<worksheet name='LP - Tile Course Failures'>\r\n      <table>",
            "<worksheet name='LP - Tile Course Failures'>\r\n" + lo + "      <table>",
        ),
        (
            "<run fontname='Tableau Regular' fontsize='10'>% Failing 2+</run>",
            "<run fontname='Tableau Regular' fontsize='13'>% failing 2 or more courses</run>",
        ),
        (value, value + BRK + denom),
    ]
    drop_filter(edits, GRADES_DS, "none:Calculation_4005670422414364681:nk")
    drop_filter(edits, GRADES_DS, "none:hos:nk")
    drop_filter(edits, GRADES_DS, "none:school_level:nk")
    t = clone_worksheet(
        t, "Y1 Landing - BAN Network Failing ≥2", "LP - Tile Course Failures", edits
    )
    return add_window(t, "LP - Tile Course Failures")


#: `Students still needed` and its whole input closure are absent from
#: `GPA - BAN % 3.0+`. Every line below is lifted verbatim from
#: `GPA - BAN Students needed` at build time so the copies cannot drift.
#: Dependency-closure invariant (holds for all 250 worksheet-local calc
#: definitions across base.twb, zero exceptions): every field a worksheet's
#: <column> calculation references is itself declared in that worksheet's
#: <datasource-dependencies>. Copying the calc alone breaks it.
NEEDED_CALC = "Calculation_5262281088199017638"
NEEDED_INST = f"[usr:{NEEDED_CALC}:qk]"
#: Controller Ruling 10. `Students still needed` branches on
#: `[Parameters].[Parameter 3]` (p_Region). The tile drops its region filter,
#: but a Tableau parameter is workbook-global: a user who sets p_Region on the
#: Cumulative GPA Monitor would silently switch the NETWORK tile's shortfall to
#: a region goal, with nothing on the tile saying so. The tile therefore reads
#: the org-goal copy instead, and every reference the tile carries -- column
#: definition, column-instance, text encoding, mark-label token and the
#: `#,##0` format line -- is repointed to it.
ORG_INST = f"[usr:{LP_NEEDED_ORG}:qk]"
#: the inputs of NEEDED_CALC's formula, in the order the source declares them
NEEDED_INPUTS = (
    ("Measured (projected)", "Calculation_4693780698737655073"),
    ("At 3.0+ (projected)", "Calculation_9485136151529756033"),
)
NEEDED_FIELDS = ("gpa_goal_proportion_org", "gpa_goal_proportion_region")


def paired_column(src: str, name: str) -> str:
    """One `<column ...>...</column>` block, verbatim, without its newline."""
    return element(
        src,
        rf"\r\n            <column [^>]*name='\[{re.escape(name)}\]'[^>]*(?<!/)>",
        "            </column>\r\n",
    ).rstrip("\r\n")


def one_line(src: str, pattern: str, what: str) -> str:
    m = re.search(pattern, src)
    if not m:
        raise RuntimeError(f"no {what} to copy from GPA - BAN Students needed")
    return m.group(0)


def needed_lines(t: str) -> dict[str, str]:
    """Every line the cumulative tile has to borrow, keyed for readability.

    Ruling 10: the calc itself is NOT borrowed -- it is the org-goal copy
    written at worksheet depth. The instance and the number format ARE
    borrowed, so their attribute spelling stays whatever the donor sheet uses,
    with only the calc name repointed."""
    src = worksheet_block(t, "GPA - BAN Students needed")
    out = {
        "calc": "\r\n" + lp_calc_column(LP_NEEDED_ORG, 12).rstrip("\r\n"),
        "inst": one_line(
            src,
            rf"\r\n            <column-instance column='\[{NEEDED_CALC}\]'[^>]*/>",
            "column-instance",
        ).replace(NEEDED_CALC, LP_NEEDED_ORG),
        "format": one_line(
            src,
            rf"\r\n            <format attr='text-format' field='\[{re.escape(GOAL_DS)}\]\.\[usr:{NEEDED_CALC}:qk\]'[^>]*/>",
            "text-format rule",
        ).replace(NEEDED_CALC, LP_NEEDED_ORG),
    }
    for _caption, name in NEEDED_INPUTS:
        out[name] = paired_column(src, name)
    for field in NEEDED_FIELDS:
        out[field] = one_line(
            src,
            rf"\r\n            <column caption='[^']*' datatype='real' name='\[{field}\]'[^>]*/>",
            field,
        )
    return out


def add_tile_cumulative(t: str) -> str:
    # Ruling 8: the clone keeps the source's Grade filter
    # ([grade_level] = [Parameters].[Parameter 10]), so the title names the
    # grade rather than implying the tile covers every HS grade. Both tokens
    # are parameters, which resolve in a <title> and nowhere else.
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Grade <[Parameters].[Parameter 10]> · unweighted cumulative GPA · <[Parameters].[Parameter 11]>]]></run>",
        "HS students in the grade selected on the Cumulative GPA Monitor.",
    )
    value = "<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='30'><![CDATA[<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_9335003396903351453:qk]>]]></run>"
    # Ruling 9: the headline % follows [Parameter 11] through Cum GPA
    # (unweighted); the borrowed count is hard-wired to the projected columns,
    # so the run says so, mirroring the Monitor's own "always projected".
    still = f"<run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'><![CDATA[<[{GOAL_DS}].{ORG_INST}> students still needed (projected)]]></run>"
    edits = [
        (
            "<worksheet name='LP - Tile Cumulative GPA'>\r\n      <table>",
            "<worksheet name='LP - Tile Cumulative GPA'>\r\n" + lo + "      <table>",
        ),
        (
            "<run fontname='Tableau Regular' fontsize='13'>At 3.0+ cumulative</run>",
            "<run fontname='Tableau Regular' fontsize='13'>% at or above 3.0 unweighted cumulative GPA</run>",
        ),
        (value, value + BRK + still),
    ]
    # the clone lacks the Students-still-needed dependency: add the calc, its
    # four inputs, its instance, its number format and the text encoding
    # before the label references it. Each is one asserted count()==1 edit.
    if NEEDED_INST not in worksheet_block(t, "GPA - BAN % 3.0+"):
        src = needed_lines(t)
        at3_col = "\r\n            <column caption='At 3.0+' datatype='integer' name='[Calculation_5286411607457784114]' role='measure' type='quantitative'>"
        at3_inst = "\r\n            <column-instance column='[Calculation_5286411607457784114]' derivation='User' name='[usr:Calculation_5286411607457784114:qk]' pivot='key' type='quantitative' />"
        pct_text = f"\r\n              <text column='[{GOAL_DS}].[usr:Calculation_9335003396903351453:qk]' />"
        pct_fmt = f"\r\n            <format attr='text-format' field='[{GOAL_DS}].[usr:Calculation_9335003396903351453:qk]' value='*0.0%' />"
        year_col = "\r\n            <column caption='Academic Year' datatype='integer' name='[academic_year]' role='dimension' type='quantitative' />"
        grade_col = "\r\n            <column caption='Grade Level' datatype='integer' name='[grade_level]' role='measure' type='quantitative' />"
        needed_open = src["calc"].split("\r\n")[1]
        edits += [
            # the calc itself, before the At 3.0+ column (source ordering)
            (at3_col, src["calc"] + at3_col),
            # Measured (projected), immediately before the calc that reads it
            (
                "\r\n" + needed_open,
                src["Calculation_4693780698737655073"] + "\r\n" + needed_open,
            ),
            # At 3.0+ (projected), where the source keeps it: before academic_year
            (year_col, src["Calculation_9485136151529756033"] + year_col),
            # the two goal-proportion fields, before grade_level
            (grade_col, src["gpa_goal_proportion_org"] + grade_col),
            (grade_col, src["gpa_goal_proportion_region"] + grade_col),
            (at3_inst, src["inst"] + at3_inst),
            (pct_fmt, pct_fmt + src["format"]),
            (
                pct_text,
                pct_text
                + f"\r\n              <text column='[{GOAL_DS}].{ORG_INST}' />",
            ),
        ]
    drop_filter(
        edits, GOAL_DS, "none:Calculation_5742832717263693013:nk"
    )  # Region filter (goals source)
    t = clone_worksheet(t, "GPA - BAN % 3.0+", "LP - Tile Cumulative GPA", edits)
    clone = worksheet_block(t, "LP - Tile Cumulative GPA")
    # Ruling 8: the title names [Parameter 10], so the clone must declare it.
    if clone.count("name='[Parameter 10]'") != 1:
        raise RuntimeError("LP - Tile Cumulative GPA does not declare [Parameter 10]")
    assert_closure(clone, "LP - Tile Cumulative GPA")
    return add_window(t, "LP - Tile Cumulative GPA")


def assert_closure(block: str, name: str) -> None:
    """Every field a worksheet calc references must be declared in the sheet.

    The invariant every worksheet in base.twb satisfies (250/250 calc
    definitions). Checked here because the cumulative tile is the one clone
    that imports a calculation its source sheet never carried.

    A `//` comment line is not code: the LP calcs open with
    `// LP copy of [Students still needed] ...`, and scanning the raw formula
    reads that caption as a field reference and fails on a sheet that is in
    fact closed. Comment lines are dropped before the scan. Formula newlines
    are the XML entity `&#10;`, not a real newline.
    """
    declared = set(re.findall(r"<column(?:-instance)? [^>]*name='\[([^\]]*)\]'", block))
    for formula in re.findall(r"<calculation class='tableau' formula='([^']*)'", block):
        code = "&#10;".join(
            line
            for line in formula.split("&#10;")
            if not line.lstrip().startswith("//")
        )
        for ref in re.findall(r"\[([A-Za-z_][A-Za-z0-9_ ]*)\]", code):
            if ref in ("Parameters",) or ref in declared:
                continue
            raise RuntimeError(f"[{name}] calc references undeclared field [{ref}]")


def add_tile_gradebook(t: str) -> str:
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Health basis: <[Parameters].[Parameter 1 1]> · current quarter · middle and high schools]]></run>",
        "Teachers with at least one audited section this quarter.",
    )
    edits = [
        (
            "<worksheet name='LP - Tile Gradebook Health'>\r\n      <table>",
            "<worksheet name='LP - Tile Gradebook Health'>\r\n" + lo + "      <table>",
        ),
        (
            "<run fontcolor='#ffffff' fontname='Tableau Medium' fontsize='16'>Network</run>",
            "<run fontcolor='#ffffff' fontname='Tableau Medium' fontsize='13'>% of teachers with a healthy gradebook</run>",
        ),
    ]
    drop_filter(edits, GB_DS, "none:region:nk")
    drop_filter(edits, GB_DS, "none:school:nk")
    drop_filter(edits, GB_DS, "none:school_level:nk")
    t = clone_worksheet(t, "BAN Network", "LP - Tile Gradebook Health", edits)
    return add_window(t, "LP - Tile Gradebook Health")


# ---------------------------------------------------------------- task 5: strips
REGION_COL_LINE = (
    "            <column caption='Region' datatype='string' name='[region]' "
    "role='dimension' type='nominal' />"
)
REGION_INST_LINE = (
    "            <column-instance column='[region]' derivation='None' "
    "name='[none:region:nk]' pivot='key' type='nominal' />"
)


def insert_dep_sorted(w: str, name: str, ds: str, line: str, key: str) -> str:
    """Add one dependency line to a worksheet's <datasource-dependencies>.

    Tableau writes the children of that element in plain ASCII order of their
    `name='[...]'`, columns and column-instances interleaved, and rewrites the
    order on every save. Inserting at the sorted position keeps a hand-edited
    sheet byte-comparable with one Desktop has re-saved, which is what makes a
    later diff of the file readable."""
    dep = element(
        w,
        rf"\r\n          <datasource-dependencies datasource='{re.escape(ds)}'>",
        "          </datasource-dependencies>",
    )
    pos = None
    for m in re.finditer(
        r"\r\n            <column(?:-instance)? [^>]*name='\[([^\]]*)\]'", dep
    ):
        if m.group(1) > key:
            pos = m.start()
            break
    if pos is None:
        pos = dep.rindex("\r\n          </datasource-dependencies>")
    return sub_once(w, dep, dep[:pos] + "\r\n" + line + dep[pos:])


def set_title(w: str, name: str, run: str) -> str:
    """Replace the single <title> run.

    A parameter token in a <title> whose parameter the sheet does not declare
    renders as literal text, so every `[Parameters].[...]` the run carries is
    checked against the clone's own Parameters dependencies first -- the same
    guard the cumulative TILE step applies."""
    for param in re.findall(r"\[Parameters\]\.\[([^\]]*)\]", run):
        if f"name='[{param}]'" not in w:
            raise RuntimeError(f"[{name}] title names undeclared parameter [{param}]")
    w, n = re.subn(
        r"(<title>\r\n          <formatted-text>\r\n)            <run [^>]*>.*?</run>"
        r"(\r\n          </formatted-text>\r\n        </title>)",
        lambda m: f"{m.group(1)}            {run}{m.group(2)}",
        w,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise RuntimeError(f"[{name}] title run: matched {n}, wanted 1")
    return w


def set_label(w: str, name: str, runs: list[str]) -> str:
    """Replace the whole mark label with `runs`, one per line.

    Field tokens only resolve in a mark label when the sheet declares the
    column-instance they name, so every token is checked against the sheet's
    own dependencies before it is written."""
    body = "                " + BRK.join(runs)
    for tok in re.findall(r"\[((?:usr|none):[^\]]*)\]", body):
        if f"name='[{tok}]'" not in w:
            raise RuntimeError(f"[{name}] label token [{tok}] is not declared")
    w, n = re.subn(
        r"(<customized-label>\r\n              <formatted-text>\r\n).*?"
        r"(\r\n              </formatted-text>\r\n            </customized-label>)",
        lambda m: m.group(1) + body + m.group(2),
        w,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise RuntimeError(f"[{name}] customized-label: matched {n}, wanted 1")
    return w


def strip_from_tile(
    t: str,
    tile: str,
    name: str,
    ds: str,
    title_run: str,
    label_runs: list[str],
    extra: list[tuple[str, str]] | None = None,
) -> str:
    """One region strip: the matching tile, cloned, with region on rows.

    Cloning the tile rather than the tile's own source means the region
    filters are already gone and the <layout-options> are already there. The
    strip then differs from the tile in four ways: region on rows (no explicit
    sort, so Tableau's default ascending order applies), a short static header
    instead of the tile's parameter-bearing title, no caption (a strip column
    has no room for one), and a two-line label."""
    edits = [
        ("\r\n        <rows />", f"\r\n        <rows>[{ds}].[none:region:nk]</rows>"),
        *(extra or []),
    ]
    t = clone_worksheet(t, tile, name, edits)
    w0 = worksheet_block(t, name)
    # Task 4's apply_drop_filters removes a dropped filter's column-instance
    # and, for a calculated filter, that calc's <column>. Two of the four tiles
    # therefore reach here without the region instance, and any tile could in
    # principle reach here without the [region] column, so each is re-added
    # only when it is missing.
    w = w0
    if "name='[region]'" not in w:
        w = insert_dep_sorted(w, name, ds, REGION_COL_LINE, "region")
    if "name='[none:region:nk]'" not in w:
        w = insert_dep_sorted(w, name, ds, REGION_INST_LINE, "none:region:nk")
    w = set_title(w, name, title_run)
    w = cut_once(
        w, r"\r\n        <caption>.*?\r\n        </caption>", f"{name} caption"
    )
    w = set_label(w, name, label_runs)
    assert_closure(w, name)
    if "<aggregation value='true' />" not in w:
        raise RuntimeError(f"[{name}] lost <aggregation>")
    t = sub_once(t, w0, w)
    return add_window(t, name)


def cumulative_strip_edits(t: str) -> list[tuple[str, str]]:
    """Repoint the cumulative strip from the org shortfall to the region one.

    The tile reads `LP Students still needed (org)`; a per-region row has to
    compare against its own region's goal, so every one of the tile's four
    references to the org calc is swapped for the region calc. Each swap is a
    literal the clone carries exactly once, so clone_worksheet asserts it.

    The FIFTH reference site, the mark-label token, is not swapped here:
    set_label() rewrites the whole label and writes LP_NEEDED_REGION directly
    from add_strips' label_runs. Change one and check the other."""
    tile = worksheet_block(t, "LP - Tile Cumulative GPA")
    org_def = paired_column(tile, LP_NEEDED_ORG)
    region_def = "\r\n" + lp_calc_column(LP_NEEDED_REGION, 12).rstrip("\r\n")
    swaps = [(org_def, region_def)]
    for pattern, what in (
        (
            rf"\r\n            <column-instance column='\[{LP_NEEDED_ORG}\]'[^>]*/>",
            "column-instance",
        ),
        (
            rf"\r\n            <format attr='text-format' field='\[{re.escape(GOAL_DS)}\]\.\[usr:{LP_NEEDED_ORG}:qk\]'[^>]*/>",
            "text-format rule",
        ),
        (
            rf"\r\n              <text column='\[{re.escape(GOAL_DS)}\]\.\[usr:{LP_NEEDED_ORG}:qk\]' />",
            "text encoding",
        ),
    ):
        line = one_line(tile, pattern, what)
        swaps.append((line, line.replace(LP_NEEDED_ORG, LP_NEEDED_REGION)))
    return swaps


def add_strips(t: str) -> str:
    t = strip_from_tile(
        t,
        "LP - Tile Y1 GPA",
        "LP - Strip Y1 GPA",
        GRADES_DS,
        f"<run {TITLE_STYLE}>Y1 GPA at or above 3.0</run>",
        [
            f"<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='12'><![CDATA[<[{GRADES_DS}].[usr:Calculation_4005670422403850240:qk]>]]></run>",
            f"<run fontname='Tableau Light' fontsize='8'><![CDATA[(<[{GRADES_DS}].[usr:Calculation_1000000000000000011:qk]> vs. 1 wk)]]></run>",
        ],
    )
    t = strip_from_tile(
        t,
        "LP - Tile Course Failures",
        "LP - Strip Course Failures",
        GRADES_DS,
        f"<run {TITLE_STYLE}>Failing 2 or more</run>",
        [
            f"<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='12'><![CDATA[<[{GRADES_DS}].[usr:Calculation_4005670422403997698:qk]>]]></run>",
            f"<run fontname='Tableau Light' fontsize='8'><![CDATA[(<[{GRADES_DS}].[usr:Calculation_1000000000000000013:qk]> vs. 1 wk)]]></run>",
        ],
    )
    # the goals source carries no weekly comparison, so the second line is the
    # region shortfall instead of a delta
    t = strip_from_tile(
        t,
        "LP - Tile Cumulative GPA",
        "LP - Strip Cumulative GPA",
        GOAL_DS,
        # Ruling 11: this strip keeps the tile's Grade filter
        # ([grade_level] = [Parameters].[Parameter 10]), so its header has to
        # say which grade -- the one strip title that is not static. set_title
        # asserts the clone declares [Parameter 10] before writing the token.
        f"<run {TITLE_STYLE}><![CDATA[Grade <[Parameters].[Parameter 10]> · cumulative GPA at or above 3.0]]></run>",
        [
            f"<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='12'><![CDATA[<[{GOAL_DS}].[usr:Calculation_9335003396903351453:qk]>]]></run>",
            f"<run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='8'><![CDATA[<[{GOAL_DS}].[usr:{LP_NEEDED_REGION}:qk]> still needed (region goal)]]></run>",
        ],
        extra=cumulative_strip_edits(t),
    )
    # the gradebook sheet paints its own #001e62 table background, so its mark
    # label runs stay white; the title sits outside that shading, which is why
    # the tile's own title is the grey TITLE_STYLE and the strip's matches it.
    # Ruling 12: the tile had no row headers, the strip does, and that same
    # background now sits behind the region names -- so the sheet-level style
    # gets the white `color` rule that `Y1 Landing - Title` uses on
    # element='worksheet', scoped here to element='header'.
    gb_style_anchor = "\r\n        <style>\r\n          <style-rule element='table'>"
    gb_header_rule = (
        "\r\n          <style-rule element='header'>"
        "\r\n            <format attr='color' value='#ffffff' />"
        "\r\n          </style-rule>"
    )
    t = strip_from_tile(
        t,
        "LP - Tile Gradebook Health",
        "LP - Strip Gradebook Health",
        GB_DS,
        f"<run {TITLE_STYLE}>Healthy gradebooks</run>",
        [
            f"<run fontcolor='#ffffff' fontname='Tableau Semibold' fontsize='12'><![CDATA[<[{GB_DS}].[usr:Calculation_1052997927363244036:qk]>]]></run>",
            f"<run fontcolor='#ffffff' fontname='Tableau Light' fontsize='8'><![CDATA[of <[{GB_DS}].[usr:Calculation_1052997927363395589:nk]> teachers]]></run>",
        ],
        extra=[
            (
                gb_style_anchor,
                "\r\n        <style>"
                + gb_header_rule
                + "\r\n          <style-rule element='table'>",
            )
        ],
    )
    return t


# ---------------------------------------------------------------- task 6: cards
#: One directory card per tab in the suite. `tab` is the tab's own name, so the
#: card's first line reads as the label a user will look for in the tab strip;
#: `names` marks the two tabs that put student names on screen.
CARD_COPY = {
    "Home": dict(
        tab="Academic Health Home",
        q="How is this year's weighted GPA and course-failure picture moving, by school, school level and subject?",
        grain="School",
        scope="MS and HS. Camden, Newark, Paterson",
        built="Regional and school leaders",
        names=False,
    ),
    "Schools": dict(
        tab="Academic Health Schools",
        q="Where is failure concentrated by teacher, and which students near the 2.0 and 3.0 cusps need office hours?",
        grain="School, teacher, student",
        scope="MS and HS",
        built="School leaders, APs, counselors",
        names=True,
    ),
    "Monitor": dict(
        tab="Cumulative GPA Monitor",
        q="Are HS cohorts on track for the unweighted cumulative GPA goal by year end, and who sits just below 3.0?",
        grain="Grade, school, student",
        scope="HS only. Camden and Newark",
        built="KIPP Forward, HS leaders",
        names=True,
    ),
    "Rollup": dict(
        tab="Gradebook School Rollup",
        q="What share of teachers have healthy gradebooks, by school and manager?",
        grain="School, manager, teacher",
        scope="MS and HS. Camden, Newark, Paterson MS",
        built="School leaders, instructional coaches",
        names=False,
    ),
    "Teacher": dict(
        tab="Gradebook Teacher View",
        q="What does my own gradebook need before the quarter closes?",
        grain="Teacher, section",
        scope="Your own sections",
        built="Teachers",
        names=False,
    ),
}

#: A card label is one run per line, so a hard break is its own run. Unlike
#: BRK (which is spliced BETWEEN two runs on one source line) this form is a
#: whole line, indentation and trailing CRLF included.
BR = "                <run>Æ&#10;</run>\r\n"


def esc(s: str) -> str:
    """Card copy -> run text. Attribute quoting in this file is single, and
    the source's own tooltip runs spell an apostrophe `&apos;`, so `'` is
    escaped too rather than left bare."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&apos;")
    )


def card_label(c: dict) -> str:
    """The whole mark label for one directory card, as run lines.

    No field or parameter token appears anywhere in it: the card is static
    copy, and a token a sheet does not declare renders as literal text."""
    lines = [
        f"                <run fontcolor='#57c0e9' fontname='Tableau Semibold' fontsize='12' underline='true'>{esc(c['tab'])}</run>\r\n",
        BR,
        f"                <run fontcolor='#ffffff' fontname='Tableau Regular' fontsize='9'>{esc(c['q'])}</run>\r\n",
        BR,
        BR,
        "                <run fontcolor='#b9c7e6' fontname='Tableau Semibold' fontsize='8'>Grain: </run>\r\n",
        f"                <run fontcolor='#ffffff' fontsize='8'>{esc(c['grain'])}</run>\r\n",
        BR,
        "                <run fontcolor='#b9c7e6' fontname='Tableau Semibold' fontsize='8'>Scope: </run>\r\n",
        f"                <run fontcolor='#ffffff' fontsize='8'>{esc(c['scope'])}</run>\r\n",
        BR,
        "                <run fontcolor='#b9c7e6' fontname='Tableau Semibold' fontsize='8'>Built for: </run>\r\n",
        f"                <run fontcolor='#ffffff' fontsize='8'>{esc(c['built'])}</run>\r\n",
    ]
    if c["names"]:
        lines += [
            BR,
            "                <run fontcolor='#f28e2b' fontname='Tableau Semibold' fontsize='8'>Shows student names</run>\r\n",
        ]
    return "".join(lines).rstrip("\r\n")


CULL_ON = "<format attr='mark-labels-cull' value='true' />"
CULL_OFF = "<format attr='mark-labels-cull' value='false' />"
MARK_RULE = "\r\n              <style-rule element='mark'>"
CELL_LEFT = (
    "\r\n              <style-rule element='cell'>"
    "\r\n                <format attr='text-align' value='left' />"
    "\r\n              </style-rule>"
)
CELL_CENTER_FMT = "\r\n                <format attr='text-align' value='center' />"
CELL_LEFT_FMT = "\r\n                <format attr='text-align' value='left' />"


def body_style(w: str) -> str:
    r"""Ruling 13, applied to every card body and guide sheet.

    Two changes, both on the pane's own <style>:

    - `mark-labels-cull` off. Both clone sources ship it ON, and on a Text
      mark a culled label does not clip -- the cell renders blank. A card
      label is about ten lines, so culling it is a silent blank card.
    - a left-aligned cell rule. The Title clone has no cell rule at all, so
      one is inserted before the existing mark rule (the order Tableau writes
      them in). The roster clone already carries a CENTRED one; a second rule
      for the same element would be shadowed by the later one, so that rule is
      converted in place instead of a second being added. Either way the sheet
      ends with exactly one `element='cell'` rule, aligned left.

    The inserted rule uses the file's own 14/16/14 indentation -- the same
    bytes Desktop writes for the roster's centred rule -- so a later diff
    against a Desktop re-save stays readable.
    """
    w = sub_once(w, CULL_ON, CULL_OFF)
    if "<style-rule element='cell'>" in w:
        w = sub_once(w, CELL_CENTER_FMT, CELL_LEFT_FMT)
    else:
        w = insert_before(w, MARK_RULE, CELL_LEFT)
    return w


def add_cards(t: str) -> str:
    """Five directory cards, cloned from `Y1 Landing - Title`.

    The Title sheet is already a static text mark with no filters; the
    `Sheet Card - expectations` alternative carries two action filters bound
    to the Teacher View that would all have to be stripped."""
    old_label = (
        "                <run bold='true' fontalignment='0' fontsize='16'>Academic Health</run>\r\n"
        "                <run fontalignment='0' fontsize='16'> | Home</run>"
    )
    for key, c in CARD_COPY.items():
        name = f"LP - Card {key}"
        t = clone_worksheet(t, "Y1 Landing - Title", name, [(old_label, card_label(c))])
        w = worksheet_block(t, name)
        # the Title sheet's <layout-options> holds a caption and nothing else;
        # a card sits in a framed dashboard zone that wants neither a sheet
        # title nor a caption above the copy.
        w2 = cut_once(
            w,
            r"      <layout-options>.*?</layout-options>\r\n",
            f"{name} layout-options",
        )
        w2 = body_style(w2)
        assert_closure(w2, name)
        t = sub_once(t, w, w2)
        t = add_window(t, name)
    return t


def add_guides(t: str) -> str:
    """Five help-guide slots, cloned from `Links - GPA Roster - Newark`.

    Placeholder state, deliberately: one muted italic run, no underline and no
    URL action, so nothing on the dashboard looks clickable before the guides
    exist. Task 10 fills them in."""
    old_label = (
        "                <run fontcolor='#57c0e9' underline='true'>&lt;</run>\r\n"
        f"                <run fontcolor='#57c0e9' underline='true'>[{GRADES_DS}].[none:Calculation_7500000000000000001:nk]</run>\r\n"
        "                <run fontcolor='#57c0e9' underline='true'>&gt;</run>"
    )
    new_label = "                <run fontcolor='#b9c7e6' fontsize='8' italic='true'>Help guide: coming soon</run>"
    for key in CARD_COPY:
        name = f"LP - Guide {key}"
        t = clone_worksheet(
            t, "Links - GPA Roster - Newark", name, [(old_label, new_label)]
        )
        w = worksheet_block(t, name)
        # Drop EVERY filter and every slice except [Exclude ES]. The base
        # republished 2026-09-10 13:40 UTC added two action filters to the
        # roster sheets on top of their cross-source school filter, and a
        # placeholder that nothing points at needs none of the three.
        #
        # `[^>]*(?<!/)>` and the leading \r\n are the same two guards
        # apply_drop_filters() carries, and for the same reasons:
        # selftest_drop_filters() proves that without the negative lookbehind
        # the opening-tag match runs straight through one of base.twb's 6
        # SELF-CLOSING categorical filters and `.*?</filter>` then eats on to
        # the NEXT filter's close, deleting two elements in one substitution.
        # All three roster filters are paired today, so the bug would not fire
        # -- and the `n < 3` count guard would not catch it if it did, because
        # the run-on deletion lowers the match count rather than raising it.
        # Every removal below is likewise \r\n-anchored at the line start
        # instead of consuming the trailing newline: a 10-space-indented
        # literal is a substring of a 12-space-indented one.
        w2, n = re.subn(
            r"\r\n          <filter class='categorical' [^>]*(?<!/)>.*?</filter>",
            "",
            w,
            flags=re.S,
        )
        if n < 3:
            raise RuntimeError(f"{name}: dropped {n} filters, wanted at least 3")
        w2, n = re.subn(
            rf"\r\n            <column>(?!\[{re.escape(GRADES_DS)}\]\.\[Exclude ES\])[^<]*</column>",
            "",
            w2,
        )
        if n < 1:
            raise RuntimeError(f"{name}: no slice entries dropped")
        # end state, not just the removal count: one slice, the workbook-wide set
        sl = element(w2, r"\r\n          <slices>", "          </slices>")
        if sl.count("<column>") != 1 or "[Exclude ES]" not in sl:
            raise RuntimeError(f"{name}: slices did not reduce to [Exclude ES]")
        # the cross-source filter was the only use of the goals source here
        w2 = cut_once(
            w2,
            rf"\r\n          <datasource-dependencies datasource='{re.escape(GOAL_DS)}'>.*?</datasource-dependencies>",
            f"{name} goals dependencies",
        )
        w2 = sub_once(
            w2,
            f"\r\n            <datasource caption='rpt_tableau__gpa_goal_progress (kipptaf_tableau)' name='{GOAL_DS}' />",
            "",
        )
        # Drop the roster tooltip AND turn tooltips off. Deleting
        # <customized-tooltip> alone does not silence the hover: it restores
        # Tableau's DEFAULT tooltip, and the mark's text encoding is the
        # cloned `'Newark'` calc, so every placeholder would pop
        # `'Newark': Newark`. The roster source carries no <tooltip-style>
        # element at all, so one is added in the position the card clones
        # already have it (inherited from Y1 Landing - Title): straight after
        # <cols />, the last child of <table>.
        w2 = cut_once(
            w2,
            r"\r\n            <customized-tooltip>.*?</customized-tooltip>",
            f"{name} tooltip",
        )
        w2 = insert_after(
            w2,
            "\r\n        <cols />",
            "\r\n        <tooltip-style tooltip-mode='none' />",
        )
        w2 = body_style(w2)
        assert_closure(w2, name)
        if GOAL_DS in w2:
            raise RuntimeError(f"{name}: the goals source is still referenced")
        t = sub_once(t, w, w2)
        t = add_window(t, name)
    return t


# ---------------------------------------------------------------- task 7: geometry
#: One pixel of the 1366 x 1500 canvas in Tableau's 100000-unit zone space. A
#: zone's `fixed-size` is the PIXEL size along its parent's flow axis; `w`/`h`
#: are the unit sizes, and the two have to agree or the render drifts from the
#: XML.
W_UNIT = 100000 / 1366
H_UNIT = 100000 / 1500
_zone_id = [0]


def zid() -> int:
    _zone_id[0] += 1
    return _zone_id[0]


def px_w(px: float) -> int:
    return round(px * W_UNIT)


def px_h(px: float) -> int:
    return round(px * H_UNIT)


def attrs(a: dict) -> str:
    """`k='v'` pairs in the plain ASCII order Tableau writes them in.

    Every zone tag in base.twb has its attributes sorted (`fixed-size`,
    `forceUpdate`, `friendly-name`, `h`, `id`, `is-fixed`, `is-scaled`,
    `mode`, `name`, `param`, `show-caption`, `show-title`, `type-v2`, `w`,
    `x`, `y`), so building the tag from a dict and sorting keeps a hand-built
    zone byte-comparable with one Desktop has re-saved. Attribute order is
    semantically irrelevant; diff readability is the whole point."""
    return " ".join(f"{k}='{v}'" for k, v in sorted(a.items()))


STYLE_NONE = (
    "<zone-style>\r\n"
    "  <format attr='border-color' value='#000000' />\r\n"
    "  <format attr='border-style' value='none' />\r\n"
    "  <format attr='border-width' value='0' />\r\n"
    "  <format attr='margin' value='4' />\r\n"
    "</zone-style>\r\n"
)


def indent(block: str, n: int) -> str:
    pad = " " * n
    return "".join(
        pad + line if line.strip() else line for line in block.splitlines(keepends=True)
    )


def zone(a: dict, inner: str, depth: int, style: str = STYLE_NONE) -> str:
    """One `<zone>`; children first, the container's own style last.

    Content model, verified in references/content-models.md:
    `(formatted-text, layout-cache?, zone, flipboard, zone-style?)`. Putting
    `<zone-style>` before the child zones is rejected by Desktop."""
    pad = " " * depth
    return (
        f"{pad}<zone {attrs(a)}>\r\n{inner}{indent(style, depth + 2)}{pad}</zone>\r\n"
    )


def fixed(a: dict, fixed_px: int | None) -> dict:
    if fixed_px:
        a["fixed-size"] = fixed_px
        a["is-fixed"] = "true"
    return a


#: Every sheet zone on this dashboard gets the plain cell layout-cache. The
#: roster zones on Home carry `fixed-size-h/-w` instead; a fixed cache pins
#: the sheet to a pixel box that the flow container is already deciding.
SHEET_CACHE = (
    "<layout-cache cell-count-h='1' cell-count-w='1' type-h='cell' type-w='cell' />\r\n"
)


def sheet_zone(
    name: str,
    x: int,
    y: int,
    w: int,
    h: int,
    depth: int,
    *,
    title: bool = False,
    caption: bool = False,
    fixed_px: int | None = None,
) -> str:
    a = fixed(
        {
            "h": h,
            "id": zid(),
            "name": name,
            "show-caption": str(caption).lower(),
            "show-title": str(title).lower(),
            "w": w,
            "x": x,
            "y": y,
        },
        fixed_px,
    )
    return zone(a, " " * (depth + 2) + SHEET_CACHE, depth)


def text_zone(
    runs: str,
    x: int,
    y: int,
    w: int,
    h: int,
    depth: int,
    fixed_px: int | None = None,
    bg: str | None = None,
) -> str:
    a = fixed(
        {
            "forceUpdate": "true",
            "h": h,
            "id": zid(),
            "type-v2": "text",
            "w": w,
            "x": x,
            "y": y,
        },
        fixed_px,
    )
    inner = (
        " " * (depth + 2)
        + "<formatted-text>\r\n"
        + indent(runs, depth + 4)
        + " " * (depth + 2)
        + "</formatted-text>\r\n"
    )
    style = (
        STYLE_NONE
        if not bg
        else STYLE_NONE.replace(
            "</zone-style>",
            f"  <format attr='background-color' value='{bg}' />\r\n</zone-style>",
        )
    )
    return zone(a, inner, depth, style)


def button_zone(
    caption: str,
    target_window_uuid: str,
    x: int,
    y: int,
    w: int,
    h: int,
    depth: int,
    fixed_px: int,
) -> str:
    """A navigation button, in the shape this workbook's own buttons carry.

    The four Tableau-written buttons in base.twb hold exactly `<caption>`,
    `<button-caption-font-style>` and `<format attr='background-color'>` per
    `<button-visual-state>`. `<tooltip-text>` -- which the brief's form adds --
    appears nowhere in this workbook (byte-counted: 0) and the manifest
    declares only `BasicButtonObject` and `BasicButtonObjectTextSupport`, so an
    undeclared element risks `no declaration found for element 'tooltip-text'`
    on open and would make `check_twb --ref base.twb` report an unknown
    element. Omitted; the caption is the label either way."""
    a = {
        "fixed-size": fixed_px,
        "h": h,
        "id": zid(),
        "is-fixed": "true",
        "type-v2": "dashboard-object",
        "w": w,
        "x": x,
        "y": y,
    }
    inner = indent(
        crlf(f"""
<button action='tabdoc:goto-sheet window-id=&quot;{target_window_uuid}&quot;' button-type='text'>
  <button-visual-state>
    <caption>{esc(caption)}</caption>
    <button-caption-font-style fontcolor='#ffffff' fontname='Tableau Bold' fontsize='10' />
    <format attr='background-color' value='#333333' />
  </button-visual-state>
</button>
"""),
        depth + 2,
    )
    return zone(a, inner, depth)


def empty_zone(x: int, y: int, w: int, h: int, depth: int) -> str:
    return zone(
        {"h": h, "id": zid(), "type-v2": "empty", "w": w, "x": x, "y": y}, "", depth
    )


def flow(
    param: str,
    x: int,
    y: int,
    w: int,
    h: int,
    depth: int,
    children: str,
    fixed_px: int | None = None,
    bg: str | None = None,
    name: str | None = None,
) -> str:
    a = fixed(
        {
            "h": h,
            "id": zid(),
            "param": param,
            "type-v2": "layout-flow",
            "w": w,
            "x": x,
            "y": y,
        },
        fixed_px,
    )
    if name:
        a["friendly-name"] = name
    style = (
        "<zone-style>\r\n"
        "  <format attr='border-color' value='#000000' />\r\n"
        "  <format attr='border-style' value='none' />\r\n"
        "  <format attr='border-width' value='0' />\r\n"
        + (f"  <format attr='background-color' value='{bg}' />\r\n" if bg else "")
        + "</zone-style>\r\n"
    )
    return zone(a, children, depth, style)


# ---------------------------------------------------------------- task 7: the page
ROOT_X, ROOT_W = 586, 98828
ROOT_Y, ROOT_H = px_h(8), 100000 - 2 * px_h(8)
NAVY = "#001e62"

#: target window uuids, re-read from base.twb by read_window_uuids()
WIN = {
    "Academic Health Home": "{0AC26311-199E-49CE-9660-25C6B2FCF0C8}",
    "Academic Health Schools": "{73F774A6-1C5F-4D0D-A201-1444AD0D3D59}",
    "Cumulative GPA Monitor": "{ADAF5834-6C69-47A2-8FED-EBF0C9A782FC}",
    "Gradebook School Rollup": "{3F237DC3-54DD-4F2D-8E5C-EB1C7DE8FC10}",
    "Gradebook Teacher View": "{8248DE6A-1111-444E-8496-6E843188D9A6}",
}
#: tab order, which is the header button order
TABS = tuple(WIN)
BUTTON_CAPTION = {
    "Academic Health Home": "Home",
    "Academic Health Schools": "School View",
    "Cumulative GPA Monitor": "GPA Monitor",
    "Gradebook School Rollup": "Gradebook Rollup",
    "Gradebook Teacher View": "Teacher View",
}
CARD_KEYS = tuple(CARD_COPY)
CARD_TARGET = {k: str(c["tab"]) for k, c in CARD_COPY.items()}
TILE_TARGET = {
    "LP - Tile Y1 GPA": "Academic Health Home",
    "LP - Tile Course Failures": "Academic Health Schools",
    "LP - Tile Cumulative GPA": "Cumulative GPA Monitor",
    "LP - Tile Gradebook Health": "Gradebook School Rollup",
}
REGIONS = ("Newark", "Camden", "Paterson")
ROSTER_SHEETS = [f"Links - GPA Roster - {r}" for r in REGIONS]
LP_SHEETS = [
    "LP - Title",
    "LP - Tile Y1 GPA",
    "LP - Tile Course Failures",
    "LP - Tile Cumulative GPA",
    "LP - Tile Gradebook Health",
    "LP - Strip Y1 GPA",
    "LP - Strip Course Failures",
    "LP - Strip Cumulative GPA",
    "LP - Strip Gradebook Health",
] + [f"LP - {k} {c}" for k in ("Card", "Guide") for c in CARD_KEYS]

#: a line break inside a dashboard text zone. BR is the same run at the mark
#: label's 16-space indent; here indent() supplies the padding.
TEXT_BR = "<run>Æ&#10;</run>\r\n"


def header(y: int, depth: int) -> str:
    h = px_h(80)
    x = ROOT_X
    logo_w, year_w, btn_w = px_w(167), px_w(130), px_w(120)
    title_w = ROOT_W - logo_w - year_w - len(TABS) * btn_w
    parts = [
        zone(
            {
                "fixed-size": 167,
                "h": h,
                "id": zid(),
                "is-fixed": "true",
                "is-scaled": "1",
                "param": "Image/CMO_logo_whiteOrange.png",
                "type-v2": "bitmap",
                "w": logo_w,
                "x": x,
                "y": y,
            },
            "",
            depth + 2,
        )
    ]
    x += logo_w
    parts.append(sheet_zone("LP - Title", x, y, title_w, h, depth + 2, caption=True))
    x += title_w
    parts.append(
        zone(
            {
                "custom-title": "true",
                "fixed-size": 130,
                "h": h,
                "id": zid(),
                "is-fixed": "true",
                "mode": "compact",
                "param": "[Parameters].[Parameter 2]",
                "type-v2": "paramctrl",
                "w": year_w,
                "x": x,
                "y": y,
            },
            " " * (depth + 4)
            + "<formatted-text>\r\n"
            + " " * (depth + 6)
            + "<run>Academic Year</run>\r\n"
            + " " * (depth + 4)
            + "</formatted-text>\r\n",
            depth + 2,
        )
    )
    x += year_w
    for tab in TABS:
        parts.append(
            button_zone(BUTTON_CAPTION[tab], WIN[tab], x, y, btn_w, h, depth + 2, 120)
        )
        x += btn_w
    return flow(
        "horz",
        ROOT_X,
        y,
        ROOT_W,
        h,
        depth,
        "".join(parts),
        fixed_px=80,
        bg=NAVY,
        name="Header",
    )


def _row(names: list[str], y: int, h: int, depth: int, **kw) -> str:
    """Sheet zones side by side, the last one taking the width remainder."""
    w = ROOT_W // len(names)
    parts, x = [], ROOT_X
    for i, name in enumerate(names):
        ww = w if i < len(names) - 1 else ROOT_X + ROOT_W - x
        parts.append(sheet_zone(name, x, y, ww, h, depth, **kw))
        x += ww
    return "".join(parts)


def tiles(y: int, depth: int) -> str:
    h = px_h(220)
    body = _row(list(TILE_TARGET), y, h, depth + 2, title=True, caption=True)
    return flow("horz", ROOT_X, y, ROOT_W, h, depth, body, fixed_px=220, name="Tiles")


def region_strip(y: int, depth: int) -> str:
    h = px_h(150)
    names = [n.replace("Tile", "Strip") for n in TILE_TARGET]
    body = _row(names, y, h, depth + 2, title=True)
    return flow("horz", ROOT_X, y, ROOT_W, h, depth, body, fixed_px=150, name="Regions")


#: Controller ruling 2. The strip's region rows are the only place a reader
#: learns which regions are in the sources at all, so the sentence that says
#: why Miami is absent sits directly under it, with the Paterson HS caveat
#: that the cumulative column raises.
FOOTNOTE = (
    "Miami is not yet in any measure on this page. It joins when Focus gradebook "
    "data is onboarded. Paterson has no high school, so its cumulative GPA cell is blank."
)


def footnote(y: int, depth: int) -> str:
    runs = (
        f"<run fontcolor='#8c8c8c' fontsize='8' italic='true'>{esc(FOOTNOTE)}</run>\r\n"
    )
    return text_zone(runs, ROOT_X, y, ROOT_W, px_h(20), depth, fixed_px=20)


def cards(y: int, depth: int) -> str:
    """Five navy panels, each a card body over its 24 px guide slot."""
    h, body_h, guide_h = px_h(220), px_h(196), px_h(24)
    w = ROOT_W // len(CARD_KEYS)
    parts, x = [], ROOT_X
    for i, key in enumerate(CARD_KEYS):
        ww = w if i < len(CARD_KEYS) - 1 else ROOT_X + ROOT_W - x
        inner = sheet_zone(
            f"LP - Card {key}", x, y, ww, body_h, depth + 4
        ) + sheet_zone(
            f"LP - Guide {key}", x, y + body_h, ww, guide_h, depth + 4, fixed_px=24
        )
        parts.append(flow("vert", x, y, ww, h, depth + 2, inner, bg=NAVY))
        x += ww
    return flow(
        "horz",
        ROOT_X,
        y,
        ROOT_W,
        h,
        depth,
        "".join(parts),
        fixed_px=220,
        name="Directory",
    )


#: Controller ruling 14. Each of the two long-copy text zones opens with a
#: bold 11 pt heading run and a break, taken out of the zone's existing
#: height rather than added to it: definitions runs 21 lines in a 400 px zone
#: and coverage 12 in a 220 px one.
DEF_HEADING = "What the terms mean"
COV_HEADING = "Where each tab has data"
HEADING_SIZE = 11


def heading_run(text: str) -> str:
    """The zone's own heading. No `fontname`, so it inherits the zone's
    regular face -- which is what keeps the coverage heading out of Courier
    while every grid line below it stays monospaced."""
    return (
        f"<run bold='true' fontcolor='{NAVY}' fontsize='{HEADING_SIZE}'>"
        f"{esc(text)}</run>\r\n" + TEXT_BR
    )


#: The spec's definitions table, verbatim. Each entry is the term and its
#: sentence split into visual lines: a tall text zone's wrap behaviour has not
#: been probed in this corpus, so every line break is explicit and no line
#: exceeds DEF_LINE_MAX rendered characters, term prefix included.
DEF_LINE_MAX = 110
DEFINITIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Y1 GPA",
        (
            "Weighted, current year only, quarter to date. The GPA on Home, School View and the two Y1 tiles.",
        ),
    ),
    (
        "Cumulative GPA",
        (
            "Unweighted, every high school year on record. The GPA on the Monitor and the cumulative tile.",
            "The two GPAs are never interchangeable.",
        ),
    ),
    (
        "Weighted versus unweighted",
        (
            "An unweighted GPA scores every course on the same scale,",
            "topping out at 4.33 for an A+. An A in AP Biology counts the same as an A in regular Biology.",
            "A weighted GPA gives honors and AP courses a bump above that for the same letter grade.",
            "Y1 GPA on this suite is weighted. Cumulative GPA is unweighted, so a student's cumulative",
            "number will usually read lower than their Y1 number, and that is expected, not an error.",
        ),
    ),
    (
        "Projected versus on the books",
        (
            "The Monitor's basis switch. On the books is the cumulative GPA from posted",
            "grades today. Projected carries this year's in-progress grades to year end. The tile uses projected.",
        ),
    ),
    (
        "Marking period",
        (
            "Q1 through Q4 are quarter grades. Y1 is the running year grade. Home's default is Y1.",
        ),
    ),
    (
        "Failing",
        (
            "A course whose Y1 letter grade is an F. The failures tile counts students with 2 or more.",
        ),
    ),
    (
        "Healthy gradebook",
        (
            "A teacher with no flag on any of their sections this quarter. The two bases differ by one",
            "flag: excluding comments ignores the below-70-without-comment flag until quarter close.",
            "The tile uses excluding comments.",
        ),
    ),
    (
        "The three gradebook flags",
        (
            "Not enough assignments entered against the expectation for the category.",
            "A grade above 100. A grade below 70 with no comment.",
        ),
    ),
    (
        "Goal",
        (
            "The share of students expected at or above 3.0 cumulative, set per network, region and",
            "school in the GPA goals source.",
        ),
    ),
    (
        "Can still reach 3.0",
        (
            "A student below 3.0 whose GPA needed to get there is within the grade scale.",
        ),
    ),
)


def definitions(y: int, depth: int) -> str:
    runs = [heading_run(DEF_HEADING)]
    for i, (term, lines) in enumerate(DEFINITIONS):
        if i:
            runs.append(TEXT_BR)
        runs.append(
            f"<run bold='true' fontcolor='{NAVY}' fontsize='9'>{esc(term)}  </run>\r\n"
        )
        for j, line in enumerate(lines):
            if j:
                runs.append(TEXT_BR)
            runs.append(f"<run fontcolor='#333333' fontsize='9'>{esc(line)}</run>\r\n")
            rendered = len(term) + 2 + len(line) if j == 0 else len(line)
            if rendered > DEF_LINE_MAX:
                raise RuntimeError(
                    f"definitions line {rendered} chars: {term}/{line[:40]!r}"
                )
    return text_zone("".join(runs), ROOT_X, y, ROOT_W, px_h(400), depth, fixed_px=400)


#: The spec's coverage grid, verbatim, as of 2026-09-10.
COV_COLS = ("Home", "Schools", "Monitor", "Rollup", "Teacher View")
COV_ROWS: tuple[tuple[str, tuple[bool, ...]], ...] = (
    ("Camden MS", (True, True, False, True, True)),
    ("Camden HS", (True, True, True, True, True)),
    ("Newark MS", (True, True, False, True, True)),
    ("Newark HS", (True, True, True, True, True)),
    ("Paterson MS", (True, True, False, True, True)),
    ("Paterson HS", (False, False, False, False, False)),
    ("Miami", (False, False, False, False, False)),
)
COV_NOTES = (
    "Paterson HS: no high school.",
    "Miami: not in the suite until Focus gradebook data is onboarded.",
)
COV_LABEL_W, COV_COL_W = 14, 9


def coverage(y: int, depth: int) -> str:
    """The coverage grid: a monospaced text zone, not a worksheet.

    Space padding only aligns if the runs render in a fixed-pitch face, hence
    `fontname='Courier New'` on every run; the zone is one text object, so a
    single face applies to the whole grid."""
    lines = [
        " " * COV_LABEL_W
        + "".join(c.ljust(COV_COL_W) for c in COV_COLS[:-1])
        + COV_COLS[-1]
    ]
    for label, marks in COV_ROWS:
        lines.append(
            label.ljust(COV_LABEL_W)
            + "".join(("●" if m else "—").ljust(COV_COL_W) for m in marks[:-1])
            + ("●" if marks[-1] else "—")
        )
    lines.append("")
    lines.extend(COV_NOTES)
    runs = [heading_run(COV_HEADING)]
    for i, line in enumerate(lines):
        if i:
            runs.append(TEXT_BR)
        runs.append(
            f"<run fontname='Courier New' fontsize='9'>{esc(line)}</run>\r\n"
            if line
            else ""
        )
    return text_zone("".join(runs), ROOT_X, y, ROOT_W, px_h(220), depth, fixed_px=220)


def links(y: int, depth: int) -> str:
    """The roster strip: a label, the three existing link sheets, a spacer.

    Home styles the same label `#b9c7e6` because it sits on the navy header;
    this strip is on the page's white ground, so the label takes the navy."""
    h = px_h(60)
    label_w, sheet_w = px_w(100), px_w(60)
    x = ROOT_X
    parts = [
        text_zone(
            f"<run bold='true' fontcolor='{NAVY}' fontsize='8'>GPA Roster</run>\r\n",
            x,
            y,
            label_w,
            h,
            depth + 2,
            fixed_px=100,
        )
    ]
    x += label_w
    for region in REGIONS:
        parts.append(
            sheet_zone(
                f"Links - GPA Roster - {region}",
                x,
                y,
                sheet_w,
                h,
                depth + 2,
                fixed_px=60,
            )
        )
        x += sheet_w
    parts.append(empty_zone(x, y, ROOT_X + ROOT_W - x, h, depth + 2))
    return flow(
        "horz", ROOT_X, y, ROOT_W, h, depth, "".join(parts), fixed_px=60, name="Links"
    )


#: (builder, pixel height) top to bottom. The heights sum to 1370 px; the
#: root's usable 1484 px (1500 less the 8 px inset top and bottom) leaves a
#: 114 px spacer, which is also the root flow's one non-fixed child.
PAGE = (
    (header, 80),
    (tiles, 220),
    (region_strip, 150),
    (footnote, 20),
    (cards, 220),
    (definitions, 400),
    (coverage, 220),
    (links, 60),
)


def parameter2_dependencies(t: str) -> str:
    """The dashboard-level `[Parameter 2]` block, copied from Home.

    Home is the attested dashboard-level form for a `p_Academic_Year`
    paramctrl: it carries the `<aliases>` AND the `<members>` that a
    `param-domain-type='list'` control needs to populate its dropdown. The
    worksheet-level copy on the tiles carries the aliases only."""
    home = element(
        t,
        r"\r\n    <dashboard [^>]*name='Academic Health Home'>",
        "    </dashboard>\r\n",
    )
    dep = element(
        home,
        r"\r\n      <datasource-dependencies datasource='Parameters'>",
        "      </datasource-dependencies>\r\n",
    )
    col = element(
        dep,
        r"\r\n        <column [^>]*name='\[Parameter 2\]'[^>]*(?<!/)>",
        "        </column>\r\n",
    )
    if "<members>" not in col or "<aliases>" not in col:
        raise RuntimeError("Home's [Parameter 2] block lost its aliases or members")
    return (
        "      <datasource-dependencies datasource='Parameters'>"
        + col
        + "      </datasource-dependencies>\r\n"
    )


def build_dashboard(t: str) -> tuple[str, str]:
    """Return (dashboard element, dashboard window element)."""
    _zone_id[0] = 0
    depth = 8
    y = ROOT_Y
    body = []
    for fn, px in PAGE:
        body.append(fn(y, depth + 2))
        y += px_h(px)
    spacer_h = ROOT_Y + ROOT_H - y
    if spacer_h != px_h(114):
        raise RuntimeError(f"spacer is {spacer_h}, wanted {px_h(114)}")
    body.append(empty_zone(ROOT_X, y, ROOT_W, spacer_h, depth + 2))
    root = flow("vert", ROOT_X, ROOT_Y, ROOT_W, ROOT_H, depth, "".join(body))
    dashboard = (
        crlf(f"""
    <dashboard enable-sort-zone-taborder='true' name='Landing Page'>
      <style />
      <size maxheight='1500' maxwidth='1366' minheight='1500' minwidth='1366' sizing-mode='fixed' />
      <datasources>
        <datasource name='Parameters' />
        <datasource caption='rpt_tableau__student_course_grades+ (kipptaf_tableau)' name='{GRADES_DS}' />
        <datasource caption='rpt_tableau__gpa_goal_progress (kipptaf_tableau)' name='{GOAL_DS}' />
        <datasource caption='rpt_tableau__gradebook_audit (kipptaf_tableau)' name='{GB_DS}' />
      </datasources>
""")
        + parameter2_dependencies(t)
        + crlf("""
      <zones>
""")
        + root
        + crlf(f"""
      </zones>
      <simple-id uuid='{new_uuid()}' />
    </dashboard>
""")
    )
    viewpoints = "".join(
        f"        <viewpoint name='{esc(n)}'>\r\n"
        f"          <zoom type='entire-view' />\r\n"
        f"        </viewpoint>\r\n"
        for n in sorted(LP_SHEETS + ROSTER_SHEETS)
    )
    window = (
        crlf("""
    <window class='dashboard' maximized='true' name='Landing Page'>
      <viewpoints>
""")
        + viewpoints
        + crlf(f"""
      </viewpoints>
      <active id='-1' />
      <simple-id uuid='{new_uuid()}' />
    </window>
""")
    )
    return dashboard, window


def read_window_uuids(t: str) -> None:
    """The five target window uuids, read from the file and checked.

    `(?:(?!</window>).)*?` rather than `.*?` under re.S: a plain lazy any
    crosses `</window>`, so a target window that ever lost its own trailing
    `<simple-id>` would silently pick up the NEXT window's uuid and the five
    header buttons would point at the wrong tabs with nothing failing."""
    for tab in WIN:
        m = re.search(
            rf"<window class='dashboard'[^>]*name='{re.escape(tab)}'"
            r"(?:(?!</window>).)*?"
            r"<simple-id uuid='([^']*)' />\r\n    </window>",
            t,
            re.S,
        )
        if not m:
            raise RuntimeError(f"window uuid for {tab}")
        if m.group(1) != WIN[tab]:
            raise RuntimeError(
                f"window uuid for {tab} is {m.group(1)}, the plan says {WIN[tab]}"
            )
        WIN[tab] = m.group(1)


ROSTER = {
    "Newark": "https://docs.google.com/spreadsheets/d/12RHEUde41uR91Fp1aNrpImxhg72kOjPAQu7xLJ90evc/edit?gid=0#gid=0",
    "Camden": "https://docs.google.com/spreadsheets/d/1qM6DQk_mqh4x_rI5YVQyZdYbfDxzOaLGyrqjySlVv2Y/edit?gid=0#gid=0",
    "Paterson": "https://docs.google.com/spreadsheets/d/13j1khv49eSxTFUJGxbgQKnjvmUhYTgH-SshZr5NWCbU/edit?gid=0#gid=0",
}


def read_roster_urls(t: str) -> None:
    """The roster URLs, from the base's own Home actions, not from the plan."""
    for region in ROSTER:
        m = re.search(
            rf"<action caption='GPA Roster {region} \(Academic Health Home\)'[^>]*>.*?"
            r"<link caption='[^']*' expression='([^']*)' />",
            t,
            re.S,
        )
        if not m:
            raise RuntimeError(f"no Home roster action for {region}")
        if m.group(1) != ROSTER[region]:
            raise RuntimeError(f"roster URL for {region} differs from the plan")


def add_dashboard(t: str) -> str:
    read_window_uuids(t)
    read_roster_urls(t)
    dashboard, window = build_dashboard(t)
    t = insert_before(t, "  </dashboards>\r\n", dashboard)
    # the base's <windows> tag carries source-height='114'; anchor on the tag
    # as found rather than on a guessed spelling
    windows_tag = re.search(r"  <windows[^>]*>\r\n", t)
    if not windows_tag:
        raise RuntimeError("no <windows> opening tag")
    t = insert_after(t, windows_tag.group(0), window)
    # move the default-view marker off whichever existing window carries it
    # (the one sanctioned edit to an existing element). The base of 2026-09-10
    # 13:40 UTC has it on Academic Health Home.
    if t.count(" maximized='true'") != 2:
        raise RuntimeError("expected exactly one pre-existing maximized window")
    t = re.sub(
        r"(<window class='dashboard') maximized='true' (name='(?!Landing Page)[^']*')",
        r"\1 \2",
        t,
        count=1,
    )
    if t.count(" maximized='true'") != 1:
        raise RuntimeError("default-view marker move failed")
    return t


def nav_action(n: int, source_sheet: str, target: str) -> str:
    return crlf(f"""
    <nav-action caption='LP {n:02d} {esc(source_sheet)} to {esc(target)}' name='[LP_Nav_{n:02d}_{uuid.uuid4().hex.upper()}]'>
      <activation type='on-select' />
      <source dashboard='Landing Page' type='sheet' worksheet='{esc(source_sheet)}' />
      <params>
        <param name='sheet' value='{esc(target)}' />
      </params>
    </nav-action>
""")


#: base.twb groups <actions> children by kind -- every <action>, then every
#: <nav-action>, then every <edit-parameter-action> -- which is what Desktop
#: writes and very likely the content model. Inserting before </actions> would
#: put an <action> after the <edit-parameter-action> block; each new element
#: goes at the end of its OWN group instead.
FIRST_NAV_ACTION = "    <nav-action caption='Open Teacher' name='[Action18_A5B48E9807DE44888A395CF989A57E39]'>"
FIRST_PARAM_ACTION = "    <edit-parameter-action caption='Close panel' name='[Action13_EAD260FCB5F84BAAB48B5C74E92D9862]'>"


def add_actions(t: str) -> str:
    navs = []
    n = 0
    for key, target in CARD_TARGET.items():
        n += 1
        navs.append(nav_action(n, f"LP - Card {key}", target))
    for sheet, target in TILE_TARGET.items():
        n += 1
        navs.append(nav_action(n, sheet, target))
    urls = [
        crlf(f"""
    <action caption='GPA Roster {region} (Landing Page)' name='[LP_Link_{region}]'>
      <activation type='on-select' />
      <source dashboard='Landing Page' type='sheet' worksheet='Links - GPA Roster - {region}' />
      <link caption='' expression='{esc(url)}' />
    </action>
""")
        for region, url in ROSTER.items()
    ]
    t = insert_before(t, FIRST_NAV_ACTION, "".join(urls))
    return insert_before(t, FIRST_PARAM_ACTION, "".join(navs))


STEPS = [
    add_goal_calcs,
    add_title,
    add_tile_y1,
    add_tile_failures,
    add_tile_cumulative,
    add_tile_gradebook,
    add_strips,
    add_cards,
    add_guides,
    add_dashboard,
    add_actions,
]


def main() -> None:
    selftest_drop_filters()
    t = BASE.read_text(encoding="utf-8", newline="")
    if "\r\n" not in t:
        raise RuntimeError("base is not CRLF; stop")
    for step in STEPS:
        before = len(t)
        t = step(t)
        print(f"{step.__name__}: +{len(t) - before} bytes")
    # trunk-ignore(bandit/B314): parse-only well-formedness check on a file we just wrote
    ET.fromstring(t.encode("utf-8"))  # well-formed or raise
    OUT.write_text(t, encoding="utf-8", newline="")
    print(f"wrote {OUT} ({len(t)} chars)")


if __name__ == "__main__":
    main()
