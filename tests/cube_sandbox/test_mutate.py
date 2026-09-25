from __future__ import annotations

from pathlib import Path

import pytest
import yaml

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


def test_an_empty_run_does_not_report_a_perfect_score() -> None:
    # `uncaught_ratio: 0.0` on a run that mutated nothing reads as 100%
    # caught. exit_code fails it, but the JSON travels separately — it is
    # what gets attached to a kit release.
    result = mutate.report({})
    assert result["mutations"] == 0
    assert result["uncaught_ratio"] is None
    assert "NOT MEASURED" in result["verdict"]
    assert mutate.exit_code({}) == 1


def test_a_measured_run_states_its_verdict_in_words_too() -> None:
    assert mutate.report({"a": True, "b": False})["verdict"] == (
        "1 of 2 mutations uncaught"
    )


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


def test_the_committed_model_yields_one_mutation_per_policy() -> None:
    # Enumerated from the committed views, not hand-listed: a new
    # access_policy block becomes a new mutation nobody has to remember.
    mutations = mutate.policy_mutations(Path("src/cube"))

    assert mutations, "the model declares access policies; none were enumerated"
    assert len({m.name for m in mutations}) == len(mutations)
    for mutation in mutations:
        assert mutation.relative_path.parts[:2] == ("model", "views")


def test_a_mutation_drops_exactly_one_policy() -> None:
    mutations = mutate.policy_mutations(Path("src/cube"))
    by_file: dict[Path, list[mutate.Mutation]] = {}
    for mutation in mutations:
        by_file.setdefault(mutation.relative_path, []).append(mutation)

    for relative, group in by_file.items():
        original = yaml.safe_load(
            (Path("src/cube") / relative).read_text(encoding="utf-8")
        )
        before = sum(
            len(view.get("access_policy", [])) for view in original.get("views", [])
        )
        for mutation in group:
            after_doc = yaml.safe_load(mutation.mutated_text)
            after = sum(
                len(view.get("access_policy", []))
                for view in after_doc.get("views", [])
            )
            assert after == before - 1


def test_run_applies_each_mutation_and_restores_the_file(tmp_path: Path) -> None:
    served = tmp_path / "model" / "views"
    served.mkdir(parents=True)
    target = served / "v.yml"
    target.write_text("original", encoding="utf-8")
    seen: list[str] = []

    def canaries() -> int:
        seen.append(target.read_text(encoding="utf-8"))
        return 1

    caught = mutate.run(
        [
            mutate.Mutation("drop a", Path("model/views/v.yml"), "mutated-a"),
            mutate.Mutation("drop b", Path("model/views/v.yml"), "mutated-b"),
        ],
        tmp_path,
        canaries,
        settle=0.0,
    )

    assert seen == ["mutated-a", "mutated-b"]
    assert caught == {"drop a": True, "drop b": True}
    # Leaving a mutated policy behind in a served model tree is worse than
    # any score this produces.
    assert target.read_text(encoding="utf-8") == "original"


def test_a_mutation_no_canary_notices_is_reported_uncaught(tmp_path: Path) -> None:
    # A canary that still passes with its policy deleted proves nothing, and
    # a suite of those reports confidence nobody earned.
    served = tmp_path / "model" / "views"
    served.mkdir(parents=True)
    (served / "v.yml").write_text("original", encoding="utf-8")

    caught = mutate.run(
        [mutate.Mutation("drop a", Path("model/views/v.yml"), "mutated")],
        tmp_path,
        lambda: 0,
        settle=0.0,
    )

    assert caught == {"drop a": False}
    assert mutate.exit_code(caught) == 1
    assert mutate.report(caught)["uncaught"] == ["drop a"]


def test_the_file_is_restored_even_when_the_runner_raises(tmp_path: Path) -> None:
    served = tmp_path / "model" / "views"
    served.mkdir(parents=True)
    target = served / "v.yml"
    target.write_text("original", encoding="utf-8")

    def explode() -> int:
        raise RuntimeError("the deployment went away mid-run")

    with pytest.raises(RuntimeError):
        mutate.run(
            [mutate.Mutation("drop a", Path("model/views/v.yml"), "mutated")],
            tmp_path,
            explode,
            settle=0.0,
        )

    assert target.read_text(encoding="utf-8") == "original"


def test_the_runner_refuses_to_guess_a_deployment(monkeypatch: pytest.MonkeyPatch):
    for name in (mutate.MODEL_DIR, mutate.SQL_HOST, mutate.SQL_PASSWORD):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(SystemExit, match=mutate.MODEL_DIR):
        mutate.main([])
