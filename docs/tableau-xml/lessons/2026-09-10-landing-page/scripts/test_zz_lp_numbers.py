"""Throwaway (Task 9, 2026-09-10, then deleted from tests/): publish a PROBE copy
of the Landing Page workbook with the tiles, strips and source BANs LIVE, pull
each sheet's CSV, compare the tile numbers against their source BANs, and delete
the probe.

Why a probe: on this server (REST 3.25) `populate_csv` on a DASHBOARD view
returns the first sheet's data only, and the LP sheets are hidden on the review
copy, so they cannot be queried there.

`hidden_views` can only hide MORE views, never reveal one: a window carrying
`hidden='true'` in `<windows>` is not publishable at all, and omitting it from
`hidden_views` does nothing (verified -- the first probe published only the six
dashboards as views). So `repack_probe.py` strips `hidden='true'` from the
thirteen windows we need and writes `probe.twbx`, which is what we publish here.

Retries the whole block up to 3x (5s apart) because concurrent
tableau-mcp-server processes on the same PAT invalidate tableauserverclient
sessions mid-run (401002 at sign-in, NotSignedInError between calls). A publish
in Overwrite mode with the same name into the same project is idempotent.
"""

import csv
import io
import os
import re
import time
from datetime import date
from pathlib import Path

import tableauserverclient as tsc
from tableauserverclient.server.endpoint.exceptions import (
    FailedSignInError,
    NotSignedInError,
    ServerResponseError,
)

OUT = Path("/workspaces/teamster/.claude/scratch/tableau/lp")

#: The user named this project explicitly; do not ask again.
TEMP_PROJECT = "c74d8e08-b856-4430-a759-ebacb061e376"
#: Every id a build may publish to. Production is never added here.
NON_PRODUCTION_PROJECTS = {
    "c74d8e08-b856-4430-a759-ebacb061e376": "GPA-monitor-temp",
}

PROBE_NAME = f"ZZ-REVIEW {date.today():%Y-%m-%d} AGHS landing page PROBE"

DASHBOARDS = [
    "Landing Page",
    "Academic Health Home",
    "Academic Health Schools",
    "Cumulative GPA Monitor",
    "Gradebook School Rollup",
    "Gradebook Teacher View",
]
TILES = [
    "LP - Tile Y1 GPA",
    "LP - Tile Course Failures",
    "LP - Tile Cumulative GPA",
    "LP - Tile Gradebook Health",
]
STRIPS = [
    "LP - Strip Y1 GPA",
    "LP - Strip Course Failures",
    "LP - Strip Cumulative GPA",
    "LP - Strip Gradebook Health",
]
BANS = [
    "Y1 Landing - BAN Network ≥3.0",
    "Y1 Landing - BAN Network Failing ≥2",
    "GPA - BAN % 3.0+",
    "GPA - BAN Students needed",
    "BAN Network",
]
SHEETS = TILES + STRIPS + BANS
KEEP_LIVE = set(DASHBOARDS) | set(SHEETS)

#: (label, tile sheet, tile column, source sheet, source column)
COMPARISONS = [
    (
        "% Y1 GPA at or above 3.0",
        "LP - Tile Y1 GPA",
        "% Y1 GPA at or above 3.0",
        "Y1 Landing - BAN Network ≥3.0",
        "% Y1 GPA at or above 3.0",
    ),
    (
        "% Y1 Failing 2 or more",
        "LP - Tile Course Failures",
        "% Y1 Failing 2 or more",
        "Y1 Landing - BAN Network Failing ≥2",
        "% Y1 Failing 2 or more",
    ),
    (
        "% at 3.0+",
        "LP - Tile Cumulative GPA",
        "% at 3.0+",
        "GPA - BAN % 3.0+",
        "% at 3.0+",
    ),
    (
        "% healthy",
        "LP - Tile Gradebook Health",
        "% healthy",
        "BAN Network",
        "% healthy",
    ),
    (
        "Students still needed",
        "LP - Tile Cumulative GPA",
        "LP Students still needed (org)",
        "GPA - BAN Students needed",
        "Students still needed",
    ),
]

#: Anything matching these in a CSV header is student-level and must not print.
PII_HEADER = re.compile(
    r"student\s*(number|name|id)|first\s*name|last\s*name|\bemail\b|birth",
    re.IGNORECASE,
)


def _server() -> tuple[tsc.Server, tsc.PersonalAccessTokenAuth]:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    return tsc.Server(
        os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True
    ), auth


def _with_retry(server, auth, work, attempts=3, delay=5):
    """Run `work(server)` inside a fresh sign-in block, up to `attempts` times."""
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            with server.auth.sign_in(auth):
                return work(server)
        except FailedSignInError as exc:
            last_exc = exc
        except NotSignedInError as exc:
            last_exc = exc
        except ServerResponseError as exc:
            if getattr(exc, "code", None) != "401002":
                raise
            last_exc = exc
        if i < attempts - 1:
            print(
                f"RETRY {i + 1}/{attempts} after {type(last_exc).__name__}: {last_exc}"
            )
            time.sleep(delay)
    if last_exc is None:
        raise RuntimeError("unreachable: no attempts were made")
    raise last_exc


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _num(text: str) -> float | None:
    """Parse a Tableau CSV cell into a float, or None when it is not numeric."""
    s = (text or "").strip().replace(",", "").replace("$", "").replace("−", "-")
    pct = s.endswith("%")
    if pct:
        s = s[:-1].strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        val = float(s)
    except ValueError:
        return None
    return val / 100 if pct else val


def _pick(header: list[str], wanted: str) -> str | None:
    """Resolve a caption to the CSV header Tableau actually emitted."""
    if wanted in header:
        return wanted

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().casefold()

    target = norm(wanted)
    for h in header:
        if norm(h) == target:
            return h
    for h in header:
        if target in norm(h):
            return h
    return None


def _csv_rows(server: tsc.Server, view: tsc.ViewItem) -> list[dict]:
    opts = tsc.CSVRequestOptions()
    server.views.populate_csv(view, opts)
    text = b"".join(view.csv).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def _publish_probe_and_pull(server: tsc.Server) -> dict:
    out_twb = (OUT / "out.twb").read_text(encoding="utf-8", newline="")
    windows = re.findall(
        r"<window class='(?:worksheet|dashboard)'[^>]*name='([^']*)'", out_twb
    )
    windows = {n.replace("&lt;", "<").replace("&amp;", "&") for n in windows}
    publishable = set(
        re.findall(
            r"<window class='(?:worksheet|dashboard)'(?![^>]*hidden='true')[^>]*name='([^']*)'",
            out_twb,
        )
    )
    publishable = {n.replace("&lt;", "<").replace("&amp;", "&") for n in publishable}
    # repack_probe.py unhid these thirteen in probe.twbx, so they are
    # publishable on the probe even though out.twb still marks them hidden.
    publishable |= set(SHEETS)

    missing = sorted(KEEP_LIVE - windows)
    if missing:
        raise RuntimeError(f"names not present in <windows>: {missing}")

    item = tsc.WorkbookItem(
        project_id=TEMP_PROJECT,
        name=PROBE_NAME,
        show_tabs=True,
    )
    item.hidden_views = sorted(publishable - KEEP_LIVE)
    live_will_be = sorted(KEEP_LIVE)
    print("HIDING", len(item.hidden_views), "sheets:", item.hidden_views)
    print("LIVE will be", live_will_be)
    if live_will_be != sorted(set(DASHBOARDS) | set(SHEETS)) or len(live_will_be) != 19:
        raise RuntimeError(f"LIVE set is not the expected 19 names: {live_will_be}")

    # Gate BEFORE the call. By the time publish returns, the overwrite has
    # already happened on the server.
    if TEMP_PROJECT not in NON_PRODUCTION_PROJECTS:
        raise RuntimeError("target is not an agreed non-production project")
    if not (item.name or "").startswith("ZZ-REVIEW "):
        raise RuntimeError("review copies carry the ZZ-REVIEW prefix")

    # trunk-ignore(pyright/reportCallIssue): false positive, see tsc_session.py note
    item = server.workbooks.publish(
        item, str(OUT / "probe.twbx"), mode=tsc.Server.PublishMode.Overwrite
    )
    if item.project_id != TEMP_PROJECT:
        raise RuntimeError(f"published to {item.project_name}, not the temp project")
    print(f"PUBLISHED: {item.id} into {item.project_name}")

    server.workbooks.populate_views(item)
    by_name = {v.name: v for v in item.views}
    print("PROBE_LIVE_VIEWS", sorted(n for n in by_name if n))

    data: dict[str, list[dict]] = {}
    for name in SHEETS:
        view = by_name.get(name)
        if view is None:
            raise RuntimeError(f"probe has no live view named {name!r}")
        rows = _csv_rows(server, view)
        data[name] = rows
        (OUT / f"csv-{_slug(name)}.txt").write_text(
            "\n".join(",".join(f"{k}={v}" for k, v in r.items()) for r in rows),
            encoding="utf-8",
        )
        header = list(rows[0].keys()) if rows else []
        pii = [h for h in header if PII_HEADER.search(h or "")]
        print(f"\nCSV {name}: {len(rows)} rows")
        if pii:
            print(f"  HEADER WITHHELD: student-level columns present {pii}")
        else:
            print(f"  HEADER {header}")
            for r in rows[:3]:
                print(f"  ROW {r}")

    return {"luid": item.id, "data": data}


def _delete_probe(luid: str):
    def work(server: tsc.Server):
        server.workbooks.delete(luid)
        still = [
            wb.id for wb in tsc.Pager(server.workbooks) if wb.project_id == TEMP_PROJECT
        ]
        return luid not in still

    return work


def test_lp_numbers() -> None:
    server, auth = _server()
    result = _with_retry(server, auth, _publish_probe_and_pull)
    luid = result["luid"]
    data = result["data"]

    lines = ["# Landing page numbers: tiles vs source BANs", ""]
    lines.append(f"Probe: `{PROBE_NAME}` in GPA-monitor-temp, parameters at their")
    lines.append("defaults (`p_Region` = `All`). Values parsed from the view CSV.")
    lines.append("")
    lines.append(
        "| Measure | Tile sheet | Tile value | Source sheet | Source value | Equal |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")

    all_equal = True
    problems: list[str] = []
    for label, tsheet, tcol, ssheet, scol in COMPARISONS:
        trows, srows = data[tsheet], data[ssheet]
        thead = list(trows[0].keys()) if trows else []
        shead = list(srows[0].keys()) if srows else []
        tkey, skey = _pick(thead, tcol), _pick(shead, scol)
        traw = trows[0].get(tkey, "") if (trows and tkey) else None
        sraw = srows[0].get(skey, "") if (srows and skey) else None
        tval, sval = (
            (_num(traw) if traw is not None else None),
            (_num(sraw) if sraw is not None else None),
        )
        if tval is None or sval is None:
            equal = "NO (column not found)"
            all_equal = False
            problems.append(
                f"{label}: tile column {tcol!r} -> {tkey!r} raw={traw!r}; "
                f"source column {scol!r} -> {skey!r} raw={sraw!r}; "
                f"tile header={thead}; source header={shead}"
            )
        elif abs(tval - sval) <= 1e-9:
            equal = "yes"
        else:
            equal = "NO"
            all_equal = False
            problems.append(
                f"{label}: tile {tval!r} (raw {traw!r}) != source {sval!r} "
                f"(raw {sraw!r}); tile header={thead}; source header={shead}"
            )
        lines.append(
            f"| {label} | `{tsheet}` | {traw if traw is not None else 'n/a'} "
            f"({tval}) | `{ssheet}` | {sraw if sraw is not None else 'n/a'} "
            f"({sval}) | {equal} |"
        )
        print(
            f"COMPARE {label}: tile={traw!r}({tval}) source={sraw!r}({sval}) -> {equal}"
        )

    # Strip row sets.
    lines += [
        "",
        "## Region strips",
        "",
        "| Strip sheet | Regions | Values |",
        "| --- | --- | --- |",
    ]
    strip_regions: dict[str, list[str]] = {}
    strip_values: dict[str, dict[str, str]] = {}
    measure_for = {
        "LP - Strip Y1 GPA": "% Y1 GPA at or above 3.0",
        "LP - Strip Course Failures": "% Y1 Failing 2 or more",
        "LP - Strip Cumulative GPA": "% at 3.0+",
        "LP - Strip Gradebook Health": "% healthy",
    }
    for name in STRIPS:
        rows = data[name]
        head = list(rows[0].keys()) if rows else []
        rkey = _pick(head, "Region")
        mkey = _pick(head, measure_for[name])
        regions = (
            sorted({(r.get(rkey) or "").strip() for r in rows if rkey}) if rkey else []
        )
        vals = {
            (r.get(rkey) or "").strip(): (r.get(mkey) or "")
            for r in rows
            if rkey and mkey
        }
        strip_regions[name] = regions
        strip_values[name] = vals
        lines.append(
            f"| `{name}` | {', '.join(regions) or 'n/a'} | "
            + "; ".join(f"{k}={v}" for k, v in sorted(vals.items()))
            + " |"
        )
        print(f"STRIP {name}: regions={regions} values={vals}")

    msh = [
        "LP - Strip Y1 GPA",
        "LP - Strip Course Failures",
        "LP - Strip Gradebook Health",
    ]
    sets = {n: set(strip_regions[n]) for n in msh}
    same = len({frozenset(v) for v in sets.values()}) == 1
    cum = set(strip_regions["LP - Strip Cumulative GPA"])
    base = set(strip_regions[msh[0]])
    lines += [
        "",
        f"- Three MS/HS strips share a region set: {'yes' if same else 'NO'} "
        f"({', '.join(sorted(base)) or 'n/a'})",
        f"- Cumulative strip regions: {', '.join(sorted(cum)) or 'n/a'}; "
        f"strict subset of the other three: {'yes' if cum < base else 'NO'}",
    ]
    print(
        f"STRIP_SETS same_three={same} base={sorted(base)} cum={sorted(cum)} subset={cum < base}"
    )

    (OUT / "numbers.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE {OUT / 'numbers.md'}")

    if not all_equal:
        for p in problems:
            print(f"BLOCKED {p}")
        print(f"PROBE_LEFT {luid}")
        raise AssertionError("tile vs source BAN mismatch; probe left in place")

    try:
        gone = _with_retry(server, auth, _delete_probe(luid))
    except Exception as exc:  # noqa: BLE001 - report and continue, per spec
        print(f"PROBE_LEFT {luid} (delete refused: {exc})")
        return
    if gone:
        print("PROBE_DELETED")
    else:
        print(f"PROBE_LEFT {luid} (still listed after delete)")
