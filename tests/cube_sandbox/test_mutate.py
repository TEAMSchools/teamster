from __future__ import annotations

from teamster.cube_sandbox import mutate


def test_every_mutation_caught_is_zero_uncaught() -> None:
    assert mutate.uncaught_ratio([True, True, True]) == 0.0


def test_an_uncaught_mutation_is_reported() -> None:
    # A canary that would still pass with the policy deleted proves nothing.
    assert mutate.uncaught_ratio([True, False]) == 0.5


def test_no_mutations_is_not_a_zero_ratio_pass() -> None:
    # An empty measurement is not a passing one: a run that perturbed
    # nothing has said nothing about whether the canaries are load-bearing.
    assert mutate.uncaught_ratio([]) == 0.0
    assert mutate.exit_code({}) == 1


def test_uncaught_mutations_are_named_not_just_counted() -> None:
    # A percentage says how bad it is; the names say which policy or persona
    # scope no canary actually exercises.
    assert mutate.uncaught(
        {
            "staff-pii-teaching_staff": True,
            "student-network": False,
            "staff-pii-reporting_chain": False,
        }
    ) == ["staff-pii-reporting_chain", "student-network"]


def test_a_surviving_mutant_fails_by_default() -> None:
    # The spec asks for at least one canary to flip red for EACH
    # perturbation, so the default threshold is zero survivors.
    assert mutate.exit_code({"a": True, "b": False}) == 1
    assert mutate.exit_code({"a": True, "b": True}) == 0


def test_a_threshold_can_be_raised_deliberately() -> None:
    assert mutate.exit_code({"a": True, "b": False}, threshold=0.5) == 0
    assert mutate.exit_code({"a": True, "b": False}, threshold=0.49) == 1


def test_report_carries_both_the_count_and_the_names() -> None:
    result = mutate.report({"a": True, "b": False})
    assert result["mutations"] == 2
    assert result["uncaught"] == ["b"]
    assert result["uncaught_ratio"] == 0.5
