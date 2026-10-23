"""Snapshot folders and manifest."""

import datetime as dt

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import snapshot


def test_new_and_latest_snapshot(tmp_path):
    a = snapshot.new_snapshot("dash", dt.datetime(2026, 10, 15, 16, 5), root=tmp_path)
    b = snapshot.new_snapshot(
        "dash", dt.datetime(2026, 10, 15, 21, 0), "2025-26", root=tmp_path
    )
    assert a.dir.name == "2026-10-15T1605" and b.dir.name == "2026-10-15T2100-2025-26"
    assert snapshot.latest_snapshot("dash", root=tmp_path).dir == b.dir


def test_manifest_round_trip_and_export_path(tmp_path):
    s = snapshot.new_snapshot("dash", dt.datetime(2026, 10, 15, 16, 5), root=tmp_path)
    snapshot.write_manifest(s, {"cuts": {"default": {}}})
    assert snapshot.read_manifest(s) == {"cuts": {"default": {}}}
    p = s.export_path("default", "ADA by School")
    assert (
        p == s.dir / "exports" / "default" / "ada-by-school.csv" and p.parent.is_dir()
    )
