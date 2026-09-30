"""Unit tests for eval family 4 (src/cube/mcp/eval): traps, scoring, arms and stub."""

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "src" / "cube" / "mcp" / "eval")
)

# trunk-ignore(pyright/reportMissingImports): eval modules load from src/cube/mcp/eval via sys.path
import arms  # noqa: E402

# trunk-ignore(pyright/reportMissingImports): eval modules load from src/cube/mcp/eval via sys.path
import run_eval_cc  # noqa: E402

# trunk-ignore(pyright/reportMissingImports): eval modules load from src/cube/mcp/eval via sys.path
import scorer  # noqa: E402

# trunk-ignore(pyright/reportMissingImports): eval modules load from src/cube/mcp/eval via sys.path
import traps  # noqa: E402

V = "student_assessment_scores_view"


def q(**kw):
    return {
        "measures": kw.get("measures", []),
        "dimensions": kw.get("dimensions", []),
        "filters": kw.get("filters", []),
    }


def f(member, operator="equals", values=None):
    out = {"member": f"{V}.{member}", "operator": operator}
    if values is not None:
        out["values"] = values
    return out


def test_grade_filter_on_vendor():
    fired = traps.TRAPS["grade_filter_on_vendor"]
    assert fired([q(filters=[f("grade_level_tested", values=["3"])])], "")
    assert not fired([q(filters=[f("grade_level", values=["3"])])], "")


def test_null_via_equals():
    fired = traps.TRAPS["null_via_equals"]
    assert fired([q(filters=[f("proficiency_level", values=["null"])])], "")
    assert not fired([q(filters=[f("proficiency_level", "notSet")])], "")


def test_module_code_without_subject():
    fired = traps.TRAPS["module_code_without_subject"]
    assert fired([q(filters=[f("module_code", values=["QA3"])])], "")
    assert not fired(
        [
            q(
                filters=[
                    f("module_code", values=["QA3"]),
                    f("academic_subject", values=["Mathematics"]),
                ]
            )
        ],
        "",
    )


def test_internal_flag_for_source():
    fired = traps.TRAPS["internal_flag_for_source"]
    assert fired([q(filters=[f("is_internal_assessment", values=["false"])])], "")
    assert not fired(
        [q(filters=[f("assessment_type", values=["iready", "dibels", "star"])])], ""
    )


def test_formative_alone():
    fired = traps.TRAPS["formative_alone"]
    assert fired([q(measures=[f"{V}.pct_proficient_formative"])], "")
    assert not fired(
        [q(measures=[f"{V}.pct_proficient"], dimensions=[f"{V}.module_type"])], ""
    )


def test_most_recent_not_named_round():
    fired = traps.TRAPS["most_recent_not_named_round"]
    assert fired([q(dimensions=[f"{V}.date_taken"])], "")
    assert not fired([q(filters=[f("administration_period", values=["MOY"])])], "")


def test_paterson_zero_as_failure_reads_the_answer():
    fired = traps.TRAPS["paterson_zero_as_failure"]
    assert not fired(
        [], "Paterson has no i-Ready data on this view, so there is nothing to report."
    )
    assert fired([], "Paterson's i-Ready math proficiency is 0%.")


def test_is_paterson_query_matches_only_paterson():
    assert traps.is_paterson_query(q(filters=[f("region_name", values=["Paterson"])]))
    assert not traps.is_paterson_query(q(filters=[f("region_name", values=["Newark"])]))
    assert not traps.is_paterson_query(q(measures=[f"{V}.pct_proficient"]))


def test_score_record_scores_a_trap_prompt_on_view_queries_only():
    prompt = {"id": "p", "family": 4, "trap": "internal_flag_for_source"}
    attendance = {
        "measures": ["student_attendance_enrollment_daily_view.count_students"],
        "filters": [
            {
                "member": "x.is_internal_assessment",
                "operator": "equals",
                "values": ["true"],
            }
        ],
    }
    clean = {
        "measures": [f"{V}.pct_proficient"],
        "filters": [f("assessment_type", values=["iready"])],
    }
    rec = scorer.score_record(
        prompt, {"load_queries": [attendance, clean], "final_text": ""}
    )
    assert rec["trap"] == "internal_flag_for_source"
    assert rec["trap_fired"] is False


def test_aggregate_reports_a_trap_rate():
    recs = [
        {
            "model": "haiku",
            "arm": "B4_post",
            "id": "a",
            "family": 4,
            "trap": "t",
            "trap_fired": True,
            "ground_truth_start": None,
            "error": None,
        },
        {
            "model": "haiku",
            "arm": "B4_post",
            "id": "b",
            "family": 4,
            "trap": "t",
            "trap_fired": False,
            "ground_truth_start": None,
            "error": None,
        },
    ]
    cell = scorer.aggregate(recs)[("haiku", "B4_post")]
    assert cell["trap_rate"][0] == 0.5


def test_aggregate_drops_harness_errors_but_keeps_turn_limits():
    base = {"model": "sonnet", "arm": "C4_skill", "family": 4, "trap": "t"}
    base |= {"ground_truth_start": None}
    recs = [
        base | {"id": "a", "trap_fired": False, "error": None},
        # Ran out of turns: its queries were captured, so it still scores.
        base
        | {
            "id": "b",
            "trap_fired": True,
            "error": "Reached maximum number of turns (12)",
        },
        # Cut off by the harness: no queries, so the trap "fires" on nothing.
        base
        | {"id": "c", "trap_fired": True, "error": "You've hit your session limit"},
    ]
    cell = scorer.aggregate(recs)[("sonnet", "C4_skill")]
    assert cell["n_trap"] == 2
    assert cell["trap_rate"][0] == 0.5
    assert cell["n_unscored"] == 1


def test_a_query_trap_with_no_view_query_is_not_scored():
    # With no query, 4 of the 6 query predicates read a pass and 2 a fire,
    # so neither outcome means anything. The answer-scored trap still scores.
    query_trap = {"id": "q", "family": 4, "trap": "formative_alone"}
    answer_trap = {"id": "a", "family": 4, "trap": "paterson_zero_as_failure"}
    empty = {"load_queries": [], "final_text": "Paterson has no i-Ready data."}
    recs = [
        scorer.score_record(p, empty) | {"model": "haiku", "arm": "C4_skill"}
        for p in (query_trap, answer_trap)
    ]
    assert recs[0]["n_view_queries"] == 0
    cell = scorer.aggregate(recs)[("haiku", "C4_skill")]
    assert cell["n_trap"] == 1
    assert cell["n_unscored"] == 1
    assert cell["trap_rate"][0] == 0.0


_COMPILER = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "cube"
    / "node_modules"
    / "@cubejs-backend"
    / "schema-compiler"
)


@pytest.mark.skipif(
    not _COMPILER.exists() or shutil.which("node") is None,
    reason="Cube node_modules not installed (npm ci in src/cube)",
)
def test_assessment_arms_differ_only_where_intended():
    built = arms.build_assessment_arms(arms.load_server())
    assert set(built) == {"A4_pre", "B4_post", "C4_skill"}
    pre_load = next(t for t in built["A4_pre"]["tools"] if t["name"] == "load")
    post_load = next(t for t in built["B4_post"]["tools"] if t["name"] == "load")
    for sentence in arms.NEW_LOAD_SENTENCES:
        assert sentence not in pre_load["description"]
        assert sentence in post_load["description"]
    assert "ai_context" not in str(built["A4_pre"]["meta"])
    assert "ai_context" in str(built["B4_post"]["meta"])
    assert built["A4_pre"]["empty_note"] is False
    assert built["B4_post"]["empty_note"] is True
    assert "Flag, don't invent" in built["C4_skill"]["instructions"]
    assert "Session log" not in built["C4_skill"]["instructions"]


def test_strip_sentences_raises_when_a_sentence_is_missing():
    with pytest.raises(RuntimeError):
        arms._strip_sentences("some docstring", ["a sentence that is not there"])


def test_stub_load_empties_paterson_and_notes_it_only_on_drained_arms():
    server = arms.load_server()
    paterson = q(
        measures=[f"{V}.pct_proficient"],
        filters=[f("region_name", values=["Paterson"])],
    )
    newark = q(
        measures=[f"{V}.pct_proficient"], filters=[f("region_name", values=["Newark"])]
    )
    drained = run_eval_cc._stub_load(paterson, {"empty_note": True}, server)
    assert drained["data"] == [] and drained["note"] == server.EMPTY_RESULT_NOTE
    pre = run_eval_cc._stub_load(paterson, {"empty_note": False}, server)
    assert pre == {"data": []}
    assert run_eval_cc._stub_load(newark, {"empty_note": True}, server)["data"]
    attendance = {
        "measures": ["student_attendance_enrollment_daily_view.count_students"]
    }
    assert run_eval_cc._stub_load(attendance, {}, server) == run_eval_cc._LOAD_RESULT


def test_stub_load_rows_follow_the_query():
    server = arms.load_server()
    by_subject = q(
        measures=[f"{V}.pct_proficient"],
        dimensions=[f"{V}.academic_subject"],
        filters=[f("assessment_type", values=["iready"])],
    )
    by_round = q(
        measures=[f"{V}.count_scored"],
        dimensions=[f"{V}.administration_period"],
        filters=[f("assessment_type", values=["iready"])],
    )
    a = run_eval_cc._stub_load(by_subject, {"empty_note": True}, server)
    b = run_eval_cc._stub_load(by_round, {"empty_note": True}, server)
    assert a != b
    assert a == run_eval_cc._stub_load(by_subject, {"empty_note": True}, server)
    assert all(f"{V}.academic_subject" in row for row in a["data"])
    assert all(f"{V}.pct_proficient" in row for row in a["data"])
    assert {row[f"{V}.administration_period"] for row in b["data"]} <= {
        "BOY",
        "MOY",
        "EOY",
    }


def test_sql_stub_does_not_look_like_an_access_denial():
    sql = run_eval_cc._SQL_RESULT["sql"]["sql"][0]
    assert "SELECT 1" not in sql and "1 = 0" not in sql
