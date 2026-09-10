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
    # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    ds = re.search(
        rf"<datasource caption='[^']*' inline='true' name='{GOAL_DS}'.*?</datasource>",
        t,
        re.S,
    ).group(0)
    for name, cap in (
        ("Calculation_7700000000000000001", "LP Students still needed \\(region\\)"),
        ("Calculation_7700000000000000002", "LP Gap to goal \\(region\\)"),
    ):
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(ds, rf"<column caption='{cap}' [^>]*name='\[{name}\]'") == 1, name
        # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
        assert count(t, rf"\[{name}\]") >= 1
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    assert "gpa_goal_proportion_region" in ds
    # trunk-ignore(bandit/B101): this is a standalone assertion script; the assert IS the check
    # trunk-ignore(pyright/reportOptionalMemberAccess): a miss here is a genuine bug to surface
    assert "Parameter 3" not in re.search(
        r"name='\[Calculation_7700000000000000001\]'.*?</column>", ds, re.S
    ).group(0)


CHECKS = [task3]

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
