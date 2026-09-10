"""Throwaway (2026-09-10, delete after use): re-pull the production suite
workbook as a NEW base after the owner made further fixes, and diff it against
the archived revision-25 base.

Same 401002 / NotSignedInError retry as test_zz_lp_pull.py: concurrent
tableau-mcp-server processes share the PAT and invalidate a tableauserverclient
session mid-run. Never run concurrently with another Tableau script.

Unlike the original pull this ALWAYS downloads: the whole point is to replace
a base that is known stale.
"""

import hashlib
import os
import re
import time
import zipfile
from pathlib import Path

import tableauserverclient as tsc
from tableauserverclient.server.endpoint.exceptions import (
    FailedSignInError,
    NotSignedInError,
    ServerResponseError,
)

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
PREVIOUS = LP / "rev25" / "base.twb"
LUID = "b3c14d67-3130-46ac-82a0-0637a5cc2da5"

# The ten sheets build_lp.py clones from, plus the dashboards it anchors on.
CLONE_SOURCES = [
    "Y1 Landing - BAN Network ≥3.0",
    "Y1 Landing - BAN Network Failing ≥2",
    "GPA - BAN % 3.0+",
    "GPA - BAN Students needed",
    "BAN Network",
    "Y1 Landing - Title",
    "Links - GPA Roster - Newark",
    "Links - GPA Roster - Camden",
    "Links - GPA Roster - Paterson",
]


def _fetch(auth, server):
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(LUID)
        server.workbooks.populate_views(wb)
        server.workbooks.populate_revisions(wb)
        revision = max(int(r.revision_number) for r in wb.revisions)
        view_names = [v.name for v in wb.views]
        got = Path(
            server.workbooks.download(
                LUID, filepath=str(LP / "base"), include_extract=True
            )
        )
        return wb, revision, view_names, got


def _fetch_with_retry(auth, server, attempts=3, delay=5):
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return _fetch(auth, server)
        except (FailedSignInError, NotSignedInError) as exc:
            last_exc = exc
        except ServerResponseError as exc:
            if getattr(exc, "code", None) != "401002":
                raise
            last_exc = exc
        if i < attempts - 1:
            print(f"retry {i + 1}: {type(last_exc).__name__}")
            time.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _worksheet_blocks(text: str) -> dict[str, str]:
    return {
        m.group(1): m.group(0)
        for m in re.finditer(r"<worksheet name='([^']*)'>.*?</worksheet>", text, re.S)
    }


def test_repull() -> None:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)

    wb, revision, view_names, got = _fetch_with_retry(auth, server)

    if got != LP / "base.twbx":
        got.replace(LP / "base.twbx")
    size = (LP / "base.twbx").stat().st_size
    if size < 20_000_000:
        raise RuntimeError(f"extract missing from download ({size} bytes)")
    with zipfile.ZipFile(LP / "base.twbx") as z:
        name = next(n for n in z.namelist() if n.endswith(".twb"))
        (LP / "base.twb").write_bytes(z.read(name))

    meta = [
        f"revision={revision}",
        f"updated_at={wb.updated_at}",
        f"show_tabs={wb.show_tabs}",
        f"default_view_id={wb.default_view_id}",
        f"twbx_bytes={size}",
        "live_views=" + "|".join(view_names),
    ]
    (LP / "base-meta.txt").write_text("\n".join(meta) + "\n")
    print("=== NEW BASE ===")
    print("\n".join(meta))

    new = (LP / "base.twb").read_text(encoding="utf-8", newline="")
    old = PREVIOUS.read_text(encoding="utf-8", newline="")
    print(f"twb chars: old={len(old)} new={len(new)}")

    print("=== INVENTORY DIFF vs revision 25 ===")
    for label, pat in (
        ("worksheets", r"<worksheet name='([^']*)'"),
        ("dashboards", r"<dashboard [^>]*name='([^']*)'"),
        ("parameters", r"name='(\[Parameter [^\]]*\])'"),
        ("actions", r"<(?:nav-)?action caption='([^']*)'"),
        ("calcs", r"name='\[(Calculation_\d+)\]'"),
    ):
        a, b = set(re.findall(pat, old)), set(re.findall(pat, new))
        print(f"DIFF {label}: removed={sorted(a - b)} added={sorted(b - a)}")

    print("=== CLONE-SOURCE SHEETS: byte-identical? ===")
    ob, nb = _worksheet_blocks(old), _worksheet_blocks(new)
    for sheet in CLONE_SOURCES:
        o, n = ob.get(sheet), nb.get(sheet)
        if o is None or n is None:
            print(f"  {sheet!r}: MISSING old={o is not None} new={n is not None}")
        elif o == n:
            print(f"  {sheet!r}: identical ({len(n)} chars)")
        else:
            oh = hashlib.sha256(o.encode()).hexdigest()[:12]
            nh = hashlib.sha256(n.encode()).hexdigest()[:12]
            print(f"  {sheet!r}: CHANGED {len(o)}->{len(n)} chars  {oh} -> {nh}")

    print("=== ALL CHANGED WORKSHEETS ===")
    changed = [k for k in sorted(set(ob) & set(nb)) if ob[k] != nb[k]]
    print(f"{len(changed)} of {len(set(ob) & set(nb))} common sheets changed")
    for k in changed:
        print(f"  {k!r}: {len(ob[k])} -> {len(nb[k])}")

    print("=== LP LEAKAGE CHECK (must be empty) ===")
    print(
        f"  'LP - ' sheets in new base: {sorted(k for k in nb if k.startswith('LP - '))}"
    )
    print(f"  Calculation_77 in new base: {len(re.findall('Calculation_77', new))}")
    print(f"  'Landing Page' dashboard:   {"<dashboard name='Landing Page'" in new}")
