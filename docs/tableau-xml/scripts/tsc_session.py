"""Template for the credentialed half of the loop: download, publish, render.

In this repo it runs as a throwaway pytest file, because the autouse fixture in
`tests/conftest.py` loads secrets from 1Password. A plain `uv run python` gets
no credentials, and that failure reads like a missing account rather than a
missing fixture.

    cp tsc_session.py tests/test_zz_tableau.py
    uv run pytest tests/test_zz_tableau.py -s
    rm tests/test_zz_tableau.py

Adapt the credential lines for any other host. Everything below the sign-in is
portable.

One session at a time: the `with server.auth.sign_in(auth)` block IS the session
and releases it on exit, including on an exception. Poll a job with your own
loop and re-sign-in on `401002`; see the skill's references/build-workflow.md.

A publish drops server-side state. Before publishing, set `hidden_views` on the
WorkbookItem (the names to hide: publishable sheets from `<windows>` minus the
target's live views minus sheets this edit added) and record the target's
revision number via `populate_revisions`. Both recipes are in the same file.
"""

import os
import zipfile
from datetime import date
from pathlib import Path

import tableauserverclient as tsc

# This file is copied to tests/test_zz_*.py, so parents[1] is the checkout root
# (main repo or worktree), never a hard-coded main-checkout path.
OUT = Path(__file__).resolve().parents[1] / ".claude" / "scratch" / "tableau" / "server"
OUT.mkdir(parents=True, exist_ok=True)

WORKBOOK_LUID = "REPLACE-ME"
#: Publishing anywhere else is the one unrecoverable mistake available here.
#: Ask the user which non-production project or subproject this build lands in
#: and put that id here AND in the allowlist below.
TEMP_PROJECT = "REPLACE-ME"
#: Every id a build may publish to. GPA-monitor-temp is the fallback when the
#: user names no project. Production is never added here.
NON_PRODUCTION_PROJECTS = {
    "c74d8e08-b856-4430-a759-ebacb061e376": "GPA-monitor-temp",
}


def _server() -> tuple[tsc.Server, tsc.PersonalAccessTokenAuth]:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    return tsc.Server(
        os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True
    ), auth


def test_download() -> None:
    """Pull a fresh base and unpack the .twb beside it."""
    server, auth = _server()
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(WORKBOOK_LUID)
        # Record these. A base that drifted under you is the most expensive
        # rebuild in this workflow.
        print(f"PROJECT: {wb.project_name}")
        print(f"UPDATED: {wb.updated_at}")

        # tableauserverclient APPENDS the extension, so pass the stem and take
        # the path it returns. include_extract=True or you get a stub.
        got = Path(
            server.workbooks.download(
                WORKBOOK_LUID, filepath=str(OUT / "base"), include_extract=True
            )
        )

    twbx = OUT / "base.twbx"
    if got != twbx:
        got.replace(twbx)
    if twbx.stat().st_size < 20_000_000:
        raise RuntimeError(f"extract missing: only {twbx.stat().st_size} bytes")

    with zipfile.ZipFile(twbx) as z:
        name = next(n for n in z.namelist() if n.endswith(".twb"))
        (OUT / "base.twb").write_bytes(z.read(name))
    print(f"TWBX {twbx.stat().st_size} bytes; TWB {(OUT / 'base.twb').stat().st_size}")


def test_publish_and_render() -> None:
    """Publish to the scratch project and render, with the parameter set both ways."""
    server, auth = _server()
    with server.auth.sign_in(auth):
        item = tsc.WorkbookItem(
            project_id=TEMP_PROJECT,
            # Dated so two sessions cannot overwrite each other's review copy.
            name=f"ZZ-REVIEW {date.today():%Y-%m-%d} <describe the build>",
            # Whether True changes a setting the owner chose is unverified;
            # read wb.show_tabs off the download and pass it through if so.
            show_tabs=True,
        )
        # Gate BEFORE the call. By the time publish returns, the overwrite has
        # already happened on the server; the check after the call can only
        # confirm where it landed. Raises, not asserts: asserts are stripped
        # under -O.
        if TEMP_PROJECT not in NON_PRODUCTION_PROJECTS:
            raise RuntimeError("target is not an agreed non-production project")
        if not (item.name or "").startswith("ZZ-REVIEW "):
            raise RuntimeError("review copies carry the ZZ-REVIEW prefix")
        # Pyright reports "No overloads for publish match" here. It is a false
        # positive: the runtime signature types `mode` as `str` and
        # PublishMode.Overwrite is the string 'Overwrite'. Verified from the
        # installed tableauserverclient source, not assumed.
        # trunk-ignore(pyright/reportCallIssue): false positive, see the note above
        item = server.workbooks.publish(
            item, str(OUT / "final.twbx"), mode=tsc.Server.PublishMode.Overwrite
        )
        # Confirms where it landed; the preventive gate is above the call.
        if item.project_id != TEMP_PROJECT:
            raise RuntimeError(
                f"published to {item.project_name}, not the temp project"
            )
        print(f"PUBLISHED: {item.id} into {item.project_name}")

        server.workbooks.populate_views(item)
        view = next(v for v in item.views if v.name == "REPLACE-ME")

        # Render once per parameter value, so a parameter-dependent change is
        # visible both ways. Note this bypasses the domain validation a real
        # click performs -- a render once "proved" an action that was broken.
        for value, slug in (("Value A", "a"), ("Value B", "b")):
            opts = tsc.ImageRequestOptions(
                imageresolution=tsc.ImageRequestOptions.Resolution.High
            )
            opts.parameter("Parameter Caption", value)
            server.views.populate_image(view, opts)
            out = OUT / f"render-{slug}.png"
            out.write_bytes(view.image)
            print(f"RENDERED {value!r}: {out.name} {out.stat().st_size} bytes")
