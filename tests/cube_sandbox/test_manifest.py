from __future__ import annotations

from pathlib import Path

import pytest

from teamster.cube_sandbox import manifest, model
from teamster.cube_sandbox.personas import Persona

SNAP = {
    "tables": {
        "dim_x": {
            "student_key": {"type": "STRING", "nullable": True},
            "nickname": {"type": "STRING", "nullable": True},
            "abbreviation": {"type": "STRING", "nullable": True},
        }
    }
}


def _null_columns(cells) -> set[str]:
    return {c["column"] for c in cells if c["kind"] == "null"}


def test_keys_and_policy_columns_are_exempt_from_the_null_rule() -> None:
    cells = manifest.build(
        snap=SNAP,
        referenced={"dim_x": {"student_key", "nickname", "abbreviation"}},
        key_columns={("dim_x", "student_key")},
        policy_columns={("dim_x", "abbreviation")},
        not_null=set(),
        scopes={},
        people=[],
        join_paths=[],
    )["cells"]
    # A null join key breaks the fixtures; a null policy column makes the
    # persona resolve to nothing.
    assert _null_columns(cells) == {"nickname"}


def test_key_exemption_is_per_table_not_per_column_name() -> None:
    # The exemption is keyed on (table, column), so the same column name on a
    # table that does not join on it still needs a null cell. A bare set of
    # column names — or the name-suffix heuristic this replaced — would exempt
    # both.
    snap = {
        "tables": {
            "dim_x": {"student_key": {"type": "STRING", "nullable": True}},
            "dim_y": {"student_key": {"type": "STRING", "nullable": True}},
        }
    }
    cells = manifest.build(
        snap=snap,
        referenced={"dim_x": {"student_key"}, "dim_y": {"student_key"}},
        key_columns={("dim_x", "student_key")},
        policy_columns=set(),
        not_null=set(),
        scopes={},
        people=[],
        join_paths=[],
    )["cells"]
    assert {(c["table"], c["column"]) for c in cells if c["kind"] == "null"} == {
        ("dim_y", "student_key")
    }


def test_an_identifier_suffix_alone_does_not_exempt() -> None:
    # state_student_identifier is routinely null for a newly enrolled student,
    # and nothing joins on it. The old `_identifier` suffix rule exempted it
    # from ever getting a null cell, which is the one case the sandbox most
    # needs to teach.
    snap = {
        "tables": {
            "dim_students": {
                "state_student_identifier": {"type": "STRING", "nullable": True}
            }
        }
    }
    cells = manifest.build(
        snap=snap,
        referenced={"dim_students": {"state_student_identifier"}},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes={},
        people=[],
        join_paths=[],
    )["cells"]
    assert _null_columns(cells) == {"state_student_identifier"}


def test_each_join_path_requires_an_orphan_on_each_side() -> None:
    # The spec's "Every join path: one orphan on each side, as a named
    # fixture a test can reference." Without these cells nothing requires the
    # sandbox to contain an unmatched key, so a kit that assumes every
    # foreign key resolves passes here and breaks on production — where
    # dim_student_enrollments.location_key is documented NULL for
    # grade_level 99 placeholder schools.
    path = model.JoinPath(child=("fct_a", "b_key"), parent=("dim_b", "b_key"))
    cells = manifest.build(
        snap={"tables": {}},
        referenced={},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes={},
        people=[],
        join_paths=[path],
    )["cells"]
    orphans = [c for c in cells if c["kind"] == "orphan"]
    assert len(orphans) == 2
    assert {(c["table"], c["column"], c["detail"]) for c in orphans} == {
        ("fct_a", "b_key", "dim_b.b_key"),
        ("dim_b", "b_key", "fct_a.b_key"),
    }


def test_dbt_not_null_columns_are_exempt() -> None:
    cells = manifest.build(
        snap=SNAP,
        referenced={"dim_x": {"nickname"}},
        key_columns=set(),
        policy_columns=set(),
        not_null={("dim_x", "nickname")},
        scopes={},
        people=[],
        join_paths=[],
    )["cells"]
    # INFORMATION_SCHEMA reports every column NULLABLE, so dbt's not_null
    # tests carry the real contract.
    assert _null_columns(cells) == set()


def test_persona_with_an_unhandled_scope_value_is_rejected() -> None:
    rogue = Persona(
        email="x@ktaf-sandbox.invalid",
        given_name="X",
        surname="Y",
        purpose="invalid",
        scopes={"staff_pii_scope": "made_up"},
        reportees=[],
    )
    # A persona nothing branches on tests nothing, so the manifest must
    # refuse rather than emit a cell no policy can reach.
    with pytest.raises(ValueError, match="access.js does not handle"):
        manifest.build(
            snap={"tables": {}},
            referenced={},
            key_columns=set(),
            policy_columns=set(),
            not_null=set(),
            scopes={"staff_pii_scope": {"all_in_scope"}},
            people=[rogue],
            join_paths=[],
        )


def test_persona_with_a_non_none_sensitive_tier_value_is_accepted() -> None:
    # The three sensitive tiers map to the "__non_none__" sentinel because
    # access.js branches on `!== "none"` rather than a value list. Any
    # non-none value a persona declares for one of them must be accepted,
    # not just the literal values access.js happens to enumerate elsewhere.
    persona = Persona(
        email="x@ktaf-sandbox.invalid",
        given_name="X",
        surname="Y",
        purpose="valid",
        scopes={"staff_compensation_scope": "reporting_chain"},
        reportees=[],
    )
    result = manifest.build(
        snap={"tables": {}},
        referenced={},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes={"staff_compensation_scope": {"__non_none__"}},
        people=[persona],
        join_paths=[],
    )
    # No exception, and the sentinel itself never becomes a scope cell.
    assert not any(c["kind"] == "scope" for c in result["cells"])


def test_scope_cells_skip_the_non_none_sentinel() -> None:
    cells = manifest.build(
        snap={"tables": {}},
        referenced={},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes={
            "staff_pii_scope": {"all_in_scope", "teaching_staff"},
            "staff_benefits_scope": {"__non_none__"},
        },
        people=[],
        join_paths=[],
    )["cells"]
    scope_cells = [c for c in cells if c["kind"] == "scope"]
    assert {c["detail"] for c in scope_cells} == {"all_in_scope", "teaching_staff"}
    assert "staff_benefits_scope" not in {c["column"] for c in scope_cells}


def test_is_not_null_test_rejects_not_null_proportion() -> None:
    # A substring match on "not_null" also matches dbt_utils.not_null_proportion,
    # which asserts a PROPORTION of non-null rows, not the absence of nulls.
    # Treating it as the real not-null contract would wrongly exempt a column
    # that genuinely can contain nulls.
    assert not manifest._is_not_null_test(
        {"dbt_utils.not_null_proportion": {"at_least": 0.9}}
    )
    assert not manifest._is_not_null_test("dbt_utils.not_null_proportion")
    assert manifest._is_not_null_test("not_null")
    assert manifest._is_not_null_test({"not_null": {"config": {"severity": "warn"}}})


def test_dbt_not_null_exempts_only_the_real_not_null_column(tmp_path: Path) -> None:
    (tmp_path / "model.yml").write_text(
        """
models:
  - name: dim_x
    columns:
      - name: strict_column
        data_tests:
          - not_null
      - name: proportion_only_column
        data_tests:
          - dbt_utils.not_null_proportion:
              at_least: 0.9
      - name: legacy_key_tests
        tests:
          - not_null
"""
    )
    result = manifest.dbt_not_null(tmp_path)
    assert ("dim_x", "strict_column") in result
    assert ("dim_x", "legacy_key_tests") in result
    # A column carrying ONLY not_null_proportion must never be treated as a
    # not-null guarantee — the manifest still needs a null cell for it.
    assert ("dim_x", "proportion_only_column") not in result


SENTINEL_SCOPES = (
    "staff_benefits_scope",
    "staff_compensation_scope",
    "staff_observations_scope",
)


def _variety_columns(cells) -> set[str]:
    return {c["column"] for c in cells if c["kind"] == "scope_variety"}


def test_a_sentinel_scope_requires_two_distinct_non_none_values() -> None:
    # access.js branches on `!== "none"` for the sensitive tiers, so the
    # manifest emitted NO cell for them at all and the spec's two-value rule
    # was unasserted. personas.yml happens to satisfy it; nothing would catch
    # an edit that stops.
    cells = manifest.build(
        snap={"tables": {}},
        referenced={},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes={name: {"__non_none__"} for name in SENTINEL_SCOPES},
        people=[],
        join_paths=[],
    )["cells"]
    assert _variety_columns(cells) == set(SENTINEL_SCOPES)
    # No per-value cell: no single value stands in for the domain.
    assert not [
        c for c in cells if c["kind"] == "scope" and c["detail"] == "__non_none__"
    ]


def test_an_enumerated_scope_gets_per_value_cells_not_a_variety_cell() -> None:
    cells = manifest.build(
        snap={"tables": {}},
        referenced={},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes={"staff_pii_scope": {"all_in_scope", "teaching_staff"}},
        people=[],
        join_paths=[],
    )["cells"]
    assert _variety_columns(cells) == set()
    assert {c["detail"] for c in cells if c["kind"] == "scope"} == {
        "all_in_scope",
        "teaching_staff",
    }


def test_the_declared_personas_satisfy_every_variety_cell() -> None:
    # The personas are written into dim_staff_cube_access verbatim, so they
    # ARE the rows this cell is scored against. Asserting it here is what
    # turns "personas.yml happens to satisfy the rule" into a contract.
    from teamster.cube_sandbox import coverage, personas

    people = personas.load(manifest.PERSONAS_PATH)
    built = manifest.build(
        snap={"tables": {}},
        referenced={},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes=model.scope_values(manifest.CUBE_ROOT / "access.js"),
        people=people,
        join_paths=[],
    )
    variety = {"cells": [c for c in built["cells"] if c["kind"] == "scope_variety"]}
    assert _variety_columns(variety["cells"]) == set(SENTINEL_SCOPES)
    rows = [dict(person.scopes) for person in people]
    result = coverage.assess(variety, {"dim_staff_cube_access": rows})
    assert coverage.uncovered(result) == []
    assert all(c["observed"] >= 2 for c in result)


def test_a_not_null_snapshot_column_gets_no_null_cell() -> None:
    # The snapshot records the warehouse's REQUIRED/NULLABLE mode, and
    # avro.bq_schema builds the sandbox table from it. Asking for a null in a
    # REQUIRED column asks the generator to produce a row the table cannot
    # hold, and the failure lands at load time rather than here.
    #
    # Not redundant with the dbt not_null exemption: a column can be REQUIRED
    # in BigQuery with no dbt test on it, which is exactly
    # additional_location_grants.
    snap = {
        "tables": {
            "dim_x": {
                "required": {"type": "STRING", "nullable": False},
                "optional": {"type": "STRING", "nullable": True},
            }
        }
    }
    cells = manifest.build(
        snap=snap,
        referenced={"dim_x": {"required", "optional"}},
        key_columns=set(),
        policy_columns=set(),
        not_null=set(),
        scopes={},
        people=[],
        join_paths=[],
    )["cells"]

    assert _null_columns(cells) == {"optional"}
