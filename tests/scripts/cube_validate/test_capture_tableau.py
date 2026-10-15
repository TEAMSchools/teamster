from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import capture_tableau, workbook

snap = capture_tableau


def test_session_refuses_a_production_project():
    with pytest.raises(snap.SessionError, match="non-production"):
        snap.Session(SimpleNamespace(), "some-production-project")


def test_vf_value_escapes_commas_and_expands_all_and_blank():
    assert snap.vf_value("KIPP, Newark", []) == "KIPP\\, Newark"
    assert snap.vf_value(snap.ALL, ["A", "B, C"]) == "A,B\\, C"
    assert snap.vf_value(snap.BLANK, []) == "Null"


def test_pick_click_row_takes_the_largest_or_smallest_mark():
    data = "Title,School,Score\r\nT1,All,50\r\nT1,Alpha,80\r\nT2,Beta,20\r\nT3,*,90\r\n".encode()
    assert snap.pick_click_row(data, "largest", ["Title", "School"]) == {
        "Title": "T1",
        "School": "Alpha",
    }
    assert snap.pick_click_row(data, "small", ["Title", "School"]) == {
        "Title": "T2",
        "School": "Beta",
    }


def test_retry_recovers_then_gives_up():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("401002")
        return "ok"

    assert snap.retry(flaky, sleep=lambda s: None) == "ok"
    with pytest.raises(RuntimeError):
        snap.retry(
            lambda: (_ for _ in ()).throw(RuntimeError("x")), sleep=lambda s: None
        )


def test_a_lost_session_waits_signs_in_again_and_retries():
    # Live on DDI, another sign-in on the shared token ended the tool's session.
    calls = {"get": 0, "sign_in": 0}

    def get_by_id(luid):
        calls["get"] += 1
        if calls["get"] <= 2:
            raise RuntimeError("401002: Unauthorized Access")
        return SimpleNamespace(updated_at=dt.datetime(2026, 10, 9, 5, 0, tzinfo=dt.UTC))

    waits = []
    server = SimpleNamespace(
        workbooks=SimpleNamespace(get_by_id=get_by_id),
        auth=SimpleNamespace(
            sign_in=lambda a: calls.__setitem__("sign_in", calls["sign_in"] + 1)
        ),
    )
    s = snap.Session(server, snap.TEMP_CB, auth="pat", sleep=waits.append)
    s.call(lambda: server.workbooks.get_by_id("w1"))
    assert calls == {"get": 3, "sign_in": 2} and waits == [snap.SIGN_IN_WAIT] * 2


def test_exports_wait_out_the_dashboards_quiet_minutes():
    waits = []

    def at(h, m, s=0):
        return lambda: dt.datetime(2026, 10, 14, h, m, s, tzinfo=dt.UTC)

    busy = snap.Session(
        SimpleNamespace(), snap.TEMP_CB, now=at(18, 4, 30), sleep=waits.append
    )
    busy.wait_out_refreshes()
    assert waits == [330]  # until 18:10
    snap.Session(
        SimpleNamespace(), snap.TEMP_CB, now=at(18, 15), sleep=waits.append
    ).wait_out_refreshes()
    assert waits == [330]
    # A dashboard whose refreshes sign in at :30 sets its own window.
    late = snap.Session(
        SimpleNamespace(),
        snap.TEMP_CB,
        now=at(18, 31),
        sleep=waits.append,
        quiet=(30, 40),
    )
    late.wait_out_refreshes()
    assert waits == [330, 540]


def test_a_failed_sign_out_after_a_lost_session_is_not_an_error():
    def gone():
        raise RuntimeError("401002: Unauthorized Access")

    server = SimpleNamespace(
        auth=SimpleNamespace(sign_in=lambda a: None, sign_out=gone)
    )
    with snap.signed_in(server, "pat"):
        pass


def test_export_signs_in_again_when_tableau_drops_the_session():
    # A PAT allows one session: another sign-in with it ends ours (401002).
    calls = {"populate": 0, "sign_in": 0}
    view = SimpleNamespace(name="S1", csv=[b"A\r\n1\r\n"])

    def populate_csv(v, opts):
        calls["populate"] += 1
        if calls["populate"] == 1:
            raise RuntimeError("401002: Unauthorized Access")

    server = SimpleNamespace(
        views=SimpleNamespace(populate_csv=populate_csv),
        auth=SimpleNamespace(
            sign_in=lambda a: calls.__setitem__("sign_in", calls["sign_in"] + 1)
        ),
    )
    s = snap.Session(server, snap.TEMP_CB, auth="pat", sleep=lambda w: None)
    s._views = {"S1": view}
    assert s.export_view("S1", []) == b"A\r\n1\r\n"
    assert calls == {"populate": 2, "sign_in": 1}


def test_review_name():
    assert (
        capture_tableau.review_name(
            dt.datetime(2026, 10, 15, 16, 5), "Attendance Dashboard"
        )
        == "ZZ-REVIEW 2026-10-15 1605 Attendance Dashboard"
    )


def test_click_targets_follow_the_action_and_its_exclusions():
    wb = workbook.Workbook(
        dashboards={"Overview": ["ADA by School", "Trend", "Roster"]},
        filters=[],
        params=[],
        actions=[
            workbook.Action(
                "Overview", "c", "ADA by School", "filter", "Overview", ("Roster",)
            )
        ],
    )
    assert capture_tableau.click_targets(wb, ["Overview"], "ADA by School") == ["Trend"]


def test_capture_resumes_without_publishing_again(tmp_path):
    import json
    import zipfile

    # trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
    from cube_validate import config, snapshot

    twb = (
        "<workbook><datasources><datasource caption='DS'>"
        "<extract><connection class='hyper' dbname='x.hyper'/></extract>"
        "</datasource></datasources></workbook>"
    )
    snap = snapshot.Snapshot(tmp_path)
    with zipfile.ZipFile(snap.twbx, "w") as z:
        z.writestr("w.twb", twb)
        z.writestr("Data/Extracts/x.hyper", b"stub")
    snap.manifest_path.write_text(
        json.dumps(
            {
                "review_copy": {"name": "ZZ-REVIEW n", "url": "u", "id": "copy-1"},
                "cuts": {"default": {"sheets": {"S1": "exports/default/s1.csv"}}},
            }
        )
    )
    checks = SimpleNamespace(
        workbook="W",
        datasource="DS",
        dashboards=("Overview",),
        sheets=("S1",),
        cuts=(
            config.Cut("default"),
            config.Cut("filter-x", filters={"School": "Alpha"}),
        ),
    )

    class Fake:
        def __init__(self):
            self.attached, self.published, self.exported = [], [], []

        def attach(self, luid):
            self.attached.append(luid)

        def publish(self, *a):
            self.published.append(a)

        def wait_out_refreshes(self):
            pass

        def export_view(self, sheet, filters, params=()):
            self.exported.append((sheet, list(filters)))
            return b"A\r\n1\r\n"

    session = Fake()
    m = capture_tableau.capture(checks, snap, session, dt.datetime(2026, 10, 15, 16, 5))
    assert session.published == [] and session.attached == ["copy-1"]
    assert session.exported == [("S1", [("School", "Alpha")])]
    assert set(m["cuts"]) == {"default", "filter-x"}
    assert set(snapshot.read_manifest(snap)["cuts"]) == {"default", "filter-x"}
    assert snap.extract.exists() and not (tmp_path / "x.hyper").exists()


def test_download_with_a_signed_in_server_does_not_sign_in_again(tmp_path):
    calls = []

    class Workbooks:
        def get_by_id(self, luid):
            return SimpleNamespace(updated_at=dt.datetime(2026, 10, 15, 20, 0))

        def download(self, luid, filepath, include_extract):
            calls.append("download")
            return str(tmp_path / "live.twbx")

    class Auth:
        def sign_in(self, auth):
            calls.append("sign_in")

        def sign_out(self):
            calls.append("sign_out")

    server = SimpleNamespace(workbooks=Workbooks(), auth=Auth())
    path, at = capture_tableau.download("l", tmp_path, server=server)
    assert calls == ["download"]
    assert path == tmp_path / "live.twbx" and at.startswith("2026-10-15T20:00")
