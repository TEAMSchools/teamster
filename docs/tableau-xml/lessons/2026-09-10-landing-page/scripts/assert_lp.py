"""assert_lp.py: assertions on out.twb, one function per task, all run every time."""

import re
import sys

OUT = "/workspaces/teamster/.claude/scratch/tableau/lp/out.twb"
GOAL_DS = "federated.0n798br073i5kb170j6l90uiv50a"


def load() -> str:
    return open(OUT, encoding="utf-8", newline="").read()


def count(text: str, pat: str) -> int:
    return len(re.findall(pat, text, flags=re.S))


def task3(t: str) -> None:
    ds = re.search(
        rf"<datasource caption='[^']*' inline='true' name='{GOAL_DS}'.*?</datasource>",
        t,
        re.S,
    ).group(0)
    for name, cap in (
        ("Calculation_7700000000000000001", "LP Students still needed \\(region\\)"),
        ("Calculation_7700000000000000002", "LP Gap to goal \\(region\\)"),
    ):
        assert count(ds, rf"<column caption='{cap}' [^>]*name='\[{name}\]'") == 1, name
        assert count(t, rf"\[{name}\]") >= 1
    assert "gpa_goal_proportion_region" in ds
    assert "Parameter 3" not in re.search(
        r"name='\[Calculation_7700000000000000001\]'.*?</column>", ds, re.S
    ).group(0)


def task4(t: str) -> None:
    for name in (
        "LP - Title",
        "LP - Tile Y1 GPA",
        "LP - Tile Course Failures",
        "LP - Tile Cumulative GPA",
        "LP - Tile Gradebook Health",
    ):
        ws = re.search(rf"<worksheet name='{re.escape(name)}'>.*?</worksheet>", t, re.S)
        assert ws, f"missing worksheet {name}"
        w = ws.group(0)
        assert "<repository-location" not in w, name
        assert "<aggregation value='true' />" in w, name
        assert count(w, r"<simple-id uuid=") == 1, name
        assert (
            count(
                t, rf"<window class='worksheet' hidden='true' name='{re.escape(name)}'"
            )
            == 1
        ), name
    y1 = re.search(
        r"<worksheet name='LP - Tile Y1 GPA'>.*?</worksheet>", t, re.S
    ).group(0)
    assert "Calculation_4005670422414364681" not in y1  # Region Filter gone
    assert "[none:hos:nk]" not in y1 and "[none:school_level:nk]" not in y1
    assert (
        "<layout-options>" in y1 and "[Parameters].[Parameter 4]" in y1
    )  # MP in title
    assert "<Data Update Time>" in y1
    gb = re.search(
        r"<worksheet name='LP - Tile Gradebook Health'>.*?</worksheet>", t, re.S
    ).group(0)
    assert (
        "[none:region:nk]' filter-group" not in gb
        and "[none:school:nk]' filter-group" not in gb
    )
    assert "[Parameters].[Parameter 1 1]" in re.search(
        r"<layout-options>.*?</layout-options>", gb, re.S
    ).group(0)
    title = re.search(r"<worksheet name='LP - Title'>.*?</worksheet>", t, re.S).group(0)
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
            assert len(found) == 1, blk[:60]
            added.append(found[0])
    assert len(added) == 10, len(added)
    assert len(added) == len(set(added)), "duplicate simple-id among the additions"
    for uid in added:
        assert t.count(uid) == 1, f"simple-id {uid} reused"


CHECKS = [task3, task4]

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
