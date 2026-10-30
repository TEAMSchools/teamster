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
    approved_decisions,
    example_cell,
    hand_check,
    note_refusal,
    parse_answers,
    questions_json,
)

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import CellDiff, Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, Decision, ViewConfig

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import Applied, apply

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

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


def _cfg(dashboard_region="regions_region_name"):
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


def _questions(run, cfg=None, triage=TRIAGE):
    return questions_json([run], [cfg or _cfg()], DEFS, triage, START)


def test_questions_json_matches_markdown_questions_one_to_one():
    run = _owner_run([_cell()])
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
        "since SY 2023-2024",
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


def test_a_missing_filter_in_cause_is_decided_across_the_view():
    # As triage writes it: a comparison it was found on, and the sheet filter
    # as its proven cause.
    item = {
        "id": "filter:Exclude Future", "kind": "gap", "suggestion": "cause",
        "comparison": "ada", "stub": {"missing_filter": "Exclude Future"},
        "cause": [{"side": "dashboard", "step": "sheet filter Exclude Future",
                   "label": "sheet filter Exclude Future", "n_rows": None}],
        "proof": {"kind": "workbook"},
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
        approved_decisions([entry], TRIAGE, FPS)


# --- cause decisions (T17) ---------------------------------------------------

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import triage as triage_mod  # noqa: E402

NO_SECTION = "score has no section on the anchor date"
LATE = "score dated after week 20250701"
CAUSE_FPS = {"enrollment": {"cube": "c1", "dashboard": "d1"}}
PROOF = {"kind": "query", "path": "proofs/v/enrollment__dashboard_only.sql",
         "fingerprint": "p1"}  # fmt: skip


def _cause_entry(label, side="cube", n_rows=20):
    return {"side": side, "step": "b", "label": label, "n_rows": n_rows}


def _cause_item(item_id, *causes, proof=PROOF, key=""):
    return {"id": item_id, "key": key, "kind": "group", "comparison": "enrollment",
            "label": "l", "stub": {"comparison": "enrollment"},
            "suggestion": "cause", "evidence": ["proof line"], "candidates": [],
            "cause": list(causes), "proof": proof}  # fmt: skip


def _ok(id, item, call="domain_owner", reason="r", cause=""):
    out = {"id": id, "call": call, "reason": reason, "item": item}
    return {**out, "cause": cause} if cause else out


def _existing(id="no-section", label=NO_SECTION, call="domain_owner", proof="p1",
              cube="c1", **kw):  # fmt: skip
    return Decision(id, "enrollment", call, "kept reason",
                    cause={"side": "cube", "label": label},
                    fingerprints={"cube": cube, "dashboard": "d1", "proof": proof},
                    **kw)  # fmt: skip


def test_a_proven_group_becomes_a_decision_on_its_cause():
    item = _cause_item("k1", _cause_entry(LATE))

    (decision,) = approved_decisions([_ok("late", "k1")], {"items": [item]}, CAUSE_FPS)

    assert decision == {
        "id": "late",
        "comparison": "enrollment",
        # The words' long number never reaches the file.
        "cause": {"side": "cube", "label": "score dated after week <n>"},
        "call": "domain_owner",
        "reason": "r",
        "fingerprints": {"cube": "c1", "dashboard": "d1", "proof": "p1"},
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


def test_a_cause_decision_on_a_changed_proof_is_re_approved():
    item = _cause_item("k2", _cause_entry(NO_SECTION))
    stale = _existing(proof="old")

    (decision,) = approved_decisions(
        [_ok("new", "k2", call="fix_cube", reason="fresh")], {"items": [item]},
        CAUSE_FPS, existing=[stale],
    )  # fmt: skip

    assert (decision["id"], decision["call"], decision["reason"]) == (
        "no-section", "fix_cube", "fresh")  # fmt: skip
    assert decision["fingerprints"] == {"cube": "c1", "dashboard": "d1", "proof": "p1"}


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
    (it,) = triage_mod.open_items(run)
    mixed = {**items[0], "id": it.id, "key": it.key}

    only_d2 = [Decision(**d) for d in approved_decisions(
        [entries[2] | {"item": "mixed"}], {"items": items}, CAUSE_FPS)]  # fmt: skip
    triage_mod.mark_decided(run, [mixed], only_d2)
    assert mixed["decided"] is False

    both = [
        Decision(**d) for d in approved_decisions(entries, {"items": items}, CAUSE_FPS)
    ]
    triage_mod.mark_decided(run, [mixed], both)
    assert mixed["decided"] is True


@pytest.mark.parametrize(
    "existing, entry, match",
    [
        (_existing(call="fix_cube", task="#1"), {}, "decided fix_cube"),
        (_existing(proof="old", answer="fix_cube"), {}, "answered.*proof changed"),
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
                              proof={**PROOF, "path": "proofs/v/x.sql", "fingerprint": "p9"})  # fmt: skip
    blank = _cause_item("k4", _cause_entry(""))
    split = _cause_item("k5", _cause_entry(NO_SECTION), _cause_entry(LATE))
    unproven = {**_cause_item("k6", _cause_entry(NO_SECTION)), "proof": None}

    for approved, items, match in [
        ([_ok("a", "k1"), _ok("b", "k2", call="deliberate")], [one, two], "domain_owner"),
        ([_ok("a", "k1"), _ok("b", "k1")], [one], "twice"),
        ([_ok("a", "k1"), _ok("b", "k1", cause=NO_SECTION)], [one], "twice"),
        ([_ok("a", "k1")], [one, other_proof], "2 proof"),
        ([_ok("a", "k4")], [blank], "no words"),
        ([_ok("a", "k5")], [split], "2 causes; approve each"),
        ([_ok("a", "k5", cause="nothing like it")], [split], "has no cause"),
        ([_ok("a", "k6")], [unproven], "no proof decides"),
    ]:  # fmt: skip
        with pytest.raises(AnswerError, match=match):
            approved_decisions(approved, {"items": items}, CAUSE_FPS)


LEAD = "lead: read docs/models/x-data-model.md (mentions rpt_x)"


def _review(groups, items, decisions, runs_extra=()):
    run = _run([])
    run.applied = apply(decisions, groups, CAUSE_FPS)
    run.fingerprints = CAUSE_FPS
    triage_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {
        "enrollment": triage_mod.cause_asks(
            run, loaded, decisions, {"enrollment": LEAD}
        )
    }
    questions = questions_json(
        [run], [_cfg()], DEFS, {"enrollment": loaded}, START, causes
    )
    return questions, render_review_issue("Registrar", [run], DEFS, questions, causes)


def _ddi():
    """3 schools x 2 proven causes: each school has a group of each cause."""
    groups = [
        Group("enrollment", (("region", s), ("grade_level", grade)),
              "dashboard_only", 30, 12)
        for s in ("Newark", "Camden", "Paterson") for grade in ("7", "8")
    ]  # fmt: skip
    run = _run([])
    run.applied = apply([], groups, CAUSE_FPS)
    opened = triage_mod.open_items(run)
    items = [
        _cause_item(it.id, _cause_entry(NO_SECTION if g.value_of("grade_level") == "7"
                                        else LATE, n_rows=30), key=it.key)
        for g, it in zip(groups, opened, strict=True)
    ]  # fmt: skip
    return groups, items


def test_review_asks_one_question_per_cause_not_per_school():
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
        "`enrollment` (dashboard_only): <10 row groups, 90 rows",
    ]
    assert late["evidence"][0] == "cause (cube side): score dated after week <n>"
    assert "20250701" not in body
    bullets = [x for x in body.split("## Proposed")[0].splitlines() if "Reason:" in x]
    assert len(bullets) == 2
    assert f"`{NO_SECTION}`" in bullets[0] and "<10 row groups, 90 rows" in bullets[0]


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
    triage_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {"enrollment": triage_mod.cause_asks(run, loaded, decisions)}
    questions = questions_json(
        [run], [_cfg()], DEFS, {"enrollment": loaded}, START, causes
    )
    for q in questions:
        q["reproduce"] = {
            "queries": [{"bucket": "C1", "sql": "SELECT 1 AS n_rows" + " " * 400}],
            "proofs": [], "cube": [], "expires": "2026-11-06",
            "after": ["run v.yml", "triage v.yml"],
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
        for i, (item, (call, task, reason)) in enumerate(zip(items, calls))
    ]  # fmt: skip
    decisions = [
        Decision(**d) for d in approved_decisions(approved, {"items": items}, CAUSE_FPS)
    ]
    run = _run([])
    run.applied = apply(decisions, groups, CAUSE_FPS)
    run.fingerprints = CAUSE_FPS
    triage_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {"enrollment": triage_mod.cause_asks(run, loaded, decisions)}
    decided = {"enrollment": triage_mod.cause_asks(run, loaded, decisions, owner=False)}
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
        for it in triage_mod.open_items(run)
    ]  # fmt: skip
    decisions = [
        Decision(**d)
        for d in approved_decisions(
            [_ok("a", items[0]["id"]), _ok("b", items[1]["id"])], {"items": items}, fps
        )
    ]
    triage_mod.mark_decided(run, items, decisions)
    loaded = {"view": "enrollment", "items": items}
    causes = {"enrollment": triage_mod.cause_asks(run, loaded, decisions)}

    (question,) = questions_json(
        [run], [_cfg()], DEFS, {"enrollment": loaded}, START, causes
    )

    assert question["decisions"] == ["a", "b"]
    # The cause once, then each comparison's share; 1 view, so no view names.
    assert question["counts"] == [
        f"cause `{NO_SECTION}` on the cube side",
        "`enrollment` (dashboard_only): <10 row group, 30 rows",
        "`other` (dashboard_only): <10 row group, 30 rows",
    ]
    assert question["evidence"] == [f"cause (cube side): {NO_SECTION}"]


def test_a_split_group_shows_only_each_causes_own_rows():
    groups = [
        Group("enrollment", (("region", "Newark"),), "dashboard_only", 30, 12),
        Group("enrollment", (("region", "Camden"),), "dashboard_only", 30, 12),
    ]
    run = _run([])
    run.applied = apply([], groups, CAUSE_FPS)
    newark, camden = triage_mod.open_items(run)
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
    # The bullet and the evidence both give the cause's own 57 rows; the
    # groups' whole 60 never shows, so nothing gives the other cause's 3 away.
    numbers = set(re.findall(r"(?<![<\d])\d+ rows", posted))
    assert numbers == {"57 rows"}


# --- reproducing a cause ---------------------------------------------------------------

from dataclasses import replace as _replace  # noqa: E402

from cube_validation import confirm as confirm_mod  # noqa: E402
from cube_validation import pipeline as pipeline_mod  # noqa: E402
from cube_validation.answers import (  # noqa: E402
    ProofSource,
    merged_reproduce,
    reproduce_json,
)
from cube_validation.report import CauseAsk, _reproduce_lines  # noqa: E402

PROOF_SQL = (
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


def _ask(proofs):
    decision = Decision(
        id="c1",
        comparison="enrollment",
        call="domain_owner",
        reason="r",
        cause={"side": "dashboard", "label": "the sheet drops WPP"},
    )
    return CauseAsk(decision, [], 30, "", proofs)


def _stored_proof(tmp_path, reproduce):
    directory = tmp_path / "proofs" / "enrollment"
    directory.mkdir(parents=True)
    path = confirm_mod.proof_path(directory, "enrollment", "cube_only")
    path.write_text(
        confirm_mod.compose({"C1": ("dashboard", "drops WPP")}, PROOF_SQL, reproduce)
    )
    return "proofs/enrollment/enrollment__cube_only.sql"


def test_a_cause_reproduces_through_cube_a_live_count_and_the_proof(tmp_path):
    path = _stored_proof(tmp_path, {"C1": LIVE})
    source = ProofSource("src/cube/validation/e.yml", tmp_path, "https://x/blob/b/dir")
    run = _run([_cell("b", 10, 20)])

    part = reproduce_json(
        "enrollment", _ask(((path, "C1"),)), run, _cause_cfg(), source, START
    )

    query = part["cube"]["query"]
    assert query["measures"] == ["enrollment.student_count"]
    assert {"member": "enrollment.grade_level", "operator": "equals",
            "values": ["7"]} in query["filters"]  # fmt: skip
    (proof,) = part["proofs"]
    assert proof["reproduce"] == LIVE
    assert proof["confirm"] == (
        "triage confirm src/cube/validation/e.yml --comparison enrollment "
        "--bucket cube_only"
    )
    assert proof["after"] == [
        "run src/cube/validation/e.yml",
        "triage src/cube/validation/e.yml",
    ]
    assert proof["url"] == f"https://x/blob/b/dir/{path}"

    block = merged_reproduce([part])
    assert block["queries"] == [{"bucket": "C1", "sql": LIVE}]
    assert block["proofs"] == [
        {"bucket": "C1", "query": 0, "path": path, "confirm": [proof["confirm"]]},
    ]  # fmt: skip
    assert block["blob"] == "https://x/blob/b/dir"
    text = "\n".join(_reproduce_lines("Q1", block))
    assert "<summary>Reproduce Q1</summary>" in text
    assert "With the Cube connector in Claude chat" in text
    assert "today's data; counts drift from the run" in text and LIVE in text
    assert (
        f"- Cause `C1` in [`enrollment__cube_only.sql`](https://x/blob/b/dir/{path}) "
        "(live count 1)"
    ) in text


def test_a_cause_with_no_reproduce_block_says_so(tmp_path):
    path = _stored_proof(tmp_path, None)
    source = ProofSource("v.yml", tmp_path)

    part = reproduce_json(
        "enrollment", _ask(((path, "C1"),)), _run([]), _cause_cfg(), source, START
    )

    assert part["cube"] is None and part["proofs"][0]["reproduce"] is None
    block = merged_reproduce([part])
    assert block["queries"] == [] and block["cube"] == []
    text = "\n".join(_reproduce_lines("Q2", block))
    assert f"- Cause `C1` in `{path}` (no live count yet)" in text


def test_a_proof_source_links_the_branch_and_never_the_remote_s_credentials(tmp_path):
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

    source = pipeline_mod.proof_source(view)

    assert source.view_file == "src/cube/validation/v.yml"
    assert source.blob == "https://github.com/org/repo/blob/feat/x/src/cube/validation"
    assert "secret" not in source.blob


def test_a_proof_source_outside_git_has_no_link(tmp_path):
    view = tmp_path / "v.yml"
    view.write_text("")

    source = pipeline_mod.proof_source(view)

    assert source.blob is None and source.base == tmp_path
