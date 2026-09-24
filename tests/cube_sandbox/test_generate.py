from __future__ import annotations

import random

import pytest

from teamster.cube_sandbox import coverage, generate, personas, snapshot


def test_dependencies_are_generated_first() -> None:
    order = generate.generation_order(
        tables={"fct_a", "dim_b", "dim_c"},
        edges={("fct_a", "dim_b"), ("dim_b", "dim_c")},
    )
    assert order.index("dim_c") < order.index("dim_b") < order.index("fct_a")


def test_the_spine_cycle_is_reported_not_raised() -> None:
    # dim_student_enrollments and dim_student_section_enrollments reference
    # each other in the Cube join graph. No order satisfies both, so the cycle
    # is broken deliberately rather than treated as an error.
    order = generate.generation_order(
        tables={"dim_student_enrollments", "dim_student_section_enrollments"},
        edges={
            ("dim_student_enrollments", "dim_student_section_enrollments"),
            ("dim_student_section_enrollments", "dim_student_enrollments"),
        },
    )
    assert set(order) == {
        "dim_student_enrollments",
        "dim_student_section_enrollments",
    }
    # Enrollments first. The homeroom join is declared FROM the enrollment side
    # but its foreign key (student_enrollment_key) lives on the section table,
    # so the enrollment table needs nothing from it — that edge is the one to
    # break. Breaking the other one instead orders sections first, and every
    # section's student_enrollment_key then has no generated stint to sample.
    assert order[0] == "dim_student_enrollments"


def test_a_cycle_that_is_not_the_spine_still_raises() -> None:
    # Only the one known, deliberately-broken edge is special. Any other cycle
    # is a model change the generator cannot silently paper over.
    with pytest.raises(ValueError, match="unbroken dependency cycle"):
        generate.generation_order(
            tables={"dim_p", "dim_q"},
            edges={("dim_p", "dim_q"), ("dim_q", "dim_p")},
        )


def _stints(n: int) -> list[dict]:
    return [{"student_enrollment_key": f"e{i}"} for i in range(n)]


def _sections(per_stint: int, stints: int) -> list[dict]:
    return [
        {
            "student_section_enrollment_key": f"s{i}-{j}",
            "student_enrollment_key": f"e{i}",
            "is_homeroom": j == 0,
        }
        for i in range(stints)
        for j in range(per_stint)
    ]


def test_current_homeroom_is_a_mix_not_wholly_unset() -> None:
    rows = generate.resolve_spine(
        enrollments=_stints(20),
        sections=_sections(per_stint=3, stints=20),
        rng=random.Random(0),
    )
    flags = [r["is_current_homeroom"] for r in rows]
    # A deliberate slice of stints resolves to no current homeroom.
    assert not all(flags), "the unresolved slice is a required cell"
    # All-false is the silent failure: the data loads cleanly, the
    # homeroom-teacher join matches nothing, and it surfaces only at query
    # time. That is the whole reason this third pass exists.
    assert any(flags), "all-false means the cycle never closed"


def test_at_most_one_current_homeroom_per_stint() -> None:
    rows = generate.resolve_spine(
        enrollments=_stints(30),
        sections=_sections(per_stint=4, stints=30),
        rng=random.Random(1),
    )
    per_stint: dict[str, int] = {}
    for row in rows:
        if row["is_current_homeroom"]:
            per_stint[row["student_enrollment_key"]] = (
                per_stint.get(row["student_enrollment_key"], 0) + 1
            )
    # student_school_enrollments joins student_homeroom_section one_to_one.
    # Two current homerooms on one stint fans the attendance views out and
    # silently doubles every day-weighted measure.
    assert per_stint and max(per_stint.values()) == 1


def test_only_a_homeroom_section_can_be_the_current_homeroom() -> None:
    rows = generate.resolve_spine(
        enrollments=_stints(10),
        sections=_sections(per_stint=3, stints=10),
        rng=random.Random(2),
    )
    assert all(r["is_homeroom"] for r in rows if r["is_current_homeroom"])


def test_resolve_spine_is_deterministic_for_a_seed() -> None:
    # The manifest's coverage is asserted against a seeded run, so a seed that
    # does not reproduce makes every coverage result unfalsifiable.
    def run() -> list[bool]:
        return [
            r["is_current_homeroom"]
            for r in generate.resolve_spine(
                enrollments=_stints(15),
                sections=_sections(per_stint=3, stints=15),
                rng=random.Random(7),
            )
        ]

    assert run() == run()


def test_tiny_and_full_differ_only_in_row_count() -> None:
    tiny = generate.row_target("dim_students", scale="tiny")
    full = generate.row_target("dim_students", scale="full")
    # Same generator, same seed, same manifest coverage. Only the multiplier
    # differs, so a tiny run that satisfies the manifest proves the generator
    # correct without waiting on a full build.
    assert tiny < full
    assert tiny >= generate.MANIFEST_FLOOR


def test_dim_dates_is_bounded_in_both_profiles() -> None:
    # Production's calendar spine runs to the year 9999, and an unbounded date
    # dimension is what drove the partitioned pre-aggregation incident (#4460).
    for scale in ("tiny", "full"):
        assert generate.row_target("dim_dates", scale=scale) <= generate.DATE_SPINE_MAX


def test_an_unknown_scale_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown scale"):
        generate.row_target("dim_students", scale="medium")


def test_the_unresolved_slice_is_null_not_false() -> None:
    # The manifest requires a null row for is_current_homeroom, and a
    # generator writing False everywhere makes that cell unsatisfiable by
    # construction. The dbt column is `(is_homeroom and homeroom_rank = 1)`,
    # which is genuinely NULL when the rank does not resolve; its YAML claims
    # "never null" but no dbt not_null test asserts it, so per the spec the
    # sandbox nulls it and the fix belongs in dbt.
    rows = generate.resolve_spine(
        enrollments=_stints(20),
        sections=_sections(per_stint=3, stints=20),
        rng=random.Random(0),
    )
    flags = [r["is_current_homeroom"] for r in rows]
    assert any(f is None for f in flags), "the null slice is a required cell"
    assert any(f is True for f in flags)
    assert any(f is False for f in flags)


def test_the_null_slice_survives_a_tiny_run() -> None:
    # A bare 5% coin flip can come up empty on the tiny profile, which would
    # leave the required null cell unsatisfied at random. A flaky gate
    # teaches nothing, so the first stint is unresolved unconditionally.
    for seed in range(5):
        rows = generate.resolve_spine(
            enrollments=_stints(2),
            sections=_sections(per_stint=2, stints=2),
            rng=random.Random(seed),
        )
        assert any(r["is_current_homeroom"] is None for r in rows)


# ---------------------------------------------------------------------------
# The whole-dataset contract
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tiny() -> dict[str, list[dict]]:
    return generate.generate(
        snapshot.load(),
        personas.load(generate.PERSONAS_PATH),
        "tiny",
        generate.DEFAULT_SEED,
    )


def test_a_tiny_run_leaves_no_uncovered_cell(tiny: dict[str, list[dict]]) -> None:
    """The test that matters most.

    The manifest is the generator's specification, so a `tiny` run that
    leaves an uncovered cell means the generator does not satisfy its own
    contract. Eight cells are reported UNPROVEN rather than uncovered — the
    two derived states, the unresolvable identity and the three divergences
    — because proving them needs a live query against the deployment rather
    than a scan of rows; the canary and divergence suites own those, each
    with its own non-zero exit.
    """
    cells = generate.load_cells()
    assessed = coverage.assess({"cells": cells}, tiny)

    assert coverage.uncovered(assessed) == []
    assert coverage.exit_code(assessed) == 0
    assert len(coverage.unproven(assessed)) == 8


def test_every_table_in_the_snapshot_is_generated(tiny: dict[str, list[dict]]) -> None:
    snap = snapshot.load()
    assert set(tiny) == set(snap["tables"])
    for table, rows in tiny.items():
        # Every row carries every column, or the Avro write fails on the
        # missing field rather than on anything a reader would recognise.
        assert all(set(row) == set(snap["tables"][table]) for row in rows)


def test_the_same_seed_and_commit_produce_the_same_rows() -> None:
    snap = snapshot.load()
    people = personas.load(generate.PERSONAS_PATH)
    first = generate.generate(snap, people, "tiny", 7)
    second = generate.generate(snap, people, "tiny", 7)
    assert first == second


def test_a_different_seed_produces_different_rows() -> None:
    # A "deterministic" generator that ignores its seed is deterministic for
    # the wrong reason, and every seeded test above would pass on it.
    snap = snapshot.load()
    people = personas.load(generate.PERSONAS_PATH)
    assert generate.generate(snap, people, "tiny", 1) != generate.generate(
        snap, people, "tiny", 2
    )


def test_the_declared_personas_are_written_verbatim(
    tiny: dict[str, list[dict]],
) -> None:
    # canaries.yml names these by address. A seed-derived persona means a
    # seed change silently changes who the canaries test, and the suite
    # stays green while testing something else.
    people = personas.load(generate.PERSONAS_PATH)
    by_email = {row["google_email"]: row for row in tiny["dim_staff_cube_access"]}
    for person in people:
        row = by_email[person.email]
        for name, value in person.scopes.items():
            assert row[name] == value, f"{person.email}.{name}"


def test_has_remit_and_has_chain_each_resolve_both_ways(
    tiny: dict[str, list[dict]],
) -> None:
    """The supporting rows, not just the declared ones.

    `personas.yml` declares the two remit scopes, but hasRemit also depends
    on rows the generator supplies — the locations universe, and this row's
    own region_key / location_abbreviation / department_group — and the chain
    is declared as reportees rather than as chain rows. Both states have to
    come out true for some persona and false for another, or the branch
    production cannot reach (reporting_chain with an empty chain) is not in
    the sandbox either.
    """
    people = personas.load(generate.PERSONAS_PATH)
    by_email = {row["google_email"]: row for row in tiny["dim_staff_cube_access"]}
    abbreviations = {row["abbreviation"] for row in tiny["dim_locations"]}
    department_groups = {
        row["department_group"]
        for row in tiny["dim_staff_cube_access"]
        if row["department_group"]
    }
    managers = {row["manager_staff_key"] for row in tiny["dim_staff_reporting_chain"]}

    remit, chain = set(), set()
    for person in people:
        row = by_email[person.email]
        allowed_abbreviations = {
            "network": abbreviations,
            "region": {row["location_abbreviation"]} if row["region_key"] else set(),
            "school": {row["location_abbreviation"]},
        }.get(row["staff_location_scope"], set())
        allowed_departments = {
            "all": department_groups,
            "own_group": {row["department_group"]},
        }.get(row["staff_department_scope"], set())
        remit.add(bool(allowed_abbreviations and allowed_departments))
        chain.add(row["staff_key"] in managers)
        # The declaration is what the derived state has to match.
        assert bool(person.reportees) == (row["staff_key"] in managers), person.email

    assert remit == {True, False}
    assert chain == {True, False}


def test_one_identity_resolves_to_no_access_row(tiny: dict[str, list[dict]]) -> None:
    # The clean default-deny fixture: a real staff member the warehouse has
    # never given a Cube access row.
    staff = {row["google_email"] for row in tiny["dim_staff"]}
    access = {row["google_email"] for row in tiny["dim_staff_cube_access"]}
    assert personas.UNRESOLVABLE in staff
    assert personas.UNRESOLVABLE not in access


def test_every_fabricated_address_is_unresolvable_by_construction(
    tiny: dict[str, list[dict]],
) -> None:
    # RFC 2606 reserves .invalid and guarantees it never resolves, so no mail
    # can reach a synthetic person even by accident. Nulls are skipped, not
    # tolerated by accident: the manifest requires a null row on both of
    # these columns, because neither carries a dbt `not_null` test.
    for row in tiny["dim_staff"]:
        for column in ("google_email", "personal_email", "work_email"):
            if row[column] is not None:
                assert row[column].endswith(".invalid"), f"{column}: {row[column]}"


def test_every_phone_is_in_the_block_reserved_for_fiction(
    tiny: dict[str, list[dict]],
) -> None:
    for row in tiny["dim_staff"]:
        if row["personal_cell_phone"] is not None:
            assert generate.PHONE_PREFIX in row["personal_cell_phone"]


def test_identifiers_come_from_a_range_production_never_issues(
    tiny: dict[str, list[dict]],
) -> None:
    for row in tiny["dim_students"]:
        if row["lea_student_identifier"] is not None:
            assert row["lea_student_identifier"] >= generate.RESERVED_ID_BASE
    for row in tiny["dim_staff"]:
        if row["staff_unique_id"] is not None:
            assert row["staff_unique_id"] >= generate.RESERVED_ID_BASE


def test_every_surname_is_a_reserved_one(tiny: dict[str, list[dict]]) -> None:
    # The surname carries the proof: nothing else uses these words, so the
    # appearance of the name is what identifies the row as fabricated.
    reserved = set(generate.reserved_surnames())
    for row in tiny["dim_staff"]:
        if row["last_name"] is not None:
            assert row["last_name"] in reserved


def test_every_declared_character_class_appears(tiny: dict[str, list[dict]]) -> None:
    # Cycling the reserved given names rather than sampling them is what
    # makes this true on every seed instead of on most of them.
    present = {
        entry["class"]
        for entry in generate.reserved_given_names()
        if any(row["first_name"] == entry["name"] for row in tiny["dim_staff"])
    }
    assert present == generate.given_name_classes()


def test_the_date_spine_is_bounded_to_a_real_academic_year_range(
    tiny: dict[str, list[dict]],
) -> None:
    # Production's calendar spine runs to the year 9999, and an unbounded
    # date dimension is what drove the partitioned pre-aggregation incident
    # (#4460).
    days = [row["date_key"] for row in tiny["dim_dates"]]
    assert min(days) == generate.DATE_SPINE_START
    assert max(days).year < 2100
    assert len(days) == generate.DATE_SPINE_MAX


def test_the_school_week_is_not_the_iso_week(tiny: dict[str, list[dict]]) -> None:
    # The semantic hazard, reproduced rather than smoothed: an ISO grouping
    # over these rows compiles, runs, and returns a different breakdown, and
    # there is no query-time guard anywhere.
    diverging = sum(
        1
        for row in tiny["dim_dates"]
        if row["school_week_start_date"] != row["calendar_week_start_date"]
    )
    assert diverging > 0


def test_a_scale_score_stays_inside_its_own_assessment_range(
    tiny: dict[str, list[dict]],
) -> None:
    # SAT at 400-1600 beside ACT at 1-36 is the point: a wrong cross-scope
    # average produces a number nobody can read as plausible, which is the
    # one failure no assertion catches.
    scope_of = {row["assessment_key"]: row["scope"] for row in tiny["dim_assessments"]}
    scope_by_administration = {
        row["assessment_administration_key"]: scope_of.get(row["assessment_key"])
        for row in tiny["dim_assessment_administrations"]
    }
    seen = set()
    for row in tiny["fct_assessment_scores_enrollment_scoped"]:
        scope = scope_by_administration.get(row["assessment_administration_key"])
        if scope not in generate._SCALE_RANGES or row["scale_score"] is None:
            continue
        low, high = generate._SCALE_RANGES[scope]
        assert low <= row["scale_score"] <= high, f"{scope}: {row['scale_score']}"
        seen.add(scope)
    # Two incomparable ranges have to be present, or nothing announces itself.
    assert len(seen) >= 2


def test_row_targets_are_honoured(tiny: dict[str, list[dict]]) -> None:
    # A table whose FK must be one-to-one cannot exceed its parent pool. It
    # is capped rather than padded, because repeating a parent to hit a row
    # count is what put two access rows on one staff member.
    capped = {table for table, _ in generate.UNIQUE_FK}
    for table, rows in tiny.items():
        target = generate.row_target(table, "tiny")
        if table in capped:
            assert 0 < len(rows) <= target
        else:
            assert len(rows) == target


def test_a_capped_table_still_covers_almost_every_staff_member(
    tiny: dict[str, list[dict]],
) -> None:
    # Capping the table to its parent pool must not quietly gut it. Three
    # staff legitimately have no access row: the unresolvable identity, which
    # is excluded on purpose; the row `_referenceable` holds back so an orphan
    # has somewhere to point; and the row the planted orphan displaced.
    #
    # The manifest REQUIRES an orphan on this column, so exactly one access
    # key pointing at no staff member is the contract rather than a fault.
    staff_keys = {row["staff_key"] for row in tiny["dim_staff"]}
    access_keys = {row["staff_key"] for row in tiny["dim_staff_cube_access"]}

    assert len(access_keys - staff_keys) == 1, "expected exactly one planted orphan"
    assert len(access_keys & staff_keys) >= len(staff_keys) - 3


def test_each_staff_member_has_at_most_one_access_row(
    tiny: dict[str, list[dict]],
) -> None:
    # dim_staff_cube_access is one row per staff member. A filler row draws
    # its staff_key from the same dim_staff pool the personas sit in, so
    # without a guard it adopts a persona's key and that persona gets two
    # rows — the declared one and a mechanical one whose scope columns hold
    # placeholder strings.
    #
    # resolveAccess reads ONE row and a placeholder matches no enum, so the
    # persona then resolves to no groups and default-denies. This was live on
    # sheryl.swoopes, whose whole purpose is full access.
    keys = [row["staff_key"] for row in tiny["dim_staff_cube_access"]]
    duplicated = sorted({key for key in keys if keys.count(key) > 1})

    assert not duplicated, f"{len(duplicated)} staff_key(s) with several rows"


def test_no_persona_access_row_carries_a_placeholder_scope(
    tiny: dict[str, list[dict]],
) -> None:
    # The failure above is only dangerous because the duplicate row is
    # junk. Assert the values directly too: a persona's scopes come from
    # personas.yml verbatim, so anything shaped like a generated placeholder
    # means a mechanical pass reached a row it should never have touched.
    declared = {person.email for person in personas.load(generate.PERSONAS_PATH)}
    scope_columns = [
        column
        for column in tiny["dim_staff_cube_access"][0]
        if column.endswith("_scope")
    ]
    for row in tiny["dim_staff_cube_access"]:
        if row.get("google_email") not in declared:
            continue
        for column in scope_columns:
            assert not str(row[column]).startswith(column), (
                f"{row['google_email']} carries the placeholder "
                f"{row[column]!r} in {column}"
            )
