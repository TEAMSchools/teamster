"""Probes over a tiny extract: 3 students in 2 grades."""

from dataclasses import replace

import pytest

pytest.importorskip("tableauhyperapi")

# trunk-ignore(pyright/reportAttributeAccessIssue)
from cube_validate import cells, config, hyper, probes  # noqa: E402

from .test_cells import _checks as base_checks  # noqa: E402

DASH = "select avg(is_absent) from {extract} where {where}"
CAND = "select avg(is_absent) from {extract} where {where} and grade_level = 9"


def _checks(*probe_list):
    return replace(
        base_checks(),
        probes=tuple(probe_list),
        defaults={"Region": ("Camden",)},
    )


def _cell(**over):
    base = dict(
        cut="default",
        sheet="ADA",
        dims={"School": "Rise"},
        measure="ADA",
        tableau="33.3%",
        cube=0.5,
        verdict=cells.FORMULA_GAP,
        fmt=cells.Format(1, True),
    )
    base.update(over)
    return cells.Cell(**base)


def _ws(tmp_path):
    ws = hyper.Workspace(tmp_path / "x.hyper", {})
    ws.__enter__()
    ws.execute(
        "create temporary table ext (region text, school_abbreviation text,"
        " grade_level bigint, is_absent double precision)"
    )
    ws.execute(
        "insert into ext values ('Camden','Rise',9,1.0),('Camden','Rise',10,0.0),"
        "('Camden','Rise',10,0.0),('Newark','Rise',9,1.0)"
    )
    return ws


def _run(tmp_path, probe, cell):
    ws = _ws(tmp_path)
    try:
        return probes.run(ws, _checks(probe), [cell], extract="ext")
    finally:
        ws.__exit__(None, None, None)


def _probe(dashboard=DASH, candidate=CAND, param=None):
    return config.Probe("p", "ADA", param, dashboard, candidate)


def test_a_probe_that_reproduces_the_export_is_proven(tmp_path):
    [res] = _run(tmp_path, _probe(), _cell())
    assert res.proven
    assert res.cells[0].reproduces and res.cells[0].error == ""
    assert res.cells[0].dashboard == pytest.approx(1 / 3)


def test_a_candidate_matching_cube_is_counted_per_cell(tmp_path):
    [res] = _run(tmp_path, _probe(), _cell(cube=1.0))
    assert res.cells[0].candidate == 1.0
    assert res.cells[0].candidate_matches_cube
    [res] = _run(tmp_path, _probe(), _cell(cube=0.5))
    assert not res.cells[0].candidate_matches_cube


def test_a_probe_with_bad_sql_reports_the_error_and_is_not_proven(tmp_path):
    [res] = _run(tmp_path, _probe(dashboard="select nope from {extract}"), _cell())
    assert not res.proven
    assert res.cells[0].error and not res.cells[0].reproduces


def test_a_probe_returning_null_does_not_reproduce(tmp_path):
    [res] = _run(
        tmp_path,
        _probe(dashboard="select avg(is_absent) from {extract} where false"),
        _cell(),
    )
    assert res.cells[0].dashboard is None
    assert not res.cells[0].reproduces and not res.proven


def test_a_probe_skips_cells_it_does_not_apply_to(tmp_path):
    ws = _ws(tmp_path)
    try:
        c = [_cell(measure="Other"), _cell(verdict=cells.NO_ROWS)]
        [res] = probes.run(ws, _checks(_probe()), c, extract="ext")
    finally:
        ws.__exit__(None, None, None)
    assert res.cells == [] and not res.proven


def test_a_param_probe_applies_only_to_cuts_with_that_value(tmp_path):
    probe = _probe(param=("Mode", "A"))
    checks = replace(
        _checks(probe),
        cuts=(
            config.Cut("default"),
            config.Cut("a", params={"Mode": "A"}),
            config.Cut("b", params={"Mode": "B"}),
        ),
    )
    ws = _ws(tmp_path)
    try:
        c = [_cell(cut="default"), _cell(cut="a"), _cell(cut="b")]
        [res] = probes.run(ws, checks, c, extract="ext")
    finally:
        ws.__exit__(None, None, None)
    assert [p.cut for p in res.cells] == ["a"]


def test_reproduces_compares_at_the_dashboards_format():
    pct = cells.Format(1, True)
    assert probes.reproduces(0.3333, "33.3%", pct)
    assert probes.reproduces(0.3333, "0.3333", pct)
    assert not probes.reproduces(0.3366, "33.3%", pct)
    assert probes.reproduces(1204.4, "1,204", cells.Format(0, False))
    assert probes.reproduces(0.942, "94.2%", None)
    assert not probes.reproduces(None, "94.2%", pct)
    assert not probes.reproduces(0.9, "", pct)
