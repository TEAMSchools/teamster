from dataclasses import replace
from datetime import datetime, timezone

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import latest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import Comparison, Proof

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

    assert latest.read_all(folder) == {"ada-region": result, "ada/odd id": other}
    assert folder == tmp_path / "v" / latest.DIR / "kipptaf_marts"
    assert latest.read_all(tmp_path / "nothing") == {}


def test_a_dev_build_s_results_are_kept_apart_from_production(tmp_path):
    prod = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    dev = latest.folder(tmp_path / "v", "zz_cbaldor_kipptaf_marts.fct_f")
    result = latest.Latest(BUILD, "f", "e", "t", {}, fact="kipptaf_marts.fct_f")

    latest.write(prod, "c1", result)

    assert prod != dev and latest.read_all(dev) == {}
    assert latest.read_all(prod)["c1"].fact == "kipptaf_marts.fct_f"


def test_a_result_missing_a_key_is_skipped(tmp_path, capsys):
    folder = latest.folder(tmp_path / "v", "kipptaf_marts.fct_f")
    latest.write(folder, "c1", latest.Latest(BUILD, "f", "e", "t", {}))
    (path,) = folder.glob("*.json")
    path.write_text('{"comparison": "c1"}')

    assert latest.read_all(folder) == {}
    assert "cannot be read" in capsys.readouterr().out


def test_the_entry_fingerprint_changes_with_the_rebuild_check():
    proof = Proof(fingerprint="abc", cells=2, proven_at="2026-10-26T12:00:00+00:00")
    comparison = Comparison(id="c", measure="m", proof=proof)

    same = latest.entry_fingerprint(replace(comparison))
    rebuilt = latest.entry_fingerprint(
        replace(comparison, proof=replace(proof, fingerprint="abd"))
    )
    edited = latest.entry_fingerprint(replace(comparison, measure="n"))

    assert same == latest.entry_fingerprint(comparison)
    assert len({same, rebuilt, edited}) == 3
