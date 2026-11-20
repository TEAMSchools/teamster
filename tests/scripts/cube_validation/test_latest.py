from dataclasses import replace
from datetime import datetime, timezone

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import latest, pipeline

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import Comparison, RebuildCheck

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

BUILD = Build(
    datetime(2026, 10, 22, 20, 30, tzinfo=timezone.utc),
    datetime(2026, 10, 22, 20, 44, tzinfo=timezone.utc),
    "job-1",
)


def test_a_result_round_trips_with_its_moment(tmp_path):
    result = latest.Latest(
        moment=BUILD,
        fingerprint="f" * 64,
        entry="e" * 64,
        ran_at="2026-10-23T20:44:00+00:00",
        data={"cells": [], "fingerprints": {"ada-region": {"cube": "c"}}},
    )
    other = replace(result, moment=Build(BUILD.end, BUILD.end, "job-2"))
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")

    latest.write(folder, "ada-region", result)
    latest.write(folder, "ada/odd id", other)

    assert latest.read_all(folder, "") == {"ada-region": result, "ada/odd id": other}
    assert folder == tmp_path / "v" / latest.DIR / "kipptaf_marts"
    assert latest.read_all(tmp_path / "nothing", "") == {}


def test_a_dev_build_s_results_are_kept_apart_from_production(tmp_path):
    prod = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    dev = latest.folder(tmp_path / "v", "zz_cbaldor_kipptaf_marts.fct_f")
    result = latest.Latest(BUILD, "f", "e", "t", {}, fact="kipptaf_marts.fct_f")

    latest.write(prod, "c1", result)

    assert prod != dev and latest.read_all(dev, "kipptaf_marts.fct_f") == {}
    assert latest.read_all(prod, "kipptaf_marts.fct_f")["c1"].fact == (
        "kipptaf_marts.fct_f"
    )


def test_a_result_missing_a_key_is_skipped(tmp_path, capsys):
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    latest.write(folder, "c1", latest.Latest(BUILD, "f", "e", "t", {}))
    (path,) = folder.glob("*.json")
    path.write_text('{"comparison": "c1"}')

    assert latest.read_all(folder, "") == {}
    assert "cannot be read" in capsys.readouterr().out


def test_the_entry_fingerprint_changes_with_the_rebuild_check():
    proof = RebuildCheck(
        fingerprint="abc", cells=2, matched_at="2026-10-26T12:00:00+00:00"
    )
    comparison = Comparison(id="c", measure="m", rebuild_check=proof)

    same = latest.entry_fingerprint(replace(comparison))
    rebuilt = latest.entry_fingerprint(
        replace(comparison, rebuild_check=replace(proof, fingerprint="abd"))
    )
    edited = latest.entry_fingerprint(replace(comparison, measure="n"))

    assert same == latest.entry_fingerprint(comparison)
    assert len({same, rebuilt, edited}) == 3


def test_definitions_change_neither_fingerprint():
    # The analyst adds `definitions:` after a formula difference; the
    # comparison's result stays current and its saved rows stay its own.
    comparison = Comparison(id="c", measure="m")
    defined = replace(comparison, definitions={"m": "students present / enrolled"})
    sides = {"cube": "c", "dashboard": "d"}

    assert latest.entry_fingerprint(defined) == latest.entry_fingerprint(comparison)
    assert pipeline.checkpoint_fingerprint(
        defined, sides
    ) == pipeline.checkpoint_fingerprint(comparison, sides)


def test_a_result_of_another_fact_is_not_read(tmp_path, capsys):
    # One dataset's folder, 2 facts: the view's fact moved to fct_g.
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    latest.write(
        folder,
        "c1",
        latest.Latest(BUILD, "f", "e", "t", {}, fact="kipptaf_marts.fct_f"),
    )

    assert latest.read_all(folder, "kipptaf_marts.fct_g") == {}
    assert set(latest.read_all(folder, "kipptaf_marts.fct_f")) == {"c1"}


def _check(comparison="c1"):
    return {"comparison": comparison, "fingerprint": "f", "formula": [],
            "coverage": [], "not_compared": {}, "lines": []}  # fmt: skip


def test_a_formula_check_is_kept_beside_its_result(tmp_path):
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    latest.write(folder, "c1", latest.Latest(BUILD, "f", "e", "t", {"cells": []}))

    latest.add_formula_check(folder, "c1", _check())

    assert latest.read_all(folder, "")["c1"].data == {
        "cells": [],
        "formula_check": _check(),
    }


def test_a_formula_check_with_no_result_is_dropped(tmp_path):
    # The next `compare` writes a fresh result, which no older check fits.
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")

    latest.add_formula_check(folder, "c1", _check())

    assert not folder.exists() or not list(folder.glob("*.json"))


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("{not json", id="not JSON"),
        pytest.param(b"\xff\xfe", id="not text"),
        pytest.param("[1]", id="not an object"),
        pytest.param('{"comparison": "c1"}', id="no data"),
        pytest.param('{"comparison": "c1", "data": []}', id="data not an object"),
    ],
)
def test_a_formula_check_beside_an_unreadable_result_is_skipped(tmp_path, capsys, text):
    # As `read_all` skips it: never raised into `sort`.
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    latest.write(folder, "c1", latest.Latest(BUILD, "f", "e", "t", {}))
    (path,) = folder.glob("*.json")
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    before = path.read_bytes()

    latest.add_formula_check(folder, "c1", _check())

    assert path.read_bytes() == before
    assert f"Latest result {path.name} skipped: it cannot be read" in (
        capsys.readouterr().out
    )


def test_a_formula_check_of_another_comparison_is_refused(tmp_path):
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    latest.write(folder, "c1", latest.Latest(BUILD, "f", "e", "t", {}))
    (path,) = folder.glob("*.json")
    before = path.read_text()

    with pytest.raises(ValueError, match="checks c2, not c1"):
        latest.add_formula_check(folder, "c1", _check("c2"))

    assert path.read_text() == before
