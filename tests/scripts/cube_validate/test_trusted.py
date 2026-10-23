"""Trust carried across runs."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

pytest.importorskip("tableauhyperapi")

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest registers cube_validate at runtime
from cube_validate import cells, handchecks, report, trusted  # noqa: E402


def _cell(verdict):
    return cells.Cell(
        "default", "ADA", {"School": "Rise"}, "ADA", "94.2%", 0.95, verdict
    )


def _rows(*pairs):
    return SimpleNamespace(
        buckets=[{"base": b, "cause": c} for b, c in pairs] + [{"base": "match"}]
    )


def _write(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data))
    return path


def test_fingerprints_ignore_findings_sections(tmp_path):
    base = {"filters": {"a": 1}, "causes": {"x": 1}, "decisions": []}
    p = _write(tmp_path / "c.yml", base)
    before = trusted.mapping_fingerprint(p)
    _write(p, {**base, "causes": {"x": 2}, "probes": {"y": 1}})
    assert trusted.mapping_fingerprint(p) == before
    _write(p, {**base, "filters": {"a": 2}})
    assert trusted.mapping_fingerprint(p) != before


def test_code_fingerprint_follows_file_bytes(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    before = trusted.code_fingerprint(tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n")
    assert trusted.code_fingerprint(tmp_path) != before


def test_kinds_are_verdicts_and_non_match_buckets():
    got = trusted.kinds(
        [_cell(cells.PASS), _cell(cells.ROW_GAP)], _rows(("cube_only", "unexplained"))
    )
    assert got == {cells.PASS, cells.ROW_GAP, "cube_only / unexplained"}


def test_a_new_verdict_stops_the_carry_over(tmp_path):
    trusted.record(tmp_path, "s1", "c", "m", {cells.PASS}, dashboard="d")
    rec = trusted.read(tmp_path)
    assert trusted.carries(rec, "c", "m", {cells.PASS}, dashboard="d")
    assert not trusted.carries(
        rec, "c", "m", {cells.PASS, cells.ROW_GAP}, dashboard="d"
    )
    assert not trusted.carries(rec, "c2", "m", {cells.PASS}, dashboard="d")
    assert not trusted.carries(rec, "c", "m2", {cells.PASS}, dashboard="d")
    assert not trusted.carries(rec, "c", "m", {cells.PASS}, dashboard="other")


def test_no_record_means_no_carry_over(tmp_path):
    assert trusted.read(tmp_path) is None
    assert not trusted.carries(None, "c", "m", set())


def test_hand_checks_cover_only_what_is_new():
    cs = [_cell(cells.PASS), _cell(cells.ROW_GAP), _cell(cells.FORMULA_GAP)]
    rows = [
        {"base": "cube_only", "cause": "unexplained", "k_student": 1, "k_day": "d"},
        {"base": "dashboard_only", "cause": "late", "k_student": 2, "k_day": "d"},
    ]
    known = {cells.ROW_GAP, "cube_only / unexplained"}
    got = handchecks.pick(cs, rows, seed="s", known=known)
    assert {h.covers for h in got} == {cells.FORMULA_GAP, "dashboard_only / late"}
    assert (
        handchecks.pick(
            cs,
            rows,
            seed="s",
            known={*known, cells.FORMULA_GAP, "dashboard_only / late"},
        )
        == []
    )


def test_carried_trust_line_and_a_broken_invariant_still_wins():
    ok = {"capture completeness": True}
    assert report.trust(ok, {}, 5, carried_from="s1") == (
        "Trusted: carried over from s1 (code and mapping unchanged, no new verdicts)."
    )
    assert report.trust({"x": False}, {}, 5, carried_from="s1").startswith(
        "Not trusted"
    )
