import json
from datetime import datetime, timedelta, timezone

import pytest
from cube_validation.answers import (
    Answer,
    AnswerError,
    HandCheck,
    approved_decisions,
    example_cell,
    hand_check,
    note_refusal,
    parse_answers,
    questions_json,
)
from cube_validation.compare import CellDiff, Group
from cube_validation.config import ColumnPair, Comparison, Decision, ViewConfig
from cube_validation.decisions import Applied
from cube_validation.moment import Build
from cube_validation.report import RunResult, render_review_issue

START = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 27, 6, 5, tzinfo=timezone.utc)
DIMS = [["regions_region_name", "Newark"], ["grade_level", "7"]]


def _cell(key="a", dashboard=10.0, cube=12.0, n=30, dims=DIMS):
    return {
        "comparison": "enrollment",
        "cut": "All",
        "key": key,
        "dims": dims,
        "dashboard": dashboard,
        "cube": cube,
        "n_students": n,
    }


def _run(cells):
    return RunResult(
        view="enrollment",
        moment=Build(start=START, end=END, job_id="j"),
        measures=[],
        applied=Applied(),
        diff_cells=cells,
        cell_sql={"enrollment": {"All": ["SELECT 1 AS d", "SELECT 2 AS c"]}},
        cell_sql_usd={"enrollment": {"All": [0.01, 0.02]}},
    )


def _cfg(dashboard_region="regions_region_name"):
    cmp = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[
            ColumnPair(dashboard_region, "regions_region_name"),
            ColumnPair("grade_level", "grade_level"),
        ],
    )
    return ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])


def test_example_cell_is_biggest_difference_with_reviewed_dims_only():
    run = _run([_cell("a", 10, 12), _cell("b", 10, 20), _cell("c", 10, 15)])

    assert example_cell(run, "enrollment")["key"] == "b"


def test_example_cell_ties_go_to_the_lowest_key():
    run = _run([_cell("b", 10, 20), _cell("a", 10, 20)])

    assert example_cell(run, "enrollment")["key"] == "a"


def test_example_cell_skips_cells_under_10_students():
    run = _run([_cell("small", 10, 99, n=9), _cell("none", 10, 98, n=None)])
    assert example_cell(run, "enrollment") is None

    run = _run([_cell("small", 10, 99, n=9), _cell("ok", 10, 12, n=10)])
    assert example_cell(run, "enrollment")["key"] == "ok"


def test_example_cell_skips_a_teacher_or_student_dim():
    run = _run([_cell(dims=[["teacher_name", "x"]])])

    assert example_cell(run, "enrollment") is None


def test_no_example_cell_returns_none():
    run = _run([])

    assert example_cell(run, "enrollment") is None
    assert hand_check(run, _cfg(), "enrollment", START) is None


def test_hand_check_sql_filters_to_the_example_cell():
    check = hand_check(_run([_cell()]), _cfg(), "enrollment", START)

    assert isinstance(check, HandCheck)
    want = (
        "WHERE regions_region_name = 'Newark' AND SAFE_CAST(grade_level AS NUMERIC) = 7"
    )
    assert check.dashboard_sql == f"SELECT * FROM (\nSELECT 1 AS d\n) {want}"
    assert check.cube_sql == f"SELECT * FROM (\nSELECT 2 AS c\n) {want}"
    assert (check.dashboard, check.cube) == (10.0, 12.0)
    assert (check.dashboard_usd, check.cube_usd) == (0.01, 0.02)


def test_hand_check_filters_the_dashboard_side_by_its_own_column_names():
    check = hand_check(_run([_cell()]), _cfg("Region"), "enrollment", START)

    assert check.dashboard_sql.endswith(
        "WHERE Region = 'Newark' AND SAFE_CAST(grade_level AS NUMERIC) = 7"
    )
    assert check.cube_sql.endswith(
        "WHERE regions_region_name = 'Newark' AND SAFE_CAST(grade_level AS NUMERIC) = 7"
    )


def test_hand_checks_expire_after_7_days():
    run = _run([_cell()])
    expires = START + timedelta(days=7)

    before = hand_check(run, _cfg(), "enrollment", expires - timedelta(seconds=1))
    at = hand_check(run, _cfg(), "enrollment", expires)

    assert before.expires == expires and not before.expired
    assert at.expired


def _where(dims):
    check = hand_check(_run([_cell(dims=dims)]), _cfg_for(dims), "enrollment", START)
    return check.cube_sql.split(") WHERE ", 1)[1]


def _cfg_for(dims):
    cmp = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[ColumnPair(m, m) for m, _ in dims],
    )
    return ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])


def test_typed_dims_get_predicates_valid_for_their_column_type():
    # Keys are `pipeline._key` text: '7', 'True', '' and an ISO date.
    assert _where([["regions_region_name", "1.50"]]) == (
        "SAFE_CAST(regions_region_name AS NUMERIC) = 1.5"
    )
    assert _where([["regions_region_name", "True"]]) == (
        "LOWER(CAST(regions_region_name AS STRING)) = 'true'"
    )
    assert _where([["regions_region_name", ""]]) == "regions_region_name IS NULL"
    assert _where([["regions_region_name", "2026-01-05"]]) == (
        "regions_region_name = '2026-01-05'"
    )


def test_a_total_cell_with_no_dims_is_an_example_and_keeps_the_sql():
    run = _run([_cell(dims=[])])
    cfg = ViewConfig(
        view="enrollment",
        fact="d.t",
        comparisons=[Comparison(id="enrollment", measure="student_count")],
    )

    check = hand_check(run, cfg, "enrollment", START)

    assert check.dashboard_sql == "SELECT 1 AS d"
    assert check.cube_sql == "SELECT 2 AS c"


def test_a_trailing_comment_cannot_swallow_the_closing_paren():
    run = _run([_cell()])
    run.cell_sql["enrollment"]["All"] = ["SELECT 1 -- note", "SELECT 2"]

    check = hand_check(run, _cfg(), "enrollment", START)

    assert "-- note\n) WHERE" in check.dashboard_sql


# --- questions_json ----------------------------------------------------------

REASON = "Registrar owns the rule"


def _owner_run(diff_cells, measure_cells=3):
    def group_decision(id, value):
        return Decision(
            id, "enrollment", "domain_owner", f"{REASON} (1234567)",
            {"column": "region", "values": [value]},
        )  # fmt: skip

    cells = Decision("c1", "enrollment", "domain_owner", "Codes differ?", cells=True)
    applied = Applied(
        quiet=[
            (group_decision("d-newark", "Newark"),
             Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)),
            (group_decision("d-camden", "Camden"),
             Group("enrollment", (("region", "Camden"),), "value_differs", 5, 5)),
        ],
        quiet_cells=[(cells, CellDiff("enrollment", {"differs": measure_cells}))],
    )  # fmt: skip
    run = _run(diff_cells)
    run.applied = applied
    return run


TRIAGE = {
    "enrollment": {
        "view": "enrollment",
        "items": [
            {
                "id": "enrollment:region=<redacted>",
                "kind": "group",
                "comparison": "enrollment",
                "label": "x",
                "stub": {
                    "comparison": "enrollment",
                    "group": {"column": "region", "values": ["Camden"]},
                },
                "suggestion": "owner",
                "evidence": ["note on Camden, student 1234567"],
                "candidates": [],
            },
            {
                "id": "enrollment:cells",
                "kind": "cells",
                "comparison": "enrollment",
                "label": "y",
                "stub": {"comparison": "enrollment", "cells": True},
                "suggestion": "owner",
                "evidence": ["no description or ai_context answers it"],
                "candidates": [],
            },
            {
                "id": "other:cells",
                "kind": "cells",
                "comparison": "other",
                "label": "z",
                "stub": {"comparison": "other", "cells": True},
                "suggestion": "owner",
                "evidence": ["UNRELATED"],
                "candidates": [],
            },
        ],
    }
}
DEFS = {"enrollment": {"enrollment": {"dashboard": "codes ET, T", "cube": "codes T%"}}}


def _questions(run, cfg=None, triage=TRIAGE):
    return questions_json([run], [cfg or _cfg()], DEFS, triage, START)


def test_questions_json_matches_markdown_questions_one_to_one():
    run = _owner_run([_cell()])
    questions = _questions(run)
    body = render_review_issue("Registrar", [run], DEFS, questions)
    bullets = [x for x in body.split("## Proposed")[0].splitlines() if "Reason:" in x]

    assert [q["id"] for q in questions] == ["Q1", "Q2"]
    assert len(bullets) == len(questions)
    for q, bullet in zip(questions, bullets):
        assert bullet.startswith(f"- {q['id']}. ")
        assert all(count in bullet for count in q["counts"])
        assert f"Reason: {q['reason']}" in bullet
    assert questions[0]["decisions"] == ["d-newark", "d-camden"]
    assert questions[1]["decisions"] == ["c1"]
    assert questions[0]["views"] == ["enrollment"]
    assert questions[0]["definitions"] == {
        "dashboard": ["`enrollment` in `enrollment`: codes ET, T"],
        "cube": ["`enrollment` in `enrollment`: codes T%"],
    }
    assert questions[0]["evidence"] == ["note on <redacted>, student <redacted>"]
    assert questions[1]["evidence"] == ["no description or ai_context answers it"]
    assert questions[0]["moment"] == {
        "start": START.isoformat(),
        "end": END.isoformat(),
        "job_id": "j",
    }
    assert questions[0]["expires"] == (START + timedelta(days=7)).isoformat()
    assert questions[0]["expired"] is False
    check = questions[0]["hand_checks"][0]
    assert check["comparison"] == "enrollment" and check["view"] == "enrollment"
    assert check["dims"] == [["regions_region_name", "Newark"], ["grade_level", "7"]]
    assert (check["dashboard"], check["cube"]) == ("10", "12")
    assert check["cube_sql"].endswith("SAFE_CAST(grade_level AS NUMERIC) = 7")
    assert (check["dashboard_usd"], check["cube_usd"]) == (0.01, 0.02)


def test_questions_json_hides_what_the_markdown_hides():
    cmp = Comparison(
        id="enrollment",
        measure="count_tardies",
        dims=[
            ColumnPair("regions_region_name", "regions_region_name"),
            ColumnPair("grade_level", "grade_level"),
        ],
    )
    cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])
    run = _owner_run([_cell(dashboard=7.0, cube=12.0)])

    text = json.dumps(_questions(run, cfg))

    # Camden's group has 5 students, so its value and its counts stay hidden.
    assert "Camden" not in text and "1234567" not in text
    assert "UNRELATED" not in text
    assert "<10 cells differ" in text and "3 cells" not in text
    assert "45 rows" in text and " 5 rows" not in text
    # A count measure's value under 10 is masked like any count.
    check = _questions(run, cfg)[0]["hand_checks"][0]
    assert (check["dashboard"], check["cube"]) == ("<10", "12")
    assert "stub" not in text


def test_question_without_example_cell_says_find_one_locally():
    run = _owner_run([_cell(n=9)])
    questions = _questions(run, triage={})

    assert questions[0]["hand_checks"] == [
        {
            "view": "enrollment",
            "comparison": "enrollment",
            "none": "no group cell with 10+ students differs; find an example "
            "under your own access",
        }
    ]
    assert questions[0]["evidence"] == []
    body = render_review_issue("Registrar", [run], DEFS, questions)
    assert "no group cell with 10+ students differs" in body.split("<details>")[0]


def test_hand_check_values_under_10_are_masked_whatever_the_measure():
    for measure in ("tardies", "student_count"):
        cmp = Comparison(
            id="enrollment",
            measure=measure,
            dims=[
                ColumnPair("regions_region_name", "regions_region_name"),
                ColumnPair("grade_level", "grade_level"),
            ],
        )
        cfg = ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])
        run = _owner_run([_cell(dashboard=7.0, cube=12.0)])

        questions = _questions(run, cfg)
        check = questions[0]["hand_checks"][0]

        assert (check["dashboard"], check["cube"]) == ("<10", "12"), measure
        body = render_review_issue("Registrar", [run], DEFS, questions)
        assert "the dashboard shows <10, Cube shows 12" in body

    # A rate is no count: it prints as it is.
    run = _owner_run([_cell(dashboard=7.5, cube=0.25)])
    check = _questions(run)[0]["hand_checks"][0]
    assert (check["dashboard"], check["cube"]) == ("7.5", "0.25")


def _body(*blocks):
    fenced = "".join(f"```json\n{json.dumps(b)}\n```\n\n" for b in blocks)
    return "## Answers\n\nQ1: the dashboard is right.\n\n" + fenced


def test_parse_answers_reads_the_one_json_block():
    body = _body(
        [
            {
                "question": "Q1",
                "decisions": ["a", "b"],
                "call": "fix_cube",
                "note": "the fact drops them",
            },
            {
                "question": "Q2",
                "decisions": ["c"],
                "call": "fix_source",
                "note": "Miami entered tardies wrong",
                "task": "#9001",
            },
        ]  # fmt: skip
    )

    assert parse_answers(body) == [
        Answer("Q1", ("a", "b"), "fix_cube", "the fact drops them"),
        Answer("Q2", ("c",), "fix_source", "Miami entered tardies wrong", "#9001"),
    ]


@pytest.mark.parametrize(
    "body, match",
    [
        ("no block here", "1 fenced json block"),
        (_body([], []), "1 fenced json block"),
        (
            _body(
                [{"question": "Q1", "decisions": ["a"], "call": "fix_it", "note": ""}]
            ),
            "fix_it",
        ),  # fmt: skip
        (
            _body(
                [
                    {
                        "question": "Q1",
                        "decisions": ["a"],
                        "call": "fix_source",
                        "note": "n",
                    }
                ]
            ),
            "fix_source needs a task",
        ),  # fmt: skip
        (
            _body(
                [
                    {
                        "question": "Q1",
                        "decisions": ["a"],
                        "call": "fix_source",
                        "note": "n",
                        "task": "ask Ana",
                    }
                ]
            ),
            "https://",
        ),  # fmt: skip
        (
            _body(
                [{"question": "Q1", "decisions": [], "call": "deliberate", "note": "n"}]
            ),
            "decision id",
        ),  # fmt: skip
        (_body({"question": "Q1"}), "list"),
        (_body([]), "at least 1 answer"),
        ("```json\n{not json\n```", "not JSON"),
    ],
)
def test_parse_answers_refuses(body, match):
    with pytest.raises(AnswerError, match=match):
        parse_answers(body)


@pytest.mark.parametrize(
    "note",
    [
        "ask jane.doe@example.org",
        "student 1234567 was missed",
        "call 555-123-4567",
        "ids 12 34 56",
        "973-555-1234",
        "(973) 555 1234",
        "12 345",
        "1234567",
    ],
)
def test_note_refusal_catches_emails_and_digit_runs(note):
    assert note_refusal(note)


@pytest.mark.parametrize(
    "note",
    [
        "checked on 2026-10-27, Cube is right",
        "grade 9 only",
        "",
        "grades 9, 10, 11",
        "since SY 2023-24",
        "Cube 93.25 vs 93.10",
        "rate 100.0%",
    ],
)
def test_note_refusal_lets_dates_and_small_numbers_through(note):
    assert note_refusal(note) is None


TRIAGE = {
    "items": [
        {"id": "ada:region=Miami", "stub": {"comparison": "ada",
         "group": {"column": "regions_region_name", "values": ["Miami"]}}},
        {"id": "cut:Team", "stub": {"missing_cut": "Team"}},
        {"id": "ada:cells", "stub": {"comparison": "ada", "cells": True}},
    ]
}  # fmt: skip
FPS = {"ada": {"cube": "c1", "dashboard": "d1"}}


def test_approved_decisions_take_the_stub_and_the_run_fingerprints():
    approved = [
        {"id": "miami", "call": "fix_cube", "reason": "r1", "task": "#1",
         "item": "ada:region=Miami"},
        {"id": "team", "call": "deliberate", "reason": "r2", "task": "",
         "item": "cut:Team"},
        {"id": "cells", "call": "domain_owner", "reason": "r3", "item": "ada:cells"},
    ]  # fmt: skip

    miami, team, cells = approved_decisions(approved, TRIAGE, FPS)

    assert miami == {
        "id": "miami",
        "comparison": "ada",
        "group": {"column": "regions_region_name", "values": ["Miami"]},
        "call": "fix_cube",
        "reason": "r1",
        "task": "#1",
        "fingerprints": {"cube": "c1", "dashboard": "d1"},
    }
    assert team == {"id": "team", "missing_cut": "Team", "call": "deliberate",
                    "reason": "r2"}  # fmt: skip
    assert cells["cells"] is True and cells["fingerprints"] == FPS["ada"]


@pytest.mark.parametrize(
    "entry, match",
    [
        ({"id": "x", "call": "deliberate", "reason": "r", "item": "nope"}, "nope"),
        ({"id": "x", "call": "deliberate", "item": "cut:Team"}, "reason"),
    ],
)
def test_approved_decisions_refuse(entry, match):
    with pytest.raises(AnswerError, match=match):
        approved_decisions([entry], TRIAGE, FPS)


def test_approved_decisions_refuse_a_comparison_the_run_has_no_fingerprints_for():
    entry = {"id": "x", "call": "deliberate", "reason": "r", "item": "ada:cells"}

    with pytest.raises(AnswerError, match="fingerprints"):
        approved_decisions([entry], TRIAGE, {})


def test_parse_answers_reads_a_crlf_comment():
    body = _body([{"question": "Q1", "decisions": ["a"], "call": "deliberate",
                   "note": "n"}]).replace("\n", "\r\n")  # fmt: skip

    assert parse_answers(body) == [Answer("Q1", ("a",), "deliberate", "n")]


def test_approved_decisions_refuse_a_reason_a_note_could_not_carry():
    entry = {"id": "x", "call": "deliberate", "reason": "ask a@b.org",
             "item": "cut:Team"}  # fmt: skip

    with pytest.raises(AnswerError, match="email"):
        approved_decisions([entry], TRIAGE, FPS)
