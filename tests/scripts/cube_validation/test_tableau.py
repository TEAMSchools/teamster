import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.discover import sheet_shape

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.tableau import (
    RefreshMovedError,
    Tableau,
    displayed_decimals,
    drop_number_formats,
    expose_sheet,
    formula_fingerprint,
    prove,
    set_shelves,
    split_cuts,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sheet_formats.twb"
T0 = datetime(2026, 10, 22, 20, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)


def _twb(crlf: bool = False) -> str:
    text = FIXTURE.read_text(encoding="utf-8", newline="")
    return text.replace("\n", "\r\n") if crlf else text


def _formats(xml: str) -> dict[str, list[str]]:
    """Return default-format per column name and text-format per field."""
    root = ET.fromstring(xml)
    out: dict[str, list[str]] = {}
    for col in root.iter("column"):
        if col.get("default-format") is not None:
            out.setdefault(col.get("name") or "", []).append(col.get("default-format"))
    for ws in root.iter("worksheet"):
        for fmt in ws.iter("format"):
            if fmt.get("attr") == "text-format":
                out.setdefault(fmt.get("field") or "", []).append(fmt.get("value"))
    return out


def test_drop_number_formats_removes_only_named_measures():
    src = _twb(crlf=True)
    out = drop_number_formats(src, ["Rate"])

    before, after = _formats(src), _formats(out)
    # Rate loses its column format (datasource and dependency copies) and every
    # text-format rule on it, including the table-calc instance in the pane.
    assert before["[Calculation_1001]"] == ["p0.0%", "p0.0%"]
    assert "[Calculation_1001]" not in after
    assert "[federated.0sample].[usr:Calculation_1001:qk]" not in after
    assert "[federated.0sample].[pcto:usr:Calculation_1001:qk:2]" not in after
    # Count is untouched.
    assert after["[Calculation_1002]"] == ["n#,##0", "n#,##0"]
    assert after["[federated.0sample].[usr:Calculation_1002:qk]"] == ["n#,##0"]
    # A non-number format on the dropped measure survives.
    assert "attr='width' field='[federated.0sample].[usr:Calculation_1001:qk]'" in out
    # Line endings stay CRLF. 2 format lines go, and the pane's mark rule,
    # emptied by the edit, goes with its 2 lines; its <style> stays.
    assert out.count("\n") == out.count("\r\n")
    assert src.count("\r\n") - out.count("\r\n") == 4
    root = ET.fromstring(out)
    rules = [r.get("element") for r in root.iter("style-rule")]
    assert rules == ["cell"]
    assert all(len(r) for r in root.iter("style-rule"))
    assert root.find(".//pane/style") is not None
    assert out.count("default-format=") == src.count("default-format=") - 2


def test_drop_number_formats_by_column_name_and_unknown_measure():
    out = drop_number_formats(_twb(), ["Calculation_1002"])
    assert "[Calculation_1002]" not in _formats(out)
    assert _formats(out)["[Calculation_1001]"] == ["p0.0%", "p0.0%"]

    with pytest.raises(ValueError, match="Rat"):
        drop_number_formats(_twb(), ["Rat"])


def test_expose_sheet_unhides_only_that_worksheet_window():
    src = _twb(crlf=True).replace(
        "<window class='worksheet' name='Rate by Region'>",
        "<window class='worksheet' hidden='true' name='Rate by Region'>\r\n"
        "    </window>\r\n"
        "    <window class='worksheet' hidden='true' name='Other'>",
    )

    out = expose_sheet(src, "Rate by Region")

    assert "<window class='worksheet' name='Rate by Region'>" in out
    assert "<window class='worksheet' hidden='true' name='Other'>" in out
    assert out.count("\r\n") == src.count("\r\n")
    # An already visible sheet, or a name with no window, is left as is.
    assert expose_sheet(out, "Rate by Region") == out
    assert expose_sheet(out, "Missing") == out


def test_expose_sheet_refuses_a_duplicate_window():
    src = _twb().replace(
        "<window class='worksheet' name='Rate by Region'>",
        "<window class='worksheet' name='Rate by Region'></window>"
        "<window class='worksheet' hidden='true' name='Rate by Region'>",
    )
    with pytest.raises(ValueError, match="2 worksheet windows"):
        expose_sheet(src, "Rate by Region")


def test_displayed_decimals_cases():
    assert displayed_decimals("p0.0%") == 3
    assert displayed_decimals("p0%") == 2
    assert displayed_decimals("n#,##0") == 0
    assert displayed_decimals("0.00") == 2
    assert displayed_decimals('n#,##0"%";-#,##0"%"') == 0
    assert displayed_decimals('*+0.0"pp";-0.0"pp";0.0"pp"') == 1
    assert displayed_decimals("0.0%") == 3
    assert displayed_decimals(r"0.0\%") == 1
    with pytest.raises(ValueError):
        displayed_decimals("")


def _comparison(**kw) -> Comparison:
    base = dict(
        id="rate-region",
        measure="avg_daily_attendance",
        workbook="wb-luid",
        sheet="Rate by Region",
        decimals=3,
        dims=[ColumnPair("region", "regions_region_name")],
    )
    base.update(kw)
    return Comparison(**base)


def _rows(values: dict[str, float | None]) -> list[dict]:
    return [{"region": k, "value": v} for k, v in values.items()]


def test_prove_fails_on_one_mismatch():
    exports = _rows({"North": "0.9123", "South": "0.8504", "East": "0.7001"})
    probe = _rows({"North": 0.91249, "South": 0.85, "East": 0.7012})

    proof = prove(_comparison(), exports, probe, twb_xml=_twb(), now=NOW)

    assert proof.cells == 3
    assert len(proof.failures) == 1
    assert "region=East" in proof.failures[0]
    assert not proof.proven
    assert proof.proven_at == NOW
    assert proof.fingerprint == formula_fingerprint(_twb(), "Rate by Region")


def test_prove_passes_when_all_cells_round_equal():
    exports = _rows({"North": "0.9123", "South": "0.8504"})
    probe = _rows({"North": 0.91249, "South": 0.85})

    proof = prove(_comparison(), exports, probe, twb_xml=_twb(), now=NOW)

    assert proof.failures == []
    assert proof.proven
    assert proof.cells == 2


def test_prove_one_sided_and_empty_exports_fail():
    exports = _rows({"North": "0.9", "South": "0.8"})
    probe = _rows({"North": 0.9, "West": 0.8})
    proof = prove(_comparison(), exports, probe, twb_xml=_twb(), now=NOW)
    assert proof.cells == 1
    assert any("region=South" in f and "export only" in f for f in proof.failures)
    assert any("region=West" in f and "probe only" in f for f in proof.failures)

    empty = prove(_comparison(), [], [], twb_xml=_twb(), now=NOW)
    assert not empty.proven and empty.cells == 0


def test_prove_matches_numeric_dims_across_types_and_cut_keys():
    comparison = _comparison(dims=[ColumnPair("academic_year", "dates_academic_year")])
    exports = [
        {"cut": "0", "academic_year": "2026", "value": "0.5"},
        {"cut": "1", "academic_year": "2026", "value": "0.6"},
    ]
    probe = [
        {"cut": "1", "academic_year": 2026, "value": 0.6},
        {"cut": "0", "academic_year": 2026.0, "value": 0.5},
    ]
    proof = prove(comparison, exports, probe, twb_xml=_twb(), now=NOW)
    assert proof.proven and proof.cells == 2


def test_prove_refuses_formatted_values_and_missing_decimals():
    with pytest.raises(ValueError, match="number format"):
        prove(
            _comparison(),
            _rows({"North": "91.2%"}),
            _rows({"North": 0.912}),
            twb_xml=_twb(),
        )
    with pytest.raises(ValueError, match="decimals"):
        prove(_comparison(decimals=None), [], [], twb_xml=_twb())


def test_parameter_cuts_go_to_the_browser_list():
    cuts = [{}, {"Region": "South"}, {"Basis": "Year end"}]
    exportable, browser = split_cuts(cuts, _twb())
    assert exportable == [{}, {"Region": "South"}]
    assert browser == [{"Basis": "Year end"}]

    proof = prove(
        _comparison(cuts=cuts),
        _rows({"North": "0.9"}),
        _rows({"North": 0.9}),
        twb_xml=_twb(),
        now=NOW,
    )
    assert proof.browser == [{"Basis": "Year end"}]


def test_fingerprint_follows_formulas_and_filters_not_formats():
    base = formula_fingerprint(_twb(), "Rate by Region")
    assert (
        formula_fingerprint(drop_number_formats(_twb(), ["Rate"]), "Rate by Region")
        == base
    )

    changed = _twb().replace("COUNTD([row_key])", "COUNT([row_key])")
    assert formula_fingerprint(changed, "Rate by Region") != base

    refiltered = _twb().replace("&quot;North&quot;' user", "&quot;South&quot;' user")
    assert formula_fingerprint(refiltered, "Rate by Region") != base

    with pytest.raises(ValueError, match="Missing"):
        formula_fingerprint(_twb(), "Missing")


# --- Tableau, against a fake server -----------------------------------------


class FakeQuery(list):
    pass


class FakeServer:
    """The tableauserverclient surface `Tableau` uses, recording every call."""

    def __init__(self, twb: str, jobs=None, projects=None, connections=None):
        self.twb = twb
        self.jobs_seq = list(jobs or [[]])
        self.job_details = {j.id: j for batch in self.jobs_seq for j in batch}
        self.job_error: Exception | None = None
        self.calls: list[tuple] = []
        self.published: list[tuple] = []
        self.csv = b"\xef\xbb\xbfRegion,Rate\r\nNorth,0.9123\r\nSouth,0.85\r\n"
        self._projects = (
            projects
            if projects is not None
            else [SimpleNamespace(id="proj-temp", name="TEMP-CB")]
        )
        self._connections = connections or []

        server = self
        source_wb = SimpleNamespace(
            id="wb-luid",
            name="Sample Dashboard",
            updated_at=T0,
            project_id="proj-prod",
        )

        class Workbooks:
            def get_by_id(self, luid):
                server.calls.append(("get_by_id", luid))
                return (
                    source_wb
                    if luid == "wb-luid"
                    else SimpleNamespace(
                        id=luid, name="ZZ-VALIDATE Sample Dashboard", views=[]
                    )
                )

            def download(self, luid, filepath=None, include_extract=True):
                server.calls.append(("download", luid, include_extract))
                path = Path(f"{filepath}.twbx")
                with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr("Sample Dashboard.twb", server.twb.encode("utf-8"))
                    z.writestr("Data/Extracts/sample.hyper", b"HYPER")
                return str(path)

            def populate_connections(self, wb):
                wb.connections = server._connections

            def populate_views(self, wb):
                wb.views = [
                    SimpleNamespace(id="view-1", name="Rate by Region"),
                    SimpleNamespace(id="view-2", name="Other"),
                ]

            def publish(self, item, file, mode):
                with zipfile.ZipFile(file) as z:
                    contents = {n: z.read(n) for n in z.namelist()}
                server.published.append((item, contents, mode))
                return SimpleNamespace(
                    id="copy-luid", project_id=item.project_id, name=item.name
                )

        class Projects:
            def filter(self, **kw):
                server.calls.append(("projects.filter", kw))
                return FakeQuery(
                    p for p in server._projects if p.name == kw.get("name")
                )

        class Jobs:
            def filter(self, **kw):
                server.calls.append(("jobs.filter", kw))
                seq = server.jobs_seq
                batch = seq.pop(0) if len(seq) > 1 else seq[0]
                # The live server parses only the ISO form with a Z.
                since = datetime.strptime(
                    kw["started_at__gte"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                return FakeQuery(j for j in batch if j.started_at >= since)

            def get_by_id(self, job_id):
                server.calls.append(("jobs.get_by_id", job_id))
                if server.job_error is not None:
                    raise server.job_error
                job = server.job_details[job_id]
                return SimpleNamespace(
                    id=job.id,
                    workbook_id=job.wb,
                    datasource_id=job.ds,
                    started_at=job.started_at,
                )

        class Views:
            def populate_csv(self, view, opts):
                server.calls.append(
                    ("populate_csv", view.name, list(opts.view_filters))
                )
                view.csv = iter([server.csv[:10], server.csv[10:]])

        self.workbooks = Workbooks()
        self.projects = Projects()
        self.jobs = Jobs()
        self.views = Views()


_JOB_IDS = iter(range(10**6))


def _job(
    label,
    started,
    status="Success",
    job_type="refresh_extracts",
    wb="wb-luid",
    ds=None,
):
    """A job-list item as the live server returns it: no title or subtitle.

    `label` only names the item for a reader. `wb` and `ds` are what
    `jobs.get_by_id` reports; an embedded extract sets `wb` only.
    """
    return SimpleNamespace(
        id=f"job-{next(_JOB_IDS)}",
        title=None,
        subtitle=None,
        started_at=started,
        status=status,
        type=job_type,
        wb=wb,
        ds=ds,
    )


def _tab(server):
    return Tableau(server, now=lambda: NOW)


SQLPROXY = SimpleNamespace(
    connection_type="sqlproxy", datasource_name="Sample Rows", datasource_id="ds-luid"
)


def test_refresh_started_takes_latest_of_workbook_and_published_source():
    jobs = [
        _job("Sample Dashboard", T0),
        _job("Sample Rows", T0 + timedelta(hours=1), wb=None, ds="ds-luid"),
        _job("Unrelated", T0 + timedelta(hours=5), wb="other"),
        _job("Sample Rows", T0 + timedelta(hours=3), status="Failed", ds="ds-luid"),
        _job("Sample Dashboard", T0 + timedelta(hours=4), job_type="publish_workbook"),
    ]
    conns = [
        SQLPROXY,
        SimpleNamespace(
            connection_type="bigquery", datasource_name="Embedded", datasource_id="e"
        ),
    ]
    tab = _tab(FakeServer(_twb(), jobs=[jobs], connections=conns))
    assert tab.refresh_started("wb-luid") == T0 + timedelta(hours=1)

    with pytest.raises(LookupError, match="no completed extract refresh"):
        _tab(FakeServer(_twb(), jobs=[[]])).refresh_started("wb-luid")


def test_refresh_started_ignores_other_workbooks_and_sources():
    later = T0 + timedelta(hours=6)
    jobs = [
        _job("Sample Dashboard", T0),
        # Later refreshes of another workbook and another published source,
        # same names or not: only the ids tell them apart.
        _job("Sample Dashboard", later, wb="other-wb"),
        _job("Sample Rows", later, wb=None, ds="other-ds"),
    ]
    server = FakeServer(_twb(), jobs=[jobs], connections=[SQLPROXY])
    assert _tab(server).refresh_started("wb-luid") == T0
    # Newest first, stopping at the first confirmed job.
    looked_up = [c[1] for c in server.calls if c[0] == "jobs.get_by_id"]
    assert looked_up == [jobs[1].id, jobs[2].id, jobs[0].id]


def test_refresh_job_query_is_bounded_to_the_lookback():
    old = _job("Sample Dashboard", NOW - timedelta(days=9))
    server = FakeServer(_twb(), jobs=[[old]])
    with pytest.raises(LookupError, match="since"):
        _tab(server).refresh_started("wb-luid")
    kw = next(c[1] for c in server.calls if c[0] == "jobs.filter")
    assert kw["started_at__gte"] == "2026-10-19T15:00:00Z"
    assert kw["job_type__in"] == ["refresh_extracts", "increment_extracts"]
    assert kw["status"] == "Success"
    assert not any(c[0] == "jobs.get_by_id" for c in server.calls)


def test_refresh_bound_is_utc_whatever_the_clock_zone():
    eastern = timezone(timedelta(hours=-4))
    server = FakeServer(_twb(), jobs=[[_job("Sample Dashboard", T0)]])
    tab = Tableau(server, now=lambda: NOW.astimezone(eastern))
    assert tab.refresh_started("wb-luid") == T0
    kw = next(c[1] for c in server.calls if c[0] == "jobs.filter")
    assert kw["started_at__gte"] == "2026-10-19T15:00:00Z"


def test_refresh_lookup_error_propagates():
    server = FakeServer(_twb(), jobs=[[_job("Sample Dashboard", T0)]])
    server.job_error = RuntimeError("400031")
    with pytest.raises(RuntimeError, match="400031"):
        _tab(server).refresh_started("wb-luid")


def test_refresh_lookups_stop_at_the_cap():
    others = [
        _job("Other", T0 + timedelta(minutes=m), wb="other-wb") for m in range(1, 202)
    ]
    target = _job("Sample Dashboard", T0)
    server = FakeServer(_twb(), jobs=[[target, *others]])
    with pytest.raises(LookupError, match="Sample Dashboard.*cap"):
        _tab(server).refresh_started("wb-luid")
    lookups = [c[1] for c in server.calls if c[0] == "jobs.get_by_id"]
    assert len(lookups) == 200
    assert target.id not in lookups

    # Within the cap, the target is found after the newer jobs of others.
    server = FakeServer(_twb(), jobs=[[target, *others[:199]]])
    assert _tab(server).refresh_started("wb-luid") == T0
    assert sum(1 for c in server.calls if c[0] == "jobs.get_by_id") == 200


def test_download_twb_reads_the_packaged_workbook_without_extract():
    server = FakeServer(_twb(crlf=True))
    text = Tableau(server).download_twb("wb-luid")
    assert text == _twb(crlf=True)
    assert ("download", "wb-luid", False) in server.calls
    assert Tableau(server).workbook_updated("wb-luid") == T0


def test_publish_copy_goes_only_to_temp_cb_with_prefix():
    server = FakeServer(_twb(crlf=True))
    copy = Tableau(server).publish_copy(
        "wb-luid", lambda xml: drop_number_formats(xml, ["Rate"])
    )

    assert copy == "copy-luid"
    item, contents, mode = server.published[0]
    assert item.project_id == "proj-temp"
    assert item.name == "ZZ-VALIDATE Sample Dashboard"
    assert mode == "Overwrite"
    assert ("download", "wb-luid", True) in server.calls
    packed = contents["Sample Dashboard.twb"].decode("utf-8")
    assert packed == drop_number_formats(_twb(crlf=True), ["Rate"])
    assert contents["Data/Extracts/sample.hyper"] == b"HYPER"


def test_publish_copy_refuses_without_a_single_temp_cb_project():
    for projects in ([], [SimpleNamespace(id="a", name="TEMP-CB")] * 2):
        server = FakeServer(_twb(), projects=projects)
        with pytest.raises(RuntimeError, match="TEMP-CB"):
            Tableau(server).publish_copy("wb-luid", lambda xml: xml)
        assert server.published == []


def test_publish_copy_refuses_an_edit_that_flattens_crlf():
    server = FakeServer(_twb(crlf=True))
    with pytest.raises(ValueError, match="line ending"):
        Tableau(server).publish_copy("wb-luid", lambda xml: xml.replace("\r\n", "\n"))
    assert server.published == []


def test_export_applies_view_filters_and_parses_csv():
    server = FakeServer(_twb())
    rows = Tableau(server).export(
        "copy-luid", "Rate by Region", {"Region": ["North", "So,uth"], "Year": 2026}
    )
    assert rows == [
        {"Region": "North", "Rate": "0.9123"},
        {"Region": "South", "Rate": "0.85"},
    ]
    assert (
        "populate_csv",
        "Rate by Region",
        [("Region", "North,So\\,uth"), ("Year", "2026")],
    ) in server.calls

    with pytest.raises(LookupError, match="Missing"):
        Tableau(server).export("copy-luid", "Missing", {})


def test_refresh_moved_triggers_retry():
    t1, t2 = T0, T0 + timedelta(hours=1)
    jobs = [
        [_job("Sample Dashboard", t1)],  # before, attempt 1
        [_job("Sample Dashboard", t2)],  # after, attempt 1: moved
        [_job("Sample Dashboard", t2)],  # before, attempt 2
        [_job("Sample Dashboard", t2)],  # after, attempt 2: stable
    ]
    server = FakeServer(_twb(), jobs=jobs)
    snap = _tab(server).capture(
        "wb-luid", "Rate by Region", [{}, {"Region": "South"}], lambda xml: xml
    )

    assert snap.refresh_started == t2
    assert snap.copy_luid == "copy-luid"
    assert len(snap.exports) == 2
    assert len(server.published) == 2
    assert sum(1 for c in server.calls if c[0] == "populate_csv") == 4


def test_refresh_moving_twice_raises():
    jobs = [[_job("Sample Dashboard", T0 + timedelta(hours=h))] for h in range(4)]
    server = FakeServer(_twb(), jobs=jobs)
    with pytest.raises(RefreshMovedError):
        _tab(server).capture("wb-luid", "Rate by Region", [{}], lambda xml: xml)
    assert len(server.published) == 2


def test_later_unrelated_refresh_does_not_hide_a_real_one():
    t1, t2 = T0, T0 + timedelta(hours=1)
    unrelated = _job("Sample Dashboard", T0 + timedelta(hours=5), wb="other-wb")
    jobs = [
        [unrelated, _job("Sample Dashboard", t1)],  # before, attempt 1
        [unrelated, _job("Sample Dashboard", t2)],  # after, attempt 1: moved
        [unrelated, _job("Sample Dashboard", t2)],  # before, attempt 2
        [unrelated, _job("Sample Dashboard", t2)],  # after, attempt 2: stable
    ]
    server = FakeServer(_twb(), jobs=jobs)
    snap = _tab(server).capture("wb-luid", "Rate by Region", [{}], lambda xml: xml)
    assert snap.refresh_started == t2
    assert len(server.published) == 2


def test_sign_in_from_env_names_missing_vars_without_values(monkeypatch):
    # trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
    from cube_validation.tableau import sign_in_from_env

    for name in (
        "TABLEAU_SERVER_ADDRESS",
        "TABLEAU_SITE_ID",
        "TABLEAU_TOKEN_NAME",
        "TABLEAU_PERSONAL_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TABLEAU_SITE_ID", "site-value")

    with pytest.raises(RuntimeError) as err:
        sign_in_from_env()
    msg = str(err.value)
    assert "TABLEAU_PERSONAL_ACCESS_TOKEN" in msg and "TABLEAU_SITE_ID" not in msg
    assert "site-value" not in msg


def test_csv_bom_is_stripped():
    server = FakeServer(_twb())
    server.csv = b"\xef\xbb\xbfA\r\n1\r\n"
    assert Tableau(server).export("copy-luid", "Rate by Region", {}) == [{"A": "1"}]


# --- parameters on the proof copy ----------------------------------------------

PARAM_TWB = (Path(__file__).parent / "fixtures" / "sheet_formats.twb").read_text()


def test_set_parameters_sets_the_current_value_and_formula():
    from cube_validation.tableau import set_parameters

    edited = set_parameters(PARAM_TWB, {"Basis": "Year end"})
    column = re.search(r"<column[^>]*name='\[Parameter 1\]'[^>]*>", edited)[0]
    assert "value='&quot;Year end&quot;'" in column
    assert "formula='&quot;Year end&quot;'" in edited
    assert edited.count("&quot;Today&quot;") == 1  # only the member list keeps it


def test_set_parameters_refuses_a_value_off_the_list():
    from cube_validation.tableau import set_parameters

    with pytest.raises(ValueError, match="Today, Year end"):
        set_parameters(PARAM_TWB, {"Basis": "Tomorrow"})
    with pytest.raises(ValueError, match="no parameter 'Nope'.*Basis"):
        set_parameters(PARAM_TWB, {"Nope": "x"})


def test_sign_out_returns_a_sign_in_error_instead_of_raising():
    from cube_validation.tableau import Tableau
    from tableauserverclient.server.endpoint.exceptions import FailedSignInError

    class Server:
        class auth:  # noqa: N801
            @staticmethod
            def sign_out():
                raise FailedSignInError("401002", "Unauthorized Access", "")

    assert "401002" in (Tableau(Server()).sign_out() or "")


# --- shelves on the proof copy ---------------------------------------------------

SHELVES_TWB = (Path(__file__).parent / "fixtures" / "shelves.twb").read_text()
RESHAPE = {
    "drop": ["Week Start Monday", "Grade/Subject"],
    "add": {"rows": ["Grade Level", "Subject Area"]},
}


def _worksheets(xml: str) -> dict[str, str]:
    return {
        m[1]: m[0]
        for m in re.finditer(r"<worksheet name='([^']*)'>.*?</worksheet>", xml, re.S)
    }


def test_set_shelves_reshapes_one_sheet_only():
    for src in (SHELVES_TWB, SHELVES_TWB.replace("\n", "\r\n")):
        out = set_shelves(src, "Mastery Grid", RESHAPE)

        ET.fromstring(out)
        shape = sheet_shape(out, "Mastery Grid")
        assert shape.rows == ["Grade Level", "Subject Area"]
        assert shape.cols == ["Module Code", "School"]
        assert (
            "<rows onTop='true'>([federated.0ddi (copy)].[none:grade_level:ok] / "
            in out
        )
        before, after = _worksheets(src), _worksheets(out)
        assert after["Mastery by Week"] == before["Mastery by Week"]
        assert out.replace(after["Mastery Grid"], "") == src.replace(
            before["Mastery Grid"], ""
        )
        # Subject Area was not on the sheet: its column and the instance the
        # workbook already uses join the sheet's dependencies, line endings kept.
        grid = after["Mastery Grid"]
        assert grid.count("name='[subject_area]'") == 1
        assert grid.count("name='[none:subject_area:nk]'") == 1
        assert ("\r\n" in src) == ("\r\n" in grid) and "\r\r" not in grid
        assert grid.count("name='[grade_level]'") == 1


def test_set_shelves_fills_an_empty_shelf_and_keeps_its_attributes():
    src = SHELVES_TWB.replace(
        "<cols onLeft='true'>([federated.0ddi (copy)].[none:module_code:nk] / "
        "[federated.0ddi (copy)].[none:school:nk])</cols>",
        "<cols onLeft='true' />",
    )
    out = set_shelves(src, "Mastery Grid", {"add": {"cols": ["School"]}})

    assert "<cols onLeft='true'>[federated.0ddi (copy)].[none:school:nk]</cols>" in out


def test_set_shelves_refuses_a_drop_off_the_shelves_and_an_unknown_add():
    with pytest.raises(ValueError, match="'Subject Area' is not on .*Grade/Subject"):
        set_shelves(SHELVES_TWB, "Mastery Grid", {"drop": ["Subject Area"]})
    with pytest.raises(ValueError, match="no field 'Grade Band'"):
        set_shelves(SHELVES_TWB, "Mastery Grid", {"add": {"rows": ["Grade Band"]}})
    with pytest.raises(ValueError, match="no worksheet 'Nope'"):
        set_shelves(SHELVES_TWB, "Nope", RESHAPE)


def test_set_shelves_refuses_a_measure_and_an_unlisted_calculation():
    with pytest.raises(ValueError, match="'Is Mastery Int' is a measure"):
        set_shelves(SHELVES_TWB, "Mastery Grid", {"add": {"rows": ["Is Mastery Int"]}})
    with pytest.raises(ValueError, match="'Mastery Band' is a calculation"):
        set_shelves(SHELVES_TWB, "Mastery Grid", {"add": {"rows": ["Mastery Band"]}})


DKI_TWB = (Path(__file__).parent / "fixtures" / "dki_grid.twb").read_text()
DKI_DS = "[federated.0dki (copy)]"


def test_set_shelves_drop_takes_the_sorts_formats_and_table_calcs_along_it():
    out = set_shelves(DKI_TWB, "Mastery Grid", {"drop": ["Week Start Monday"]})

    ET.fromstring(out)
    before, after = _worksheets(DKI_TWB), _worksheets(out)
    grid = after["Mastery Grid"]
    week, calc = "none:week_start_monday:ok", "diff:avg:is_mastery_int:qk:2"
    # The sort and the per-field formats on the dropped field go.
    assert "<natural-sort" not in grid
    assert f"field='{DKI_DS}.[{week}]'" not in grid
    # The table calc ordered along the week goes everywhere it appears.
    assert calc not in grid
    # Filters on the week stay, with their slices; so does every other field's
    # formats, the table calc along the rows, and the other label run.
    assert grid.count(f"<filter class='categorical' column='{DKI_DS}.[") == 4
    assert grid.count("<slices>") == 1 and grid.count("<column>[federated") == 4
    assert f"field='{DKI_DS}.[none:school:nk]' value='12'" in grid
    assert "name='[diff:avg:is_mastery_int:qk]'" in grid
    assert f"<tooltip column='{DKI_DS}.[diff:avg:is_mastery_int:qk]' />" in grid
    assert f"<![CDATA[<{DKI_DS}.[avg:is_mastery_int:qk]>]]>" in grid
    # Rules the edit emptied (header, mark) go; the others stay.
    assert "<style-rule element='mark'>" not in grid
    assert "<style-rule element='header'>" not in grid
    assert grid.count("<style-rule ") == 2
    assert after["Mastery by Week"] == before["Mastery by Week"]
    assert out.replace(grid, "") == DKI_TWB.replace(before["Mastery Grid"], "")


def test_set_shelves_drop_keeps_a_table_calc_along_kept_fields():
    out = set_shelves(DKI_TWB, "Mastery Grid", {"drop": ["School"]})

    grid = _worksheets(out)["Mastery Grid"]
    assert grid.count("diff:avg:is_mastery_int:qk:2") == DKI_TWB.count(
        "diff:avg:is_mastery_int:qk:2"
    )
    assert f"field='{DKI_DS}.[none:school:nk]'" not in grid
    assert "<natural-sort" in grid
