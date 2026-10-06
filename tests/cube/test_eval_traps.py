"""Unit tests for eval family 4 (src/cube/mcp/eval): traps, scoring, arms and stub."""

import asyncio
import shutil
import sys
import types
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
    # The final-review advice: filter is_mastery with notSet for "no verdict".
    assert not fired([q(filters=[f("is_mastery", "notSet")])], "")
    assert fired([q(filters=[f("is_mastery", values=["null"])])], "")


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
    # A subject in another query does not scope this one.
    assert fired(
        [
            q(filters=[f("module_code", values=["QA3"])]),
            q(
                measures=[f"{V}.pct_proficient"],
                dimensions=[f"{V}.academic_subject"],
            ),
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
    # module_type in another query does not split this one.
    assert fired(
        [
            q(measures=[f"{V}.pct_proficient_formative"]),
            q(measures=[f"{V}.count_scored"], dimensions=[f"{V}.module_type"]),
        ],
        "",
    )
    assert not fired(
        [
            q(
                measures=[f"{V}.pct_proficient_formative"],
                dimensions=[f"{V}.module_type"],
            )
        ],
        "",
    )


def test_most_recent_not_named_round():
    fired = traps.TRAPS["most_recent_not_named_round"]
    assert fired([q(dimensions=[f"{V}.date_taken"])], "")
    assert not fired([q(filters=[f("administration_period", values=["MOY"])])], "")
    # All 3 rounds at once is no scoping, and notEquals keeps the other rounds.
    rounds = ["BOY", "MOY", "EOY"]
    assert fired([q(filters=[f("administration_period", values=rounds)])], "")
    assert fired(
        [q(filters=[f("administration_period", "notEquals", values=["BOY"])])], ""
    )


def test_paterson_zero_as_failure_reads_the_answer():
    fired = traps.TRAPS["paterson_zero_as_failure"]
    assert not fired(
        [], "Paterson has no i-Ready data on this view, so there is nothing to report."
    )
    assert not fired([], "There is a coverage gap for Paterson on this view.")
    # A saved Haiku answer (B4_post, rep 1) reported the gap this way.
    assert not fired(
        [], "Paterson is not showing up in the dataset for this academic year."
    )
    assert fired([], "Paterson's i-Ready math proficiency is 0%.")
    # "coverage" alone is not a coverage report.
    assert fired([], "Coverage looks fine, and Paterson scored 0%.")
    assert fired([], "Coverage is missing for Newark math. Paterson scored 0%.")


@pytest.mark.parametrize(
    "text",
    [
        "Paterson's i-Ready math proficiency was 0% - no students reached grade "
        "level on i-Ready.",
        "Paterson is missing the mark on i-Ready: 0% proficient.",
    ],
)
def test_paterson_zero_read_as_a_result_fires(text):
    assert traps.TRAPS["paterson_zero_as_failure"]([], text)


@pytest.mark.parametrize(
    "text",
    [
        "Paterson schools do not administer i-Ready.",
        "Paterson doesn't use i-Ready.",
        "i-Ready isn't used in Paterson.",
    ],
)
def test_paterson_not_using_iready_does_not_fire(text):
    assert not traps.TRAPS["paterson_zero_as_failure"]([], text)


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


def test_turn_limit_reads_the_sdk_subtype_before_the_error_text():
    base = {"model": "sonnet", "arm": "C4_skill", "family": 4, "trap": "t"}
    base |= {"ground_truth_start": None, "trap_fired": True, "error": "boom"}
    recs = [
        base | {"id": "a", "subtype": "error_max_turns"},
        # A session limit can end on a "success" result with an error raised.
        base | {"id": "b", "subtype": "success"},
        base | {"id": "c", "subtype": "error_during_execution"},
    ]
    cell = scorer.aggregate(recs)[("sonnet", "C4_skill")]
    assert cell["n_trap"] == 1
    assert cell["n_unscored"] == 2


def test_trap_rate_covers_only_prompts_every_arm_scored():
    def rec(arm, pid, fired, error=None):
        return {
            "model": "haiku",
            "arm": arm,
            "id": pid,
            "family": 4,
            "trap": "t",
            "trap_fired": fired,
            "ground_truth_start": None,
            "error": error,
        }

    cutoff = "You've hit your session limit"
    recs = [
        rec("A4_pre", "p1", True),
        rec("A4_pre", "p2", False),
        rec("B4_post", "p1", True),
        # B4_post lost p2 to the session limit: A4_pre's p2 must not count.
        rec("B4_post", "p2", True, error=cutoff),
        # Another model's arms are compared among themselves only.
        rec("A4_pre", "p2", False) | {"model": "sonnet"},
    ]
    summary = scorer.aggregate(recs)
    pre, post = summary[("haiku", "A4_pre")], summary[("haiku", "B4_post")]
    assert pre["trap_rate"][0] == post["trap_rate"][0] == 1.0
    assert pre["k_trap"] == post["k_trap"] == 1
    assert pre["k_dropped"] == 1 and post["k_dropped"] == 0
    assert post["n_unscored"] == 1
    assert summary[("sonnet", "A4_pre")]["k_trap"] == 1
    table = scorer.format_summary(summary)
    assert "drop" in table.splitlines()[0]


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


def _pooled_wilson(k, n):
    """The pre-clustering interval: one Wilson over every record as independent."""
    z = 1.96
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / denom
    return (p, max(0.0, center - half), min(1.0, center + half))


def _trap_cell(fired_by_prompt, reps):
    """Trap records for one cell: each prompt id fires (or not) on every rep."""
    return [
        {
            "model": "haiku",
            "arm": "B4_post",
            "id": pid,
            "rep": rep,
            "family": 4,
            "trap": "t",
            "trap_fired": fired,
            "ground_truth_start": None,
            "error": None,
        }
        for pid, fired in fired_by_prompt.items()
        for rep in range(reps)
    ]


# 7 prompts, as in prompts_assessment.yaml: 3 always fire, 4 never do.
_SPLIT = {f"p{i}": i < 3 for i in range(7)}


def test_more_reps_of_the_same_prompts_do_not_narrow_the_trap_interval():
    def width(reps):
        _, lo, hi = scorer.aggregate(_trap_cell(_SPLIT, reps))[("haiku", "B4_post")][
            "trap_rate"
        ]
        return hi - lo

    # Identical reps add no information about a new prompt, so the width holds.
    assert width(10) == pytest.approx(width(3))
    # The pooled interval treated those 70 records as independent and shrank.
    _, lo_old, hi_old = _pooled_wilson(30, 70)
    assert width(10) > 2 * (hi_old - lo_old)


def test_reps_that_agree_within_a_prompt_widen_the_interval():
    cell = scorer.aggregate(_trap_cell(_SPLIT, 3))[("haiku", "B4_post")]
    p, lo, hi = cell["trap_rate"]
    p_old, lo_old, hi_old = _pooled_wilson(9, 21)
    assert p == p_old
    assert hi - lo > hi_old - lo_old


def test_aggregate_reports_cluster_counts():
    cell = scorer.aggregate(_trap_cell(_SPLIT, 3))[("haiku", "B4_post")]
    assert cell["n_trap"] == 21
    assert cell["k_trap"] == 7


def test_point_rates_match_the_pooled_rate():
    # Uneven reps per prompt: the point rate is still k / n over records.
    recs = _trap_cell({"a": True, "b": False}, 2) + _trap_cell({"c": True}, 5)
    p, _, _ = scorer.aggregate(recs)[("haiku", "B4_post")]["trap_rate"]
    assert p == _pooled_wilson(7, 9)[0]


def test_year_family_rates_cluster_on_prompt_id():
    def rec(pid, wrong, rep):
        return {
            "model": "sonnet",
            "arm": "A",
            "id": pid,
            "rep": rep,
            "family": 1,
            "ground_truth_start": 2025,
            "wrong": wrong,
            "correct": not wrong,
            "no_query": False,
            "silent_wrong": wrong,
            "error": None,
        }

    recs = [rec(f"y{i}", i < 2, rep) for i in range(6) for rep in range(4)]
    cell = scorer.aggregate(recs)[("sonnet", "A")]
    assert cell["k_determinate"] == 6
    p, lo, hi = cell["wrong_rate"]
    _, lo_old, hi_old = _pooled_wilson(8, 24)
    assert p == pytest.approx(1 / 3)
    assert hi - lo > hi_old - lo_old


def test_a_single_prompt_gives_no_interval():
    # One cluster: the between-prompt variance is unestimable.
    cell = scorer.aggregate(_trap_cell({"a": True}, 5))[("haiku", "B4_post")]
    assert cell["trap_rate"] == (1.0, 0.0, 1.0)


def test_t_quantile_matches_published_values():
    # Student-t 0.975 quantiles from standard tables.
    for df, t in [(1, 12.706), (6, 2.447), (20, 2.086), (120, 1.980)]:
        assert scorer._t_inv_cdf(0.975, df) == pytest.approx(t, abs=1e-3)


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


def test_compile_failure_surfaces_stderr(monkeypatch):
    def failing_run(*args, **kwargs):
        raise arms.subprocess.CalledProcessError(
            1, args[0], output="", stderr="Error: unknown member foo"
        )

    monkeypatch.setattr(arms.subprocess, "run", failing_run)
    with pytest.raises(RuntimeError, match="unknown member foo"):
        arms.load_assessment_meta("post")


def test_jobs_interleave_arms_within_each_prompt(monkeypatch, tmp_path):
    """A sweep cut short by a session limit must cut every arm at about the
    same prompt, so the arm varies fastest."""
    order = []

    async def fake_run_one(**kwargs):
        order.append((kwargs["prompt"], kwargs["instructions"]))
        return {"load_queries": [], "final_text": ""}

    # claude-agent-sdk is a runtime --with dep; stand in for its one import.
    sdk = types.ModuleType("claude_agent_sdk")
    sdk.__dict__["create_sdk_mcp_server"] = lambda **kw: None
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", sdk)
    monkeypatch.setattr(run_eval_cc, "run_one", fake_run_one)
    monkeypatch.setattr(run_eval_cc, "_make_tools", lambda *a: {})
    monkeypatch.setattr(run_eval_cc, "_arm_tool_names", lambda name: [])
    arm_defs = {a: {"instructions": a} for a in ("A4_pre", "B4_post")}
    prompts = [
        {"id": p, "family": 4, "trap": "formative_alone", "prompt": p}
        for p in ("p1", "p2")
    ]
    asyncio.run(
        run_eval_cc.sweep(
            arm_defs=arm_defs,
            arm_names=["A4_pre", "B4_post"],
            models=["haiku"],
            prompts=prompts,
            reps=1,
            concurrency=1,
            tool_desc_by_arm={a: {} for a in arm_defs},
            out_path=tmp_path / "out.jsonl",
            server=None,
        )
    )
    assert order == [
        ("p1", "A4_pre"),
        ("p1", "B4_post"),
        ("p2", "A4_pre"),
        ("p2", "B4_post"),
    ]


def test_strip_sentences_raises_when_a_sentence_is_missing():
    with pytest.raises(RuntimeError):
        arms._strip_sentences("some docstring", ["a sentence that is not there"])


def test_dry_run_handles_an_arm_with_no_year_members(capsys):
    """Family 4 catalogs carry no academic-year members; a dry run must not
    crash on them."""
    arm = {
        "instructions": "system prompt",
        "tools": [
            {"name": n, "description": f"{n} tool"} for n in ("meta", "load", "sql")
        ],
        "meta": {"cubes": []},
    }
    run_eval_cc.do_dry_run({"B4_post": arm}, ["B4_post"], [{"id": "p"}])
    assert "=== B4_post ===" in capsys.readouterr().out


def test_stub_load_empties_paterson_and_notes_it_only_on_drained_arms():
    server = arms.load_server()
    paterson = q(
        measures=[f"{V}.pct_proficient"],
        filters=[f("region_name", values=["Paterson"])],
    )
    newark = q(
        measures=[f"{V}.pct_proficient"], filters=[f("region_name", values=["Newark"])]
    )
    # Measure-only: Cube's empty slice is 1 row of nulls, one key per measure.
    null_row = {"data": [{f"{V}.pct_proficient": None}]}
    drained = run_eval_cc._stub_load(paterson, {"empty_note": True}, server)
    assert drained == null_row | {"note": server.EMPTY_RESULT_NOTE}
    pre = run_eval_cc._stub_load(paterson, {"empty_note": False}, server)
    assert pre == null_row
    # Grouped by a dimension: no rows.
    by_subject = paterson | {"dimensions": [f"{V}.academic_subject"]}
    drained = run_eval_cc._stub_load(by_subject, {"empty_note": True}, server)
    assert drained["data"] == [] and drained["note"] == server.EMPTY_RESULT_NOTE
    pre = run_eval_cc._stub_load(by_subject, {"empty_note": False}, server)
    assert pre == {"data": []}
    assert run_eval_cc._stub_load(newark, {"empty_note": True}, server)["data"]
    assert "note" not in run_eval_cc._stub_load(newark, {"empty_note": True}, server)
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
