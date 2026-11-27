"""Assert dashboard zone geometry is internally consistent.

Three invariants, none of which any schema check covers:

1. Visible siblings do not overlap, including at top level.
2. A flow container's parent-minus-children gap matches the baseline's.
3. The top-level layout-basic zone spans the full 100000-unit canvas.

Usage:
    uv run python check_geometry.py <twb> "<dashboard>" [--baseline <base.twb>] [--show <zone-id>]

--baseline makes checks 1 and 2 differential. A gap must equal the same
container's gap in the baseline; a container the baseline lacks gets the
absolute 0-3000 bound. An overlap the baseline also has is reported as
"also in baseline" and not counted: floating zones overlap the tiled root by
design. Without --baseline every gap gets the absolute bound and every overlap
fails.

Hidden zones are skipped, so a pass says nothing about a pop-out a show/hide
button opens. --show un-hides one zone and every zone inside it, in both files,
before checking. Name the pop-out's outermost hidden container; one per run.
"""

import argparse
import sys

# trunk-ignore(bandit/B405): parses workbooks this tool downloaded itself, not untrusted input
import xml.etree.ElementTree as ET

ABSOLUTE_GAP = (0, 3000)


def rect(z):
    return tuple(int(z.get(k, 0)) for k in ("x", "y", "w", "h"))


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def visible(zones):
    return [z for z in zones if not z.get("hidden-by-user")]


def _require(node, tag: str, where: str):
    """`find` returns None on a missing element; fail with the reason, not a
    TypeError three frames later."""
    found = node.find(tag)
    if found is None:
        sys.exit(f"malformed workbook: no <{tag}> in {where}")
    return found


def load_zones(path, dashboard, role):
    """The dashboard's default-layout <zones>, never its <devicelayouts> copy."""
    try:
        # trunk-ignore(bandit/B314): see the B405 note at the import
        root = ET.parse(path).getroot()
    except FileNotFoundError:
        sys.exit(f"{role} file not found: {path}")
    for d in _require(root, "dashboards", path):
        if d.get("name") == dashboard:
            return _require(d, "zones", dashboard)
    sys.exit(f"dashboard '{dashboard}' not found in {role} {path}")


def show(zones, zid, where):
    """Strip hidden-by-user from zone `zid` and its subtree. False if absent.

    Tableau marks every zone inside a hidden pop-out, not only the container,
    so un-hiding one zone under a hidden ancestor would change nothing.
    """
    parent = {c: p for p in zones.iter() for c in p}
    target = next((z for z in zones.iter("zone") if z.get("id") == zid), None)
    if target is None:
        return False
    up = parent.get(target)
    while up is not None and up is not zones:
        if up.get("hidden-by-user"):
            sys.exit(
                f"zone {zid} sits inside hidden zone {up.get('id')} in {where}; "
                f"pass --show {up.get('id')}"
            )
        up = parent.get(up)
    for z in target.iter("zone"):
        z.attrib.pop("hidden-by-user", None)
    return True


def survey(zones):
    """Overlap lines, {zone id: (flow, gap)} and top-level layout failures."""
    found, gaps, layout = [], {}, []

    def pairs(kids, where):
        for i, a in enumerate(kids):
            for b in kids[i + 1 :]:
                if overlaps(rect(a), rect(b)):
                    found.append(
                        f"overlap at {where}: zone {a.get('id')} and zone {b.get('id')}"
                    )

    def walk(z, path):
        here = f"{path}/{z.get('id')}"
        kids = visible(z.findall("zone"))
        pairs(kids, here)
        flow = z.get("param")
        if kids and z.get("type-v2") == "layout-flow" and flow in ("vert", "horz"):
            idx = 3 if flow == "vert" else 2
            gaps[z.get("id")] = (flow, rect(z)[idx] - sum(rect(c)[idx] for c in kids))
        for c in kids:
            walk(c, here)

    tops = visible(zones.findall("zone"))
    pairs(tops, "top-level")
    for z in tops:
        x, y, w, h = rect(z)
        if z.get("type-v2") == "layout-basic" and (x, y, w, h) != (
            0,
            0,
            100000,
            100000,
        ):
            layout.append(
                f"top-level layout-basic zone {z.get('id')} is {x},{y},{w},{h}"
            )
        walk(z, "")
    return found, gaps, layout


def gap_failures(gaps, base_gaps):
    lo, hi = ABSOLUTE_GAP
    bad = []
    for zid, (flow, gap) in gaps.items():
        if base_gaps is not None and zid in base_gaps:
            want = base_gaps[zid][1]
            if gap != want:
                bad.append(
                    f"zone {zid} ({flow}) gap is {gap}, expected {want} (from baseline)"
                )
        elif not lo <= gap <= hi:
            note = " (new zone)" if base_gaps is not None else ""
            bad.append(f"zone {zid} ({flow}) gap is {gap}, expected {lo}-{hi}{note}")
    return bad


def main(path, dashboard, baseline_path=None, show_id=None):
    zones = load_zones(path, dashboard, "workbook")
    if show_id and not show(zones, show_id, path):
        sys.exit(f"zone {show_id} not found in '{dashboard}' in {path}")
    found, gaps, bad = survey(zones)

    base_found, base_gaps = set(), None
    if baseline_path:
        base = load_zones(baseline_path, dashboard, "baseline")
        if show_id and not show(base, show_id, baseline_path):
            print(f"  zone {show_id} is not in the baseline; its zones count as new")
        base_list, base_gaps, _ = survey(base)
        base_found = set(base_list)

    known = [line for line in found if line in base_found]
    bad += [line for line in found if line not in base_found]
    bad += gap_failures(gaps, base_gaps)

    for line in bad:
        print(f"  FAIL {line}")
    for line in known:
        print(f"  also in baseline: {line}")

    mode = (
        f"with baseline {baseline_path}"
        if baseline_path
        else "without baseline (absolute bounds)"
    )
    if show_id:
        mode += f", showing zone {show_id}"
    print(f"  Mode: {mode}")
    if known:
        print(f"  {len(known)} overlap(s) also in the baseline, not counted")

    if bad:
        sys.exit(f"{len(bad)} geometry failures in '{dashboard}'")
    print(f"  OK: geometry consistent in '{dashboard}'")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Assert dashboard zone geometry is internally consistent."
    )
    ap.add_argument("twb")
    ap.add_argument("dashboard")
    ap.add_argument("--baseline", metavar="BASE_TWB")
    ap.add_argument(
        "--show",
        metavar="ZONE_ID",
        help="un-hide this zone and its subtree in both files before checking",
    )
    a = ap.parse_args()
    main(a.twb, a.dashboard, a.baseline, a.show)
