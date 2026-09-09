"""Assert dashboard zone geometry is internally consistent.

Three invariants, none of which any schema check covers:

1. Siblings in a layout-flow do not overlap.
2. A flow container's children sum to the container along the flow axis.
3. The top-level zone spans the full 100000-unit canvas.

Usage: uv run python check_geometry.py <twb> "<dashboard name>" [--baseline <baseline.twb>]

With --baseline: compare parent-minus-children gaps to baseline for matching zones.
For new zones, allow gaps in range [0, 3000].

Without --baseline: allow gaps in range [0, 3000] for all zones.
"""

import sys

# trunk-ignore(bandit/B405): parses workbooks this tool downloaded itself, not untrusted input
import xml.etree.ElementTree as ET


def rect(z):
    return tuple(int(z.get(k, 0)) for k in ("x", "y", "w", "h"))


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _require(node, tag: str, where: str):
    """`find` returns None on a missing element; fail with the reason, not a
    TypeError three frames later."""
    found = node.find(tag)
    if found is None:
        sys.exit(f"malformed workbook: no <{tag}> in {where}")
    return found


def extract_gaps(path, dashboard):
    """Extract parent-minus-children gaps for all flow containers."""
    # trunk-ignore(bandit/B314): see the B405 note at the import
    root = ET.parse(path).getroot()
    dash = next(
        d for d in _require(root, "dashboards", path) if d.get("name") == dashboard
    )
    gaps = {}

    def collect_gaps(z):
        kids = [c for c in z.findall("zone") if not c.get("hidden-by-user")]
        if (
            kids
            and z.get("type-v2") == "layout-flow"
            and z.get("param") in ("vert", "horz")
        ):
            idx = 3 if z.get("param") == "vert" else 2
            total = sum(rect(c)[idx] for c in kids)
            want = rect(z)[idx]
            gaps[z.get("id")] = want - total
        for c in kids:
            collect_gaps(c)

    for z in _require(dash, "zones", dashboard).findall("zone"):
        collect_gaps(z)
    return gaps


def walk(z, path, bad, baseline_gaps=None):
    kids = [c for c in z.findall("zone") if not c.get("hidden-by-user")]
    for i, a in enumerate(kids):
        for b in kids[i + 1 :]:
            if overlaps(rect(a), rect(b)):
                bad.append(
                    f"overlap at {path}: zone {a.get('id')} and zone {b.get('id')}"
                )

    flow = z.get("param")
    if kids and z.get("type-v2") == "layout-flow" and flow in ("vert", "horz"):
        idx = 3 if flow == "vert" else 2
        total = sum(rect(c)[idx] for c in kids)
        want = rect(z)[idx]
        gap = want - total
        zid = z.get("id")

        if baseline_gaps is not None:
            # Baseline mode: compare to baseline
            if zid in baseline_gaps:
                expected_gap = baseline_gaps[zid]
                if gap != expected_gap:
                    bad.append(
                        f"zone {zid} ({flow}) gap is {gap}, expected {expected_gap} (from baseline)"
                    )
            else:
                # New zone not in baseline; use absolute bounds
                if gap < 0 or gap > 3000:
                    bad.append(
                        f"zone {zid} ({flow}) gap is {gap}, expected 0-3000 (new zone)"
                    )
        else:
            # Non-baseline mode: absolute bounds only
            if gap < 0 or gap > 3000:
                bad.append(f"zone {zid} ({flow}) gap is {gap}, expected 0-3000")

    for c in kids:
        walk(c, f"{path}/{z.get('id')}", bad, baseline_gaps)


def main(path, dashboard, baseline_path=None):
    # Load baseline gaps if provided
    baseline_gaps = None
    if baseline_path:
        try:
            baseline_gaps = extract_gaps(baseline_path, dashboard)
        except FileNotFoundError:
            sys.exit(f"baseline file not found: {baseline_path}")
        except StopIteration:
            sys.exit(f"dashboard '{dashboard}' not found in baseline {baseline_path}")

    # Load and parse workbook
    try:
        # trunk-ignore(bandit/B314): see the B405 note at the import
        root = ET.parse(path).getroot()
    except FileNotFoundError:
        sys.exit(f"workbook file not found: {path}")

    try:
        dash = next(
            d for d in _require(root, "dashboards", path) if d.get("name") == dashboard
        )
    except StopIteration:
        sys.exit(f"dashboard '{dashboard}' not found in {path}")

    bad = []
    tops = _require(dash, "zones", dashboard).findall("zone")

    # Check top-level zones pairwise for overlap
    visible_tops = [z for z in tops if not z.get("hidden-by-user")]
    for i, a in enumerate(visible_tops):
        for b in visible_tops[i + 1 :]:
            if overlaps(rect(a), rect(b)):
                bad.append(
                    f"overlap at top-level: zone {a.get('id')} and zone {b.get('id')}"
                )

    # Check each top-level zone
    for z in tops:
        if z.get("hidden-by-user"):
            continue
        x, y, w, h = rect(z)
        if (x, y, w, h) != (0, 0, 100000, 100000) and z.get(
            "type-v2"
        ) == "layout-basic":
            bad.append(f"top-level layout-basic zone {z.get('id')} is {x},{y},{w},{h}")
        walk(z, "", bad, baseline_gaps)

    for line in bad:
        print(f"  FAIL {line}")

    mode = (
        f"with baseline {baseline_path}"
        if baseline_path
        else "without baseline (absolute bounds)"
    )
    print(f"  Mode: {mode}")

    if bad:
        sys.exit(f"{len(bad)} geometry failures in '{dashboard}'")
    print(f"  OK: geometry consistent in '{dashboard}'")


if __name__ == "__main__":
    # Parse arguments
    if len(sys.argv) < 3:
        sys.exit(
            'usage: check_geometry.py <twb> "<dashboard name>" [--baseline <baseline.twb>]'
        )

    path = sys.argv[1]
    dashboard = sys.argv[2]
    baseline_path = None

    # Check for --baseline option
    if len(sys.argv) > 3:
        if sys.argv[3] == "--baseline":
            if len(sys.argv) < 5:
                sys.exit("--baseline requires a path argument")
            baseline_path = sys.argv[4]
            # Check for extra arguments
            if len(sys.argv) > 5:
                sys.exit(f"unrecognized argument: {sys.argv[5]}")
        else:
            sys.exit(f"unrecognized argument: {sys.argv[3]}")

    main(path, dashboard, baseline_path)
