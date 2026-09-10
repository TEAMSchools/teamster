"""check_additive.py: prove an edit only ADDED things.

Strips every addition the edit is allowed to make, then requires the remainder
to be byte-identical to the base. Text surgery, not ElementTree, so an
unmutated file round-trips byte-exact.

    uv run python check_additive.py edited.twb base.twb \
        --sheet-prefix "LP - " --dashboard "Landing Page" \
        --calc-prefix Calculation_77 --action-prefix LP_
"""

import argparse
import difflib
import re
import sys


def strip_elements(text: str, pattern: str) -> tuple[str, int]:
    """Remove whole elements matching a regex; the regex must consume the
    element from its leading indentation through its trailing newline."""
    new, n = re.subn(pattern, "", text, flags=re.S)
    return new, n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("edited")
    p.add_argument("base")
    p.add_argument("--sheet-prefix", required=True)
    p.add_argument("--dashboard", required=True)
    p.add_argument("--calc-prefix", required=True)
    p.add_argument("--action-prefix", required=True)
    a = p.parse_args()

    edited = open(a.edited, encoding="utf-8", newline="").read()
    base = open(a.base, encoding="utf-8", newline="").read()
    sp = re.escape(a.sheet_prefix)
    db = re.escape(a.dashboard)
    cp = re.escape(a.calc_prefix)
    ap = re.escape(a.action_prefix)

    removed = {}
    # order matters only for readability; each pattern is independent
    patterns = {
        "worksheets": rf"[ \t]*<worksheet name='{sp}[^']*'>.*?</worksheet>\r?\n",
        "dashboard": rf"[ \t]*<dashboard [^>]*name='{db}'>.*?</dashboard>\r?\n",
        "dashboard-window": rf"[ \t]*<window class='dashboard'[^>]*name='{db}'[^>]*>.*?</window>\r?\n",
        "sheet-windows": rf"[ \t]*<window class='worksheet'[^>]*name='{sp}[^']*'[^>]*>.*?</window>\r?\n",
        "nav-actions": rf"[ \t]*<nav-action [^>]*name='\[{ap}[^\]]*\]'>.*?</nav-action>\r?\n",
        "url-actions": rf"[ \t]*<action [^>]*name='\[{ap}[^\]]*\]'>.*?</action>\r?\n",
        "calcs": rf"[ \t]*<column [^>]*name='\[{cp}\d+\]'[^>]*>.*?</column>\r?\n",
    }
    for label, pat in patterns.items():
        edited, n = strip_elements(edited, pat)
        removed[label] = n

    # the one sanctioned edit to an existing element: the default-view marker
    # moves between dashboard windows. Normalize it out on both sides, and
    # require that the edited file still has exactly one.
    if (
        edited.count(" maximized='true'") not in (0, 1)
        or base.count(" maximized='true'") != 1
    ):
        print("FAIL: expected exactly one maximized window in each file")
        return 1
    edited = edited.replace(" maximized='true'", "")
    base = base.replace(" maximized='true'", "")

    print("stripped:", removed)
    if edited == base:
        print("OK: remainder is byte-identical to base")
        return 0
    diff = difflib.unified_diff(
        base.splitlines(keepends=True),
        edited.splitlines(keepends=True),
        "base",
        "edited-minus-additions",
        n=2,
    )
    out = list(diff)
    print(f"FAIL: {len(out)} diff lines; first 60:")
    sys.stdout.writelines(out[:60])
    return 1


if __name__ == "__main__":
    sys.exit(main())
