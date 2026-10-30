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
        out = set_shelves(src, "Mastery Grid", RESHAPE).xml

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
    out = set_shelves(src, "Mastery Grid", {"add": {"cols": ["School"]}}).xml

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
    out = set_shelves(DKI_TWB, "Mastery Grid", {"drop": ["Week Start Monday"]}).xml

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
    out = set_shelves(DKI_TWB, "Mastery Grid", {"drop": ["School"]}).xml

    grid = _worksheets(out)["Mastery Grid"]
    assert grid.count("diff:avg:is_mastery_int:qk:2") == DKI_TWB.count(
        "diff:avg:is_mastery_int:qk:2"
    )
    assert f"field='{DKI_DS}.[none:school:nk]'" not in grid
    assert "<natural-sort" in grid


def test_set_shelves_clears_a_filter_on_one_sheet_only():
    for src in (DKI_TWB, DKI_TWB.replace("\n", "\r\n")):
        out = set_shelves(
            src,
            "Mastery Grid",
            {"drop": ["Week Start Monday"], "clear_filters": ["Discipline"]},
        ).xml

        ET.fromstring(out)
        before, after = _worksheets(src), _worksheets(out)
        nl = "\r\n" if "\r\n" in src else "\n"
        grid = after["Mastery Grid"]
        assert (
            f"<filter class='categorical' column='{DKI_DS}.[Discipline]' "
            f"filter-group='94'>{nl}            <groupfilter function='level-members' "
            "level='[Discipline]' user:ui-enumeration='all' "
            f"user:ui-marker='enumerate' />{nl}          </filter>"
        ) in grid
        assert "&quot;ELA&quot;' user:ui-domain" not in grid
        # The year filter still narrows; the other sheet keeps its own, though
        # it shares the cleared filter's filter-group.
        assert "member='2026'" in grid
        assert "[Discipline]' filter-group='94'>" in before["Mastery by Week"]
        assert after["Mastery by Week"] == before["Mastery by Week"]


def test_set_shelves_refuses_to_clear_a_missing_or_range_filter():
    with pytest.raises(ValueError, match="no filter on 'School'; it filters Disc"):
        set_shelves(DKI_TWB, "Mastery Grid", {"clear_filters": ["School"]})
    ranged = DKI_TWB.replace(
        "<filter class='categorical' column='[federated.0dki (copy)].[none:academic",
        "<filter class='quantitative' column='[federated.0dki (copy)].[none:academic",
    )
    with pytest.raises(ValueError, match="'Academic Year' .* is not on members"):
        set_shelves(ranged, "Mastery Grid", {"clear_filters": ["Academic Year"]})


WEEK_CALC = f"{DKI_DS}.[diff:avg:is_mastery_int:qk:2]"
_NATURAL_SORT = (
    f"<natural-sort column='{DKI_DS}.[none:week_start_monday:ok]' direction='DESC' />"
)


def _grid_with(extra: str) -> str:
    """The DKI fixture with `extra` added after the grid's natural sort."""
    assert DKI_TWB.count(_NATURAL_SORT) == 2
    return DKI_TWB.replace(_NATURAL_SORT, _NATURAL_SORT + extra, 1)


def test_set_shelves_drop_removes_every_attribute_naming_a_removed_calc():
    src = _grid_with(
        f"\n          <sort class='computed' column='{DKI_DS}.[none:module_code:nk]' "
        f"direction='DESC' using='{WEEK_CALC}' />"
        f"\n          <filter class='categorical' column='{DKI_DS}.[:Measure Names]'>"
        "\n            <groupfilter function='union' user:op='manual'>"
        "\n              <groupfilter function='member' level='[:Measure Names]' "
        f"member='&quot;{DKI_DS}.[avg:is_mastery_int:qk]&quot;' />"
        "\n              <groupfilter function='member' level='[:Measure Names]' "
        f"member='&quot;{WEEK_CALC}&quot;' />"
        "\n            </groupfilter>"
        "\n          </filter>"
    )

    grid = _worksheets(
        set_shelves(src, "Mastery Grid", {"drop": ["Week Start Monday"]}).xml
    )["Mastery Grid"]

    assert "diff:avg:is_mastery_int:qk:2" not in grid
    assert "<sort class='computed'" not in grid
    assert f"member='&quot;{DKI_DS}.[avg:is_mastery_int:qk]&quot;'" in grid


def test_set_shelves_drop_removes_a_manual_sort_on_the_dropped_field():
    src = _grid_with(
        f"\n          <sort class='manual' column='{DKI_DS}.[none:week_start_monday:ok]' "
        "direction='ASC'>\n            <dictionary>\n              "
        "<bucket>#2026-01-05#</bucket>\n            </dictionary>\n          </sort>"
        f"\n          <sort class='manual' column='{DKI_DS}.[none:school:nk]' "
        "direction='ASC'>\n            <dictionary>\n              "
        "<bucket>&quot;A&quot;</bucket>\n            </dictionary>\n          </sort>"
    )

    out = set_shelves(src, "Mastery Grid", {"drop": ["Week Start Monday"]}).xml

    ET.fromstring(out)
    grid = _worksheets(out)["Mastery Grid"]
    assert "#2026-01-05#" not in grid
    assert f"<sort class='manual' column='{DKI_DS}.[none:school:nk]'" in grid


def test_set_shelves_drop_removes_a_label_and_encodings_it_emptied():
    grid = _worksheets(DKI_TWB)["Mastery Grid"]
    only_calc = grid.replace(
        f"<tooltip column='{DKI_DS}.[diff:avg:is_mastery_int:qk]' />\n"
        "              <text column='"
        f"{DKI_DS}.[avg:is_mastery_int:qk]' />\n              ",
        "",
    ).replace(
        "<run fontsize='12'><![CDATA[<"
        f"{DKI_DS}.[avg:is_mastery_int:qk]>]]></run>\n"
        "                <run>Æ&#10;</run>\n                ",
        "",
    )
    assert only_calc.count("<text column=") == 1 and only_calc.count("<run") == 1
    src = DKI_TWB.replace(grid, only_calc)

    out = set_shelves(src, "Mastery Grid", {"drop": ["Week Start Monday"]}).xml

    ET.fromstring(out)
    after = _worksheets(out)["Mastery Grid"]
    assert "<encodings>" not in after
    assert "<formatted-text>" not in after
    assert "<customized-label>" not in after
    assert "<mark class='Square' />" in after


def test_set_shelves_names_the_table_calcs_it_removes_and_recomputes():
    dropped = set_shelves(DKI_TWB, "Mastery Grid", {"drop": ["Week Start Monday"]})

    assert dropped.removed == (
        "Difference in Avg. Is Mastery Int (along Week Start Monday, Module Code)",
    )
    # Only the columns changed; the kept calc runs down the rows.
    assert dropped.recomputed == {}

    reshaped = set_shelves(
        DKI_TWB,
        "Mastery Grid",
        {"drop": ["Week Start Monday"], "add": {"rows": ["Subject Area"]}},
    )

    assert reshaped.recomputed == {"rows": ("Difference in Avg. Is Mastery Int",)}
    assert set_shelves(DKI_TWB, "Mastery Grid", {"drop": ["School"]}).removed == ()


def test_set_shelves_names_a_table_or_pane_calc_on_any_changed_shelf():
    src = DKI_TWB.replace(
        "ordering-type='Rows' type='Difference'",
        "ordering-type='Table' type='Difference'",
    )
    assert src != DKI_TWB

    dropped = set_shelves(src, "Mastery Grid", {"drop": ["Week Start Monday"]})

    assert dropped.recomputed == {"columns": ("Difference in Avg. Is Mastery Int",)}


def test_set_shelves_names_a_field_calc_whose_partition_gains_a_field():
    added = set_shelves(DKI_TWB, "Mastery Grid", {"add": {"rows": ["Subject Area"]}})

    # Both calcs share a caption: the Field one (partition gains Subject Area)
    # and the Rows one (its rows changed); the caption is named once.
    assert added.removed == ()
    assert added.recomputed == {"rows": ("Difference in Avg. Is Mastery Int",)}
    field_only = DKI_TWB.replace(
        "ordering-type='Rows' type='Difference'",
        "ordering-type='Field' type='Difference'",
    )
    added = set_shelves(field_only, "Mastery Grid", {"add": {"rows": ["Subject Area"]}})
    assert added.recomputed == {"rows": ("Difference in Avg. Is Mastery Int",)}


def test_set_shelves_drop_removes_a_rule_it_empties_beside_one_already_empty():
    src = DKI_TWB.replace(
        "<style-rule element='cell'>",
        "<style-rule element='axis'>\n          </style-rule>\n"
        "          <style-rule element='cell'>",
        1,
    )

    grid = _worksheets(
        set_shelves(src, "Mastery Grid", {"drop": ["Week Start Monday"]}).xml
    )["Mastery Grid"]

    assert "<style-rule element='axis'>\n          </style-rule>" in grid
    assert "<style-rule element='mark'>" not in grid
    assert "<style-rule element='header'>" not in grid


# --- a session Tableau ends mid-run (another sign-in with the shared token) ----------

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation import tableau as tableau_mod  # noqa: E402
from tableauserverclient.server.endpoint.exceptions import (  # noqa: E402
    FailedSignInError,
)


def _unauthorized():
    return FailedSignInError("401002", "Unauthorized Access", "")


class _Calls(list):
    """A call log that answers 401 at the named calls, once each, after
    letting the first `skip` of them through."""

    def __init__(self, fail_on, skip=0):
        super().__init__()
        self.fail_on = list(fail_on)
        self.skip = skip

    def append(self, call):
        super().append(call)
        if call[0] in self.fail_on:
            if self.skip:
                self.skip -= 1
                return
            self.fail_on.remove(call[0])
            raise _unauthorized()


class RevokedServer(FakeServer):
    """A FakeServer whose session Tableau ends at the named calls."""

    def __init__(self, twb, fail_on=(), csv_fails=False, skip=0, **kw):
        super().__init__(twb, **kw)
        self.calls = _Calls(fail_on, skip)
        self.signed_out = 0
        self.auth = SimpleNamespace(sign_out=self._sign_out)
        if csv_fails:
            # The CSV is fetched as it is read: the 401 comes on the read.
            def populate_csv(view, opts):
                def read():
                    raise _unauthorized()
                    yield b""

                view.csv = read()

            self.views.populate_csv = populate_csv

    def _sign_out(self):
        self.signed_out += 1
        raise _unauthorized()  # the ended session cannot sign out either


def _signer(servers):
    made = []

    def sign_in():
        made.append(servers.pop(0))
        return made[-1]

    return sign_in, made


def test_a_401_mid_capture_signs_in_again_and_retries_that_call(capsys):
    jobs = [[_job("Sample Dashboard", T0)]]
    first = RevokedServer(_twb(), fail_on=["download"], jobs=jobs)
    second = RevokedServer(_twb(), jobs=jobs)
    sign_in, made = _signer([second])
    tab = Tableau(first, now=lambda: NOW, sign_in=sign_in)

    snap = tab.capture("wb-luid", "Rate by Region", [{}], lambda xml: xml)

    assert made == [second] and first.signed_out == 1
    # The failed download ran again on the new session, and everything after it.
    names = [c[0] for c in second.calls]
    assert names[0] == "download" and "populate_csv" in names
    assert len(second.published) == 1 and first.published == []
    assert snap.copy_luid == "copy-luid" and len(snap.exports[0]) == 2
    assert "signing in again" in capsys.readouterr().err


def test_a_401_while_reading_the_csv_retries_the_export():
    first = RevokedServer(_twb(), csv_fails=True)
    second = RevokedServer(_twb())
    sign_in, _ = _signer([second])

    rows = Tableau(first, sign_in=sign_in).export("copy-luid", "Rate by Region", {})

    assert rows == [
        {"Region": "North", "Rate": "0.9123"},
        {"Region": "South", "Rate": "0.85"},
    ]


def test_a_second_401_in_a_row_ends_the_run():
    first = RevokedServer(_twb(), fail_on=["get_by_id"])
    second = RevokedServer(_twb(), fail_on=["get_by_id"])
    sign_in, _ = _signer([second])

    with pytest.raises(tableau_mod.SessionEnded, match="again .*right after a new"):
        Tableau(first, sign_in=sign_in).workbook_updated("wb-luid")


def test_a_refused_new_sign_in_ends_the_run():
    def sign_in():
        raise _unauthorized()

    with pytest.raises(tableau_mod.SessionEnded, match="refused the new sign-in"):
        Tableau(
            RevokedServer(_twb(), fail_on=["get_by_id"]), sign_in=sign_in
        ).workbook_updated("wb-luid")


def test_a_session_signs_in_again_at_most_a_few_times():
    # Each new session answers the retried call, then ends on the next call.
    servers = [RevokedServer(_twb(), fail_on=["get_by_id"])] + [
        RevokedServer(_twb(), fail_on=["get_by_id"], skip=1)
        for _ in range(tableau_mod.MAX_RECONNECTS)
    ]
    sign_in, _ = _signer(servers[1:])
    tab = Tableau(servers[0], sign_in=sign_in)

    for _ in range(tableau_mod.MAX_RECONNECTS):
        assert tab.workbook_updated("wb-luid") == T0
    with pytest.raises(tableau_mod.SessionEnded, match="at most"):
        tab.workbook_updated("wb-luid")


def test_source_fingerprint_follows_the_connection_not_the_extract():
    from cube_validation.tableau import source_fingerprint

    def twb(table, refreshed, other="x"):
        return f"""<workbook><datasources>
<datasource name='federated.a'>
  <connection class='federated'><relation name='r' table='[ds].[{table}]' type='table' /></connection>
  <extract enabled='true'><connection class='hyper' update-time='{refreshed}' /></extract>
</datasource>
<datasource name='federated.b'><connection class='federated'><relation table='[ds].[{other}]' /></connection></datasource>
</datasources><worksheets><worksheet name='S'><table><view>
<datasource-dependencies datasource='federated.a' />
</view></table></worksheet></worksheets></workbook>"""

    base = source_fingerprint(twb("v1", "10/29/2026"), "S")

    assert source_fingerprint(twb("v1", "10/30/2026"), "S") == base
    assert source_fingerprint(twb("v1", "10/29/2026", other="y"), "S") == base
    assert source_fingerprint(twb("v2", "10/29/2026"), "S") != base
