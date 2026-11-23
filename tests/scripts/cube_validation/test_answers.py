import dataclasses
import itertools
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.answers import (
    Answer,
    AnswerError,
    HandCheck,
    _covers,
    approved_decisions,
    cell_causes,
    example_cell,
    hand_check,
    note_refusal,
    parse_answers,
    questions_json,
)

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import (
    ColumnPair,
    Comparison,
    Decision,
    RowSpec,
    ViewConfig,
)

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import Applied, apply

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.reconcile import CellDiff, Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import RunResult, render_review_issue

START = datetime(2026, 10, 27, 6, 0, tzinfo=timezone.utc)
END = datetime(2026, 10, 27, 6, 5, tzinfo=timezone.utc)
DIMS = [["regions_region_name", "Newark"], ["grade_level", "7"]]
# A cut's label, as `pipeline.cut_label` writes it.
CUT = '{"Grade": "7"}'


def _cell(key="a", dashboard=10.0, cube=12.0, n: int | None = 30, dims=DIMS):
    return {
        "comparison": "enrollment",
        "cut": CUT,
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
        cell_sql={"enrollment": {CUT: ["SELECT 1 AS d", "SELECT 2 AS c"]}},
        cell_sql_usd={"enrollment": {CUT: [0.01, 0.02]}},
    )


def _cfg(dashboard_region="regions_region_name", rows=None):
    cmp = Comparison(
        id="enrollment",
        measure="student_count",
        dims=[
            ColumnPair(dashboard_region, "regions_region_name"),
            ColumnPair("grade_level", "grade_level"),
        ],
        workbook="Attendance",
        sheet="Enrollment by Region",
        defaults={"Academic Year": "2026", "Grade": ["6", "7", "8"]},
        rows=rows,
    )
    return ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])


def test_example_cell_is_biggest_difference_with_reviewed_dims_only():
    run = _run([_cell("a", 10, 12), _cell("b", 10, 20), _cell("c", 10, 15)])

    assert example_cell(run, "enrollment")["key"] == "b"


def test_a_formula_question_s_hand_check_names_a_formula_cell():
    # A wide cell holding unmatched rows and a narrow one where every row
    # matched: the formula question's example is the narrow one.
    wide = {**_cell("wide", 10, 90), "kind": "cells"}
    narrow = {**_cell("narrow", 10, 25), "kind": "formula"}
    run = _owner_run([wide, narrow])
    run.applied.quiet = []

    (q,) = _questions(run)

    (check,) = q["hand_checks"]
    assert (check["dashboard"], check["cube"]) == ("10", "25")
    assert example_cell(run, "enrollment")["key"] == "wide"
    assert example_cell(run, "enrollment", kind="formula")["key"] == "narrow"
    # A run saved before cells carried a kind holds no formula cell.
    old = _run([_cell("old", 10, 12)])
    assert example_cell(old, "enrollment", kind="formula") is None
    assert example_cell(old, "enrollment", kind="cells")["key"] == "old"


def test_a_formula_part_merged_with_a_group_part_keeps_a_formula_example():
    # The formula decision shares the group decisions' reason, so one
    # question holds a group part and a formula part on one comparison: the
    # group part's example is the widest cell, the formula part's a formula
    # cell.
    wide = {**_cell("wide", 10, 90), "kind": "cells"}
    narrow = {**_cell("narrow", 10, 25), "kind": "formula"}
    run = _owner_run([wide, narrow])
    (d, diff), = run.applied.quiet_cells  # fmt: skip
    group_reason = run.applied.quiet[0][0].reason
    run.applied.quiet_cells = [(dataclasses.replace(d, reason=group_reason), diff)]

    (q,) = _questions(run)

    assert sorted((c["dashboard"], c["cube"]) for c in q["hand_checks"]) == [
        ("10", "25"),
        ("10", "90"),
    ]


def test_example_cell_ties_go_to_the_lowest_key():
    run = _run([_cell("b", 10, 20), _cell("a", 10, 20)])

    assert example_cell(run, "enrollment")["key"] == "a"


def test_example_cell_reads_a_view_s_bare_reference_names():
    bare = [["abbreviation", "KHS"], ["region_name", "Camden"],
            ["academic_subject", "English 300"], ["module_code", "QA2"]]  # fmt: skip
    run = _run([_cell("a", 10, 12, dims=bare)])

    assert example_cell(run, "enrollment")["key"] == "a"
    # Any column not reviewed still keeps a cell out.
    run = _run([_cell("a", 10, 12, dims=[*bare, ["student_number", "1"]])])
    assert example_cell(run, "enrollment") is None


def test_a_cause_s_example_needs_10_of_its_own_students_and_the_most_wins():
    few, many, wide = _cell("a", 10, 12), _cell("b", 10, 13), _cell("c", 10, 90)
    run = _run([few, many, wide])
    # `wide` has the widest gap but only 1 student of C1: the words of the
    # question would name them.
    cells = [(few, {"C1": 12}), (many, {"C1": 40, "C2": 3}), (wide, {"C1": 1})]

    picked = example_cell(run, "enrollment", "C1", cells)
    assert picked["key"] == "b"
    assert (picked["cause_students"], picked["mixed"]) == (40, True)
    assert example_cell(run, "enrollment", "C2", cells) is None
    assert example_cell(run, "enrollment", "C3", cells) is None


# The row grain a comparison needs before its groups can be placed in a cell.
FLOOR_ROWS = RowSpec(grain=[ColumnPair("student_number", "student_number")], values=[])


def _floor_run(groups):
    run = _run([_cell("a", 10, 20)])
    run.applied = Applied(open=list(groups))
    return run


def _floor_group(bucket, in_cut, n_rows=30, cut=CUT):
    """A group of `n_rows` rows, `in_cut` of them under `cut` on its own side."""
    rows = (cut, 0, in_cut) if bucket == "dashboard_only" else (cut, in_cut, 0)
    return Group("enrollment", tuple(map(tuple, DIMS)), bucket, n_rows, 25,
                 cut_rows=(rows, ('{"Grade": "8"}', 0, 0)))  # fmt: skip


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


def test_hand_check_names_the_sheet_and_the_filters_to_set():
    check = hand_check(_run([_cell()]), _cfg(), "enrollment", START)

    assert (check.workbook, check.sheet) == ("Attendance", "Enrollment by Region")
    # The cut's own values replace the defaults it names.
    assert check.filters == {"Academic Year": "2026", "Grade": "7"}


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
    # Keys are `pipeline.value_key` text: '7', 'true', '' and an ISO date.
    assert _where([["regions_region_name", "1.50"]]) == (
        "SAFE_CAST(regions_region_name AS NUMERIC) = 1.5"
    )
    assert _where([["regions_region_name", "true"]]) == (
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
    run.cell_sql["enrollment"][CUT] = ["SELECT 1 -- note", "SELECT 2"]

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

    cells = Decision("c1", "enrollment", "domain_owner", "Codes differ?", formula=True)
    applied = Applied(
        quiet=[
            (group_decision("d-newark", "Newark"),
             Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12)),
            (group_decision("d-camden", "Camden"),
             Group("enrollment", (("region", "Camden"),), "value_differs", 5, 5)),
        ],
        quiet_cells=[
            (cells, CellDiff("enrollment", {"differs": measure_cells}, kind="formula"))
        ],
    )  # fmt: skip
    run = _run(diff_cells)
    run.applied = applied
    return run


FORMULA_EVIDENCE = (
    "<10 differing cells hold no unmatched row: every row in them matched on both sides"
)
SORTED = {
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
                "suggestion": "cause",
                "evidence": ["note on Camden, student 1234567"],
                "candidates": [],
            },
            {
                "id": "enrollment:cells",
                "kind": "cells",
                "comparison": "enrollment",
                "label": "y",
                "stub": {"comparison": "enrollment", "cells": True},
                "suggestion": "cause",
                "evidence": ["no description or ai_context answers it"],
                "candidates": [],
            },
            {
                "id": "enrollment:formula",
                "kind": "formula",
                "comparison": "enrollment",
                "label": "f",
                "stub": {"comparison": "enrollment", "formula": True},
                "suggestion": "cause",
                "evidence": [FORMULA_EVIDENCE],
                "candidates": [],
            },
            {
                "id": "other:cells",
                "kind": "cells",
                "comparison": "other",
                "label": "z",
                "stub": {"comparison": "other", "cells": True},
                "suggestion": "cause",
                "evidence": ["UNRELATED"],
                "candidates": [],
            },
        ],
    }
}
DEFS = {"enrollment": {"enrollment": {"dashboard": "codes ET, T", "cube": "codes T%"}}}


def _questions(run, cfg=None, sorts=SORTED):
    return questions_json([run], [cfg or _cfg()], DEFS, sorts, START)


# `SORTED` is bound again further down, for the decisions-in tests.
OWNER_SORTED = SORTED


@pytest.mark.parametrize(
    "rows, evidence, total",
    [
        # 11 beside `masked` (10+) and `<10` (1+) would pin both.
        (11, ["scores: a = 1: masked rows", "scores: b = 1: <10 rows"], "10+ rows"),
        # Bounded beside exact evidence too: an earlier review's open-items
        # file may have listed the group's parts with some withheld.
        (50, ["scores: a = 1: 20 rows", "scores: b = 1: 30 rows"], "10+ rows"),
    ],
)
def test_a_group_question_bounds_its_rows_beside_hidden_evidence(rows, evidence, total):
    d = Decision("d-newark", "enrollment", "domain_owner", REASON,
                 {"column": "region", "values": ["Newark"]})  # fmt: skip
    run = _run([_cell()])
    group = Group("enrollment", (("region", "Newark"),), "value_differs", rows, 12)
    run.applied = Applied(quiet=[(d, group)])
    item = {
        "id": "enrollment:region=Newark", "kind": "group", "comparison": "enrollment",
        "label": "x", "suggestion": "cause", "evidence": evidence, "candidates": [],
        "stub": {"comparison": "enrollment",
                 "group": {"column": "region", "values": ["Newark"]}},
    }  # fmt: skip
    sorts = {"enrollment": {"view": "enrollment", "items": [item]}}

    (q,) = _questions(run, sorts=sorts)
    body = render_review_issue("Registrar", [run], questions=[q])

    assert f", {total}, " in q["counts"][0]
    assert f"{rows} rows" not in " ".join(q["counts"])
    (line,) = [x for x in body.splitlines() if x.startswith("- Q1. ")]
    assert f", {total}, " in line


def test_unsettled_items_are_not_in_the_questions_json():
    run = _owner_run([_cell(cube=25.0)])
    left = {
        "id": "enrollment:region=<redacted>#2",
        "kind": "group",
        "comparison": "enrollment",
        "label": "w",
        # The same stub as a group an owner decision covers.
        "stub": {
            "comparison": "enrollment",
            "group": {"column": "region", "values": ["Camden"]},
        },
        "suggestion": "investigate",
        "evidence": ["lead: relaxing UNSETTLED brings back 3 of 5 rows"],
        "candidates": [],
    }
    items = [*OWNER_SORTED["enrollment"]["items"], left]
    sorts = {"enrollment": {**OWNER_SORTED["enrollment"], "items": items}}

    questions = _questions(run, sorts=sorts)

    assert "UNSETTLED" not in json.dumps(questions)
    assert [q["id"] for q in questions] == ["Q1", "Q2"]


def test_a_formula_question_reads_its_evidence_from_the_run():
    # A `sort` after the formula decision holds lists no formula item: the
    # decision quiets the cells, and `sort.json` holds open items only.
    run = _owner_run([_cell(cube=25.0)])
    items = [i for i in OWNER_SORTED["enrollment"]["items"] if i["kind"] != "formula"]
    sorts = {"enrollment": {**OWNER_SORTED["enrollment"], "items": items}}

    questions = _questions(run, sorts=sorts)

    assert questions[1]["decisions"] == ["c1"]
    assert questions[1]["evidence"] == [FORMULA_EVIDENCE]


def test_a_formula_question_posts_each_origin_masked_and_no_cell():
    run = _owner_run([_cell(cube=25.0)])
    cells = Decision("c1", "enrollment", "domain_owner", "Codes differ?", formula=True)
    diff = CellDiff("enrollment", {"differs": 3}, kind="formula", matched_only=2)
    run.applied = dataclasses.replace(run.applied, quiet_cells=[(cells, diff)])
    stale = {**OWNER_SORTED["enrollment"]["items"][2], "evidence": ["STALE"]}
    sorts = {"enrollment": {"view": "enrollment", "items": [stale]}}

    (_, q) = _questions(run, sorts=sorts)

    assert q["evidence"] == [
        FORMULA_EVIDENCE,
        "<10 differing cells differ on matched rows: with their unmatched rows "
        "left out, the 2 sides still differ",
    ]


def test_questions_json_matches_markdown_questions_one_to_one():
    run = _owner_run([_cell(cube=25.0)])
    questions = _questions(run)
    body = render_review_issue("Registrar", [run], DEFS, questions)
    bullets = [x for x in body.split("## Proposed")[0].splitlines() if "Reason:" in x]

    assert [q["id"] for q in questions] == ["Q1", "Q2"]
    assert len(bullets) == len(questions)
    for q, bullet in zip(questions, bullets, strict=True):
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
    # The formula question's evidence comes from the run's quieted cells.
    assert questions[1]["evidence"] == [FORMULA_EVIDENCE]
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
    assert (check["dashboard"], check["cube"]) == ("10", "25")
    assert check["cube_sql"].endswith("SAFE_CAST(grade_level AS NUMERIC) = 7")
    assert (check["dashboard_usd"], check["cube_usd"]) == (0.01, 0.02)
    assert (check["workbook"], check["sheet"]) == ("Attendance", "Enrollment by Region")
    assert check["filters"] == {"Academic Year": "2026", "Grade": "7"}
    markdown = body.split("<summary>Questions for Claude")[0]
    location = (
        "On the dashboard: sheet `Enrollment by Region` in `Attendance`, set "
        "`Academic Year` = `2026`; `Grade` = `7`."
    )
    assert location in markdown
    assert markdown.index(location) < markdown.index(check["dashboard_sql"])


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
    run = _owner_run([_cell(dashboard=7.0, cube=25.0)])

    text = json.dumps(_questions(run, cfg))

    # Camden's group has 5 students, so its value and its counts stay hidden.
    assert "Camden" not in text and "1234567" not in text
    assert "UNRELATED" not in text
    assert "<10 cells differ" in text and "3 cells" not in text
    assert "10+ rows" in text and "45 rows" not in text and " 5 rows" not in text
    # A count measure's value under 10 is masked like any count.
    check = _questions(run, cfg)[0]["hand_checks"][0]
    assert (check["dashboard"], check["cube"]) == ("<10", "25")
    assert "stub" not in text


def test_question_without_example_cell_says_find_one_locally():
    run = _owner_run([_cell(n=9)])
    questions = _questions(run, sorts={})

    assert questions[0]["hand_checks"] == [
        {
            "none": "no group cell with 10+ students differs; find an example "
            "under your own access",
            "view": "enrollment",
            "comparisons": ["enrollment"],
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
        run = _owner_run([_cell(dashboard=7.0, cube=25.0)])

        questions = _questions(run, cfg)
        check = questions[0]["hand_checks"][0]

        assert (check["dashboard"], check["cube"]) == ("<10", "25"), measure
        body = render_review_issue("Registrar", [run], DEFS, questions)
        assert "the dashboard shows <10, Cube shows 25" in body

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
        "since SY 2023-2024",
        "Cube 93.25 vs 93.10",
        "rate 100.0%",
    ],
)
def test_note_refusal_lets_dates_and_small_numbers_through(note):
    assert note_refusal(note) is None


SORTED = {
    "items": [
        {"id": "ada:region=Miami", "kind": "group", "stub": {"comparison": "ada",
         "group": {"column": "regions_region_name", "values": ["Miami"]}}},
        {"id": "cut:Team", "stub": {"missing_cut": "Team"}},
        {"id": "ada:cells", "kind": "cells",
         "stub": {"comparison": "ada", "cells": True}},
        {"id": "ada:formula", "kind": "formula",
         "stub": {"comparison": "ada", "formula": True}},
    ]
}  # fmt: skip
FPS = {"ada": {"cube": "c1", "dashboard": "d1"}}


def test_approved_decisions_take_the_stub_and_the_run_fingerprints():
    approved = [
        {"id": "team", "call": "deliberate", "reason": "r2", "task": "",
         "item": "cut:Team"},
        {"id": "formula", "call": "domain_owner", "reason": "r3",
         "item": "ada:formula"},
    ]  # fmt: skip

    team, formula = approved_decisions(approved, SORTED, FPS)

    assert team == {"id": "team", "missing_cut": "Team", "call": "deliberate",
                    "reason": "r2"}  # fmt: skip
    assert formula == {"id": "formula", "comparison": "ada", "formula": True,
                       "call": "domain_owner", "reason": "r3",
                       "fingerprints": FPS["ada"]}  # fmt: skip


def test_a_formula_decision_records_the_cells_the_check_filed():
    entry = {"id": "f", "call": "domain_owner", "reason": "r", "item": "ada:formula"}

    (filed,) = approved_decisions([entry], SORTED, FPS, formula_cells={"ada": 3})
    (none,) = approved_decisions([entry], SORTED, FPS, formula_cells={"ada": 0})

    assert filed["fingerprints"] == {**FPS["ada"], "matched_only": "3"}
    # None filed reads as 0 with the key left out, as before the count existed.
    assert none["fingerprints"] == FPS["ada"]


def test_a_formula_decision_records_which_cells_it_covers():
    entry = {"id": "f", "call": "domain_owner", "reason": "r", "item": "ada:formula"}
    digest = "ab" * 32

    (f,) = approved_decisions(
        [entry], SORTED, FPS, formula_cells={"ada": 3},
        formula_hashes={"ada": digest, "other": "cd" * 32},
    )  # fmt: skip
    (team,) = approved_decisions(
        [{"id": "t", "call": "deliberate", "reason": "r", "item": "cut:Team"}],
        SORTED, FPS, formula_hashes={"ada": digest},
    )  # fmt: skip

    assert f["fingerprints"] == {
        **FPS["ada"], "matched_only": "3", "formula_cells": digest,
    }  # fmt: skip
    assert "fingerprints" not in team


def test_a_cell_set_takes_no_decision():
    entry = {"id": "x", "call": "deliberate", "reason": "r", "item": "ada:cells"}

    with pytest.raises(AnswerError, match="a cell set takes no decision"):
        approved_decisions([entry], SORTED, FPS)


def test_a_formula_decision_covers_only_its_comparison_s_formula_item():
    d = Decision("f", "ada", "domain_owner", "r", formula=True)

    assert _covers(d, {"comparison": "ada", "formula": True})
    assert not _covers(d, {"comparison": "other", "formula": True})
    assert not _covers(d, {"comparison": "ada", "cells": True})
    group = Decision("g", "ada", "deliberate", "r", {"column": "x", "values": ["1"]})
    assert not _covers(group, {"comparison": "ada", "formula": True})


def test_a_missing_filter_in_cause_is_decided_across_the_view():
    # As the sort writes it: a comparison it was found on, and the sheet filter
    # as its explained cause.
    item = {
        "id": "filter:Exclude Future", "kind": "gap", "suggestion": "cause",
        "comparison": "ada", "stub": {"missing_filter": "Exclude Future"},
        "cause": [{"side": "dashboard", "step": "sheet filter Exclude Future",
                   "label": "sheet filter Exclude Future", "n_rows": None}],
        "explanation": {"kind": "workbook"},
    }  # fmt: skip
    approved = [{"id": "future", "call": "deliberate", "reason": "a display filter",
                 "item": item["id"]}]  # fmt: skip

    (decision,) = approved_decisions(approved, {"items": [item]}, FPS)

    # No comparison and no fingerprints: the loader refuses either on one.
    assert decision == {"id": "future", "missing_filter": "Exclude Future",
                        "call": "deliberate", "reason": "a display filter"}  # fmt: skip


@pytest.mark.parametrize(
    "entry, match",
    [
        ({"id": "x", "call": "deliberate", "reason": "r", "item": "nope"}, "nope"),
        ({"id": "x", "call": "deliberate", "item": "cut:Team"}, "reason"),
        # A row group as `sort` writes it: decided only on an explained cause.
        (
            {"id": "x", "call": "fix_cube", "reason": "r", "item": "ada:region=Miami"},
            "a row group no explanation decides",
        ),
    ],
)
def test_approved_decisions_refuse(entry, match):
    with pytest.raises(AnswerError, match=match):
        approved_decisions([entry], SORTED, FPS)


def test_approved_decisions_refuse_a_comparison_the_run_has_no_fingerprints_for():
    entry = {"id": "x", "call": "deliberate", "reason": "r", "item": "ada:formula"}

    with pytest.raises(AnswerError, match="fingerprints"):
        approved_decisions([entry], SORTED, {})


WHOLE = {"id": "old", "comparison": "ada", "call": "deliberate",
         "reason": "an old sheet no one reads"}  # fmt: skip
# A row group still in `investigate`: a comparison decision may close it.
UNEXPLAINED = {
    "items": [
        {"id": "ada:g1", "kind": "group", "comparison": "ada",
         "suggestion": "investigate", "stub": {"comparison": "ada"}},
        *SORTED["items"],
    ]
}  # fmt: skip


def test_approved_decisions_decide_a_whole_comparison():
    (decision,) = approved_decisions([WHOLE], UNEXPLAINED, FPS)

    assert decision == {"id": "old", "comparison": "ada", "all_groups": True,
                        "call": "deliberate", "reason": "an old sheet no one reads",
                        "fingerprints": FPS["ada"]}  # fmt: skip


def test_approved_decisions_re_approve_a_comparison_decision_on_new_sql():
    was = Decision("old", "ada", "deliberate", "before", all_groups=True,
                   fingerprints={"cube": "c0", "dashboard": "d0"})  # fmt: skip

    (decision,) = approved_decisions([WHOLE], UNEXPLAINED, FPS, existing=[was])

    assert decision["fingerprints"] == FPS["ada"]
    assert decision["reason"] == "an old sheet no one reads"

    # Under another id it would be a second claim on the comparison.
    with pytest.raises(AnswerError, match="'old' already decides every open row"):
        approved_decisions([{**WHOLE, "id": "new"}], UNEXPLAINED, FPS, existing=[was])


@pytest.mark.parametrize(
    "entry, loaded, match",
    [
        ({**WHOLE, "call": "domain_owner"}, UNEXPLAINED,
         "a comparison decision is deliberate"),
        ({**WHOLE, "call": "fix_cube", "task": "#1"}, UNEXPLAINED,
         "a comparison decision is deliberate"),
        ({**WHOLE, "reason": "  "}, UNEXPLAINED, "`reason` must be non-empty"),
        ({k: v for k, v in WHOLE.items() if k != "reason"}, UNEXPLAINED, "reason"),
        ({**WHOLE, "item": "ada:g1"}, UNEXPLAINED, "either `item` or `comparison`"),
        ({**WHOLE, "comparison": "nope"}, UNEXPLAINED, "no fingerprints for 'nope'"),
        # No open row group of the comparison to close.
        (WHOLE, {"items": [i for i in SORTED["items"] if i.get("kind") != "group"]},
         "the sort lists no open row group of 'ada'"),
    ],
)  # fmt: skip
def test_approved_decisions_refuse_a_bad_comparison_decision(entry, loaded, match):
    with pytest.raises(AnswerError, match=match):
        approved_decisions([entry], loaded, {**FPS, "nope": {}})


def test_approved_decisions_refuse_a_taken_id_for_a_comparison_decision():
    taken = Decision("old", "ada", "deliberate", "r", {"column": "x", "values": ["1"]})

    with pytest.raises(AnswerError, match="decisions already has 'old'"):
        approved_decisions([WHOLE], UNEXPLAINED, FPS, existing=[taken])


def test_parse_answers_reads_a_crlf_comment():
    body = _body([{"question": "Q1", "decisions": ["a"], "call": "deliberate",
                   "note": "n"}]).replace("\n", "\r\n")  # fmt: skip

    assert parse_answers(body) == [Answer("Q1", ("a",), "deliberate", "n")]


def test_parse_answers_reads_a_block_indented_under_a_list_item():
    block = json.dumps(
        [{"question": "Q1", "decisions": ["a"], "call": "deliberate", "note": "n"}]
    )
    body = f"- Q1: intended.\n\n  ```json\n  {block}\n  ```\n"

    assert parse_answers(body) == [Answer("Q1", ("a",), "deliberate", "n")]


def test_approved_decisions_refuse_a_reason_a_note_could_not_carry():
    entry = {"id": "x", "call": "deliberate", "reason": "ask a@b.org",
             "item": "cut:Team"}  # fmt: skip

    with pytest.raises(AnswerError, match="email"):
        approved_decisions([entry], SORTED, FPS)


# --- cause decisions (T17) ---------------------------------------------------

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import sort as sort_mod  # noqa: E402

NO_SECTION = "score has no section on the anchor date"
LATE = "score dated after week 20250701"
CAUSE_FPS = {"enrollment": {"cube": "c1", "dashboard": "d1"}}
EXPLANATION = {"kind": "query", "path": "explanations/v/enrollment__dashboard_only.sql",
         "fingerprint": "p1"}  # fmt: skip


def _cause_entry(label, side="cube", n_rows=20):
    return {"side": side, "step": "b", "label": label, "n_rows": n_rows}


def _cause_item(item_id, *causes, explanation=EXPLANATION, key=""):
    return {"id": item_id, "key": key, "kind": "group", "comparison": "enrollment",
            "label": "l", "stub": {"comparison": "enrollment"},
            "suggestion": "cause", "evidence": ["proof line"], "candidates": [],
            "cause": list(causes), "explanation": explanation}  # fmt: skip


def _ok(id, item, call="domain_owner", reason="r", cause=""):
    out = {"id": id, "call": call, "reason": reason, "item": item}
    return {**out, "cause": cause} if cause else out


def _existing(id="no-section", label=NO_SECTION, call="domain_owner", explanation="p1",
              cube="c1", **kw):  # fmt: skip
    return Decision(id, "enrollment", call, "kept reason",
                    cause={"side": "cube", "label": label},
                    fingerprints={"cube": cube, "dashboard": "d1", "explanation": explanation},
                    **kw)  # fmt: skip


def test_an_explained_group_becomes_a_decision_on_its_cause():
    item = _cause_item("k1", _cause_entry(LATE))

    (decision,) = approved_decisions([_ok("late", "k1")], {"items": [item]}, CAUSE_FPS)

    assert decision == {
        "id": "late",
        "comparison": "enrollment",
        # The words' long number never reaches the file.
        "cause": {"side": "cube", "label": "score dated after week <n>"},
        "call": "domain_owner",
        "reason": "r",
        "fingerprints": {"cube": "c1", "dashboard": "d1", "explanation": "p1"},
    }
    assert "20250701" not in json.dumps(decision)


def test_groups_sharing_a_cause_share_one_decision_with_no_group_keys():
    items = [_cause_item(k, _cause_entry(NO_SECTION)) for k in ("k1", "k2", "k3")]
    approved = [_ok("no-section", "k1"), _ok("again", "k2"), _ok("more", "k3")]

    (decision,) = approved_decisions(approved, {"items": items}, CAUSE_FPS)

    assert decision["id"] == "no-section" and "groups" not in decision["cause"]


def test_a_cause_already_decided_writes_nothing_more():
    item = _cause_item("k2", _cause_entry(NO_SECTION))

    assert (
        approved_decisions(
            [_ok("new", "k2")], {"items": [item]}, CAUSE_FPS, existing=[_existing()]
        )
        == []
    )


def test_a_cause_decision_on_a_changed_explanation_is_re_approved():
    item = _cause_item("k2", _cause_entry(NO_SECTION))
    stale = _existing(explanation="old")

    (decision,) = approved_decisions(
        [_ok("new", "k2", call="fix_cube", reason="fresh")], {"items": [item]},
        CAUSE_FPS, existing=[stale],
    )  # fmt: skip

    assert (decision["id"], decision["call"], decision["reason"]) == (
        "no-section", "fix_cube", "fresh")  # fmt: skip
    assert decision["fingerprints"] == {
        "cube": "c1",
        "dashboard": "d1",
        "explanation": "p1",
    }


def _d2_d4():
    """A D2+D4 group beside a pure D2 and a pure D4 group, as DDI has."""
    d2, d4 = "no subject section covers the date", "the enrollment key has no row"
    items = [
        _cause_item("mixed", _cause_entry(d2, n_rows=7), _cause_entry(d4, n_rows=5)),
        _cause_item("pure-d2", _cause_entry(d2)),
        _cause_item("pure-d4", _cause_entry(d4)),
    ]
    entries = [
        _ok("d2", "pure-d2", reason="owner"),
        _ok("d4", "pure-d4", call="fix_cube", reason="fix"),
        _ok("m2", "mixed", reason="owner", cause=d2),
        _ok("m4", "mixed", call="fix_cube", reason="fix", cause=d4),
    ]
    return items, entries, d2, d4


def test_a_split_group_takes_one_call_per_cause_in_any_order():
    items, entries, d2, d4 = _d2_d4()

    results = []
    for order in itertools.permutations(entries):
        out = approved_decisions(list(order), {"items": items}, CAUSE_FPS)
        results.append({d["cause"]["label"]: d["call"] for d in out})

    assert all(r == {d2: "domain_owner", d4: "fix_cube"} for r in results)


def test_a_split_group_is_decided_only_once_every_cause_is():
    items, entries, d2, d4 = _d2_d4()
    run = _run([])
    group = Group("enrollment", (("region", "Newark"),), "dashboard_only", 12, 12)
    run.applied = apply([], [group], CAUSE_FPS)
    run.fingerprints = CAUSE_FPS
    (it,) = sort_mod.open_items(run)
    mixed = {**items[0], "id": it.id, "key": it.key}

    only_d2 = [Decision(**d) for d in approved_decisions(
        [entries[2] | {"item": "mixed"}], {"items": items}, CAUSE_FPS)]  # fmt: skip
    sort_mod.mark_decided(run, [mixed], only_d2)
    assert mixed["decided"] is False

    both = [
        Decision(**d) for d in approved_decisions(entries, {"items": items}, CAUSE_FPS)
    ]
    sort_mod.mark_decided(run, [mixed], both)
    assert mixed["decided"] is True


@pytest.mark.parametrize(
    "existing, entry, match",
    [
        (_existing(call="fix_cube", task="#1"), {}, "decided fix_cube"),
        (
            _existing(explanation="old", answer="fix_cube"),
            {},
            "answered.*explanation changed",
        ),
        (_existing(cube="old", answer="deliberate"), {}, "answered.*SQL changed"),
        (_existing(id="taken", label="other"), {"id": "taken"}, "already has"),
    ],
)  # fmt: skip
def test_cause_approvals_refuse(existing, entry, match):
    item = _cause_item("k2", _cause_entry(NO_SECTION))

    with pytest.raises(AnswerError, match=match):
        approved_decisions([{**_ok("new", "k2"), **entry}], {"items": [item]},
                           CAUSE_FPS, existing=[existing])  # fmt: skip


def test_cause_approvals_refuse_bad_batches():
    one = _cause_item("k1", _cause_entry(NO_SECTION))
    two = _cause_item("k2", _cause_entry(NO_SECTION))
    other_proof = _cause_item("k3", _cause_entry(NO_SECTION),
                              explanation={**EXPLANATION, "path": "explanations/v/x.sql",
                                     "fingerprint": "p9"})  # fmt: skip
    blank = _cause_item("k4", _cause_entry(""))
    split = _cause_item("k5", _cause_entry(NO_SECTION), _cause_entry(LATE))
    unexplained = {**_cause_item("k6", _cause_entry(NO_SECTION)), "explanation": None}
    waiting = {**_cause_item("k7"), "suggestion": "investigate", "cause": None,
               "explanation": None}  # fmt: skip

    for approved, items, match in [
        ([_ok("a", "k1"), _ok("b", "k2", call="deliberate")], [one, two], "domain_owner"),
        ([_ok("a", "k1"), _ok("b", "k1")], [one], "twice"),
        ([_ok("a", "k1"), _ok("b", "k1", cause=NO_SECTION)], [one], "twice"),
        ([_ok("a", "k1")], [one, other_proof], "2 explanation"),
        ([_ok("a", "k4")], [blank], "no words"),
        ([_ok("a", "k5")], [split], "2 causes; approve each"),
        ([_ok("a", "k5", cause="nothing like it")], [split], "has no cause"),
        ([_ok("a", "k6")], [unexplained], "no explanation decides"),
        ([_ok("a", "k7")], [waiting], "still in `investigate`"),
    ]:  # fmt: skip
        with pytest.raises(AnswerError, match=match):
            approved_decisions(approved, {"items": items}, CAUSE_FPS)


LEAD = "lead: read docs/models/x-data-model.md (mentions rpt_x)"


def _review(groups, items, decisions, runs_extra=()):
    run = _run([])
    run.applied = apply(decisions, groups, CAUSE_FPS)
    run.fingerprints = CAUSE_FPS
    sort_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {
        "enrollment": sort_mod.cause_asks(run, loaded, decisions, {"enrollment": LEAD})
    }
    questions = questions_json(
        [run], [_cfg()], DEFS, {"enrollment": loaded}, START, causes
    )
    return questions, render_review_issue("Registrar", [run], DEFS, questions, causes)


def _ddi():
    """3 schools x 2 explained causes: each school has a group of each cause."""
    groups = [
        Group("enrollment", (("region", s), ("grade_level", grade)),
              "dashboard_only", 30, 12)
        for s in ("Newark", "Camden", "Paterson") for grade in ("7", "8")
    ]  # fmt: skip
    run = _run([])
    run.applied = apply([], groups, CAUSE_FPS)
    opened = sort_mod.open_items(run)
    items = [
        _cause_item(it.id, _cause_entry(NO_SECTION if g.value_of("grade_level") == "7"
                                        else LATE, n_rows=30), key=it.key)
        for g, it in zip(groups, opened, strict=True)
    ]  # fmt: skip
    return groups, items


def test_ask_owner_asks_one_question_per_cause_not_per_school():
    groups, items = _ddi()
    approved = [
        _ok(f"school-{i}", item["id"], reason=f"Which rule holds at school {i}?")
        for i, item in enumerate(items)
    ]
    written = approved_decisions(approved, {"items": items}, CAUSE_FPS)
    decisions = [Decision(**d) for d in written]

    questions, body = _review(groups, items, decisions)

    assert len(decisions) == 2 and all(i["decided"] for i in items)
    assert [q["decisions"] for q in questions] == [["school-0"], ["school-1"]]
    no_section, late = questions
    # The model-doc lead stands in for member descriptions.
    # The counts carry each comparison's share; the evidence names the cause.
    assert no_section["evidence"] == [f"cause (cube side): {NO_SECTION}", LEAD]
    assert no_section["counts"] == [
        f"cause `{NO_SECTION}` on the cube side",
        "`enrollment` (dashboard_only): <10 row groups, 10+ rows",
    ]
    assert late["evidence"][0] == "cause (cube side): score dated after week <n>"
    assert "20250701" not in body
    bullets = [x for x in body.split("## Proposed")[0].splitlines() if "Reason:" in x]
    assert len(bullets) == 2
    assert f"`{NO_SECTION}`" in bullets[0] and "<10 row groups, 10+ rows" in bullets[0]


def _decided_ddi():
    groups, items = _ddi()
    approved = [
        _ok(f"school-{i}", item["id"], reason=f"Which rule holds at school {i}?")
        for i, item in enumerate(items)
    ]
    written = approved_decisions(approved, {"items": items}, CAUSE_FPS)
    return groups, items, [Decision(**d) for d in written]


def test_a_long_body_moves_the_reproduce_blocks_to_comments(monkeypatch):
    from cube_validation import report as report_mod

    groups, items, decisions = _decided_ddi()
    run = _run([])
    run.applied = apply(decisions, groups, CAUSE_FPS)
    run.fingerprints = CAUSE_FPS
    sort_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {"enrollment": sort_mod.cause_asks(run, loaded, decisions)}
    questions = questions_json(
        [run], [_cfg()], DEFS, {"enrollment": loaded}, START, causes
    )
    for q in questions:
        q["reproduce"] = {
            "queries": [{"bucket": "C1", "sql": "SELECT 1 AS n_rows" + " " * 400}],
            "explanations": [], "cube": [], "expires": "2026-11-06",
            "after": ["compare v.yml --all", "sort v.yml"],
        }  # fmt: skip
    inline = render_review_issue("Registrar", [run], DEFS, questions, causes, [])
    # Every block fits 1 comment, but not the body and a block together.
    monkeypatch.setattr(report_mod, "BODY_WARN_CHARS", len(inline) - 100)
    comments: list[str] = []

    body = render_review_issue("Registrar", [run], DEFS, questions, causes, comments)

    assert "<summary>Reproduce" not in body
    assert "Reproduce block is in the comments below" in body
    assert '"reproduce"' in body  # the owner's JSON keeps everything
    (comment,) = comments
    assert comment.startswith("Reproduce Q1 to Q2 (comment 1 of 1).")
    assert "<summary>Reproduce Q1</summary>" in comment
    assert "<summary>Reproduce Q2</summary>" in comment
    # Without a list to fill, the body keeps its blocks, however long.
    assert render_review_issue("Registrar", [run], DEFS, questions, causes) == inline


def test_other_calls_show_once_each_as_also_decided_never_as_questions():
    groups, items = _ddi()
    calls = [("deliberate", "", "Intended, as the schools agreed"),
             ("fix_cube", "#5668", "Cube drops these")]  # fmt: skip
    approved = [
        {**_ok(f"c-{i}", item["id"], call=call, reason=reason),
         **({"task": task} if task else {})}
        for i, (item, (call, task, reason)) in enumerate(zip(items, calls, strict=False))
    ]  # fmt: skip
    decisions = [
        Decision(**d) for d in approved_decisions(approved, {"items": items}, CAUSE_FPS)
    ]
    run = _run([])
    run.applied = apply(decisions, groups, CAUSE_FPS)
    run.fingerprints = CAUSE_FPS
    sort_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {"enrollment": sort_mod.cause_asks(run, loaded, decisions)}
    decided = {"enrollment": sort_mod.cause_asks(run, loaded, decisions, owner=False)}
    questions = questions_json(
        [run], [_cfg()], DEFS, {"enrollment": loaded}, START, causes
    )

    body = render_review_issue(
        "Registrar", [run], DEFS, questions, causes, decided=decided
    )

    assert questions == [] and "Nothing needs review." in body
    also = [x for x in body.splitlines() if x.startswith("- cause ")]
    assert also == [
        f"- cause `{NO_SECTION}` on the cube side (`enrollment` in `enrollment`): "
        "an intended difference; later runs stay quiet on it (`deliberate`). "
        "Reason: Intended, as the schools agreed.",
        "- cause `score dated after week <n>` on the cube side (`enrollment` in "
        "`enrollment`): Cube gets fixed (`fix_cube`). Reason: Cube drops these. "
        "Task: #5668",
    ]
    assert "Also decided (no answer needed)" in body


def test_pinned_sql_too_long_to_post_is_left_out_before_anything_else(monkeypatch):
    from cube_validation import report as report_mod

    # One owner question, so the JSON below matches the questions the run asks.
    run = _run([])
    run.applied = Applied(quiet=[(
        Decision("d", "enrollment", "domain_owner", REASON,
                 {"column": "region", "values": ["Newark"]}),
        Group("enrollment", (("region", "Newark"),), "value_differs", 40, 12),
    )])  # fmt: skip
    questions = [
        {"id": "Q1", "counts": ["a part"], "hand_checks": [{
            "view": "v", "comparison": "c", "cut": "{}", "dims": [],
            "dashboard": "1", "cube": "2", "dashboard_sql": "S" * 5000,
            "cube_sql": "T" * 7000, "dashboard_usd": 0.01, "cube_usd": 0.01,
            "expires": "2026-11-06", "expired": False, "workbook": "w",
            "sheet": "s", "filters": {}, "mixed": False}]},
    ]  # fmt: skip
    full = render_review_issue("Registrar", [run], DEFS, questions, None, [])
    monkeypatch.setattr(report_mod, "BODY_WARN_CHARS", len(full) - 1000)
    comments: list[str] = []

    body = render_review_issue("Registrar", [run], DEFS, questions, None, comments)

    assert "S" * 5000 not in body and comments == []
    assert "The pinned BigQuery SQL is left out (5,000 and 7,000 characters" in body
    assert '"sql_left_out":[5000,7000]' in body and '"dashboard_sql":null' in body


def test_recorded_cause_students_are_used_as_counted():
    run = _floor_run([_floor_group("cube_only", 12)])
    items = [{"key": it.key, "kind": "group", "cause": [{"side": "cube", "label": "C1"}]}
             for it in sort_mod.open_items(run)]  # fmt: skip
    counted = [{"cause": "cube: C1", "cut": CUT, "dims": DIMS, "n": 14}]

    ((_, held),) = cell_causes(run, _cfg(rows=FLOOR_ROWS), "enrollment", items, counted)
    assert held == {"cube: C1": 14}
    # Counted, and none in this cell: 0, though the group agrees with it.
    ((_, held),) = cell_causes(run, _cfg(rows=FLOOR_ROWS), "enrollment", items, [])
    assert held == {"cube: C1": 0}


def test_one_cause_on_several_comparisons_is_one_question():
    groups = [
        Group(cid, (("region", "Newark"),), "dashboard_only", 30, 12)
        for cid in ("enrollment", "other")
    ]
    fps = {"enrollment": CAUSE_FPS["enrollment"], "other": CAUSE_FPS["enrollment"]}
    run = _run([])
    run.applied = apply([], groups, fps)
    run.fingerprints = fps
    items = [
        {**_cause_item(it.id, _cause_entry(NO_SECTION, n_rows=30), key=it.key),
         "comparison": it.comparison, "stub": {"comparison": it.comparison}}
        for it in sort_mod.open_items(run)
    ]  # fmt: skip
    decisions = [
        Decision(**d)
        for d in approved_decisions(
            [_ok("a", items[0]["id"]), _ok("b", items[1]["id"])], {"items": items}, fps
        )
    ]
    sort_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {"enrollment": sort_mod.cause_asks(run, loaded, decisions)}

    (question,) = questions_json(
        [run], [_cfg()], DEFS, {"enrollment": loaded}, START, causes
    )

    assert question["decisions"] == ["a", "b"]
    # The cause once, then each comparison's share; 1 view, so no view names.
    assert question["counts"] == [
        f"cause `{NO_SECTION}` on the cube side",
        "`enrollment` (dashboard_only): <10 row groups, 10+ rows",
        "`other` (dashboard_only): <10 row groups, 10+ rows",
    ]
    assert question["evidence"] == [f"cause (cube side): {NO_SECTION}"]


def test_a_split_group_shows_only_each_causes_own_rows():
    groups = [
        Group("enrollment", (("region", "Newark"),), "dashboard_only", 30, 12),
        Group("enrollment", (("region", "Camden"),), "dashboard_only", 30, 12),
    ]
    run = _run([])
    run.applied = apply([], groups, CAUSE_FPS)
    newark, camden = sort_mod.open_items(run)
    items = [
        # Newark's 30 rows split 27 and 3 across the 2 causes.
        _cause_item(newark.id, _cause_entry(NO_SECTION, n_rows=27),
                    _cause_entry(LATE, n_rows=3), key=newark.key),
        _cause_item(camden.id, _cause_entry(NO_SECTION, n_rows=30), key=camden.key),
    ]  # fmt: skip
    decisions = [
        Decision(**d)
        for d in approved_decisions(
            [_ok("x", newark.id, cause=NO_SECTION), _ok("y", camden.id),
             _ok("z", newark.id, call="fix_cube", cause=LATE)],
            {"items": items}, CAUSE_FPS,
        )
    ]  # fmt: skip

    questions, body = _review(groups, items, decisions)

    posted = body.split("<summary>Questions for Claude")[0] + json.dumps(questions)
    # The bullet gives the cause's own share as a bound; neither its 57 rows
    # nor the groups' whole 60 shows, so nothing gives the other cause's 3 away.
    numbers = set(re.findall(r"(?<![<\d])\d+\+? rows", posted))
    assert numbers == {"10+ rows"}


# --- reproducing a cause ---------------------------------------------------------------

from dataclasses import replace as _replace  # noqa: E402

from cube_validation import explain as explain_mod  # noqa: E402
from cube_validation import pipeline as pipeline_mod  # noqa: E402
from cube_validation import review as review_mod  # noqa: E402
from cube_validation.answers import (  # noqa: E402
    ExplanationSource,
    merged_reproduce,
    reproduce_json,
)
from cube_validation.report import CauseAsk, _reproduce_lines  # noqa: E402

EXPLANATION_SQL = (
    "SELECT u.__row, CASE WHEN TRUE THEN 'C1' ELSE 'UNEXPLAINED' END AS cause "
    "FROM {unmatched} AS u"
)
LIVE = "SELECT school, COUNT(*) AS n_rows FROM d.t GROUP BY school"


def _cause_cfg():
    cmp = _replace(
        _cfg().comparisons[0],
        filters={
            "Academic Year": ColumnPair("academic_year", "academic_year"),
            "Grade": ColumnPair("grade_level", "grade_level"),
        },
    )
    return ViewConfig(view="enrollment", fact="d.t", comparisons=[cmp])


def _ask(explanations):
    decision = Decision(
        id="c1",
        comparison="enrollment",
        call="domain_owner",
        reason="r",
        cause={"side": "dashboard", "label": "the sheet drops WPP"},
    )
    return CauseAsk(decision, [], 30, "", explanations)


def _stored_explanation(tmp_path, reproduce):
    directory = tmp_path / "explanations" / "enrollment"
    directory.mkdir(parents=True)
    path = explain_mod.explanation_path(directory, "enrollment", "cube_only")
    path.write_text(
        explain_mod.compose(
            {"C1": ("dashboard", "drops WPP")}, EXPLANATION_SQL, reproduce
        )
    )
    return "explanations/enrollment/enrollment__cube_only.sql"


def test_a_cause_reproduces_through_cube_a_count_query_and_the_explanation(tmp_path):
    path = _stored_explanation(tmp_path, {"C1": LIVE})
    source = ExplanationSource(
        "src/cube/validation/e.yml", tmp_path, "https://x/blob/b/dir"
    )
    run = _run([_cell("b", 10, 20)])

    part = reproduce_json(
        "enrollment", _ask(((path, "C1"),)), run, _cause_cfg(), source, START
    )

    query = part["cube"]["query"]
    assert query["measures"] == ["enrollment.student_count"]
    assert {"member": "enrollment.grade_level", "operator": "equals",
            "values": ["7"]} in query["filters"]  # fmt: skip
    (explanation,) = part["explanations"]
    assert explanation["reproduce"] == LIVE
    assert explanation["explain"] == (
        "explain src/cube/validation/e.yml --comparison enrollment --bucket cube_only"
    )
    assert explanation["after"] == [
        "compare src/cube/validation/e.yml --all",
        "sort src/cube/validation/e.yml",
    ]
    assert explanation["url"] == f"https://x/blob/b/dir/{path}"

    block = merged_reproduce([part])
    assert block["queries"] == [{"bucket": "C1", "sql": LIVE}]
    assert block["explanations"] == [
        {"bucket": "C1", "query": 0, "path": path, "explain": [explanation["explain"]]},
    ]  # fmt: skip
    assert block["blob"] == "https://x/blob/b/dir"
    text = "\n".join(_reproduce_lines("Q1", block))
    assert "<summary>Reproduce Q1</summary>" in text
    assert "With the Cube connector in Claude chat" in text
    assert "today's data; counts drift from the run" in text and LIVE in text
    # One query: unnumbered, so it never reads as a count of 1.
    assert "Count query, cause `C1`, in BigQuery" in text
    assert (
        f"- Cause `C1` in [`enrollment__cube_only.sql`](https://x/blob/b/dir/{path}): "
    ) in text
    assert "live count" not in text.lower()


def test_a_reproduce_block_edited_after_confirm_is_checked_before_it_posts(tmp_path):
    # Comment lines never stale an explanation, so `ask-owner` checks the block again.
    path = _stored_explanation(tmp_path, {"C1": "SELECT * FROM d.t"})
    source = ExplanationSource("v.yml", tmp_path)

    part = reproduce_json(
        "enrollment", _ask(((path, "C1"),)), _run([]), _cause_cfg(), source, START
    )

    assert part["explanations"][0]["reproduce"] is None


def test_a_cause_with_no_reproduce_block_says_so(tmp_path):
    path = _stored_explanation(tmp_path, None)
    source = ExplanationSource("v.yml", tmp_path)

    part = reproduce_json(
        "enrollment", _ask(((path, "C1"),)), _run([]), _cause_cfg(), source, START
    )

    assert part["cube"] is None and part["explanations"][0]["reproduce"] is None
    block = merged_reproduce([part])
    assert block["queries"] == [] and block["cube"] == []
    text = "\n".join(_reproduce_lines("Q2", block))
    assert f"- Cause `C1` in `{path}` (no count query yet)" in text


def test_an_explanation_source_links_the_branch_and_never_the_remote_s_credentials(
    tmp_path,
):
    import subprocess

    def git(*args):
        subprocess.run(
            ["git", "-C", str(tmp_path), *args], check=True, capture_output=True
        )

    git("init", "-q", "-b", "feat/x")
    git("remote", "add", "origin", "https://user:secret-token@github.com/org/repo.git")
    view = tmp_path / "src" / "cube" / "validation" / "v.yml"
    view.parent.mkdir(parents=True)
    view.write_text("")

    source = review_mod.explanation_source(view)

    assert source.view_file == "src/cube/validation/v.yml"
    assert source.blob == "https://github.com/org/repo/blob/feat/x/src/cube/validation"
    assert "secret" not in source.blob


def test_an_explanation_source_outside_git_has_no_link(tmp_path):
    view = tmp_path / "v.yml"
    view.write_text("")

    source = review_mod.explanation_source(view)

    assert source.blob is None and source.base == tmp_path


def test_the_review_file_is_linked_only_once_committed_and_pushed(tmp_path):
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args], check=True, capture_output=True,
            text=True,
        ).stdout.strip()  # fmt: skip

    git("init", "-q", "-b", "feat/x")
    git("config", "user.email", "t@example.org")
    git("config", "user.name", "t")
    git("remote", "add", "origin", "https://github.com/org/repo.git")
    view = tmp_path / "src" / "v.yml"
    view.parent.mkdir()
    view.write_text("")
    cfg = ViewConfig(view="v", fact="d.t", comparisons=[])
    path = review_mod.review_file([view], [cfg], "DDI")
    assert path == tmp_path / "src" / "reviews" / "v.json"
    data = [{"id": "Q1", "counts": ["<10 rows"]}]

    with pytest.raises(pipeline_mod.Refusal, match="wrote .*commit and push it"):
        review_mod._review_file(path, data)
    assert json.loads(path.read_text()) == data
    with pytest.raises(pipeline_mod.Refusal, match="not committed and pushed"):
        review_mod._review_file(path, data)

    git("add", ".")
    git("commit", "-q", "-m", "review")
    with pytest.raises(pipeline_mod.Refusal, match="not committed and pushed"):
        review_mod._review_file(path, data)  # committed, not pushed

    git("update-ref", "refs/remotes/origin/feat/x", "HEAD")
    sha = git("rev-parse", "HEAD")
    link = f"https://github.com/org/repo/blob/{sha}/src/reviews/v.json"
    assert review_mod._review_file(path, data) == link
    # The commit hook's formatting is no change; other questions are.
    path.write_text(json.dumps(data, indent=4))
    git("commit", "-q", "-am", "fmt")
    git("update-ref", "refs/remotes/origin/feat/x", "HEAD")
    assert review_mod._review_file(path, data).endswith("/src/reviews/v.json")
    with pytest.raises(pipeline_mod.Refusal, match="wrote"):
        review_mod._review_file(path, [{"id": "Q2"}])


def test_a_text_review_file_ignores_rewrapping_and_sits_beside_the_json(tmp_path):
    path = review_mod.still_file(tmp_path / "reviews" / "v.json")
    assert path == tmp_path / "reviews" / "v-still-with-analyst.md"
    text = "# Still\n\n- `a`, 40 rows; no lead yet\n"

    with pytest.raises(pipeline_mod.Refusal, match="wrote .*commit and push it"):
        review_mod._review_file(path, text)
    assert path.read_text() == text
    # The formatter's rewrapping is no change: only the commit check refuses.
    path.write_text("# Still\n\n- `a`, 40 rows;\n  no lead yet\n")
    with pytest.raises(pipeline_mod.Refusal, match="not committed and pushed"):
        review_mod._review_file(path, text)
    with pytest.raises(pipeline_mod.Refusal, match="wrote"):
        review_mod._review_file(path, text.replace("40", "41"))


def test_review_files_writes_each_changed_file_before_refusing(tmp_path):
    reviews = tmp_path / "reviews"
    files = [(reviews / "v.json", [{"id": "Q1"}]),
             (reviews / "v-still-with-analyst.md", "# Still\n")]  # fmt: skip

    with pytest.raises(pipeline_mod.Refusal) as exc:
        review_mod._review_files(files)

    assert str(reviews / "v.json") in str(exc.value)
    assert str(reviews / "v-still-with-analyst.md") in str(exc.value)
    assert json.loads((reviews / "v.json").read_text()) == [{"id": "Q1"}]
    assert (reviews / "v-still-with-analyst.md").read_text() == "# Still\n"


def test_a_review_across_views_is_named_for_its_domain(tmp_path):
    cfgs = [ViewConfig(view=v, fact="d.t", comparisons=[]) for v in ("a", "b")]
    path = review_mod.review_file([tmp_path / "a.yml"], cfgs, "Data & Analytics")
    assert path == tmp_path / "reviews" / "data-analytics.json"


@pytest.mark.parametrize(
    ("dashboard", "cube", "shown"),
    [
        (120.0, 125.0, ("<masked>", "<masked>")),
        (120.0, 130.0, ("120", "130")),
        (120.0, 120.0, ("120", "120")),
        (0.93, 0.95, ("0.93", "0.95")),
        (4.0, 300.0, ("<10", "300")),
    ],
)
def test_a_hand_check_never_posts_2_counts_whose_difference_is_under_10(
    dashboard, cube, shown
):
    from cube_validation.answers import _check_json

    check = HandCheck(
        "enrollment", "{}", (), dashboard, cube, "", "", 0.0, 0.0, START, False
    )
    posted = _check_json("v", check)
    assert (posted["dashboard"], posted["cube"]) == shown


def test_a_hand_check_posts_its_cause_s_students_as_a_bound():
    """For a count-of-students measure, the two numbers less an exact cause
    count would post the other causes' students: 57 - 40 - 12 = 5."""
    # trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
    from cube_validation import report

    # trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
    from cube_validation.answers import _check_json

    check = HandCheck(
        "enrollment", "{}", (), 40.0, 57.0, "", "", 0.0, 0.0, START, False,
        mixed=True, cause_students=12,
    )  # fmt: skip
    posted = _check_json("v", check)
    assert posted["cause_students"] == "10+"
    text = "\n".join(report._hand_check_lines("Q1", posted))
    assert "10 or more students' rows in it have this cause" in text
    assert "12" not in text


def test_a_question_reads_its_comparison_s_own_moment():
    earlier = Build(START - timedelta(days=3), END - timedelta(days=3), "j0")
    run = dataclasses.replace(
        _owner_run([_cell(cube=25.0)]), moments={"enrollment": earlier}
    )

    questions = _questions(run)
    check = hand_check(run, _cfg(), "enrollment", START)

    assert questions[0]["moment"]["job_id"] == "j0"
    assert questions[0]["expires"] == (earlier.start + timedelta(days=7)).isoformat()
    assert check.expires == earlier.start + timedelta(days=7)
