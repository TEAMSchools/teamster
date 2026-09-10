"""assert_lp.py: assertions on out.twb, one function per task, all run every time."""

import re
import sys

OUT = "/workspaces/teamster/.claude/scratch/tableau/lp/out.twb"
GOAL_DS = "federated.0n798br073i5kb170j6l90uiv50a"
GRADES_DS = "federated.1ikycy21f3ow4k1eazzbx1iah2yl"
GB_DS = "federated.16ubt9s0rwp4cw14hwm3e1xmc56p"


def load() -> str:
    return open(OUT, encoding="utf-8", newline="").read()


def count(text: str, pat: str) -> int:
    return len(re.findall(pat, text, flags=re.S))


def task3(t: str) -> None:
    ds = re.search(
        rf"<datasource caption='[^']*' inline='true' name='{GOAL_DS}'.*?</datasource>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    for name, cap in (
        ("Calculation_7700000000000000001", "LP Students still needed \\(region\\)"),
        ("Calculation_7700000000000000002", "LP Gap to goal \\(region\\)"),
        ("Calculation_7700000000000000003", "LP Students still needed \\(org\\)"),
    ):
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(ds, rf"<column caption='{cap}' [^>]*name='\[{name}\]'") == 1, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(t, rf"\[{name}\]") >= 1
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "gpa_goal_proportion_region" in ds
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Parameter 3" not in re.search(
        r"name='\[Calculation_7700000000000000001\]'.*?</column>",
        ds,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # Ruling 10: the org variant reads the org goal only -- no p_Region branch
    # and no region field, so the network tile cannot follow another tab's
    # parameter.
    org = re.search(
        r"name='\[Calculation_7700000000000000003\]'.*?</column>",
        ds,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Parameter 3" not in org
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "gpa_goal_proportion_region" not in org
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "gpa_goal_proportion_org" in org


def task4(t: str) -> None:
    for name in (
        "LP - Title",
        "LP - Tile Y1 GPA",
        "LP - Tile Course Failures",
        "LP - Tile Cumulative GPA",
        "LP - Tile Gradebook Health",
    ):
        ws = re.search(rf"<worksheet name='{re.escape(name)}'>.*?</worksheet>", t, re.S)
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert ws, f"missing worksheet {name}"
        w = ws.group(0)
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "<repository-location" not in w, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "<aggregation value='true' />" in w, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(w, r"<simple-id uuid=") == 1, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert (
            count(
                t, rf"<window class='worksheet' hidden='true' name='{re.escape(name)}'"
            )
            == 1
        ), name
    y1 = re.search(
        r"<worksheet name='LP - Tile Y1 GPA'>.*?</worksheet>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Calculation_4005670422414364681" not in y1  # Region Filter gone
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "[none:hos:nk]" not in y1 and "[none:school_level:nk]" not in y1
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert (
        "<layout-options>" in y1 and "[Parameters].[Parameter 4]" in y1
    )  # MP in title
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "<Data Update Time>" in y1
    gb = re.search(
        r"<worksheet name='LP - Tile Gradebook Health'>.*?</worksheet>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert (
        "[none:region:nk]' filter-group" not in gb
        and "[none:school:nk]' filter-group" not in gb
    )
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "[Parameters].[Parameter 1 1]" in re.search(
        r"<layout-options>.*?</layout-options>",
        gb,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    cum = re.search(
        r"<worksheet name='LP - Tile Cumulative GPA'>.*?</worksheet>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # Ruling 10: the network tile reads the org-goal shortfall, never the
    # p_Region-aware original, whose value would follow another tab's control.
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Calculation_7700000000000000003" in cum
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Calculation_5262281088199017638" not in cum
    # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    title = re.search(r"<worksheet name='LP - Title'>.*?</worksheet>", t, re.S).group(0)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Landing Page" in title and "| Home" not in title
    # every simple-id this build added is fresh and used exactly once. A
    # file-wide uniqueness check cannot be used: 22 sheets in the untouched
    # base already share one uuid between the <worksheet> and its <window>.
    added = []
    for pat in (
        r"<worksheet name='LP - [^']*'>.*?</worksheet>",
        r"<window class='worksheet' hidden='true' name='LP - [^']*'>.*?</window>",
    ):
        for blk in re.findall(pat, t, re.S):
            found = re.findall(r"<simple-id uuid='([^']*)'", blk)
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert len(found) == 1, blk[:60]
            added.append(found[0])
    # 9 LP worksheets (title, 4 tiles, 4 strips), each with its own window
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert len(added) == 18, len(added)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert len(added) == len(set(added)), "duplicate simple-id among the additions"
    for uid in added:
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert t.count(uid) == 1, f"simple-id {uid} reused"


def task5(t: str) -> None:
    for name, ds in (
        ("LP - Strip Y1 GPA", GRADES_DS),
        ("LP - Strip Course Failures", GRADES_DS),
        ("LP - Strip Cumulative GPA", GOAL_DS),
        ("LP - Strip Gradebook Health", GB_DS),
    ):
        ws = re.search(rf"<worksheet name='{re.escape(name)}'>.*?</worksheet>", t, re.S)
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert ws, name
        w = ws.group(0)
        # region on rows, no explicit sort -> Tableau's default ascending order
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert f"<rows>[{ds}].[none:region:nk]</rows>" in w, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "name='[none:region:nk]'" in w, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "name='[region]'" in w, name
        # the strip column has no room for a caption
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "<caption>" not in w, name
        head = re.search(r"<title>.*?</title>", w, re.S)
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert head, name
        # a static header: a parameter token would render but says nothing
        # useful in a one-line strip header
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "[Parameters]." not in head.group(0), name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "<aggregation value='true' />" in w, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "<repository-location" not in w, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(w, r"<simple-id uuid=") == 1, name
        # a two-line label: value, then the delta (or the shortfall) line
        label = re.search(r"<customized-label>.*?</customized-label>", w, re.S)
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert label, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(label.group(0), r"<run>Æ&#10;</run>") == 1, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert (
            count(
                t, rf"<window class='worksheet' hidden='true' name='{re.escape(name)}'"
            )
            == 1
        ), name
    cum = re.search(
        r"<worksheet name='LP - Strip Cumulative GPA'>.*?</worksheet>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # the region-goal variant, not the org one and not the p_Region original
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Calculation_7700000000000000001" in cum
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Calculation_7700000000000000003" not in cum
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Calculation_5262281088199017638" not in cum


CHECKS = [task3, task4, task5]

if __name__ == "__main__":
    text = load()
    failed = 0
    for fn in CHECKS:
        try:
            fn(text)
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
