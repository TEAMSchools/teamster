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

    latest.write(tmp_path / "v", "ada-region", result)
    latest.write(tmp_path / "v", "ada/odd id", other)

    assert latest.read_all(tmp_path / "v") == {
        "ada-region": result,
        "ada/odd id": other,
    }
    assert (tmp_path / "v" / latest.DIR).is_dir()
    assert latest.read_all(tmp_path / "nothing") == {}


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
