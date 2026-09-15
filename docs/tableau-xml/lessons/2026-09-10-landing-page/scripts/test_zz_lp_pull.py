"""Throwaway (ran 2026-09-10, then deleted from tests/): pull the suite
workbook, record its state, unpack the .twb.

Retries sign-in up to 3x (5s apart) because concurrent tableau-mcp-server
processes on the same PAT invalidate tableauserverclient sessions mid-run
(401002 at sign-in, NotSignedInError between calls). Skips the download if a
complete base.twbx/base.twb pair is already on disk.
"""

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
LP.mkdir(parents=True, exist_ok=True)
LUID = "b3c14d67-3130-46ac-82a0-0637a5cc2da5"
PREVIOUS = Path("/workspaces/teamster/.claude/scratch/tableau/landing/aghs.twb")


def _fetch(auth, server, do_download):
    """One fresh sign-in attempt: get_by_id, populate_views, populate_revisions,
    and (only if do_download) download. Returns (wb, revision, view_names, got_path).

    `wb.views` is bound by populate_views() to a lazy fetcher that makes a live
    call on every access (tableauserverclient workbook_item.py), and
    server.auth.sign_in()'s context manager signs out on exit -- so the view
    names must be materialized here, inside the session, not read from `wb`
    later.
    """
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(LUID)
        server.workbooks.populate_views(wb)
        server.workbooks.populate_revisions(wb)
        revision = max(int(r.revision_number) for r in wb.revisions)
        view_names = [v.name for v in wb.views]
        got = None
        if do_download:
            got = Path(
                server.workbooks.download(
                    LUID, filepath=str(LP / "base"), include_extract=True
                )
            )
        return wb, revision, view_names, got


def _fetch_with_retry(auth, server, do_download, attempts=3, delay=5):
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return _fetch(auth, server, do_download)
        except FailedSignInError as exc:
            last_exc = exc
        except NotSignedInError as exc:
            last_exc = exc
        except ServerResponseError as exc:
            if getattr(exc, "code", None) != "401002":
                raise
            last_exc = exc
        if i < attempts - 1:
            time.sleep(delay)
    if last_exc is None:
        raise RuntimeError("unreachable: no attempts were made")
    raise last_exc


def test_pull() -> None:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)

    have_base = (
        (LP / "base.twbx").exists()
        and (LP / "base.twbx").stat().st_size > 20_000_000
        and (LP / "base.twb").exists()
    )
    do_download = not have_base

    wb, revision, view_names, got = _fetch_with_retry(auth, server, do_download)

    if do_download:
        if got is None:
            raise RuntimeError("do_download was True but _fetch returned no path")
        if got != LP / "base.twbx":
            got.replace(LP / "base.twbx")
        if (LP / "base.twbx").stat().st_size < 20_000_000:
            raise RuntimeError("extract missing from download")
        with zipfile.ZipFile(LP / "base.twbx") as z:
            name = next(n for n in z.namelist() if n.endswith(".twb"))
            (LP / "base.twb").write_bytes(z.read(name))

    meta = [
        f"revision={revision}",
        f"updated_at={wb.updated_at}",
        f"show_tabs={wb.show_tabs}",
        f"default_view_id={wb.default_view_id}",
        "live_views=" + "|".join(view_names),
    ]
    (LP / "base-meta.txt").write_text("\n".join(meta) + "\n")
    print("\n".join(meta))

    new = (LP / "base.twb").read_text(encoding="utf-8", newline="")
    old = PREVIOUS.read_text(encoding="utf-8", newline="")
    for label, pat in (
        ("worksheets", r"<worksheet name='([^']*)'"),
        ("dashboards", r"<dashboard [^>]*name='([^']*)'"),
        ("parameters", r"name='(\[Parameter [^\]]*\])'"),
        ("actions", r"<(?:nav-)?action caption='([^']*)'"),
    ):
        a, b = set(re.findall(pat, old)), set(re.findall(pat, new))
        print(f"DIFF {label}: removed={sorted(a - b)} added={sorted(b - a)}")
