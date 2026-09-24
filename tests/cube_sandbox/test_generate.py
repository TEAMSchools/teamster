from __future__ import annotations

import random

import pytest

from teamster.cube_sandbox import generate


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
