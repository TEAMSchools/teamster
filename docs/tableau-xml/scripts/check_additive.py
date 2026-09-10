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

MARKER = " maximized='true'"


def strip_elements(text: str, pattern: str) -> tuple[str, int]:
    """Remove whole elements matching a regex; the regex must consume the
    element from its leading indentation through its trailing newline."""
    new, n = re.subn(pattern, "", text, flags=re.S)
    return new, n


def maximized_windows(text: str) -> list[str]:
    """Names of the <window> elements whose opening tag carries the marker."""
    names = []
    for tag in re.findall(r"<window [^>]*>", text):
        if MARKER in tag:
            m = re.search(r"name='([^']*)'", tag)
            names.append(m.group(1) if m else "<unnamed window>")
    return names


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

    # the one sanctioned edit to an existing element is the default-view
    # marker, which moves between dashboard windows. Check it BEFORE any
    # stripping: the "dashboard-window" pattern below removes the window that
    # is supposed to carry it, so after the strip a file whose marker was
    # deleted outright and a file whose marker sits on some other dashboard
    # both look indistinguishable from a correct one.
    edited_max = maximized_windows(edited)
    base_max = maximized_windows(base)
    target_window = re.search(
        rf"<window class='dashboard'[^>]*name='{db}'[^>]*>", edited
    )
    if (
        edited.count(MARKER) != 1
        or base.count(MARKER) != 1
        or target_window is None
        or MARKER not in target_window.group(0)
    ):
        print(
            "FAIL: default-view marker. Expected exactly one maximized window "
            f"in each file, the edited one on '{a.dashboard}'. "
            f"edited: {edited.count(MARKER)} on {edited_max}; "
            f"base: {base.count(MARKER)} on {base_max}."
        )
        return 1

    removed = {}
    # The patterns are order-independent. "calcs" in particular does not depend
    # on "worksheets" having run first: a worksheet's own
    # datasource-dependencies carry the same calc name as a SELF-CLOSING
    # <column .../> reference (12-space indent here), and calcs is scoped to
    # the datasource-level definition instead — six-space indent at the start
    # of a line, and an opening tag that must NOT be self-closing ([^/>]
    # immediately before the closing '>') — so a reference column can never
    # satisfy it, stripped or not.
    patterns = {
        "worksheets": rf"[ \t]*<worksheet name='{sp}[^']*'>.*?</worksheet>\r?\n",
        # requires name to be the LAST attribute on the opening tag; if it is
        # not, this misses loudly (stripped count 0, plus a diff), not silently
        "dashboard": rf"[ \t]*<dashboard [^>]*name='{db}'>.*?</dashboard>\r?\n",
        "dashboard-window": rf"[ \t]*<window class='dashboard'[^>]*name='{db}'[^>]*>.*?</window>\r?\n",
        "sheet-windows": rf"[ \t]*<window class='worksheet'[^>]*name='{sp}[^']*'[^>]*>.*?</window>\r?\n",
        "nav-actions": rf"[ \t]*<nav-action [^>]*name='\[{ap}[^\]]*\]'>.*?</nav-action>\r?\n",
        "url-actions": rf"[ \t]*<action [^>]*name='\[{ap}[^\]]*\]'>.*?</action>\r?\n",
        "calcs": rf"(?<=\n)      <column [^>]*name='\[{cp}\d+\]'[^>]*[^/>]>.*?</column>\r?\n",
    }
    for label, pat in patterns.items():
        edited, n = strip_elements(edited, pat)
        removed[label] = n

    # the marker was checked above; normalize it out on both sides so the
    # remainder can be compared byte for byte.
    edited = edited.replace(MARKER, "")
    base = base.replace(MARKER, "")

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
