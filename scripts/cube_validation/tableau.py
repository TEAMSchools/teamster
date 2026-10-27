"""Prove a workbook formula once: Tableau copy, number formats, exports, proof.

Tableau is written to in one place only: a copy named `ZZ-VALIDATE <workbook>`
in the `TEMP-CB` project, published with Overwrite. Nothing is deleted. The
copy drops the compared measures' number formats so its CSV exports carry raw
values, and `prove` compares those exports with the probe's values at the
sheet's displayed decimals.

XML edits are anchored text surgery, not an ElementTree round trip, so the
copy keeps its bytes and CRLF line endings (see the `tableau-workbook-xml`
skill). The input is a workbook downloaded from the site's own server.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import tableauserverclient as TSC

from .compare import cell_verdict
from .config import Comparison

TEMP_PROJECT = "TEMP-CB"
COPY_PREFIX = "ZZ-VALIDATE "
API_VERSION = "3.25"
ENV_VARS = (
    "TABLEAU_SERVER_ADDRESS",
    "TABLEAU_SITE_ID",
    "TABLEAU_TOKEN_NAME",
    "TABLEAU_PERSONAL_ACCESS_TOKEN",
)
REFRESH_JOB_TYPES = ("refresh_extracts", "increment_extracts")

# `<column\b` would also match `<column-instance`; the hyphen is a word boundary.
_COLUMN_TAG = re.compile(r"<column(?=[\s/>])[^>]*>")
_WORKSHEET = re.compile(r"<worksheet(?=[\s>]).*?</worksheet>", re.DOTALL)
# A format element with its own line: the line break before it goes with it.
_FORMAT_LINE = re.compile(r"(?:\r?\n[ \t]*)?<format(?=[\s/>])[^>]*/>")
_ATTR = re.compile(r"""([\w:.-]+)=(?:'([^']*)'|"([^"]*)")""")
_DEFAULT_FORMAT = re.compile(r"""\s+default-format=(?:'[^']*'|"[^"]*")""")
_THOUSANDS = re.compile(r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_INSTANCE_SUFFIXES = {"nk", "ok", "qk"}


class RefreshMovedError(RuntimeError):
    """An extract refresh started while the exports were being taken, twice."""


# --- workbook XML ------------------------------------------------------------


def _attrs(tag: str) -> dict[str, str]:
    return {m[1]: html.unescape(m[2] or m[3] or "") for m in _ATTR.finditer(tag)}


def _bare(name: str) -> str:
    return name[1:-1] if name.startswith("[") and name.endswith("]") else name


def _field_column(field_ref: str) -> str:
    """Return the column name of a `[datasource].[instance]` reference.

    Parsed from the right, because a greedy derivation prefix swallows an
    all-lowercase column name: `pcto:usr:Calculation_1:qk:2` reads
    `Calculation_1`, `none:region:nk` reads `region`.
    """
    instance = field_ref.rsplit("].[", 1)[-1].lstrip("[").rstrip("]")
    parts = instance.split(":")
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in _INSTANCE_SUFFIXES:
            return parts[i - 1]
    return instance


def _target_columns(root: ET.Element, measures: list[str]) -> set[str]:
    """Resolve measure captions or column names to bare column names."""
    targets: set[str] = set()
    missing = []
    for measure in measures:
        found = {
            _bare(col.get("name") or "")
            for col in root.iter("column")
            if measure
            in (col.get("caption"), col.get("name"), _bare(col.get("name") or ""))
        }
        if not found:
            missing.append(measure)
        targets |= found
    if missing:
        raise ValueError(f"no column with caption or name {', '.join(missing)}")
    return targets


def _is_target_format(attrs: dict[str, str], targets: set[str]) -> bool:
    return (
        attrs.get("attr") == "text-format"
        and _field_column(attrs.get("field", "")) in targets
    )


def drop_number_formats(twb_xml: str, measures: list[str]) -> str:
    """Remove the number formats of some measures, so exports carry raw values.

    Drops `default-format` from every `<column>` defining a named measure (the
    datasource copy and each worksheet's dependency copy) and every
    `text-format` rule on that measure inside a worksheet, table or pane
    style. Other measures and non-number format rules are untouched. Line
    endings are kept: each dropped rule takes its own line with it.

    Args:
        twb_xml: The workbook XML.
        measures: Captions or column names (with or without brackets).

    Returns:
        The edited workbook XML.

    Raises:
        ValueError: A measure names no column, or the edit removed a different
            number of formats than the parsed workbook holds.
    """
    root = ET.fromstring(twb_xml)
    targets = _target_columns(root, measures)

    want_defaults = sum(
        1
        for col in root.iter("column")
        if _bare(col.get("name") or "") in targets
        and col.get("default-format") is not None
    )
    want_rules = sum(
        1
        for ws in root.iter("worksheet")
        for fmt in ws.iter("format")
        if _is_target_format(dict(fmt.attrib), targets)
    )

    dropped_defaults = 0

    def column_tag(m: re.Match) -> str:
        nonlocal dropped_defaults
        tag = m.group(0)
        if _bare(_attrs(tag).get("name", "")) not in targets:
            return tag
        new, n = _DEFAULT_FORMAT.subn("", tag)
        dropped_defaults += n
        return new

    out = _COLUMN_TAG.sub(column_tag, twb_xml)

    dropped_rules = 0

    def format_line(m: re.Match) -> str:
        nonlocal dropped_rules
        if not _is_target_format(_attrs(m.group(0)), targets):
            return m.group(0)
        dropped_rules += 1
        return ""

    out = _WORKSHEET.sub(lambda ws: _FORMAT_LINE.sub(format_line, ws.group(0)), out)

    if (dropped_defaults, dropped_rules) != (want_defaults, want_rules):
        raise ValueError(
            f"dropped {dropped_defaults} column formats and {dropped_rules} "
            f"text-format rules; the workbook holds {want_defaults} and {want_rules}"
        )
    ET.fromstring(out)
    return out


def displayed_decimals(format_string: str) -> int:
    """Return the digits of the compared value a number format displays.

    A percent displays the value times 100, so its fraction digits count 2
    more: `p0.0%` shows 0.912 as 91.2%, 3 digits of the fraction. Only the
    first (positive) section counts. Quoted and backslash-escaped text is
    literal, so `n#,##0"%"` is a whole number, not a percent.

    Args:
        format_string: A Tableau `default-format` or `text-format` value, such
            as `p0.0%`, `n#,##0`, `0.00` or `*+0.0"pp";-0.0"pp"`.

    Returns:
        The number of decimals of the underlying value.

    Raises:
        ValueError: The format is empty.
    """
    if not format_string:
        raise ValueError("empty number format")

    family = format_string[0] if format_string[0] in "npcCe*" else ""
    body = format_string[len(family) :]
    # Literals: "quoted text" and backslash-escaped characters.
    body = re.sub(r'"[^"]*"|\\.', "", body).split(";", 1)[0]

    fraction = 0
    if "." in body:
        fraction = len(re.match(r"[0#?]*", body.split(".", 1)[1]).group(0))
    percent = family == "p" or "%" in body
    return fraction + (2 if percent else 0)


def formula_fingerprint(twb_xml: str, sheet: str) -> str:
    """Fingerprint the workbook logic one sheet's numbers depend on.

    Covers each calculation in the sheet's datasource dependencies (formula
    and table-calculation settings, as canonical XML) and each filter on the
    sheet. Number formats, layout and data are left out, so dropping formats
    for the copy or refreshing an extract keeps the fingerprint, and editing a
    formula or a filter changes it. Relies on Tableau listing every column a
    sheet needs, nested calculations included, in its dependencies.

    Args:
        twb_xml: The workbook XML.
        sheet: The worksheet name.

    Returns:
        A sha256 hex digest.

    Raises:
        ValueError: The workbook has no worksheet of that name.
    """
    root = ET.fromstring(twb_xml)
    ws = next(
        (w for w in root.iter("worksheet") if w.get("name") == sheet),
        None,
    )
    if ws is None:
        raise ValueError(f"the workbook has no worksheet {sheet!r}")

    parts = []
    for deps in ws.iter("datasource-dependencies"):
        for col in deps.findall("column"):
            calc = col.find("calculation")
            if calc is not None:
                parts.append(
                    [
                        "calculation",
                        deps.get("datasource") or "",
                        col.get("name") or "",
                        ET.canonicalize(ET.tostring(calc, encoding="unicode")),
                    ]
                )
    for flt in ws.iter("filter"):
        parts.append(["filter", ET.canonicalize(ET.tostring(flt, encoding="unicode"))])

    return hashlib.sha256(json.dumps(sorted(parts)).encode("utf-8")).hexdigest()


def _parameter_names(twb_xml: str) -> set[str]:
    root = ET.fromstring(twb_xml)
    names: set[str] = set()
    for ds in root.iter("datasource"):
        if ds.get("name") != "Parameters":
            continue
        for col in ds.findall("column"):
            names |= {
                n
                for n in (
                    col.get("caption"),
                    col.get("name"),
                    _bare(col.get("name") or ""),
                )
                if n
            }
    return names


def split_cuts(
    cuts: list[dict[str, Any]], twb_xml: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split cuts into those a REST export can take and those it cannot.

    A cut that sets a workbook parameter is proven in the browser: the server
    rejects parameter values on export here.

    Args:
        cuts: The comparison's cuts, each `{caption: value}`.
        twb_xml: The workbook XML, read for its parameter captions.

    Returns:
        `(exportable, browser)`, each in the order given.
    """
    params = _parameter_names(twb_xml)
    exportable, browser = [], []
    for cut in cuts:
        (browser if params & set(cut) else exportable).append(cut)
    return exportable, browser


# --- the proof ---------------------------------------------------------------


@dataclass(frozen=True)
class Proof:
    """The outcome of proving one comparison's probe against the sheet.

    Attributes:
        fingerprint: `formula_fingerprint` of the sheet the proof covers.
        cells: Cells present on both sides and compared.
        failures: One line per cell that differs or is on one side only.
        proven_at: When the comparison ran.
        browser: Cuts that set a parameter, to prove in the browser.
    """

    fingerprint: str
    cells: int
    failures: list[str]
    proven_at: datetime
    browser: list[dict[str, Any]] = field(default_factory=list)

    @property
    def proven(self) -> bool:
        """True when at least 1 cell was compared and none failed."""
        return self.cells > 0 and not self.failures


def _key_text(value: Any) -> str:
    """Key text that treats 2026, 2026.0 and '2026' alike."""
    if value is None:
        return ""
    text = str(value).strip()
    if _THOUSANDS.fullmatch(text):
        text = text.replace(",", "")
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    return format(number.normalize(), "f") if number.is_finite() else text


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, (int, float)):
        return None if value is None else float(value)
    text = str(value).strip()
    if not text:
        return None
    if "%" in text or any(c.isalpha() and c not in "eE" for c in text):
        raise ValueError(
            f"export value {text!r} still carries a number format; "
            "publish the copy through drop_number_formats"
        )
    if _THOUSANDS.fullmatch(text):
        text = text.replace(",", "")
    return float(text)


def _index(
    rows: list[dict[str, Any]], dims: list[str], side: str, failures: list[str]
) -> tuple[dict[tuple, float | None], dict[tuple, str]]:
    values: dict[tuple, float | None] = {}
    labels: dict[tuple, str] = {}
    for row in rows:
        missing = [d for d in [*dims, "value"] if d not in row]
        if missing:
            raise ValueError(f"{side} row lacks {', '.join(missing)}")
        others = sorted(k for k in row if k != "value")
        key = tuple((k, _key_text(row[k])) for k in others)
        label = ", ".join(f"{k}={row[k]}" for k in others)
        if key in values:
            failures.append(f"{label}: more than 1 {side} row")
            continue
        values[key] = _number(row["value"])
        labels[key] = label
    return values, labels


def prove(
    comparison: Comparison,
    exports: list[dict[str, Any]],
    probe_values: list[dict[str, Any]],
    *,
    twb_xml: str,
    now: datetime | None = None,
) -> Proof:
    """Check that the probe reproduces every exported cell of the sheet.

    Rows on each side are matched on every key except `value`: the
    comparison's dashboard dims, plus any key the caller adds to tell cuts
    apart (such as `cut`). Numeric keys match across types (2026, 2026.0 and
    '2026'). A combination on one side only fails, and so does each matched
    pair that `cell_verdict` does not pass at `comparison.decimals`.

    Args:
        comparison: The comparison; needs `sheet` and `decimals`.
        exports: Export rows mapped to dashboard dim names plus `value`, from
            a copy with the measure's number format dropped.
        probe_values: Probe rows in the same shape, from the dashboard view
            rebuilt as of the refresh the exports read.
        twb_xml: The production workbook XML, for the fingerprint and the
            parameter cuts.
        now: The proof time; defaults to the current UTC time.

    Returns:
        The proof. It is proven only with at least 1 cell and no failures;
        parameter cuts are listed in `browser`, not failed.

    Raises:
        ValueError: `decimals` or `sheet` is unset, a row lacks a dim or
            `value`, or an exported value still carries a number format.
    """
    if comparison.decimals is None:
        raise ValueError(f"comparison {comparison.id!r} has no decimals")
    if not comparison.sheet:
        raise ValueError(f"comparison {comparison.id!r} has no sheet")

    dims = [p.dashboard for p in comparison.dims]
    failures: list[str] = []
    dash, dash_labels = _index(exports, dims, "export", failures)
    probe, probe_labels = _index(probe_values, dims, "probe", failures)

    cells = 0
    for key in sorted(dash.keys() | probe.keys()):
        if key not in probe:
            failures.append(f"{dash_labels[key]}: in the export only")
            continue
        if key not in dash:
            failures.append(f"{probe_labels[key]}: in the probe only")
            continue
        cells += 1
        verdict = cell_verdict(dash[key], probe[key], comparison.decimals)
        if verdict != "pass":
            failures.append(
                f"{dash_labels[key]}: export {dash[key]!r}, probe {probe[key]!r} "
                f"at {comparison.decimals} decimals ({verdict})"
            )
    if not exports:
        failures.append("the export has no rows")

    return Proof(
        fingerprint=formula_fingerprint(twb_xml, comparison.sheet),
        cells=cells,
        failures=failures,
        proven_at=now or datetime.now(timezone.utc),
        browser=split_cuts(comparison.cuts, twb_xml)[1],
    )


# --- Tableau Server ----------------------------------------------------------


def sign_in_from_env() -> TSC.Server:
    """Sign in to Tableau with the personal access token in the environment.

    Reads `TABLEAU_SERVER_ADDRESS`, `TABLEAU_SITE_ID`, `TABLEAU_TOKEN_NAME`
    and `TABLEAU_PERSONAL_ACCESS_TOKEN`; under pytest the secrets fixture in
    `tests/conftest.py` sets them. The caller signs out
    (`server.auth.sign_out()`).

    Returns:
        A signed-in server on REST API 3.25.

    Raises:
        RuntimeError: A variable is unset; the message names the variables,
            never their values.
    """
    missing = [name for name in ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"set {', '.join(missing)} to sign in to Tableau")

    server = TSC.Server(os.environ["TABLEAU_SERVER_ADDRESS"])
    server.version = API_VERSION
    server.auth.sign_in(
        TSC.PersonalAccessTokenAuth(
            token_name=os.environ["TABLEAU_TOKEN_NAME"],
            personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
            site_id=os.environ["TABLEAU_SITE_ID"],
        )
    )
    return server


def _vf_value(value: Any) -> str:
    """A view-filter value: a list is an OR-list, `,` and `\\` escaped."""
    values = value if isinstance(value, (list, tuple)) else [value]
    return ",".join(str(v).replace("\\", "\\\\").replace(",", "\\,") for v in values)


def _packaged_twb(archive: zipfile.ZipFile) -> str:
    names = [n for n in archive.namelist() if n.endswith(".twb") and "/" not in n]
    if len(names) != 1:
        raise ValueError(f"expected 1 workbook in the package, found {len(names)}")
    return names[0]


def _bare_lf(text: str) -> int:
    return text.count("\n") - text.count("\r\n")


@dataclass(frozen=True)
class Snapshot:
    """Exports taken with no extract refresh starting in between.

    Attributes:
        refresh_started: Start of the refresh the exports read; the probe
            runs over the dashboard view rebuilt as of this moment.
        copy_luid: The `TEMP-CB` copy the exports came from.
        exports: One list of CSV rows per cut, in the order given.
    """

    refresh_started: datetime
    copy_luid: str
    exports: list[list[dict[str, str]]]


class Tableau:
    """The Tableau reads and the 1 copy a proof needs.

    Args:
        server: A signed-in `tableauserverclient.Server` (see
            `sign_in_from_env`), or a fake with the same attributes.
    """

    def __init__(self, server: Any) -> None:
        self._server = server

    def download_twb(self, luid: str) -> str:
        """Return a workbook's XML, downloaded without its extract."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(
                self._server.workbooks.download(
                    luid, filepath=str(Path(tmp) / "workbook"), include_extract=False
                )
            )
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    return archive.read(_packaged_twb(archive)).decode("utf-8")
            return path.read_text(encoding="utf-8", newline="")

    def workbook_updated(self, luid: str) -> datetime:
        """Return when a workbook was last published."""
        return self._server.workbooks.get_by_id(luid).updated_at

    def refresh_started(self, workbook_luid: str) -> datetime:
        """Return the start of the latest successful extract refresh.

        Looks at refreshes of the workbook itself and of each published data
        source it connects to, and takes the latest start. Background jobs
        carry names, not ids, so a job is matched on its title.

        Raises:
            LookupError: No successful refresh is on record, as for a workbook
                on a live connection.
        """
        wb = self._server.workbooks.get_by_id(workbook_luid)
        self._server.workbooks.populate_connections(wb)
        titles = {wb.name} | {
            c.datasource_name
            for c in wb.connections
            if c.connection_type == "sqlproxy" and c.datasource_name
        }
        jobs = self._server.jobs.filter(
            status="Success", job_type__in=list(REFRESH_JOB_TYPES)
        )
        starts = [
            job.started_at
            for job in jobs
            if job.title in titles
            and job.status == "Success"
            and job.type in REFRESH_JOB_TYPES
            and job.started_at is not None
        ]
        if not starts:
            raise LookupError(
                f"no completed extract refresh for workbook {wb.name!r} or its "
                "published data sources"
            )
        return max(starts)

    def publish_copy(self, workbook_luid: str, xml_edit: Callable[[str], str]) -> str:
        """Publish an edited copy of a workbook to `TEMP-CB`.

        Downloads the workbook with its extract, applies `xml_edit` to the
        packaged `.twb` and publishes the result as `ZZ-VALIDATE <name>` with
        Overwrite, so a rerun replaces the earlier copy. Every other packaged
        file is copied unchanged. Embedded connection credentials are not
        carried; a copy on a live connection cannot query.

        Args:
            workbook_luid: The production workbook.
            xml_edit: Takes and returns the workbook XML, such as
                `lambda x: drop_number_formats(x, measures)`.

        Returns:
            The copy's luid.

        Raises:
            RuntimeError: `TEMP-CB` is not exactly 1 project, or the copy
                landed elsewhere.
            ValueError: The edit is not well-formed XML or flattened CRLF.
        """
        wb = self._server.workbooks.get_by_id(workbook_luid)
        projects = list(self._server.projects.filter(name=TEMP_PROJECT))
        if len(projects) != 1 or projects[0].name != TEMP_PROJECT:
            raise RuntimeError(
                f"expected 1 project named {TEMP_PROJECT}, found {len(projects)}; "
                "the copy goes nowhere else"
            )
        project = projects[0]
        name = f"{COPY_PREFIX}{wb.name}"

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(
                self._server.workbooks.download(
                    workbook_luid,
                    filepath=str(Path(tmp) / "base"),
                    include_extract=True,
                )
            )
            out = Path(tmp) / f"copy{src.suffix}"
            if zipfile.is_zipfile(src):
                with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
                    twb_name = _packaged_twb(zin)
                    for info in zin.infolist():
                        data = zin.read(info)
                        if info.filename == twb_name:
                            data = _edit(data.decode("utf-8"), xml_edit).encode("utf-8")
                        zout.writestr(info, data)
            else:
                text = src.read_text(encoding="utf-8", newline="")
                out.write_text(_edit(text, xml_edit), encoding="utf-8", newline="")

            # The gate runs before the call: a publish overwrites on arrival.
            if project.name != TEMP_PROJECT or not name.startswith(COPY_PREFIX):
                raise RuntimeError("the copy goes only to TEMP-CB as ZZ-VALIDATE")
            item = TSC.WorkbookItem(project_id=project.id, name=name)
            published = self._server.workbooks.publish(
                item, str(out), mode=TSC.Server.PublishMode.Overwrite
            )

        if published.project_id != project.id:
            raise RuntimeError(f"the copy {name!r} landed outside {TEMP_PROJECT}")
        return published.id

    def export(
        self, copy_luid: str, sheet: str, filters: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Export a sheet of the copy as CSV rows, with view filters applied.

        Args:
            copy_luid: The `TEMP-CB` copy.
            sheet: The worksheet name; a dashboard exports no rows.
            filters: `{field caption: value or list of values}`; a list is an
                OR-list. Parameters are not filters: see `split_cuts`.

        Returns:
            One dict per CSV row, keyed by the export's column headers.

        Raises:
            LookupError: The sheet is not a view on the copy; a sheet hidden
                in the workbook does not publish as a view.
        """
        wb = self._server.workbooks.get_by_id(copy_luid)
        self._server.workbooks.populate_views(wb)
        view = next((v for v in wb.views if v.name == sheet), None)
        if view is None:
            raise LookupError(
                f"no view {sheet!r} on the copy; a hidden sheet is not published"
            )

        opts = TSC.CSVRequestOptions()
        for caption, value in filters.items():
            opts.vf(caption, _vf_value(value))
        self._server.views.populate_csv(view, opts)
        text = b"".join(view.csv).decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text, newline="")))

    def capture(
        self,
        workbook_luid: str,
        sheet: str,
        cuts: list[dict[str, Any]],
        xml_edit: Callable[[str], str],
    ) -> Snapshot:
        """Publish the copy and export each cut inside 1 refresh.

        Reads the refresh start before publishing and again after the last
        export. If it moved, the exports may straddle 2 refreshes: they are
        discarded and taken once more.

        Args:
            workbook_luid: The production workbook.
            sheet: The worksheet to export.
            cuts: Exportable cuts (see `split_cuts`); `{}` is the default
                filter state.
            xml_edit: Passed to `publish_copy`.

        Returns:
            The snapshot.

        Raises:
            RefreshMovedError: A refresh started during both attempts.
        """
        for _ in range(2):
            before = self.refresh_started(workbook_luid)
            copy_luid = self.publish_copy(workbook_luid, xml_edit)
            exports = [self.export(copy_luid, sheet, cut) for cut in cuts]
            if self.refresh_started(workbook_luid) == before:
                return Snapshot(before, copy_luid, exports)
        raise RefreshMovedError(
            "an extract refresh started during the exports twice; retry later"
        )


def _edit(text: str, xml_edit: Callable[[str], str]) -> str:
    """Apply an edit, refusing one that breaks the XML or its line endings."""
    edited = xml_edit(text)
    if _bare_lf(edited) and not _bare_lf(text):
        raise ValueError("the edit changed CRLF line endings to bare LF")
    try:
        ET.fromstring(edited)
    except ET.ParseError as exc:
        raise ValueError(f"the edited workbook is not well-formed XML: {exc}") from exc
    return edited
