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


STEPS = [add_goal_calcs]


def main() -> None:
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
