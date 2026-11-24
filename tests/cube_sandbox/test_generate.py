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
    own legal_entity_region_key / location_abbreviation / department_group —
    and the chain
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
            "region": (
                {row["location_abbreviation"]}
                if row["legal_entity_region_key"]
                else set()
            ),
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


# -- region shape -----------------------------------------------------------
#
# Production has four school regions of very different sizes plus a network
# office region that enrolls no students. A sandbox with one school per
# region made "region scope" mean "one school", which hid a canary that could
# not pass and would hide the same mistake in any kit screen built for a
# region-level viewer.

_NAMED_REGIONS = {
    "Newark Region",
    "Miami Region",
    "Camden Region",
    "Paterson Region",
    "Network Office",
}


def _region_by_key(tiny: dict[str, list[dict]]) -> dict[str, dict]:
    return {row["region_key"]: row for row in tiny["dim_regions"]}


def _locations_per_region(tiny: dict[str, list[dict]]) -> dict[str, int]:
    regions = _region_by_key(tiny)
    counts: dict[str, int] = {}
    for row in tiny["dim_locations"]:
        region = regions.get(row["region_key"])
        if region is not None and region["name"] is not None:
            counts[region["name"]] = counts.get(region["name"], 0) + 1
    return counts


def test_regions_mirror_production_shape(tiny: dict[str, list[dict]]) -> None:
    names = [row["name"] for row in tiny["dim_regions"]]
    assert _NAMED_REGIONS <= set(names)
    # One nameless region carries the manifest's null cells, so the five a
    # kit actually shows are never the ones with a missing name.
    assert names.count(None) == 1


def test_schools_spread_across_regions_by_size(tiny: dict[str, list[dict]]) -> None:
    counts = _locations_per_region(tiny)
    assert counts["Network Office"] == 1
    assert (
        counts["Newark Region"]
        > counts["Miami Region"]
        > counts["Camden Region"]
        > counts["Paterson Region"]
        >= 2
    )


def test_the_network_office_enrolls_no_students(tiny: dict[str, list[dict]]) -> None:
    regions = _region_by_key(tiny)
    office = {
        row["location_key"]
        for row in tiny["dim_locations"]
        if regions.get(row["region_key"], {}).get("name") == "Network Office"
    }
    assert office
    for table in (
        "dim_student_enrollments",
        "fct_student_attendance_enrollment_daily",
        "dim_course_sections",
        "dim_school_calendars",
        "dim_terms",
    ):
        assert not {row["location_key"] for row in tiny[table]} & office, table


def test_every_persona_school_sits_in_its_region(tiny: dict[str, list[dict]]) -> None:
    region_of = {
        row["abbreviation"]: row["region_key"] for row in tiny["dim_locations"]
    }
    for person in personas.load(generate.PERSONAS_PATH):
        row = next(
            r
            for r in tiny["dim_staff_cube_access"]
            if r["google_email"] == person.email
        )
        assert (
            region_of[row["location_abbreviation"]] == row["legal_entity_region_key"]
        ), person.email


@pytest.mark.parametrize("profile", ["tiny", "realistic"])
def test_a_region_scoped_teaching_staff_persona_sees_a_teacher(
    profile: str, request: pytest.FixtureRequest
) -> None:
    """Mirror of the staff-pii-teaching_staff policy, evaluated on the rows.

    The policy keeps a work-history row when its location is in the viewer's
    region, its staff member's department group is in the viewer's remit,
    and that staff member's job function is TEACH or TIR. The ROWS canary
    asserts the same thing live; this catches it before a load.
    """
    tiny = request.getfixturevalue(profile)
    access_by_staff = {row["staff_key"]: row for row in tiny["dim_staff_cube_access"]}
    location_by_key = {row["location_key"]: row for row in tiny["dim_locations"]}
    checked = 0
    for person in personas.load(generate.PERSONAS_PATH):
        if (
            person.scopes.get("staff_location_scope") != "region"
            or person.scopes.get("staff_pii_scope") != "teaching_staff"
        ):
            continue
        checked += 1
        me = access_by_staff[
            next(
                r["staff_key"]
                for r in tiny["dim_staff_cube_access"]
                if r["google_email"] == person.email
            )
        ]
        visible = [
            row
            for row in tiny["dim_staff_work_history"]
            if (location := location_by_key.get(row["work_location_key"]))
            and location["region_key"] == me["legal_entity_region_key"]
            and (staff := access_by_staff.get(row["staff_key"]))
            and staff["department_group"] is not None
            and staff["job_function_code"] in ("TEACH", "TIR")
        ]
        assert visible, person.email
    assert checked, "no persona exercises region-scoped teaching_staff"


# -- the realistic profile -------------------------------------------------
#
# `tiny` proves every coverage cell; `realistic` is what an app builder points
# a screen at. Three academic years of students who carry forward a grade at a
# time, at schools whose band matches the grade, with one attendance row per
# calendar day of each stint. Shrunk here so the fixture stays fast: the shape
# is what is under test, not the volume.

_SMALL_STUDENTS_PER_YEAR = 60
_SMALL_STAFF = 60
_BAND = {**dict.fromkeys(range(5), "ES"), **dict.fromkeys(range(5, 9), "MS")}
_BAND |= dict.fromkeys(range(9, 13), "HS")


@pytest.fixture(scope="module")
def realistic() -> dict[str, list[dict]]:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(generate, "REALISTIC_STUDENTS_PER_YEAR", _SMALL_STUDENTS_PER_YEAR)
        patch.setattr(generate, "REALISTIC_STAFF", _SMALL_STAFF)
        return generate.generate(
            snapshot.load(),
            personas.load(generate.PERSONAS_PATH),
            "realistic",
            generate.DEFAULT_SEED,
        )


def _real_stints(data: dict[str, list[dict]]) -> list[dict]:
    """Enrollment rows that describe a real stint.

    Skips the fixtures the coverage contract needs: the planted orphan (its
    student and school resolve to nothing) and the stint carrying the
    required nulls.
    """
    students = {row["student_key"] for row in data["dim_students"]}
    locations = {row["location_key"] for row in data["dim_locations"]}
    return [
        row
        for row in data["dim_student_enrollments"]
        if row["academic_year"] is not None
        and row["student_key"] in students
        and row["location_key"] in locations
    ]


def test_realistic_is_an_accepted_scale() -> None:
    assert generate.row_target("dim_regions", "realistic") == generate.row_target(
        "dim_regions", "tiny"
    )
    assert generate.row_target("dim_dates", "realistic") <= generate.DATE_SPINE_MAX


def test_a_realistic_run_leaves_no_uncovered_cell(
    realistic: dict[str, list[dict]],
) -> None:
    assessed = coverage.assess({"cells": generate.load_cells()}, realistic)
    assert coverage.uncovered(assessed) == []


def test_realistic_enrollments_span_three_academic_years(
    realistic: dict[str, list[dict]],
) -> None:
    target = generate.TARGET_ACADEMIC_YEAR
    years = {row["academic_year"] for row in _real_stints(realistic)}
    assert years == {target - 2, target - 1, target}


def test_realistic_students_per_year_is_about_the_target(
    realistic: dict[str, list[dict]],
) -> None:
    per_year: dict[int, set[str]] = {}
    for row in _real_stints(realistic):
        per_year.setdefault(row["academic_year"], set()).add(row["student_key"])
    for year, students in per_year.items():
        assert abs(len(students) - _SMALL_STUDENTS_PER_YEAR) <= 2, year


def test_realistic_students_advance_one_grade_a_year(
    realistic: dict[str, list[dict]],
) -> None:
    grades: dict[str, dict[int, set[int]]] = {}
    for row in _real_stints(realistic):
        grades.setdefault(row["student_key"], {}).setdefault(
            row["academic_year"], set()
        ).add(row["grade_level"])

    steps = advanced = 0
    for by_year in grades.values():
        for year, grade in by_year.items():
            # A transfer splits a year in two, never across two grades.
            assert len(grade) == 1
            assert 0 <= min(grade) <= max(grade) <= 12
            if year + 1 in by_year:
                steps += 1
                delta = min(by_year[year + 1]) - min(grade)
                assert delta >= 0, "a grade went backwards"
                advanced += delta == 1
    assert steps and advanced / steps >= 0.95

    # Carried across years, not re-drawn each year.
    multi_year = sum(1 for by_year in grades.values() if len(by_year) >= 2)
    assert multi_year / len(grades) >= 0.5


def test_realistic_birth_dates_agree_with_grade_every_year(
    realistic: dict[str, list[dict]],
) -> None:
    born = {
        row["student_key"]: row["birth_date"]
        for row in realistic["dim_students"]
        if row["birth_date"] is not None
    }
    for row in _real_stints(realistic):
        birth = born.get(row["student_key"])
        if birth is None:
            continue
        # Age on 1 September of the year, against the grade's typical age;
        # birth_date_for_grade allows one year either side.
        age = row["academic_year"] - birth.year - (birth.month > 9)
        assert abs(age - (row["grade_level"] + 5)) <= 2, row["grade_level"]


def test_realistic_has_one_stint_per_student_per_year_except_transfers(
    realistic: dict[str, list[dict]],
) -> None:
    by_student_year: dict[tuple[str, int], list[dict]] = {}
    for row in _real_stints(realistic):
        by_student_year.setdefault(
            (row["student_key"], row["academic_year"]), []
        ).append(row)
    transfers = [rows for rows in by_student_year.values() if len(rows) > 1]
    assert transfers, "no mid-year transfer"
    assert len(transfers) / len(by_student_year) <= 0.1
    for rows in transfers:
        assert len(rows) == 2
        first, second = sorted(rows, key=lambda row: row["entry_date_key"])
        assert first["location_key"] != second["location_key"]
        assert first["exit_date_key"] < second["entry_date_key"]


def test_realistic_stints_sit_inside_their_academic_year(
    realistic: dict[str, list[dict]],
) -> None:
    for row in _real_stints(realistic):
        year = row["academic_year"]
        assert generate.dt.date(year, 7, 1) <= row["entry_date_key"]
        assert row["entry_date_key"] <= row["exit_date_key"]
        assert row["exit_date_key"] <= generate.dt.date(year + 1, 6, 30)
        assert row["graduation_year"] == year + 13 - row["grade_level"]
        assert row["year_in_network"] >= 1


def test_realistic_school_band_matches_grade(
    realistic: dict[str, list[dict]],
) -> None:
    location = {row["location_key"]: row for row in realistic["dim_locations"]}
    office = realistic["dim_locations"][generate._OFFICE_LOCATION]["location_key"]
    for row in _real_stints(realistic):
        school = location[row["location_key"]]
        assert row["location_key"] != office
        assert not school["is_campus"]
        assert school["grade_band"] == _BAND[row["grade_level"]]


def test_realistic_students_stay_at_one_school_per_band(
    realistic: dict[str, list[dict]],
) -> None:
    schools: dict[tuple[str, str], set[str]] = {}
    transferred = set()
    for row in _real_stints(realistic):
        key = (row["student_key"], _BAND[row["grade_level"]])
        schools.setdefault(key, set()).add(row["location_key"])
    by_student_year: dict[tuple[str, int], int] = {}
    for row in _real_stints(realistic):
        pair = (row["student_key"], row["academic_year"])
        by_student_year[pair] = by_student_year.get(pair, 0) + 1
        if by_student_year[pair] > 1:
            transferred.add(row["student_key"])
    for (student, _), seen in schools.items():
        if student not in transferred:
            assert len(seen) == 1


def test_realistic_daily_rows_cover_each_stint_exactly(
    realistic: dict[str, list[dict]],
) -> None:
    daily: dict[str, list[dict]] = {}
    for row in realistic["fct_student_attendance_enrollment_daily"]:
        daily.setdefault(row["student_enrollment_key"], []).append(row)
    counts = set()
    for stint in _real_stints(realistic):
        rows = daily.get(stint["student_enrollment_key"], [])
        days = [row["date_key"] for row in rows]
        span = (stint["exit_date_key"] - stint["entry_date_key"]).days + 1
        assert len(days) == len(set(days)) == span
        assert min(days) == stint["entry_date_key"]
        assert max(days) == stint["exit_date_key"]
        assert {row["location_key"] for row in rows} == {stint["location_key"]}
        counts.add(span)
    # Late entrants, early leavers and transfers give students different day
    # counts, which is what separates the two attendance views.
    assert len(counts) > 5


def test_realistic_daily_membership_follows_the_calendar(
    realistic: dict[str, list[dict]],
) -> None:
    calendar = {
        (row["location_key"], row["date_key"]): row
        for row in realistic["dim_school_calendars"]
    }
    stints = {row["student_enrollment_key"] for row in _real_stints(realistic)}
    checked = 0
    for row in realistic["fct_student_attendance_enrollment_daily"]:
        if row["student_enrollment_key"] not in stints:
            continue
        day = calendar[(row["location_key"], row["date_key"])]
        if day["is_membership_day"] is None or row["membership_value"] is None:
            continue
        assert row["membership_value"] == (1.0 if day["is_membership_day"] else 0.0)
        checked += 1
    assert checked


def test_realistic_calendars_cover_every_school_day(
    realistic: dict[str, list[dict]],
) -> None:
    by_location: dict[str, list] = {}
    for row in realistic["dim_school_calendars"]:
        by_location.setdefault(row["location_key"], []).append(row)
    used = {row["location_key"] for row in _real_stints(realistic)}
    assert used <= set(by_location)

    target = generate.TARGET_ACADEMIC_YEAR
    for location in used:
        rows = by_location[location]
        days = [row["date_key"] for row in rows]
        assert len(days) == len(set(days))
        for year in range(target - 2, target + 1):
            start, end = generate.calendar_span(year)
            expected = {
                start + generate.dt.timedelta(days=n)
                for n in range((end - start).days + 1)
            }
            assert expected <= set(days), (location, year)
        for row in rows:
            if row["is_in_session"] and row["date_key"].weekday() >= 5:
                pytest.fail(f"{row['date_key']} is a weekend in session")
    # Holidays, not only weekends, are out of session.
    weekday_off = {
        row["date_key"]
        for row in realistic["dim_school_calendars"]
        if row["is_in_session"] is False and row["date_key"].weekday() < 5
    }
    assert any(day.month == 11 for day in weekday_off)
    assert any(day.month == 12 for day in weekday_off)


def test_realistic_periods_have_one_year_row_per_stint(
    realistic: dict[str, list[dict]],
) -> None:
    year_rows: dict[str, int] = {}
    for row in realistic["fct_student_attendance_enrollment_periods"]:
        if row["period_type"] == "year":
            key = row["student_enrollment_key"]
            year_rows[key] = year_rows.get(key, 0) + 1
    for stint in _real_stints(realistic):
        assert year_rows.get(stint["student_enrollment_key"]) == 1


def test_realistic_sections_give_each_stint_one_homeroom(
    realistic: dict[str, list[dict]],
) -> None:
    sections: dict[str, list[dict]] = {}
    for row in realistic["dim_student_section_enrollments"]:
        sections.setdefault(row["student_enrollment_key"], []).append(row)
    stints = _real_stints(realistic)
    one_homeroom = 0
    for stint in stints:
        rows = sections.get(stint["student_enrollment_key"], [])
        assert len(rows) == generate.REALISTIC_SECTIONS_PER_STINT
        assert all(
            row["academic_year"] in (stint["academic_year"], None) for row in rows
        )
        one_homeroom += sum(1 for row in rows if row["is_homeroom"]) == 1
    # Null planting may take the flag off one row.
    assert one_homeroom >= len(stints) - 1


def test_realistic_scores_fall_inside_their_stint(
    realistic: dict[str, list[dict]],
) -> None:
    section_stint = {
        row["student_section_enrollment_key"]: row["student_enrollment_key"]
        for row in realistic["dim_student_section_enrollments"]
    }
    stints = {row["student_enrollment_key"]: row for row in _real_stints(realistic)}
    per_stint: dict[str, int] = {}
    for row in realistic["fct_assessment_scores_enrollment_scoped"]:
        stint = stints.get(section_stint.get(row["student_section_enrollment_key"]))
        if stint is None:
            continue
        per_stint[stint["student_enrollment_key"]] = (
            per_stint.get(stint["student_enrollment_key"], 0) + 1
        )
        day = row["assessment_date_key"]
        assert stint["entry_date_key"] <= day <= stint["exit_date_key"]
    low, high = generate.REALISTIC_SCORES_PER_STINT
    assert per_stint
    assert all(low <= n <= high for n in per_stint.values())


def test_school_regions_carry_their_production_bands(
    tiny: dict[str, list[dict]],
) -> None:
    # Production: Newark, Miami and Camden run elementary, middle and high
    # schools; Paterson runs elementary and middle only. A region missing a
    # band sends its students to another region's schools, which no real
    # student does.
    regions = {row["region_key"]: row["name"] for row in tiny["dim_regions"]}
    bands: dict[str, set[str]] = {}
    for row in tiny["dim_locations"][1:-1]:
        if row["is_campus"] or row["grade_band"] is None:
            continue
        bands.setdefault(regions.get(row["region_key"]), set()).add(row["grade_band"])
    for name in ("Newark Region", "Miami Region", "Camden Region"):
        assert bands[name] == {"ES", "MS", "HS"}, name
    assert bands["Paterson Region"] == {"ES", "MS"}


def test_realistic_students_stay_in_their_region_below_high_school(
    realistic: dict[str, list[dict]],
) -> None:
    # Only a Paterson high schooler leaves home, because Paterson has no high
    # school. Everyone else attends a school in their own region every year.
    locations = {row["location_key"]: row for row in realistic["dim_locations"]}
    regions_by_student: dict[str, set[str]] = {}
    for row in realistic["dim_student_enrollments"][1:-1]:
        school = locations.get(row["location_key"])
        if school is None or row["grade_level"] is None or row["grade_level"] >= 9:
            continue
        regions_by_student.setdefault(row["student_key"], set()).add(
            school["region_key"]
        )
    assert all(len(r) == 1 for r in regions_by_student.values())
