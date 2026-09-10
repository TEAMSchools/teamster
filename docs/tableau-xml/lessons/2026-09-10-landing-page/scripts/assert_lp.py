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
    # 19 LP worksheets (title, 4 tiles, 4 strips, 5 cards, 5 guides), each
    # with its own window
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert len(added) == 38, len(added)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert len(added) == len(set(added)), "duplicate simple-id among the additions"
    for uid in added:
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert t.count(uid) == 1, f"simple-id {uid} reused"


def task5(t: str) -> None:
    # the cumulative strip keeps the tile's Grade filter, so Ruling 11 puts
    # [Parameter 10] in its header; the other three headers stay static
    for name, ds, param_title in (
        ("LP - Strip Y1 GPA", GRADES_DS, False),
        ("LP - Strip Course Failures", GRADES_DS, False),
        ("LP - Strip Cumulative GPA", GOAL_DS, True),
        ("LP - Strip Gradebook Health", GB_DS, False),
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
        if param_title:
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert "[Parameters].[Parameter 10]" in head.group(0), name
            # the token only resolves if the sheet declares the parameter
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert "name='[Parameter 10]'" in w, name
        else:
            # a static header: a parameter token says nothing useful in a
            # one-line strip header
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
        # the row band is roughly 43px; 12pt over 8pt fits, 16pt over 10pt
        # does not, and a culled label on a Text mark leaves the cell blank
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(label.group(0), r"fontsize='12'") == 1, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(label.group(0), r"fontsize='8'") == 1, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(label.group(0), r"fontsize='(?:16|10)'") == 0, name
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
    gb = re.search(
        r"<worksheet name='LP - Strip Gradebook Health'>.*?</worksheet>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # Ruling 12: the sheet paints #001e62 on element='table', which now sits
    # behind the region row headers as well as the pane
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert (
        count(
            gb,
            r"<style-rule element='header'>\s*<format attr='color' value='#ffffff' />",
        )
        == 1
    )


CARDS = ["Home", "Schools", "Monitor", "Rollup", "Teacher"]
#: the tab each directory card points at, as the underlined first run reads
CARD_TABS = {
    "Home": "Academic Health Home",
    "Schools": "Academic Health Schools",
    "Monitor": "Cumulative GPA Monitor",
    "Rollup": "Gradebook School Rollup",
    "Teacher": "Gradebook Teacher View",
}
#: the two tabs whose card says so because the tab shows student names
CARD_NAMES = {"Schools", "Monitor"}


def task6(t: str) -> None:
    for c in CARDS:
        blocks = {}
        for kind in ("Card", "Guide"):
            name = f"LP - {kind} {c}"
            ws = re.search(
                rf"<worksheet name='{re.escape(name)}'>.*?</worksheet>", t, re.S
            )
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert ws, f"missing worksheet {name}"
            w = ws.group(0)
            blocks[kind] = w
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert "<filter " not in w, f"{name} carries a filter"
            label = re.search(r"<customized-label>.*?</customized-label>", w, re.S)
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert label, f"{name} has no mark label"
            # a parameter token never resolves inside a mark label
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert "[Parameters]" not in label.group(0), name
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert "<repository-location" not in w, name
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert count(w, r"<simple-id uuid=") == 1, name
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert (
                count(
                    t,
                    rf"<window class='worksheet' hidden='true' name='{re.escape(name)}'",
                )
                == 1
            ), name
            # Ruling 13: a culled label vanishes rather than clipping, and a
            # card label is about ten lines, so culling is off everywhere.
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert count(w, r"<format attr='mark-labels-cull' value='false' />") == 1, (
                name
            )
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert count(w, r"<format attr='mark-labels-cull' value='true' />") == 0, (
                name
            )
            # Ruling 13: multi-line body copy is left-aligned, never centred
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert (
                count(
                    w,
                    r"<style-rule element='cell'>\s*<format attr='text-align' value='left' />",
                )
                == 1
            ), name
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert count(w, r"<format attr='text-align' value='center' />") == 0, name
        card = blocks["Card"]
        # no title, no caption: the dashboard zone frames the card
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "<layout-options>" not in card, c
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert f">{CARD_TABS[c]}</run>" in card, c
        for field in ("Grain: ", "Scope: ", "Built for: "):
            # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
            assert f">{field}</run>" in card, f"{c} {field}"
        card_label = re.search(
            r"<customized-label>.*?</customized-label>",
            card,
            re.S,
            # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
        ).group(0)
        # 5 line breaks, 6 when the card carries the student-names warning
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(card_label, r"<run>Æ&#10;</run>") == (
            6 if c in CARD_NAMES else 5
        ), c
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert ("Shows student names" in card) == (c in CARD_NAMES), c
        g = blocks["Guide"]
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "Help guide: coming soon" in g, c
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "underline='true'" not in g, c
        # the placeholder has nothing to say on hover
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert "<customized-tooltip>" not in g, c
        # the goals source went with the cross-source school filter
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert GOAL_DS not in g, c
        # exactly one slice survives: the workbook-wide [Exclude ES] set
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert (
            count(
                g,
                rf"<slices>\s*<column>\[{re.escape(GRADES_DS)}\]\.\[Exclude ES\]</column>\s*</slices>",
            )
            == 1
        ), c
    schools = re.search(
        r"<worksheet name='LP - Card Schools'>.*?</worksheet>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Shows student names" in schools
    home = re.search(
        r"<worksheet name='LP - Card Home'>.*?</worksheet>",
        t,
        re.S,
        # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ).group(0)
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "Shows student names" not in home


CHECKS = [task3, task4, task5, task6]

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
