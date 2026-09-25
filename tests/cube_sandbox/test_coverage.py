from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from teamster.cube_sandbox import avro, coverage, generate, personas, snapshot

MANIFEST = {
    "cells": [
        {
            "kind": "null",
            "table": "dim_x",
            "column": "a",
            "detail": "",
            "status": "uncovered",
        },
        {
            "kind": "non_null",
            "table": "dim_x",
            "column": "a",
            "detail": "",
            "status": "uncovered",
        },
    ]
}


def test_a_covered_cell_reports_its_count() -> None:
    result = coverage.assess(MANIFEST, {"dim_x": [{"a": None}, {"a": "v"}]})
    assert all(c["observed"] > 0 for c in result)
    assert coverage.exit_code(result) == 0


def test_an_empty_table_fails_rather_than_passing_vacuously() -> None:
    # Zero rows means no cell was ever evaluated. Reporting that as covered is
    # the silent failure the manifest exists to prevent.
    result = coverage.assess(MANIFEST, {"dim_x": []})
    assert all(c["observed"] == 0 for c in result)
    assert coverage.exit_code(result) == 1


def test_a_table_missing_entirely_fails_rather_than_raising() -> None:
    # A generator that skipped a table is the same failure as one that wrote
    # it empty, and must not surface as a KeyError.
    result = coverage.assess(MANIFEST, {})
    assert all(c["observed"] == 0 for c in result)
    assert coverage.exit_code(result) == 1


def test_a_column_missing_from_every_row_is_not_counted_as_null() -> None:
    # `.get(column)` returns None for a column the generator never wrote at
    # all, which is indistinguishable from a written NULL. Counting the first
    # as covering the null cell lets a generator satisfy the contract by
    # omitting the column entirely — and then the non_null cell is the only
    # thing standing between that and a green run.
    result = coverage.assess(MANIFEST, {"dim_x": [{"b": 1}, {"b": 2}]})
    by_kind = {c["kind"]: c["observed"] for c in result}
    assert by_kind["null"] == 0
    assert by_kind["non_null"] == 0
    assert coverage.exit_code(result) == 1


def test_a_scope_cell_counts_matching_rows() -> None:
    manifest = {
        "cells": [
            {
                "kind": "scope",
                "table": "dim_staff_cube_access",
                "column": "staff_pii_scope",
                "detail": "all_in_scope",
                "status": "uncovered",
            }
        ]
    }
    result = coverage.assess(
        manifest,
        {
            "dim_staff_cube_access": [
                {"staff_pii_scope": "all_in_scope"},
                {"staff_pii_scope": "teaching_staff"},
            ]
        },
    )
    assert result[0]["observed"] == 1


UNPROVEN = {
    "cells": [
        {
            "kind": "derived",
            "table": None,
            "column": "hasRemit",
            "detail": "true",
            "status": "uncovered",
        },
        {
            "kind": "identity",
            "table": None,
            "column": None,
            "detail": "one email with no dim_staff_cube_access row",
            "status": "uncovered",
        },
        {
            "kind": "divergence",
            "table": None,
            "column": None,
            "detail": "school_week_vs_iso",
            "status": "uncovered",
        },
    ]
}


def test_a_cell_with_no_table_is_reported_unproven_not_silently_zero() -> None:
    # derived / identity / divergence cells name no table, so row counting
    # cannot evaluate them. They must not be scored as covered, and the
    # report has to say they were never assessed rather than implying the
    # generator failed to produce them.
    result = coverage.assess(UNPROVEN, {})
    assert [c["status"] for c in result] == ["unproven"] * 3
    assert all(c["observed"] == 0 for c in result)


def test_a_manifest_of_only_unproven_cells_exits_zero() -> None:
    # The real manifest carries eight of these permanently. Failing on them
    # made the gate unreachable: a perfect dataset still exited 1, so the
    # exit code carried no information. They are asserted by the canary and
    # divergence suites, each with its own non-zero exit.
    result = coverage.assess(UNPROVEN, {})
    assert coverage.exit_code(result) == 0
    assert coverage.uncovered(result) == []
    assert len(coverage.unproven(result)) == 3


def test_one_uncovered_cell_still_exits_one_among_unproven_ones() -> None:
    # The relaxation above must not become a general amnesty: a countable
    # cell the generated rows do not satisfy still fails the run.
    manifest = {"cells": [*UNPROVEN["cells"], *MANIFEST["cells"]]}
    result = coverage.assess(manifest, {"dim_x": [{"a": "v"}]})
    assert coverage.exit_code(result) == 1
    assert coverage.uncovered(result) == [("null", "dim_x", "a", "")]


def test_the_report_names_the_unproven_cells_a_green_run_did_not_prove() -> None:
    # "0 uncovered" on its own reads as "everything proved". The operator has
    # to see that three requirements were never assessed here, and by what.
    text = coverage.describe(coverage.assess(UNPROVEN, {}))
    assert "3 unproven" in text
    assert "canary and divergence" in text


VARIETY = {
    "cells": [
        {
            "kind": "scope_variety",
            "table": "dim_staff_cube_access",
            "column": "staff_benefits_scope",
            "detail": "at least two distinct non-none values",
            "status": "uncovered",
        }
    ]
}


def test_one_non_none_scope_value_does_not_satisfy_the_variety_cell() -> None:
    # access.js branches on `!== "none"`, so a single non-none value lets a
    # kit author write an equality check that passes every test — freezing
    # the exact mistake the sandbox exists to expose.
    result = coverage.assess(
        VARIETY,
        {
            "dim_staff_cube_access": [
                {"staff_benefits_scope": "all_in_scope"},
                {"staff_benefits_scope": "all_in_scope"},
                {"staff_benefits_scope": "none"},
                {"staff_benefits_scope": None},
            ]
        },
    )
    assert result[0]["observed"] == 1
    assert result[0]["status"] == "uncovered"
    assert coverage.exit_code(result) == 1


def test_two_distinct_non_none_scope_values_satisfy_the_variety_cell() -> None:
    result = coverage.assess(
        VARIETY,
        {
            "dim_staff_cube_access": [
                {"staff_benefits_scope": "all_in_scope"},
                {"staff_benefits_scope": "reporting_chain"},
                {"staff_benefits_scope": "none"},
            ]
        },
    )
    assert result[0]["observed"] == 2
    assert coverage.exit_code(result) == 0


def test_covered_cells_are_marked_covered() -> None:
    result = coverage.assess(MANIFEST, {"dim_x": [{"a": None}, {"a": "v"}]})
    assert {c["status"] for c in result} == {"covered"}


def test_uncovered_cells_are_listed_for_the_operator() -> None:
    result = coverage.assess(MANIFEST, {"dim_x": [{"a": "v"}]})
    assert coverage.uncovered(result) == [("null", "dim_x", "a", "")]
    assert coverage.exit_code(result) == 1


ORPHANS = {
    "cells": [
        {
            "kind": "orphan",
            "table": "fct_a",
            "column": "b_key",
            "detail": "dim_b.b_key",
            "status": "uncovered",
        },
        {
            "kind": "orphan",
            "table": "dim_b",
            "column": "b_key",
            "detail": "fct_a.b_key",
            "status": "uncovered",
        },
    ]
}


def test_an_orphan_on_each_side_is_counted() -> None:
    result = coverage.assess(
        ORPHANS,
        {
            # b3 matches no dim_b row; b2 is referenced by no fct_a row.
            "fct_a": [{"b_key": "b1"}, {"b_key": "b3"}],
            "dim_b": [{"b_key": "b1"}, {"b_key": "b2"}],
        },
    )
    assert [c["observed"] for c in result] == [1, 1]
    assert coverage.exit_code(result) == 0


def test_a_fully_referential_pair_leaves_both_orphan_cells_uncovered() -> None:
    # Perfect referential integrity is the failure here: the sandbox's job is
    # to leave no empty niche, and a kit that assumes every key resolves must
    # meet a row where it does not.
    result = coverage.assess(
        ORPHANS,
        {"fct_a": [{"b_key": "b1"}], "dim_b": [{"b_key": "b1"}]},
    )
    assert [c["observed"] for c in result] == [0, 0]
    assert coverage.exit_code(result) == 1


def test_a_null_foreign_key_is_not_an_orphan() -> None:
    # A null key is no reference at all, not a reference to a row that is
    # missing. Counting it would let the generator satisfy the orphan cell
    # without ever producing an unmatched value.
    result = coverage.assess(
        ORPHANS,
        {"fct_a": [{"b_key": None}], "dim_b": [{"b_key": "b1"}]},
    )
    assert result[0]["observed"] == 0


def test_an_unknown_cell_kind_is_rejected() -> None:
    # A new kind added to the manifest generator that coverage does not
    # understand must fail loudly; scoring it by the fall-through rule would
    # report a number that means nothing.
    manifest = {
        "cells": [
            {
                "kind": "invented",
                "table": "dim_x",
                "column": "a",
                "detail": "",
                "status": "uncovered",
            }
        ]
    }
    with pytest.raises(ValueError, match="unknown cell kind"):
        coverage.assess(manifest, {"dim_x": [{"a": 1}]})


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


def _manifest_file(tmp_path: Path, cells: list[dict]) -> Path:
    path = tmp_path / "manifest.yml"
    path.write_text(yaml.safe_dump({"cells": cells}), encoding="utf-8")
    return path


def _avro_file(tmp_path: Path, table: str, rows: list[dict]) -> None:
    schema = {
        "type": "record",
        "name": table,
        "fields": [{"name": "a", "type": ["null", "string"]}],
    }
    avro.write(tmp_path / f"{table}.avro", schema, rows)


def test_main_exits_zero_when_every_countable_cell_is_satisfied(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _manifest_file(
        tmp_path,
        [
            {"kind": "non_null", "table": "dim_x", "column": "a", "detail": ""},
            {"kind": "null", "table": "dim_x", "column": "a", "detail": ""},
        ],
    )
    _avro_file(tmp_path, "dim_x", [{"a": "value"}, {"a": None}])

    code = coverage.main(["--avro-dir", str(tmp_path), "--manifest", str(manifest)])

    assert code == 0
    assert "0 uncovered" in capsys.readouterr().out


def test_main_exits_non_zero_and_names_the_uncovered_cell(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A gate that exits zero on an uncovered cell is not a gate.
    manifest = _manifest_file(
        tmp_path,
        [{"kind": "null", "table": "dim_x", "column": "a", "detail": "needs a null"}],
    )
    _avro_file(tmp_path, "dim_x", [{"a": "value"}])

    code = coverage.main(["--avro-dir", str(tmp_path), "--manifest", str(manifest)])

    assert code == 1
    assert "uncovered: null dim_x.a" in capsys.readouterr().out


def test_main_refuses_to_assess_missing_avro(tmp_path: Path) -> None:
    # Reporting "0 uncovered" over a directory with no files in it is the
    # worst outcome available here: a green gate asserting nothing.
    manifest = _manifest_file(
        tmp_path,
        [{"kind": "non_null", "table": "dim_x", "column": "a", "detail": ""}],
    )
    with pytest.raises(SystemExit, match="no Avro to assess"):
        coverage.main(
            ["--avro-dir", str(tmp_path / "empty"), "--manifest", str(manifest)]
        )


def test_the_committed_manifest_round_trips_through_avro(tmp_path: Path) -> None:
    """Generate, write, read back, assess — the whole path the CI gate runs.

    Assessing the in-memory rows would miss anything the Avro round trip
    changes: a null that came back as an empty string, a NUMERIC that lost
    its scale. The sandbox gets the file, not the dict.
    """
    snap = snapshot.load()
    people = personas.load(generate.PERSONAS_PATH)
    tables = generate.generate(snap, people, "tiny", generate.DEFAULT_SEED)
    generate.write(tables, snap, tmp_path)

    assert coverage.main(["--avro-dir", str(tmp_path)]) == 0
