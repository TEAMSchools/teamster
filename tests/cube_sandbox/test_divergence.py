from __future__ import annotations

from pathlib import Path

import pytest

from teamster.cube_sandbox import divergence

DIVERGENCES = Path(__file__).parents[2] / "src" / "cube" / "sandbox" / "divergences.yml"


def test_convergence_is_a_failure() -> None:
    # If the pair converges, the fabricated data has lost the property that
    # makes the sandbox teach this lesson, and the suite must say so.
    assert not divergence.diverges(100.0, 101.0, min_ratio=0.10)
    assert divergence.diverges(100.0, 140.0, min_ratio=0.10)


def test_a_zero_denominator_does_not_divide() -> None:
    assert not divergence.diverges(0.0, 0.0, min_ratio=0.10)


def test_the_ratio_is_symmetric() -> None:
    # Relative to the LARGER of the two, so which query is called `a` cannot
    # change the verdict.
    assert divergence.diverges(140.0, 100.0, 0.10) == divergence.diverges(
        100.0, 140.0, 0.10
    )


def test_one_side_at_zero_is_a_total_divergence() -> None:
    assert divergence.diverges(0.0, 5.0, min_ratio=0.99)


def test_the_committed_divergences_load() -> None:
    items = divergence.load(DIVERGENCES)
    # The spec names three divergence cells, and the manifest emits three.
    assert {i.name for i in items} == {
        "unpinned_cumulative",
        "attendance_view_weighting",
        "school_week_vs_iso",
    }
    assert all(i.why and i.a and i.b for i in items)


def test_a_zero_min_ratio_is_rejected(tmp_path: Path) -> None:
    # A ratio of 0 makes diverges() true for any pair at all, including an
    # identical one, so the assertion would pass whatever the generator did.
    path = tmp_path / "divergences.yml"
    path.write_text(
        "divergences:\n"
        "  - name: x\n    min_ratio: 0\n    why: w\n    a: SELECT 1\n    b: SELECT 2\n"
    )
    with pytest.raises(ValueError, match="between 0 and 1"):
        divergence.load(path)


def test_an_empty_file_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "divergences.yml"
    path.write_text("divergences: []\n")
    with pytest.raises(ValueError, match="declares no divergences"):
        divergence.load(path)


def test_assess_marks_a_held_pair_and_a_converged_one() -> None:
    items = divergence.load(DIVERGENCES)
    result = divergence.assess(
        items,
        {
            "unpinned_cumulative": (100.0, 400.0),
            "attendance_view_weighting": (0.9207, 0.9141),
            "school_week_vs_iso": (180.0, 181.0),
        },
    )
    by_name = {r["name"]: r["status"] for r in result}
    assert by_name["unpinned_cumulative"] == "held"
    assert by_name["attendance_view_weighting"] == "held"
    assert by_name["school_week_vs_iso"] == "converged"
    assert divergence.exit_code(result) == 1


def test_a_pair_that_never_ran_is_unproven_and_still_fails() -> None:
    # Not running a pair has not shown the lesson any more than converging
    # has, so it cannot be the difference between a red and a green run.
    items = divergence.load(DIVERGENCES)
    result = divergence.assess(items, {})
    assert {r["status"] for r in result} == {"unproven"}
    assert divergence.exit_code(result) == 1


def test_all_held_passes() -> None:
    items = divergence.load(DIVERGENCES)
    result = divergence.assess(
        items,
        {
            "unpinned_cumulative": (100.0, 400.0),
            "attendance_view_weighting": (0.9207, 0.9141),
            "school_week_vs_iso": (180.0, 300.0),
        },
    )
    assert divergence.exit_code(result) == 0


def test_the_production_attendance_gap_clears_its_threshold() -> None:
    # 0.9207 against 0.9141 is the measured AY2025 divergence between the
    # day-weighted and student-weighted rates. The threshold has to sit below
    # it or the assertion fails against correct data.
    items = {i.name: i for i in divergence.load(DIVERGENCES)}
    assert divergence.diverges(
        0.9207, 0.9141, items["attendance_view_weighting"].min_ratio
    )


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


def test_a_scalar_query_measures_its_value() -> None:
    assert divergence.measure([(1234,)]) == 1234.0


def test_a_grouped_query_measures_its_bucket_count() -> None:
    # `SELECT count(*) ... GROUP BY DATE_TRUNC(attendance_date, ISOWEEK)`
    # returns one row per bucket, and the number the school-week pair
    # compares is how many buckets there are.
    assert divergence.measure([(3,), (4,), (5,)]) == 3.0


def test_a_null_aggregate_measures_zero() -> None:
    assert divergence.measure([(None,)]) == 0.0


def test_the_runner_refuses_to_guess_a_deployment(monkeypatch: pytest.MonkeyPatch):
    # Defaulting to localhost would let this suite report on a dev server and
    # call it the sandbox.
    for name in (divergence.SQL_HOST, divergence.SQL_PASSWORD):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit, match="CUBE_SANDBOX_SQL_HOST"):
        divergence.connection_settings()


def test_the_runner_names_only_what_is_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(divergence.SQL_HOST, "sandbox.example.invalid")
    monkeypatch.delenv(divergence.SQL_PASSWORD, raising=False)

    with pytest.raises(SystemExit) as caught:
        divergence.connection_settings()

    assert divergence.SQL_PASSWORD in str(caught.value)
    assert divergence.SQL_HOST not in str(caught.value)


def test_settings_default_the_port_database_and_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(divergence.SQL_HOST, "sandbox.example.invalid")
    monkeypatch.setenv(divergence.SQL_PASSWORD, "unused-in-this-test")
    monkeypatch.delenv(divergence.SQL_PORT, raising=False)
    monkeypatch.delenv(divergence.SQL_VIEWER, raising=False)

    settings = divergence.connection_settings()

    assert settings["port"] == 15432
    assert settings["dbname"] == "cube"
    # Every pair reads a student view, so the default viewer is the one
    # persona with network student scope; a narrower one returns zero rows on
    # both sides and every pair "converges" for the wrong reason.
    assert settings["user"] == divergence.DEFAULT_VIEWER


def test_a_converged_pair_fails_the_run() -> None:
    declared = divergence.load(divergence.DIVERGENCES_PATH)
    measured = {item.name: (100.0, 100.0) for item in declared}

    assessed = divergence.assess(declared, measured)

    assert divergence.exit_code(assessed) == 1
    assert all(result["status"] == "converged" for result in assessed)


def test_the_committed_pairs_hold_when_the_numbers_are_far_apart() -> None:
    declared = divergence.load(divergence.DIVERGENCES_PATH)
    measured = {item.name: (100.0, 1.0) for item in declared}

    assessed = divergence.assess(declared, measured)

    assert divergence.exit_code(assessed) == 0
    assert "HELD" in divergence.describe(assessed)
