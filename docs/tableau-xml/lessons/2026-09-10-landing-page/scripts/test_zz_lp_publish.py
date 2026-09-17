"""Throwaway (Task 8, 2026-09-10, then deleted from tests/): repack the edited
Landing Page workbook, publish a ZZ-REVIEW copy to GPA-monitor-temp, and render
its live views.

Retries the whole publish-and-render block up to 3x (5s apart) because
concurrent tableau-mcp-server processes on the same PAT invalidate
tableauserverclient sessions mid-run (401002 at sign-in, NotSignedInError
between calls). A publish in Overwrite mode with the same name into the same
project is idempotent, so retrying after a mid-upload session loss is safe.
"""

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

WORKBOOK_LUID = "b3c14d67-3130-46ac-82a0-0637a5cc2da5"
#: The user named this project explicitly; do not ask again.
TEMP_PROJECT = "c74d8e08-b856-4430-a759-ebacb061e376"
#: Every id a build may publish to. Production is never added here.
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


def _publish_and_render(server: tsc.Server) -> dict:
    out_twb = (OUT / "out.twb").read_text(encoding="utf-8", newline="")
    meta = dict(
        line.split("=", 1) for line in (OUT / "base-meta.txt").read_text().splitlines()
    )
    live = set(meta["live_views"].split("|"))
    publishable = set(
        re.findall(
            r"<window class='(?:worksheet|dashboard)'(?![^>]*hidden='true')[^>]*name='([^']*)'",
            out_twb,
        )
    )
    publishable = {n.replace("&lt;", "<").replace("&amp;", "&") for n in publishable}
    added = {"Landing Page"}

    item = tsc.WorkbookItem(
        project_id=TEMP_PROJECT,
        name=f"ZZ-REVIEW {date.today():%Y-%m-%d} AGHS landing page",
        show_tabs=meta["show_tabs"] == "True",
    )
    item.hidden_views = sorted(publishable - live - added)
    live_will_be = sorted(publishable - set(item.hidden_views))
    print("HIDING", item.hidden_views)
    print("HIDING", len(item.hidden_views), "sheets; LIVE will be", live_will_be)

    expected_live = sorted(live | added)
    if live_will_be != expected_live:
        raise RuntimeError(
            f"LIVE will be {live_will_be} != expected {expected_live}; stopping before publish"
        )

    # Gate BEFORE the call. By the time publish returns, the overwrite has
    # already happened on the server; the check after the call can only
    # confirm where it landed.
    if TEMP_PROJECT not in NON_PRODUCTION_PROJECTS:
        raise RuntimeError("target is not an agreed non-production project")
    if not (item.name or "").startswith("ZZ-REVIEW "):
        raise RuntimeError("review copies carry the ZZ-REVIEW prefix")

    hidden_count = len(item.hidden_views)

    # trunk-ignore(pyright/reportCallIssue): false positive, see tsc_session.py note
    item = server.workbooks.publish(
        item, str(OUT / "final.twbx"), mode=tsc.Server.PublishMode.Overwrite
    )
    # publish() returns a fresh WorkbookItem from the server response; it does
    # not carry hidden_views back (that field is write-only on the request).
    if item.project_id != TEMP_PROJECT:
        raise RuntimeError(f"published to {item.project_name}, not the temp project")
    print(f"PUBLISHED: {item.id} into {item.project_name}")

    server.workbooks.populate_views(item)
    by_name = {v.name: v for v in item.views}

    rendered = 0
    for name in sorted(live | added):
        view = by_name.get(name)
        if view is None:
            print(f"RENDER_FAILED {name} view not found on published item")
            continue
        try:
            opts = tsc.ImageRequestOptions(
                imageresolution=tsc.ImageRequestOptions.Resolution.High
            )
            server.views.populate_image(view, opts)
            out_path = OUT / f"render-{_slug(name)}.png"
            out_path.write_bytes(view.image)
            print(f"RENDERED {name!r}: {out_path.name} {out_path.stat().st_size} bytes")
            rendered += 1
        except Exception as exc:  # noqa: BLE001 - report and continue, per spec
            print(f"RENDER_FAILED {name} {exc}")

    landing_view = by_name.get("Landing Page")
    if landing_view is None:
        print("RENDER_FAILED Landing Page (Q1) view not found on published item")
    else:
        try:
            opts = tsc.ImageRequestOptions(
                imageresolution=tsc.ImageRequestOptions.Resolution.High
            )
            opts.parameter("p_Marking_Period", "Q1")
            server.views.populate_image(landing_view, opts)
            out_path = OUT / "render-landing-q1.png"
            out_path.write_bytes(landing_view.image)
            print(
                f"RENDERED 'Landing Page (Q1)': {out_path.name}"
                f" {out_path.stat().st_size} bytes"
            )
            rendered += 1
        except Exception as exc:  # noqa: BLE001 - report and continue, per spec
            print(f"RENDER_FAILED Landing Page (Q1) {exc}")

    review = server.workbooks.get_by_id(item.id)
    server.workbooks.populate_views(review)
    default_view_name = next(
        (v.name for v in review.views if v.id == review.default_view_id), None
    )
    print(f"DEFAULT_VIEW {default_view_name}")
    print("LIVE_VIEWS", sorted(v.name for v in review.views if v.name))

    return {
        "review_luid": item.id,
        "review_url": item.webpage_url,
        "review_name": item.name,
        "production_revision": meta["revision"],
        "default_view": default_view_name,
        "live_views": sorted(live | added),
        "hidden_count": hidden_count,
        "rendered": rendered,
    }


def test_publish_and_render() -> None:
    server, auth = _server()
    result = _with_retry(server, auth, _publish_and_render)

    meta_lines = [
        f"review_luid={result['review_luid']}",
        f"review_url={result['review_url']}",
        f"review_name={result['review_name']}",
        f"production_revision={result['production_revision']}",
        f"default_view={result['default_view']}",
        "live_views=" + "|".join(result["live_views"]),
        f"hidden_count={result['hidden_count']}",
    ]
    (OUT / "review-meta.txt").write_text("\n".join(meta_lines) + "\n")
    print("\n".join(meta_lines))

    # trunk-ignore(bandit/B101): a throwaway pytest assertion, not shipped code
    assert result["default_view"] is not None
    # trunk-ignore(bandit/B101): a throwaway pytest assertion, not shipped code
    assert result["rendered"] >= 6
