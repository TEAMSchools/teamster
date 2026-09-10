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
def add_goal_calcs(t: str) -> str:
    """Two region-goal variants of the existing goal pair, on the goals source.
    The originals read the org or region goal by p_Region; these read the
    region goal only, so a region row compares against its own goal.

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
    block = crlf(
        """
      <column caption='LP Students still needed (region)' datatype='real' name='[Calculation_7700000000000000001]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='// LP copy of [Students still needed] with the p_Region branch removed&#10;IF [Calculation_9485136151529756033] / [Calculation_4693780698737655073]&#10;   &gt;= AVG([gpa_goal_proportion_region])&#10;THEN 0&#10;ELSE ROUND(AVG([gpa_goal_proportion_region]) * [Calculation_4693780698737655073])&#10;     - [Calculation_9485136151529756033]&#10;END' />
      </column>
      <column caption='LP Gap to goal (region)' datatype='real' name='[Calculation_7700000000000000002]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='// LP copy of [Gap to goal (pts)] with the p_Region branch removed&#10;([Calculation_9485136151529756033] / [Calculation_4693780698737655073]&#10; - AVG([gpa_goal_proportion_region])) * 100' />
      </column>
"""
    )
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
    """Every line the cumulative tile has to borrow, keyed for readability."""
    src = worksheet_block(t, "GPA - BAN Students needed")
    out = {
        "calc": paired_column(src, NEEDED_CALC),
        "inst": one_line(
            src,
            rf"\r\n            <column-instance column='\[{NEEDED_CALC}\]'[^>]*/>",
            "column-instance",
        ),
        "format": one_line(
            src,
            rf"\r\n            <format attr='text-format' field='\[{re.escape(GOAL_DS)}\]\.\[usr:{NEEDED_CALC}:qk\]'[^>]*/>",
            "text-format rule",
        ),
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
    still = f"<run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'><![CDATA[<[{GOAL_DS}].{NEEDED_INST}> students still needed (projected)]]></run>"
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
                + f"\r\n              <text column='[{GOAL_DS}].{NEEDED_INST}' />",
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
    """
    declared = set(re.findall(r"<column(?:-instance)? [^>]*name='\[([^\]]*)\]'", block))
    for formula in re.findall(r"<calculation class='tableau' formula='([^']*)'", block):
        for ref in re.findall(r"\[([A-Za-z_][A-Za-z0-9_ ]*)\]", formula):
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


STEPS = [
    add_goal_calcs,
    add_title,
    add_tile_y1,
    add_tile_failures,
    add_tile_cumulative,
    add_tile_gradebook,
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
