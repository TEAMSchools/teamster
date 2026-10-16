"""Tableau side of a capture: download, review copy, exports.

Session handling and download ported from 68c59490a5 (proven on the DDI run).
"""

from __future__ import annotations

import contextlib
import csv
import datetime as dt
import io
import os
import re
import time
from pathlib import Path

from . import cells, snapshot, workbook
from .config import ALL, DEFAULT_QUIET

BLANK = "(Blank)"

TEMP_CB = "ddc817c2-6bc7-4bca-8be9-e385f95b9ebc"
#: Projects a review copy may land in. Production is never added here.
NON_PRODUCTION_PROJECTS = {TEMP_CB: "TEMP-CB"}
REVIEW_PREFIX = "ZZ-REVIEW "


class SessionError(RuntimeError):
    """The review copy could not be published, exported or removed safely."""


def retry(fn, attempts: int = 3, sleep=time.sleep, wait: float = 5.0):
    """Call fn until it succeeds; Tableau sign-ins fail transiently with 401002."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - re-raised after the last attempt
            if attempt == attempts:
                raise
            sleep(wait * attempt)
    raise ValueError("retry needs attempts >= 1")


def vf_value(value: str, all_values: list[str]) -> str:
    """A filter value as Tableau's vf takes it: commas separate values."""

    def esc(v: str) -> str:
        return v.replace(",", "\\,")

    if value == ALL:
        return ",".join(esc(v) for v in all_values)
    if value == BLANK:
        return "Null"
    return esc(value)


def pick_click_row(export: bytes, mark: str, dims: list[str] | None) -> dict[str, str]:
    """The dimension values of the mark a person would click: largest or smallest."""
    rows = list(csv.DictReader(io.StringIO(export.decode("utf-8-sig"))))
    if not rows:
        raise SessionError("the source sheet exported no marks to click")
    cols = list(rows[0])
    dims = dims or [
        c for c in cols if not all(workbook.is_number(r[c]) for r in rows if r[c])
    ]
    measure = next((c for c in cols if c not in dims), None)
    if measure is None:
        raise SessionError(
            "the source sheet has no numeric measure column to rank its marks by "
            f"(every column is a dimension: {', '.join(cols)})"
        )
    marks = [r for r in rows if not any(r[d] in ("All", "*") for d in dims)]
    if not marks:
        raise SessionError("every mark on the source sheet is a total")
    ranked = [r for r in marks if workbook.is_number((r[measure] or "").strip())]
    if not ranked:
        raise SessionError(
            f"the source sheet's {measure} is blank or not a number on every mark"
        )

    def value(r: dict) -> float:
        return float(r[measure].strip().replace(",", "").rstrip("%"))

    row = max(ranked, key=value) if mark == "largest" else min(ranked, key=value)
    return {d: cells.norm_value(row[d]) or row[d] for d in dims}


def _workbooks_in(server, project: str) -> list:
    import tableauserverclient as tsc

    return [w for w in tsc.Pager(server.workbooks) if w.project_id == project]


# The tool shares its Tableau token with the scheduled refreshes, and another
# sign-in on it ends this session (401002).
SIGN_IN_WAIT = 60.0  # seconds before signing in again
SIGN_IN_TRIES = 5


@contextlib.contextmanager
def signed_in(server, auth):
    """A Tableau session that does not fail on sign-out: another sign-in on the
    shared token may already have ended it."""
    retry(lambda: server.auth.sign_in(auth), attempts=SIGN_IN_TRIES, wait=20.0)
    try:
        yield
    finally:
        try:
            server.auth.sign_out()
        # trunk-ignore(bandit/B110): the session is already gone
        except Exception:  # noqa: BLE001 - the session is already gone
            pass


class Session:
    def __init__(
        self,
        server,
        project_luid: str,
        now=lambda: dt.datetime.now(dt.UTC),
        auth=None,
        sleep=time.sleep,
        quiet: tuple[int, int] = DEFAULT_QUIET,
    ):
        if project_luid not in NON_PRODUCTION_PROJECTS:
            raise SessionError(
                f"{project_luid} is not an agreed non-production project"
            )
        self.server, self.project, self.now = server, project_luid, now
        # Kept to sign in again: a PAT allows one session, so another sign-in with
        # the same token (a scheduled refresh, the Tableau MCP) ends this one.
        self.auth, self.sleep, self.quiet = auth, sleep, quiet
        self._views: dict = {}

    def call(self, fn):
        """Run a server call. When another sign-in on the shared token ends this
        session (401002), wait, sign in again and retry."""
        for attempt in range(1, SIGN_IN_TRIES + 1):
            try:
                return fn()
            except Exception as e:
                if (
                    "401002" not in str(e)
                    or self.auth is None
                    or attempt == SIGN_IN_TRIES
                ):
                    raise
                self.sleep(SIGN_IN_WAIT)
                try:
                    self.server.auth.sign_in(self.auth)
                # trunk-ignore(bandit/B110): the next attempt retries the sign-in
                except Exception:  # noqa: BLE001 - the next attempt retries the sign-in
                    pass
        raise ValueError("SIGN_IN_TRIES must be >= 1")

    def wait_out_refreshes(self) -> None:
        """Hold exports through the minutes of each hour when the dashboard's
        scheduled refreshes sign in with the same token (tableau_quiet_minutes)."""
        t = self.now()
        start, end = self.quiet
        if start <= t.minute < end:
            self.sleep((end - t.minute) * 60 - t.second)

    def review_copies(self, workbook: str) -> list:
        """This tool's review copies of the workbook still in the review project.
        Matched by the exact name publish gives them; other ZZ-REVIEW copies are
        other work's."""
        mine = re.compile(
            rf"^{re.escape(REVIEW_PREFIX)}\d{{4}}-\d{{2}}-\d{{2}} \d{{4}} {re.escape(workbook)}$"
        )
        return [
            w
            for w in _workbooks_in(self.server, self.project)
            if mine.match(w.name or "")
        ]

    def publish(self, twbx: Path, name: str, hidden: list[str]) -> str:
        import tableauserverclient as tsc

        if not name.startswith(REVIEW_PREFIX):
            raise SessionError(
                f"review copies carry the {REVIEW_PREFIX.strip()} prefix"
            )
        item = tsc.WorkbookItem(project_id=self.project, name=name, show_tabs=True)
        item.hidden_views = hidden
        item = self.server.workbooks.publish(item, str(twbx), mode="CreateNew")
        if item.project_id != self.project:
            raise SessionError(f"published to {item.project_name}, not TEMP-CB")
        self.copy = item
        return item.id

    def attach(self, luid: str) -> None:
        """Reuse a review copy published earlier, when a capture resumes."""
        item = self.call(lambda: self.server.workbooks.get_by_id(luid))
        if item.project_id != self.project:
            raise SessionError(f"{luid} is not in the review project")
        self.copy = item
        self._views = {}

    def export_view(
        self, sheet: str, filters: list[tuple[str, str]], params=()
    ) -> bytes:
        import tableauserverclient as tsc

        if not self._views:
            self.server.workbooks.populate_views(self.copy)
            self._views = {v.name: v for v in self.copy.views}
        view = self._views.get(sheet)
        if view is None:
            raise SessionError(f"the review copy has no view named {sheet}")

        def fetch():
            opts = tsc.CSVRequestOptions()
            for k, v in filters:
                opts = opts.vf(k, v)
            for k, v in params:
                opts = opts.parameter(k, v)
            self.server.views.populate_csv(view, opts)
            return b"".join(view.csv)

        return retry(lambda: self.call(fetch), sleep=self.sleep)


# Tableau reports the server's internal hostname in webpage_url, so the link may
# not open from a browser.
FIND_BY_NAME = (
    "  If the link does not open, find the copy by name in project TEMP-CB "
    "(Explore > TEMP-CB)."
)


def open_guard(session: Session, workbook: str) -> None:
    """Refuse to publish while an earlier review copy is still in the project. The
    tool deletes nothing on Tableau; the analyst deletes each copy by hand."""
    left = session.review_copies(workbook)
    if left:
        listed = "\n".join(f"  {w.name}: {w.webpage_url}" for w in left)
        raise SessionError(
            "delete these review copies in Tableau first, then run close and open "
            f"again:\n{listed}\n{FIND_BY_NAME}"
        )


def server_from_env():
    import tableauserverclient as tsc

    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    return tsc.Server(
        os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True
    ), auth


def download(luid: str, out_dir: Path, server=None) -> tuple[Path, str]:
    """Download a workbook with its extract.

    Args:
        luid: The workbook's LUID.
        out_dir: Where the file goes.
        server: An already signed-in server. Pass it from inside a signed_in
            block: a second sign-in on the shared token ends the first session.
            When omitted, download signs in and out itself.

    Returns:
        The downloaded path and the workbook's updated_at as ISO text.
    """

    def fetch_with(srv):
        at = srv.workbooks.get_by_id(luid).updated_at
        path = srv.workbooks.download(
            luid, filepath=str(out_dir / "live"), include_extract=True
        )
        return Path(path), at.isoformat() if at else ""

    if server is not None:
        return retry(lambda: fetch_with(server))

    own, auth = server_from_env()

    def fetch():
        with signed_in(own, auth):
            return fetch_with(own)

    return retry(fetch)


def review_name(now: dt.datetime, workbook_name: str) -> str:
    return f"{REVIEW_PREFIX}{now:%Y-%m-%d %H%M} {workbook_name}"


def click_targets(wb, dashboards: list[str], source_sheet: str) -> list[str]:
    """The sheets a filter action from source_sheet filters."""
    out: list[str] = []
    for a in wb.actions:
        if (
            a.kind != "filter"
            or a.source_sheet != source_sheet
            or a.dashboard not in dashboards
        ):
            continue
        for s in wb.dashboards.get(a.target, []):
            if s != source_sheet and s not in a.exclude and s not in out:
                out.append(s)
    return out


def capture(checks, snap, session, now: dt.datetime) -> dict:
    """Freeze the Tableau side: extract, review copy, every cut's exports.

    Args:
        checks: The checks file.
        snap: The snapshot; snap.twbx must already be downloaded.
        session: A signed-in Session on the review project.
        now: Used for the review copy's name.

    Returns:
        Manifest additions (see the task's interface list).

    Raises:
        SessionError: The data source has no embedded extract, or an earlier
            review copy is still in TEMP-CB.
    """
    m = snapshot.read_manifest(snap)
    extracts = workbook.unpack_extracts(snap.twbx, snap.dir)
    if checks.datasource not in extracts:
        raise SessionError(
            f"{checks.datasource} has no embedded extract in the workbook; a published "
            "data source would refresh under the review copy, so the snapshot would not hold"
        )
    target = extracts[checks.datasource]["file"]
    (snap.dir / target).rename(snap.extract)
    for info in extracts.values():
        if info["file"] != target:
            (snap.dir / info["file"]).unlink(missing_ok=True)
    text = workbook.twb_text(snap.twbx)
    wb = workbook.read_workbook(text)
    if "review_copy" not in m:
        session.wait_out_refreshes()
        open_guard(session, checks.workbook)
        listed = set(checks.sheets) | {
            c.click.source_sheet for c in checks.cuts if c.click
        }
        twbx, hidden = workbook.build_review_twbx(
            snap.twbx, snap.dir, list(checks.dashboards), listed
        )
        name = review_name(now, checks.workbook)
        session.publish(twbx, name, hidden)
        m["review_copy"] = {
            "name": name,
            "url": getattr(session.copy, "webpage_url", ""),
            "id": session.copy.id,
        }
        snapshot.write_manifest(snap, m)
    else:
        session.attach(m["review_copy"]["id"])
    m["extract_refreshed"] = extracts[checks.datasource]["refreshed"]
    cuts = m.setdefault("cuts", {})
    for cut in checks.cuts:
        if cut.id in cuts:
            continue
        vf = [(k, vf_value(v, [])) for k, v in cut.filters.items() if v != ALL]
        params = list(cut.params.items())
        entry = {
            "vf": vf,
            "params": dict(params),
            "click_filters": {},
            "click_targets": [],
            "sheets": {},
        }
        if cut.click:
            session.wait_out_refreshes()
            src = session.export_view(cut.click.source_sheet, vf, params)
            entry["click_filters"] = pick_click_row(src, cut.click.mark, None)
            entry["click_targets"] = click_targets(
                wb, list(checks.dashboards), cut.click.source_sheet
            )
        for sheet in checks.sheets:
            extra = (
                [(k, vf_value(v, [])) for k, v in entry["click_filters"].items()]
                if sheet in entry["click_targets"]
                else []
            )
            session.wait_out_refreshes()
            data = session.export_view(sheet, vf + extra, params)
            path = snap.export_path(cut.id, sheet)
            path.write_bytes(data)
            entry["sheets"][sheet] = str(path.relative_to(snap.dir))
        cuts[cut.id] = entry
        snapshot.write_manifest(snap, m)
    return m
